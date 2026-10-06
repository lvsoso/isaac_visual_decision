"""Episode loop shared by real Isaac and explicitly synthetic offline fixtures."""
from __future__ import annotations
import time
from .core import ACTIONS, LabError, model_state, parse_decision, judge_episode
from .protocol import make_request


def run_episode(scene, config: dict, mode: str, log, client=None, *, allow_mock=False) -> dict:
    if mode not in {"capture", "baseline", "shadow", "visual", "mock"}:
        raise ValueError(f"Unknown mode {mode}")
    if mode in {"shadow", "visual", "mock"} and client is None:
        raise ValueError("Model modes require a client")
    if mode != "mock" and allow_mock:
        raise ValueError("Only mode=mock may accept mock responses")
    start = time.perf_counter()
    previous_action = previous_result = None
    decisions = api_attempts = api_completed = 0
    predicted_actions = []
    actual_actions = []
    timed_out = released = False
    reason = "decision_limit"
    error = None
    try:
        if client is not None:
            log.event("model_health", health=client.health(allow_mock=allow_mock))
        if mode == "capture":
            png = scene.capture()
            state = model_state(scene.proprioception(), None, None)
            log.observation(0, png, state, scene.private_truth())
            reason = "capture_only"
        else:
            for index in range(config["max_decisions"]):
                decisions += 1
                png = scene.capture()  # physical state is now frozen
                state = model_state(scene.proprioception(), previous_action, previous_result)
                log.observation(decisions, png, state, scene.private_truth())
                prediction = None
                raw = None
                elapsed_ms = None
                if client is not None:
                    request = make_request(png, state)
                    log.request(decisions, request)
                    api_attempts += 1
                    raw, elapsed_ms = client.predict(request)
                    log.response(decisions, raw)
                    prediction = parse_decision(raw, allow_mock=allow_mock)
                    api_completed += 1
                    predicted_actions.append(prediction.action)
                if mode in {"baseline", "shadow"}:
                    action = ACTIONS[index]  # 7 fixed actions; release exits before index=7
                else:
                    action = prediction.action
                log.event("decision", decision_id=decisions, mode=mode,
                    proposed_action=None if prediction is None else prediction.action,
                    executed_action=action, probabilities=None if prediction is None else prediction.probabilities,
                    confidence=None if prediction is None else prediction.confidence,
                    model=None if prediction is None else prediction.model,
                    is_mock=False if prediction is None else prediction.mock,
                    http_latency_ms=elapsed_ms)
                actual_actions.append(action)
                print(f"[{mode}] decision {decisions}: proposed={getattr(prediction, 'action', None)}, execute={action}", flush=True)
                if action == "abort":
                    reason = "policy_abort"
                    break
                outcome = scene.execute(action)
                log.event("phase_end", decision_id=decisions, **outcome)
                previous_action, previous_result = action, outcome["status"]
                if outcome["status"] == "timeout":
                    timed_out = True
                    reason = "stage_timeout"
                    break  # v0.1 has a strict terminal-timeout protocol, not recovery evaluation
                if action == "release":
                    released = True
                    outcome = scene.execute("retract")
                    log.event("phase_end", decision_id=None, automatic=True, **outcome)
                    if outcome["status"] == "timeout":
                        timed_out = True
                        reason = "retract_timeout"
                        break
                    scene.settle()
                    reason = "completed"
                    break
    except KeyboardInterrupt:
        reason, error = "user_interrupt", "KeyboardInterrupt"
        log.event("error", termination_reason=reason, error=error)
    except Exception as exc:
        from .client import ModelAPIError
        from .core import ProtocolError
        reason = "model_api_error" if isinstance(exc, ModelAPIError) else "protocol_error" if isinstance(exc, ProtocolError) else "runtime_error"
        error = f"{type(exc).__name__}: {exc}"
        log.event("error", termination_reason=reason, error=error)
    try:
        # This is evaluator-only truth; no final image request and no extra physics on abort.
        truth = scene.private_truth()
        result = judge_episode(truth["cube_world_position_m"], config, released=released,
                               timed_out=timed_out, termination_reason=reason)
    except Exception as exc:
        result = {"strict_success": False, "physical_completion": False,
                  "termination_reason": reason, "evaluation_error": f"{type(exc).__name__}: {exc}"}
    result.update({"mode": mode, "num_decisions": decisions, "api_attempts": api_attempts,
        "api_completed": api_completed, "model_called": api_attempts > 0,
        "real_model_evaluated": mode in {"shadow", "visual"} and api_completed > 0,
        "model_had_control": mode == "visual", "mock_backend": mode == "mock",
        "wall_seconds": time.perf_counter()-start, "physics_updates": scene.frames,
        "recorded_frames": scene.recorded_frames, "executed_actions": actual_actions,
        "proposed_actions": predicted_actions, "error": error,
        "controller_target_source": "configured_world_coordinates",
        "end_to_end_visual_localization": False})
    log.summary(result)
    return result
