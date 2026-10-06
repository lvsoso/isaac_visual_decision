"""Paired fixed-trajectory diagnostics, not an autonomous robot policy."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import math
import random
from pathlib import Path

from .audit import sha256_file, write_json
from .core import ACTIONS, LabError, ProtocolError, judge_episode, model_state, parse_decision, vector3
from .protocol import CRITERIA, INSTRUCTIONS, make_request

GOAL_COLORS = {"blue": [0.02, 0.18, 0.95], "yellow": [1.0, 0.85, 0.02]}
STATE_KEYS = ("task", "observation", "previous_action", "previous_result", "ee_reference",
              "ee_world_position_m", "finger_joint_position_rad", "gripper_command_reference_rad", "limitations")


def factor_cells() -> list[dict]:
    return [{"id": f"A{a}B{b}C{c}", "color": color, "coordinates": bool(b), "views": c+1}
            for a, color in enumerate(GOAL_COLORS) for b in range(2) for c in range(2)]


def camera_configs(config: dict) -> list[dict]:
    first = copy.deepcopy(config["camera"])
    second = copy.deepcopy(first)
    second["position"] = [1.7, 1.4, 1.3]
    return [first, second]


def view_metadata(config: dict) -> list[dict]:
    views = []
    for index, camera in enumerate(camera_configs(config)):
        position, look_at = vector3(camera["position"], "camera position"), vector3(camera["look_at"], "look_at")
        delta = [b-a for a, b in zip(position, look_at)]
        length = math.sqrt(sum(x*x for x in delta))
        if length < .01:
            raise ProtocolError("Camera look_at and position must differ")
        direction = [x/length for x in delta]
        views.append({"image_index": index+1, "world_axes": "right-handed world coordinates, Z up, meters",
                      "camera_position_world_m": position, "look_at_world_m": look_at,
                      "view_direction_world": direction,
                      "view_azimuth_deg": math.degrees(math.atan2(direction[1], direction[0])),
                      "view_elevation_deg": math.degrees(math.asin(direction[2])),
                      "angle_definition": "view ray from camera to look_at; azimuth from +X toward +Y; elevation above XY plane",
                      "resolution_px": list(camera["resolution"]), "focal_length_mm": camera["focal_length_mm"]})
    return views


def goal_guidance(configured_goal, lower_target, tool_position, tool_frame) -> dict:
    goal = vector3(configured_goal, "configured goal")
    target, tool = vector3(lower_target, "lower tool target"), vector3(tool_position, "measured tool FK")
    delta = [round(b-a, 6) for a, b in zip(tool, target)]
    return {"source": "configured goal plus controller model FK from measured joints; no cube truth",
            "goal_center_on_ground_world_m": [goal[0], goal[1], 0.0],
            "placement_tool_target_world_m": target, "controller_tool_frame": tool_frame,
            "measured_tool_world_position_m": tool, "tool_to_placement_delta_m": delta,
            "tool_to_goal_horizontal_distance_m": math.hypot(goal[0]-tool[0], goal[1]-tool[1]),
            "tool_height_above_placement_m": tool[2]-target[2],
            "tool_to_placement_distance_m": math.dist(tool, target),
            "reference_warning": "placement target and measured tool use the SAME controller model tool frame, not the finger link or cube center; height above placement is signed measured Z minus target Z; a near target does not prove holding"}


def neutral(text: str) -> str:
    return text.replace("blue non-colliding ground outline", "square non-colliding ground outline").replace("blue ground outline", "square ground outline").replace("blue outline", "square outline").replace("blue goal", "outlined goal")


def factor_request(pngs: list[bytes], state: dict, views: list[dict], guidance: dict, cell: dict) -> dict:
    # Whitelist: never pass an entire observation/event/config to the model.
    evidence = {key: copy.deepcopy(state[key]) for key in STATE_KEYS}
    evidence["task"] = neutral(evidence["task"])
    evidence["observation"] = "Current simultaneous RGB view(s) of one frozen scene, not temporal frames; world axes are not image axes."
    evidence["camera_views"] = copy.deepcopy(views[:cell["views"]])
    if cell["coordinates"]:
        evidence["goal_guidance"] = copy.deepcopy(guidance)
    request = make_request(pngs[:cell["views"]], evidence)
    question = request["questions"]["next_stage"]
    question["criteria"] = {key: neutral(text) for key, text in CRITERIA.items()}
    question["instructions"] = neutral(INSTRUCTIONS) + " Image order matches camera_views image_index. Optional goal_guidance describes a controller model tool, never the cube center; use the image to assess holding."
    return request


def capture_pairs(scene, cameras: list, *, reverse=False) -> dict[str, list[bytes]]:
    before = scene.frozen_state()
    pairs = {}
    order = list(GOAL_COLORS)
    if reverse:
        order.reverse()
    try:
        for color in order:
            scene.set_goal_color(GOAL_COLORS[color])
            pairs[color] = scene.capture_views(cameras)
        if scene.frozen_state() != before:
            raise LabError("Color/view quartet changed frozen physical state")
        return pairs
    finally:
        scene.set_goal_color(GOAL_COLORS["blue"])
        scene.timeline.pause()


def collect_episode(scene, cameras: list, config: dict, log, *, seed=20261006) -> dict:
    records, previous_action, previous_result = [], None, None
    rng = random.Random(seed)
    target = scene.placement_tool_target()
    reason, error, released, timed_out = "runtime_error", None, False, False
    try:
        for number, action in enumerate(ACTIONS[:-1], 1):
            state = model_state(scene.proprioception(), previous_action, previous_result)
            guidance = goal_guidance(config["target_position_m"], target,
                                     scene._controller_tool_world_position(), scene.scenario._tool_frame)
            reverse = bool(rng.getrandbits(1))
            pairs = capture_pairs(scene, cameras, reverse=reverse)
            images = {}
            for color, pngs in pairs.items():
                images[color] = []
                for view, png in enumerate(pngs, 1):
                    path = log.root/"images"/f"decision_{number:03d}_{color}_view{view}.png"
                    path.write_bytes(png)
                    images[color].append({"path": str(path.relative_to(log.root)), "sha256": hashlib.sha256(png).hexdigest()})
            record = {"decision_id": number, "expected_action": action, "model_state": state,
                      "goal_guidance": guidance, "images": images,
                      "color_capture_order": list(pairs), "frozen_physics_verified": True}
            records.append(record)
            log.event("paired_observation", **record, private_ground_truth=scene.private_truth(), frozen_state=scene.frozen_state())
            outcome = scene.execute(action)
            log.event("phase_end", decision_id=number, **outcome)
            if action == "lower" and outcome["target_world_position_m"] != target:
                raise LabError("Recorded fixed placement tool target differs from executed lower target")
            previous_action, previous_result = action, outcome["status"]
            if previous_result == "timeout":
                reason, timed_out = "stage_timeout", True
                break
            if action == "release":
                released = True
                outcome = scene.execute("retract")
                log.event("phase_end", decision_id=None, automatic=True, **outcome)
                timed_out = outcome["status"] == "timeout"
                if not timed_out:
                    scene.settle()
                reason = "retract_timeout" if timed_out else "completed"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log.event("error", error=error)
    result = judge_episode(scene.private_truth()["cube_world_position_m"], config,
                           released=released, timed_out=timed_out, termination_reason=reason)
    result.update(mode="factorial_capture", complete=error is None and len(records) == 7 and reason == "completed",
                  error=error, physics_updates=scene.frames, num_observations=len(records),
                  model_had_control=False, model_called=False, real_model_evaluated=False)
    write_json(log.root/"snapshots.json", {"view_metadata": view_metadata(config), "records": records})
    log.summary(result)
    return result


def load_snapshots(source: Path) -> dict:
    source = source.resolve()
    summary = json.loads((source/"summary.json").read_text())
    if summary.get("complete") is not True or summary.get("strict_success") is not True:
        raise LabError("Require a complete successful fixed-policy capture")
    bundle = json.loads((source/"snapshots.json").read_text())
    records = bundle["records"]
    if (len(records) != 7 or [r["expected_action"] for r in records] != list(ACTIONS[:-1])
            or [r["decision_id"] for r in records] != list(range(1, 8)) or len(bundle["view_metadata"]) != 2
            or any(r.get("frozen_physics_verified") is not True for r in records)):
        raise LabError("Require exactly seven ordered fixed-policy observations")
    for record in records:
        for color in GOAL_COLORS:
            images = record["images"][color]
            if len(images) != 2:
                raise LabError("Each color must have exactly two simultaneous views")
            for image in images:
                path = (source/image["path"]).resolve()
                if not path.is_relative_to(source) or sha256_file(path) != image["sha256"]:
                    raise LabError("Snapshot path/hash mismatch")
    return bundle


def summarize(rows: list[dict]) -> dict:
    cells = []
    for cell in factor_cells():
        decisions = [row for row in rows if row["cell"] == cell["id"]]
        correct = sum(row["proposed_action"] == row["expected_action"] for row in decisions)
        final = [row for row in decisions if row["expected_action"] in {"lower", "release"}]
        cells.append({**cell, "baseline_agreement": correct, "num_decisions": len(decisions),
                      "final_two_agreement": sum(row["proposed_action"] == row["expected_action"] for row in final),
                      "mean_expected_action_probability": sum(row["probabilities"][row["expected_action"]] for row in decisions)/len(decisions) if decisions else None,
                      "proposed_actions": [row["proposed_action"] for row in sorted(decisions, key=lambda row: row["decision_id"])]})
    effects = {}
    if len(rows) == 56:
        for factor, key, high in [("A_color", "color", "yellow"), ("B_goal_guidance", "coordinates", True), ("C_second_view", "views", 2)]:
            on, off = [cell for cell in cells if cell[key] == high], [cell for cell in cells if cell[key] != high]
            effects[factor] = {"paired_agreement_fraction_delta": (sum(c["baseline_agreement"] for c in on)-sum(c["baseline_agreement"] for c in off))/28,
                              "mean_expected_probability_delta": sum(c["mean_expected_action_probability"] for c in on)/4-sum(c["mean_expected_action_probability"] for c in off)/4}
    return {"cells": cells, "descriptive_main_effects": effects,
            "scope": "One fixed trajectory; seven correlated states. Conditional paired diagnostics, not generalization/control success or statistical significance."}


def run_replay(source: Path, output: Path, client, *, seed=20261006, allow_mock=False) -> dict:
    from PIL import Image
    bundle = load_snapshots(source)
    capture_manifest = json.loads((source/"manifest.json").read_text())
    if not allow_mock and (capture_manifest.get("synthetic_fixture") or capture_manifest.get("kind") != "paired_factorial_capture"):
        raise LabError("Real replay requires a production capture manifest, not a synthetic fixture")
    health = client.health(allow_mock=allow_mock)
    if health.get("max_images", 0) < 2 or health.get("is_mock") is not bool(allow_mock):
        raise ProtocolError("Require explicit two-image capability and correct real/mock mode")
    if not allow_mock and not health.get("vision_input_audit"):
        raise ProtocolError("Real factorial replay requires an audited official processor")
    source = source.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output/"requests").mkdir(); (output/"responses").mkdir()
    manifest = {"kind": "paired_factorial_replay", "source": str(source), "source_snapshots_sha256": sha256_file(source/"snapshots.json"),
                "source_manifest_sha256": sha256_file(source/"manifest.json"), "source_summary_sha256": sha256_file(source/"summary.json"),
                "model_health": health, "seed": seed, "cells": factor_cells(), "model_had_control": False,
                "shared_wording_control_is_not_historical_shadow": True,
                "synthetic_fixture": allow_mock,
                "source_sha256": {name: sha256_file(Path(__file__).with_name(name)) for name in ["factorial.py", "protocol.py", "core.py"]}}
    write_json(output/"manifest.json", manifest)
    jobs = [(record, cell) for record in bundle["records"] for cell in factor_cells()]
    random.Random(seed).shuffle(jobs)
    rows, error = [], None
    try:
        for record, cell in jobs:
            assets = record["images"][cell["color"]][:cell["views"]]
            pngs = [(source/image["path"]).read_bytes() for image in assets]
            request = factor_request(pngs, record["model_state"], bundle["view_metadata"], record["goal_guidance"], cell)
            name = f"{cell['id']}_decision_{record['decision_id']:03d}"
            write_json(output/"requests"/f"{name}.json", request)
            raw, latency = client.predict(request)
            write_json(output/"responses"/f"{name}.json", raw)
            parsed = parse_decision(raw, allow_mock=allow_mock)
            expected_hashes = [hashlib.sha256(png).hexdigest() for png in pngs]
            meta = raw["_bridge"]
            if meta.get("is_mock") is not bool(allow_mock):
                raise ProtocolError("Response real/mock metadata changed")
            if meta.get("image_count") != len(pngs) or meta.get("image_sha256s") != expected_hashes:
                raise ProtocolError("Ordered response image hashes/count do not match")
            if not allow_mock:
                audit = raw.get("_vision_audit", {})
                rgb_hashes = []
                for png in pngs:
                    with Image.open(io.BytesIO(png)) as image:
                        rgb_hashes.append(hashlib.sha256(image.convert("RGB").tobytes()).hexdigest())
                if audit.get("normalized_rgb_sha256s") != rgb_hashes or len(audit.get("image_grid_thw", [])) != len(pngs):
                    raise ProtocolError("Official processor did not consume the same ordered images")
                if meta.get("inference_py_sha256") != health["inference_py_sha256"]:
                    raise ProtocolError("Model implementation changed during replay")
                if raw.get("calibration", {}).get("temperature") != health["temperature"]:
                    raise ProtocolError("Model calibration changed during replay")
            row = {"cell": cell["id"], "decision_id": record["decision_id"], "expected_action": record["expected_action"],
                   "proposed_action": parsed.action, "probabilities": parsed.probabilities, "confidence": parsed.confidence,
                   "http_latency_ms": latency, "image_sha256s": expected_hashes,
                   "request_sha256": sha256_file(output/"requests"/f"{name}.json"), "response_sha256": sha256_file(output/"responses"/f"{name}.json")}
            rows.append(row)
            print(f"{name}: {parsed.action}, reference={record['expected_action']}, {latency:.0f} ms", flush=True)
        final_health = client.health(allow_mock=allow_mock)
        stable_keys = ("is_mock", "max_images", "inference_py_sha256", "config_sha256", "temperature", "device", "dtype",
                       "max_length", "vision_input_audit", "bridge_source_sha256", "protocol_source_sha256", "model_files_sha256")
        if any(health.get(key) != final_health.get(key) for key in stable_keys):
            raise ProtocolError("Pinned model/service provenance changed during replay")
        write_json(output/"final_health.json", final_health)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    result = {"complete": len(rows) == 56 and error is None, "api_completed": len(rows), "error": error,
              "model_had_control": False, "real_model_evaluated": not allow_mock and bool(rows),
              "mock_backend": allow_mock, **summarize(rows), "decisions": rows}
    write_json(output/"summary.json", result)
    return result
