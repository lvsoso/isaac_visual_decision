"""Request contract shared by simulator, offline probe and model bridge."""
from __future__ import annotations
import base64
import copy
import json
from .core import ACTIONS, ProtocolError

MAX_IMAGES = 2  # Bounded experiment interface; default episodes still send one.

# criteria 是动作语义，不是通过源码替模型决定的动作掩码。
CRITERIA = {
    "pre_grasp": "Move the gripper to a high alignment pose above the red cube for pickup. Use when the fingers are open and the gripper is not yet above the resting cube. Do not use if the cube is already carried, or the gripper is already aligned above it; this skill does not open closed fingers.",
    "approach": "Descend with open fingers to the resting red cube's pickup height. Use when the gripper is above the cube but still too high to close around it. Do not use if the fingers are closed, the cube is carried, or the open gripper is already at pickup height.",
    "grasp": "Close the fingers around the red cube. Use when the fingers are open and positioned around the resting cube at pickup height. Do not use if the fingers are already closed or the cube is already carried. Closing alone is not proof of a grasp.",
    "lift": "Raise a newly closed gripper to test whether the cube is carried off the pickup floor. Use when the fingers have closed around the cube but the cube is not yet visibly elevated. Do not use if the held cube is already visibly elevated, including while above the goal; repeated lifting does not transport or release it.",
    "transport": "Carry the elevated held cube horizontally toward the blue ground outline. Use when the cube is visibly elevated between closed fingers but is not yet horizontally above the goal. Do not use if the cube was left behind, the fingers are open, or the held cube is already above the goal.",
    "lower": "Descend with the held cube toward placement height at the blue goal. Use when the elevated held cube is horizontally above the goal but still high above its ground surface. Do not use while away from the goal, with no held cube, or when the held cube is already at placement height.",
    "release": "Open the fingers to leave the cube at the blue goal and finish, followed by automatic retract. Use when the closed gripper has lowered the held cube to placement height over the goal. Do not use high above the ground or away from the goal; it is not a generic retry/open skill.",
    "abort": "Stop if the cube is lost, a retry would require opening elsewhere, observations are inconsistent, or no available skill can safely make progress.",
}
INSTRUCTIONS = (
    "Select exactly one next skill using the current RGB image and proprioception. "
    "The red cube is the object and the blue non-colliding ground outline is the goal. "
    "Match each skill's observable preconditions and exclusions to the CURRENT scene. "
    "previous_action and previous_result are context, not a mandatory sequence or proof of task progress. "
    "A finger_joint_position_rad near 0.0 means open fingers; near 0.5 means closed fingers. "
    "Closed fingers are not proof of holding: inspect whether the red cube is between them. "
    "ee_world_position_m refers to a finger link, not the cube center or grasp center; "
    "do not use that link's height as the cube's height. "
    "Before the first lift a cube between newly closed fingers can still rest on the floor. "
    "A visibly elevated held cube does not need another pickup lift; judge its relation to the goal. "
    "The image cannot prove contact or 3-D metric accuracy. Choose abort when required "
    "recovery is unavailable. No coordinates or explanation are requested."
)


def make_request(png_bytes: bytes | list[bytes], state: dict) -> dict:
    images = png_bytes if isinstance(png_bytes, list) else [png_bytes]
    if not 1 <= len(images) <= MAX_IMAGES:
        raise ProtocolError("Expected one or two current PNG images")
    for image in images:
        if not isinstance(image, bytes) or not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ProtocolError("Expected PNG bytes, not a server path or RGB array")
    if not isinstance(state, dict):
        raise ProtocolError("state must be a dict")
    result = {
        "state": copy.deepcopy(state),
        "images": [{"type": "image/png", "data": base64.b64encode(image).decode("ascii")} for image in images],
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
    if not isinstance(images, list) or not 1 <= len(images) <= MAX_IMAGES:
        raise ProtocolError("This bridge requires one or two current RGB images")
    for item in images:
        if not isinstance(item, dict) or set(item) != {"type", "data"} or item["type"] != "image/png" or not isinstance(item["data"], str):
            raise ProtocolError("Images must contain image/png and base64 data; URLs/paths are forbidden")
    json.dumps(request, allow_nan=False)
