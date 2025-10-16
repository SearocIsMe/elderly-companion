#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import OpaqueFunction
import inspect


def _print_resolved_args(context):
    get = lambda k: context.launch_configurations.get(k, '?')
    return [LogInfo(msg=f"[LAUNCH] mode={get('mode')} | target={get('deployment_target')} | SR={get('audio_sample_rate')} | ASR={get('asr_model_path')}"),
            LogInfo(msg=f"[LAUNCH] flags: fastapi={get('enable_fastapi_services')}, audio={get('enable_audio_pipeline')}, safety={get('enable_safety_systems')}, emergency={get('enable_emergency_services')}, smarthome={get('enable_smart_home')}, video={get('enable_video_streaming')}")]


# -----------------------------
# Debug helpers (line number + tuple guard)
# -----------------------------
def _where(msg: str) -> LogInfo:
    """
    打印当前调用点在本文件中的行号，便于快速二分定位。
    """
    frame = inspect.currentframe()
    caller = frame.f_back.f_back if frame and frame.f_back else None
    lineno = caller.f_lineno if caller else -1
    return LogInfo(msg=f"[LAUNCH L{lineno}] {msg}")

def _sanitize_params_dict(d: dict, node_name: str, path: str = ""):
    """
    递归检查 parameters 字典：
    - 若发现 tuple（尤其是 () / 单元素 ('INFO',) 这类），打印告警并转为 list（避免 ROS2 报 'value must be ... but got tuple'）。
    - 嵌套 dict 也会继续递归。
    返回 (fixed_dict, logs)
    """
    logs = []
    fixed = {}
    for k, v in d.items():
        key_path = f"{path}.{k}" if path else k
        if isinstance(v, tuple):
            logs.append(LogInfo(
                msg=f"[PARAM-TUPLE] node={node_name} key={key_path} value={v!r} -> auto-fix to list"
            ))
            fixed[k] = list(v)
        elif isinstance(v, dict):
            sub_fixed, sub_logs = _sanitize_params_dict(v, node_name, key_path)
            logs.extend(sub_logs)
            fixed[k] = sub_fixed
        else:
            fixed[k] = v
    return fixed, logs

def _wrap_params_for_node(context, node_name: str, params_list):
    """
    输入 parameters=[{...}, {...}]，对其中的 dict 逐个 sanitize。
    在 launch 期把日志注入（visit）到输出。
    """
    new_params = []
    for p in params_list or []:
        if isinstance(p, dict):
            fixed, logs = _sanitize_params_dict(p, node_name)
            for log in logs:
                log.visit(context)
            new_params.append(fixed)
        else:
            new_params.append(p)
    return new_params

def WrapNode(*, package, executable, name,
             output='screen', condition=None,
             parameters=None, remappings=None):
    """
    一个小包装器：在真正创建 Node 之前打印行号标记，并对 parameters 做 tuple 自检与修复。
    用法：
      actions = WrapNode(package=..., executable=..., name=..., parameters=[{...}])
      ld.add_action(actions[0]); ld.add_action(actions[1])
    """
    pre_log = _where(f"pre-create Node '{name}'")

    def _make_node_fn(context, *args, **kwargs):
        fixed_params = _wrap_params_for_node(context, name, parameters)
        node = Node(
            package=package,
            executable=executable,
            name=name,
            output=output,
            condition=condition,
            parameters=fixed_params if fixed_params else None,
            remappings=remappings
        )
        return [node]

    return [pre_log, OpaqueFunction(function=_make_node_fn)]


# -----------------------------
# Launch file proper
# -----------------------------
def generate_launch_description() -> LaunchDescription:
    # 声明所有可配置 Launch 参数（注意：不要写成带尾逗号的 tuple！）
    mode_arg                   = DeclareLaunchArgument('mode',                   default_value='hybrid')
    deployment_target_arg      = DeclareLaunchArgument('deployment_target',      default_value='development')
    use_rknpu_arg              = DeclareLaunchArgument('use_rknpu',              default_value='false')

    enable_fastapi_services_arg = DeclareLaunchArgument('enable_fastapi_services', default_value='true')
    enable_audio_pipeline_arg    = DeclareLaunchArgument('enable_audio_pipeline',   default_value='true')
    enable_safety_systems_arg    = DeclareLaunchArgument('enable_safety_systems',   default_value='true')
    enable_emergency_services_arg= DeclareLaunchArgument('enable_emergency_services', default_value='true')
    enable_smart_home_arg        = DeclareLaunchArgument('enable_smart_home',       default_value='true')
    enable_video_streaming_arg   = DeclareLaunchArgument('enable_video_streaming',  default_value='true')

    log_level_arg              = DeclareLaunchArgument('log_level',              default_value='INFO')
    audio_sample_rate_arg      = DeclareLaunchArgument('audio_sample_rate',      default_value='16000')
    asr_model_path_arg         = DeclareLaunchArgument('asr_model_path',         default_value='/models/asr-zip-zh-en')

    # 读取配置
    mode                  = LaunchConfiguration('mode')
    deployment_target     = LaunchConfiguration('deployment_target')
    use_rknpu             = LaunchConfiguration('use_rknpu')

    enable_fastapi_services = LaunchConfiguration('enable_fastapi_services')
    enable_audio_pipeline   = LaunchConfiguration('enable_audio_pipeline')
    enable_safety_systems   = LaunchConfiguration('enable_safety_systems')
    enable_emergency_services = LaunchConfiguration('enable_emergency_services')
    enable_smart_home       = LaunchConfiguration('enable_smart_home')
    enable_video_streaming  = LaunchConfiguration('enable_video_streaming')

    log_level            = LaunchConfiguration('log_level')
    audio_sample_rate    = LaunchConfiguration('audio_sample_rate')
    asr_model_path       = LaunchConfiguration('asr_model_path')

    # 顶部启动信息
    banner = LogInfo(msg="[LAUNCH] 🤖 Enhanced Elderly Companion - starting")

    # -----------------------------
    # FastAPI bridge + router coordinator
    # -----------------------------
    core_nodes = [
        *WrapNode(
            package='elderly_companion',
            executable='fastapi_bridge_node.py',
            name='fastapi_bridge_node',
            output='screen',
            condition=IfCondition(enable_fastapi_services),
            parameters=[{
                'bridge.host': '0.0.0.0',
                'bridge.port': 8090,
                'router.intent_url': 'http://localhost:7001/parse_intent',
                'router.guard_url':   'http://localhost:7002/guard/check',
                'router.smart_url':   'http://localhost:7003/smart-home/cmd',
                'router.sip_url':     'http://localhost:7003/sip/call',
                'log.level': log_level,
            }],
        ),
        *WrapNode(
            package='elderly_companion',
            executable='enhanced_router_coordinator.py',
            name='enhanced_router_coordinator',
            output='screen',
            condition=IfCondition(enable_fastapi_services),
            parameters=[{
                'mode': mode,
                'deployment.target': deployment_target,
                'use.rknpu': use_rknpu,
                'guard.enabled': True,
                'intent.enabled': True,
                'smart_home.enabled': enable_smart_home,
                'emergency.enabled': enable_emergency_services,
                'video.enabled': enable_video_streaming,
                'log.level': log_level,
            }],
        ),
    ]

    # -----------------------------
    # 音频链路（VAD + ASR + TTS + 情感）
    # -----------------------------
    audio_nodes = [
        *WrapNode(
            package='elderly_companion',
            executable='silero_vad_node.py',
            name='silero_vad_node',
            output='screen',
            condition=IfCondition(enable_audio_pipeline),
            parameters=[{
                'audio.sample_rate': audio_sample_rate,
                'audio.channels': 1,
                'audio.encoding': 'f32le',
                'vad.frame_ms': 20,
                'vad.hop_ms': 10,
                'vad.threshold': 0.015,   # 可按设备麦克风灵敏度调
                'vad.min_speech_ms': 200,
                'vad.max_sil_ms': 300,
                'resample.to_16k': True,
                'debug.log_energy': False,
                'log.level': log_level,
            }],
        ),
        *WrapNode(
            package='elderly_companion',
            executable='speech_recognition_node.py',
            name='speech_recognition_node',
            output='screen',
            condition=IfCondition(enable_audio_pipeline),
            parameters=[{
                # 兼容 sherpa-onnx asr-zip-zh-en（你已经换好的版本）
                'asr.model_path': asr_model_path,
                'asr.sample_rate': audio_sample_rate,
                'asr.languages': 'zh,en',
                'asr.stream': True,
                'asr.max_active': 7000,
                'postproc.punct': True,
                'postproc.normalize': True,
                'router.guard_url': 'http://localhost:7002/guard/check',
                'router.intent_url': 'http://localhost:7001/parse_intent',
                'log.level': log_level,
            }],
        ),
        *WrapNode(
            package='elderly_companion',
            executable='enhanced_tts_engine_node.py',
            name='enhanced_tts_engine_node',
            output='screen',
            condition=IfCondition(enable_audio_pipeline),
            parameters=[{
                'tts.backend': 'edge-tts',          # 或者 'kokoro-onnx' / 'piper' 等
                'tts.voice':   'zh-CN-XiaoxiaoNeural',
                'tts.rate':    0,
                'tts.pitch':   0,
                'audio.sample_rate': 22050,
                'sink.device': 'default',
                'log.level': log_level,
            }],
        ),
        *WrapNode(
            package='elderly_companion',
            executable='emotion_analyzer_node.py',
            name='emotion_analyzer_node',
            output='screen',
            condition=IfCondition(enable_audio_pipeline),
            parameters=[{
                'emo.enable_audio': True,
                'emo.enable_text':  True,
                'emo.window_sec':   2.0,
                'emo.text_backoff': True,
                'log.level': log_level,
            }],
        ),
    ]

    # -----------------------------
    # 其他可选组（safety / emergency / smart-home / video）
    # 这里仅放“占位/示例参数”，你可以继续用 WrapNode 添加自己的节点。
    # -----------------------------
    safety_nodes = [
        # *WrapNode(... 你的 Safety 节点 ...)
        
    ]

    emergency_nodes = [
        # *WrapNode(... 你的 SOS/SIP 网关节点 ...)
    ]

    smarthome_nodes = [
        # *WrapNode(... MQTT/Matter 适配器 ...)
    ]

    video_nodes = [
        # *WrapNode(... WebRTC 上行，或相机节点 ...)
    ]

    # -----------------------------
    # 汇总 LaunchDescription
    # -----------------------------
    ld = LaunchDescription()

    # 声明参数
    for arg in [
        mode_arg, deployment_target_arg, use_rknpu_arg,
        enable_fastapi_services_arg, enable_audio_pipeline_arg,
        enable_safety_systems_arg, enable_emergency_services_arg,
        enable_smart_home_arg, enable_video_streaming_arg,
        log_level_arg, audio_sample_rate_arg, asr_model_path_arg
    ]:
        ld.add_action(arg)

    # 顶部 banner
    ld.add_action(banner)
    ld.add_action(LogInfo(msg="[LAUNCH] 🤖 Enhanced Elderly Companion - starting"))
    ld.add_action(OpaqueFunction(function=_print_resolved_args))

    # 加载节点（注意：WrapNode 返回的是两条动作：pre-log + OpaqueFunction）
    for group in [core_nodes, audio_nodes, safety_nodes, emergency_nodes, smarthome_nodes, video_nodes]:
        for act in group:
            ld.add_action(act)

    return ld
