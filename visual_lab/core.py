"""纯 Python 协议/评测。这里不判断物体是否抓牢，也不训练或调用模型。"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ACTIONS = ("pre_grasp", "approach", "grasp", "lift", "transport", "lower", "release", "abort")
PHASES = ACTIONS[:-1] + ("retract",)
GRIPPER_PHASES = {"grasp", "release"}
NEAR_POSE_PHASES = {"approach", "lower"}

class LabError(RuntimeError):
    """需要终止回合、不能偷偷切换到规则策略的错误。"""

class ProtocolError(LabError):
    pass


def finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(f"{name}: expected a number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolError(f"{name}: non-finite number")
    return result


def vector3(value: Any, name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ProtocolError(f"{name}: expected three numbers")
    return [finite_number(v, name) for v in value]


def load_config(path: str | Path) -> dict[str, Any]:
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    if c.get("schema_version") != 1:
        raise ProtocolError("Unsupported config schema_version")
    # Resolve older config files to explicit values recorded in the run manifest.
    c.setdefault("near_pose_tolerance_m", 0.005)
    c.setdefault("near_pose_stable_frames", 12)
    for key in ("cube_position_m", "target_position_m"):
        c[key] = vector3(c[key], key)
    for key in ("frame_scale", "arm_min_frames", "gripper_min_frames", "max_decisions", "warmup_frames", "settle_frames", "near_pose_stable_frames"):
        if type(c[key]) is not int or c[key] < 1:
            raise ProtocolError(f"{key} must be a positive integer")
    for key in ("physics_dt", "cube_size_m", "ee_tolerance_m", "near_pose_tolerance_m", "gripper_tolerance_rad", "success_xy_tolerance_m", "success_z_tolerance_m", "http_timeout_seconds"):
        if finite_number(c[key], key) <= 0:
            raise ProtocolError(f"{key} must be > 0")
    if c["near_pose_tolerance_m"] > c["ee_tolerance_m"]:
        raise ProtocolError("near_pose_tolerance_m must not exceed ee_tolerance_m")
    if abs(c["cube_size_m"] - 0.05) > 1e-9:
        raise ProtocolError("Installed tutorial uses a 0.05 m cube; changing this field alone does not resize the USD")
    limits = c["tutorial_phase_limits"]
    if len(limits) != 8 or any(type(x) is not int or x <= 0 for x in limits):
        raise ProtocolError("tutorial_phase_limits must contain eight positive integers")
    cam = c["camera"]
    for key in ("position", "look_at"):
        cam[key] = vector3(cam[key], f"camera.{key}")
    if math.dist(cam["position"], cam["look_at"]) < 0.01:
        raise ProtocolError("camera position and look_at cannot coincide")
    if len(cam["resolution"]) != 2 or any(type(x) is not int or not 64 <= x <= 2048 for x in cam["resolution"]):
        raise ProtocolError("camera.resolution must contain width,height in [64,2048]")
    if finite_number(cam["focal_length_mm"], "focal_length_mm") <= 0:
        raise ProtocolError("focal_length_mm must be positive")
    if type(cam["rt_subframes"]) is not int or cam["rt_subframes"] < 1:
        raise ProtocolError("rt_subframes must be positive")
    validate_timing(c)
    return c


def validate_timing(c: dict) -> None:
    for i, action in enumerate(PHASES):
        minimum = c["gripper_min_frames"] if action in GRIPPER_PHASES else c["arm_min_frames"]
        if action in NEAR_POSE_PHASES:
            minimum = max(minimum, c["near_pose_stable_frames"])
        if minimum > c["tutorial_phase_limits"][i] * c["frame_scale"]:
            raise ProtocolError(f"{action}: minimum frames exceeds timeout; fix the protocol before running")


def phase_result(action: str, frames: int, ee_error: float, gripper_error: float, c: dict,
                 *, near_stable_frames: int = 0) -> str | None:
    """到位优先于同一帧超时；末端到位 ≠ 抓取成功。"""
    if action not in PHASES:
        raise ProtocolError(f"Unknown phase {action}")
    gripper = action in GRIPPER_PHASES
    minimum = c["gripper_min_frames"] if gripper else c["arm_min_frames"]
    error = finite_number(gripper_error if gripper else ee_error, "phase error")
    tolerance = (c["gripper_tolerance_rad"] if gripper else
                 c["near_pose_tolerance_m"] if action in NEAR_POSE_PHASES else c["ee_tolerance_m"])
    stable = action not in NEAR_POSE_PHASES or near_stable_frames >= c["near_pose_stable_frames"]
    if frames >= minimum and error <= tolerance and stable:
        return "reached"
    maximum = c["tutorial_phase_limits"][PHASES.index(action)] * c["frame_scale"]
    if frames >= maximum:
        return "timeout"
    return None


def judge_episode(cube_xyz: list[float], c: dict, *, released: bool, timed_out: bool, termination_reason: str) -> dict:
    xyz = vector3(cube_xyz, "final_cube_position")
    target = c["target_position_m"]
    dxy = math.hypot(xyz[0] - target[0], xyz[1] - target[1])
    # 场景是地面，不是桌面。5 cm 方块平放时中心高度约 0.025 m。
    dz = abs(xyz[2] - c["cube_size_m"] / 2)
    physical = released and dxy <= c["success_xy_tolerance_m"] and dz <= c["success_z_tolerance_m"]
    return {
        "physical_completion": bool(physical),
        "strict_success": bool(physical and not timed_out and termination_reason == "completed"),
        "final_cube_position_m": xyz, "final_xy_error_m": dxy, "final_z_error_m": dz,
        "release_reached": released, "timeout_occurred": timed_out,
        "termination_reason": termination_reason,
    }


@dataclass(frozen=True)
class Decision:
    action: str
    probabilities: dict[str, float]
    confidence: float
    model: str
    mock: bool = False


def parse_decision(response: dict[str, Any], *, allow_mock: bool = False) -> Decision:
    """严格解析真实答案，不补零、不改选项、不自动归一化损坏的分布。"""
    if not isinstance(response, dict):
        raise ProtocolError("Response must be a JSON object")
    meta = response.get("_bridge", {})
    if not isinstance(meta, dict):
        raise ProtocolError("Invalid bridge metadata")
    is_mock = meta.get("is_mock") is True
    if is_mock and not allow_mock:
        raise ProtocolError("Mock response is forbidden in a real visual run")
    try:
        a = response["answers"]["next_stage"]
    except (KeyError, TypeError) as exc:
        raise ProtocolError("Expected answers.next_stage") from exc
    if not isinstance(a, dict) or a.get("type") != "choice":
        raise ProtocolError("next_stage must be type=choice")
    action = a.get("choice")
    if action not in ACTIONS:
        raise ProtocolError(f"Illegal choice: {action!r}")
    p = a.get("probabilities")
    if not isinstance(p, dict) or set(p) != set(ACTIONS):
        raise ProtocolError("Probability keys must exactly match the eight action labels")
    values = {k: finite_number(p[k], f"probabilities.{k}") for k in ACTIONS}
    if any(v < 0 or v > 1 for v in values.values()) or abs(sum(values.values()) - 1) > 1e-3:
        raise ProtocolError("Probabilities must be in [0,1] and sum to 1")
    if values[action] < max(values.values()) - 1e-6:
        raise ProtocolError("choice is not a maximum-probability candidate")
    confidence = finite_number(a.get("confidence"), "confidence")
    if not 0 <= confidence <= 1:
        raise ProtocolError("confidence outside [0,1]")
    model = response.get("model")
    if not isinstance(model, str) or not model:
        raise ProtocolError("Response must identify the model")
    return Decision(action, values, confidence, model, is_mock)


def model_state(proprioception: dict, previous_action: str | None, previous_result: str | None) -> dict:
    """白名单构建请求。绝不把 cube_xyz、回合/决策编号混进视觉输入。"""
    if previous_action is not None and previous_action not in PHASES:
        raise ProtocolError("Unknown previous action")
    if previous_result not in (None, "reached", "timeout"):
        raise ProtocolError("Unknown previous phase result")
    return {
        "task": "Place the red cube inside the blue ground outline, then release it.",
        "observation": "One current RGB image from a fixed external camera; world axes are not image axes.",
        "previous_action": previous_action,
        "previous_result": previous_result,
        "ee_reference": "right_inner_finger link, not the gripper's grasp center",
        "ee_world_position_m": [round(x, 5) for x in vector3(proprioception["ee_world_position_m"], "ee_position")],
        "finger_joint_position_rad": round(finite_number(proprioception["finger_joint_position_rad"], "finger_joint"), 5),
        "gripper_command_reference_rad": {"open": 0.0, "close": 0.5},
        "limitations": "reached means actuator/pose convergence, not proof of grasp; closed fingers alone do not prove holding",
    }
