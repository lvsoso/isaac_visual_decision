"""Match prompt requirements to actual evidence, without inventing object state."""
from __future__ import annotations
import copy
from .core import ACTIONS, ProtocolError

PROMPT_POLICIES=('legacy_deletion','modality_aware_v1')
TEXT_CRITERIA={
    'pre_grasp':'将夹爪移到红色方块拾取区域上方的高位对准姿态。手指张开且当前记录与位置尚不支持已完成拾取对准时考虑；若已对准或记录支持已经进入携带过程，则不要重复。此技能不会张开闭合手指。',
    'approach':'保持手指张开，下降到红色方块的拾取高度。根据当前位置与执行记录判断是否已在拾取区域上方、但尚未到拾取高度。若手指闭合、已进入携带过程，或已经到拾取高度，则不要使用。',
    'grasp':'在拾取位置闭合手指。适用于手指张开且位置与执行记录支持已经到拾取高度的情况。若手指已闭合或已进入携带过程，则不要重复；仅闭合不能证明抓取成功。',
    'lift':'抬高刚闭合的夹爪，尝试将物体带离拾取处地面。依据手指、工具高度和执行记录判断是否尚未完成抬升。若当前位置与记录支持已升高，则不要再次执行拾取抬高；抬高不会水平搬运或释放物体。',
    'transport':'将夹爪及可能携带的物体水平移向task指定的地面目标。适用于记录与数值支持已抬升、手指闭合、工具尚未到目标水平位置的情况。若手指张开、已有信息显示物体丢失，或已在目标上方，则不要使用。',
    'lower':'将闭合夹爪及可能携带的物体降向目标放置高度。根据工具到目标的水平距离、相对放置高度及执行记录判断是否在目标上方但仍过高。远离目标、已有信息显示物体丢失，或已到放置高度时不要继续下降。工具位置不是物体位置真值。',
    'release':'张开手指，将可能携带的物体留在目标处并结束，随后自动回撤。适用于手指闭合且位置与执行记录支持已到目标放置高度的情况。远离目标或高于放置高度时不要释放；这不是通用重试或任意位置张开技能。',
    'abort':'停止当前任务。用于已有信息支持物体丢失、执行或数值相互矛盾、所需恢复不可用，或没有可用技能能合理安全推进的情况。未知状态本身不是已发生失败的证据。',
}
TEXT_INSTRUCTIONS=(
    '本次没有提供图片或视频，只提供文字与本体状态；不要要求观察未提供的图像，也不要臆测外观、接触或物体位置。'
    '红色方块是操作对象，task指定的地面轮廓线是目标。'
    '综合当前数值、上一动作previous_action、previous_result和全部技能含义，选择最合理的一个下一步技能。'
    '允许依据已有执行记录和位置推断进展，但推断不是新的测量事实；previous_action只是上下文，不是强制序列，不得只按上一动作查表。'
    'reached表示执行器或姿态收敛，不证明抓取成功。手指关节接近0.0表示张开，接近0.5表示闭合；闭合手指不能证明夹持。'
    'goal_guidance给出配置目标与关节FK工具点，不是方块位置；工具点和手指连杆也不是物体中心。'
    '没有图片本身不是必须停止或选择abort的理由，不把未知夹持状态自动等同于物体已经丢失，也不把位置接近目标当作已经抓住。'
    '按现有证据综合判断技能适用性与排除条件；当证据相互矛盾、支持不可恢复失败或没有技能能合理安全推进时选择abort。'
    '这些输出是离线动作建议，不是物体状态证明，不会直接控制机器人；只返回已有候选之一，无需输出坐标或解释。'
)


def adapt_modality(request: dict, count: int) -> dict:
    if type(count) is not int or count not in range(3): raise ProtocolError('Require zero, one or two actual images')
    if len(request['images'])<count or len(request['state'].get('camera_views',[]))!=2:
        raise ProtocolError('Require original two-camera metadata and enough original images')
    result=copy.deepcopy(request)
    result['images']=result['images'][:count]
    if count==2: return result  # Exact historical dual-image input / stability control.
    state=result['state'];state['camera_views']=state['camera_views'][:count]
    if count==1:
        state['observation']='一张当前RGB图像，来自camera_views列出的第一相机；不是时间序列帧，也没有第二相机图像；世界轴不是图像轴。'
    else:
        state['observation']='本次没有提供图片或视频，仅提供当前本体状态、上一动作执行记录、配置目标与实测关节模型FK工具信息；不包含方块位置或夹持真值。'
        question=result['questions']['next_stage']
        question['instructions']=TEXT_INSTRUCTIONS
        question['criteria']=dict(TEXT_CRITERIA)
    if tuple(result['questions']['next_stage']['criteria'])!=ACTIONS: raise ProtocolError('Action labels/order changed during prompt adaptation')
    return result
