"""Request contract shared by simulator, offline probe and model bridge."""
from __future__ import annotations
import base64
import copy
import json
from .core import ACTIONS, ProtocolError

# criteria 是动作语义，不是通过源码替模型决定的动作掩码。
CRITERIA = {
    "pre_grasp": "Move to a high approach pose above the red cube when not aligned for pickup; this does not open the gripper.",
    "approach": "Descend from above the red cube to the grasp pose while the fingers are open and pickup alignment is plausible.",
    "grasp": "Close the fingers around the red cube when at the grasp pose with open fingers. Closing is not proof of a secure grasp.",
    "lift": "After closing around the cube, attempt a vertical lift to establish whether it is carried. A cube still resting before the first lift is not by itself evidence of failure.",
    "transport": "Move the elevated held cube horizontally above the blue ground outline. Do not transport when the cube was left behind.",
    "lower": "Lower the held cube when horizontally above the blue outline and not yet at placement height.",
    "release": "Open the fingers after lowering at the blue goal. This ends the task and triggers automatic retract, so it is not a generic retry/open action.",
    "abort": "Stop if the cube is lost, a retry would require opening elsewhere, observations are inconsistent, or no available skill can safely make progress.",
}
INSTRUCTIONS = (
    "Select exactly one next skill using the current RGB image and proprioception. "
    "The red cube is the object and the blue non-colliding ground outline is the goal. "
    "Judge the CURRENT physical situation rather than just following previous_action. "
    "Do not infer grasp success from a completed close command alone. Before lifting, "
    "a correctly grasped cube can still rest on the ground; lift is the next test. "
    "The image cannot prove contact or 3-D metric accuracy. Choose abort when required "
    "recovery is unavailable. No coordinates or explanation are requested."
)


def make_request(png_bytes: bytes, state: dict) -> dict:
    if not isinstance(png_bytes, bytes) or not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProtocolError("Expected PNG bytes, not a server path or RGB array")
    if not isinstance(state, dict):
        raise ProtocolError("state must be a dict")
    result = {
        "state": copy.deepcopy(state),
        "images": [{"type": "image/png", "data": base64.b64encode(png_bytes).decode("ascii")}],
        "questions": {"next_stage": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(CRITERIA)}},
    }
    # 拒绝 NaN/Inf；不要 sort_keys，训练接口依赖选项顺序。
    json.dumps(result, allow_nan=False)
    return result


def validate_request(request: dict) -> None:
    if not isinstance(request, dict) or set(request) != {"state", "images", "questions"}:
        raise ProtocolError("This bridge accepts exactly state, images, questions")
    if not isinstance(request["state"], dict):
        raise ProtocolError("state must be an object")
    try:
        q = request["questions"]
        if set(q) != {"next_stage"} or q["next_stage"]["type"] != "choice":
            raise ProtocolError("Expected a single next_stage choice question")
        if tuple(q["next_stage"]["criteria"]) != ACTIONS:
            raise ProtocolError("Action labels/order do not match this experiment")
        if any(not isinstance(v, str) or not v.strip() for v in q["next_stage"]["criteria"].values()):
            raise ProtocolError("Every action needs a textual criterion")
        if not isinstance(q["next_stage"].get("instructions"), str):
            raise ProtocolError("instructions must be text")
    except (KeyError, TypeError) as exc:
        raise ProtocolError("Malformed decision schema") from exc
    images = request["images"]
    if not isinstance(images, list) or len(images) != 1:
        raise ProtocolError("This v0.1 experiment requires one current RGB image")
    item = images[0]
    if not isinstance(item, dict) or set(item) != {"type", "data"} or item["type"] != "image/png" or not isinstance(item["data"], str):
        raise ProtocolError("images[0] must contain image/png and base64 data; URLs/paths are forbidden")
    json.dumps(request, allow_nan=False)
