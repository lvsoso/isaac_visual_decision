"""Frozen English translation of bound text-only prompts; no new scene evidence."""
from __future__ import annotations
import copy,re
from .core import ACTIONS,ProtocolError

EN_CRITERIA={
 'pre_grasp':"Move the gripper to a high aligned pose above the red cube's pickup region. Consider this when the fingers are open and current records and position do not yet support completed pickup alignment. Do not repeat if already aligned or the records support having entered the carrying process. This skill does not open closed fingers.",
 'approach':"Keep the fingers open and descend to the red cube's pickup height. Use current position and execution records to determine whether the gripper is above the pickup region but has not reached pickup height. Do not use with closed fingers, after entering the carrying process, or when already at pickup height.",
 'grasp':"Close the fingers at the pickup position. Applicable when fingers are open and position and execution records support having reached pickup height. Do not repeat if fingers are closed or the carrying process has begun. Closing alone does not prove successful grasping.",
 'lift':"Raise the newly closed gripper, attempting to carry the object off the pickup ground. Use finger state, tool height and execution records to determine whether lifting has not yet completed. If current position and records support an already raised state, do not repeat pickup lifting. Lifting neither transports horizontally nor releases the object.",
 'transport':"Move the gripper and any possibly carried object horizontally toward the ground target specified in task. Applicable when records and numbers support completed lifting, fingers are closed and the tool has not reached the target's horizontal position. Do not use if fingers are open, existing information indicates object loss, or already above the target.",
 'lower':"Lower the closed gripper and any possibly carried object toward the target placement height. Use horizontal tool-to-target distance, relative placement height and execution records to determine whether above the target but still too high. Do not continue lowering when far from the target, existing information indicates object loss, or already at placement height. Tool position is not object-position ground truth.",
 'release':"Open the fingers, leaving any possibly carried object at the target and ending the task, followed by automatic retraction. Applicable when fingers are closed and position and execution records support having reached the target placement height. Do not release far from the target or above placement height. This is not a general retry or arbitrary-location opening skill.",
 'abort':"Stop the current task when existing information supports object loss, execution or numbers contradict each other, required recovery is unavailable, or no available skill can reasonably and safely advance. An unknown state itself is not evidence that failure has occurred.",
}
EN_INSTRUCTIONS=(
 'No images or video are provided in this request, only text and proprioceptive state. Do not require observing unavailable images or invent appearance, contact or object position. '
 'The red cube is the manipulated object and the ground outline specified in task is the target. '
 'Combine current numbers, previous_action, previous_result and the meanings of all skills to select the most reasonable single next skill. '
 'Progress may be inferred from available execution records and position, but an inference is not a new measurement. previous_action is context, not a mandatory sequence; do not select by a lookup table based only on the previous action. '
 'reached means executor or pose convergence, not successful grasping. Finger joints near 0.0 mean open and near 0.5 mean closed; closed fingers do not prove holding. '
 'goal_guidance describes a configured target and joint-FK tool point, not the object position. The tool point and finger link are not object centers. '
 'Absence of images alone does not require stopping or choosing abort. Do not automatically treat unknown holding as object loss, or proximity to the target as proof of a grasp. '
 'Match skill conditions and exclusions to available evidence. Choose abort when evidence conflicts, supports unrecoverable failure, or no skill can reasonably and safely advance. '
 'These are offline action suggestions, not object-state proofs, and will not directly control a robot. Return one existing candidate only; no coordinates or explanation are required.'
)
SPATIAL_TRANSLATIONS=(
 ('task中的','The '),('方形轮廓线就是本goal_guidance中配置的地面框；“内部”指该轮廓线围成的地面区域。','square ground outline in task is the configured ground outline in this goal_guidance; "inside" means the ground region enclosed by that outline. '),
 ('蓝色','blue '),('黄色','yellow '),('配置的地面框中心世界坐标约','Configured ground-outline center approximately '),
 ('厘米。放置工具目标约',' cm in world coordinates. Placement tool target approximately '),('厘米；实测模型工具点约',' cm; measured model tool approximately '),
 ('厘米。从工具点到放置工具目标的位移约',' cm. Displacement from tool point to placement tool target approximately '),
 ('厘米（世界轴，不是画面左右）。工具点与地面目标中心的水平距离约',' cm along world axes, not image left/right. Horizontal distance from tool point to ground-goal center approximately '),
 ('厘米。工具点相对放置工具目标的高度差（带符号，实测Z减目标Z；正数在上方、负数在下方）约',' cm. Tool height relative to placement tool target (signed measured Z minus target Z; positive is above, negative below) approximately '),
 ('厘米。到放置工具目标的直线距离约',' cm. Straight-line distance to placement tool target approximately '),
 ('厘米。位置量以厘米保留一位小数，每量舍入误差最多',' cm. Positions/distances are rounded to one decimal centimeter; rounding error per scalar at most '),
 ('厘米；不判断是否对齐、接触或夹持。',' cm; no alignment, contact or holding judgment.'),
)

def english_request(bound: dict,color: str) -> dict:
    if color not in {'blue','yellow'} or bound.get('images')!=[]: raise ProtocolError('Require bound no-image prompt and approved color')
    result=copy.deepcopy(bound);s=result['state'];word='蓝色' if color=='blue' else '黄色'
    if s['task']!=f'将红色方块放入地面{word}方形轮廓线内部，然后释放它。': raise ProtocolError('Unknown task translation')
    s['task']=f'Place the red cube inside the {color} square ground outline, then release it.'
    s['observation']='No images or video are provided, only current proprioceptive state, previous-action execution records, configured target and tool information from measured joint model FK; no cube-position or holding ground truth.'
    s['ee_reference']='right_inner_finger link, not the gripper grasp center'
    s['limitations']='reached means executor or pose convergence, not proof of grasping; closed fingers alone do not prove holding'
    s['ee_position_description']=s['ee_position_description'].replace('手指连杆世界坐标约','Finger-link world position approximately ').replace('厘米；不是抓取中心或方块中心。',' cm; not the grasp or cube center.')
    g=s['goal_guidance'];g['source']='Configured target plus controller-model forward kinematics from measured joints; no cube ground truth'
    g['reference_warning']='Placement target and measured tool use the same controller-model tool frame, not the finger link or cube center; relative placement height is signed measured Z minus target Z; proximity to target does not prove holding'
    previous=g['spatial_description']
    if not previous.startswith('task中的'+word+'方形轮廓线就是'): raise ProtocolError('Require explicit bound goal identity before English translation')
    for old,new in SPATIAL_TRANSLATIONS:g['spatial_description']=g['spatial_description'].replace(old,new)
    result['questions']['next_stage']['instructions']=EN_INSTRUCTIONS;result['questions']['next_stage']['criteria']=dict(EN_CRITERIA)
    if re.search(r'[\u4e00-\u9fff]',str(result)): raise ProtocolError('Untranslated Chinese evidence')
    if re.findall(r'[-+]?\d+(?:\.\d+)?',previous)!=re.findall(r'[-+]?\d+(?:\.\d+)?',g['spatial_description']): raise ProtocolError('Translation changed geometry')
    if tuple(result['questions']['next_stage']['criteria'])!=ACTIONS: raise ProtocolError('Translation changed candidates')
    return result
