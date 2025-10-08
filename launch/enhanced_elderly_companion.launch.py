#!/usr/bin/env python3
"""
Enhanced Elderly Companion Complete System Launch File (merged).

- 保留你原有的系统分层与分组启动（Core/Audio/Safety/Comm/SmartHome/Video）
- 对接我们前面稳定化后的节点与参数：
  * silero_vad_node.py：订阅 /audio/raw_stream_in（ByteMultiArray, float32 PCM bytes）
                        发布 /audio/processed_stream、/audio/speech_segments
  * speech_recognition_node.py：订阅 /audio/speech_segments，发布 /speech/recognized
  * enhanced_guard_engine.py：订阅 /speech/recognized，发布 /guard/events
- 统一常用参数，便于 PC 与 RK3588 两端跑通
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    # ----- Launch args -----
    launch_args = [
        DeclareLaunchArgument('mode', default_value='hybrid', description='Operation mode'),
        DeclareLaunchArgument('deployment_target', default_value='development', description='Target: development|rk3588'),
        DeclareLaunchArgument('enable_fastapi_services', default_value='true'),
        DeclareLaunchArgument('enable_audio_pipeline', default_value='true'),
        DeclareLaunchArgument('enable_safety_systems', default_value='true'),
        DeclareLaunchArgument('enable_emergency_services', default_value='true'),
        DeclareLaunchArgument('enable_smart_home', default_value='true'),
        DeclareLaunchArgument('enable_video_streaming', default_value='true'),
        DeclareLaunchArgument('log_level', default_value='INFO'),
        # 音频与ASR常用参数
        DeclareLaunchArgument('audio_sample_rate', default_value='16000'),
        DeclareLaunchArgument('asr_model_path', default_value='/models/asr-zip-zh-en'),
    ]

    # ----- Config -----
    mode = LaunchConfiguration('mode')
    deployment_target = LaunchConfiguration('deployment_target')
    enable_fastapi = LaunchConfiguration('enable_fastapi_services')
    enable_audio = LaunchConfiguration('enable_audio_pipeline')
    enable_safety = LaunchConfiguration('enable_safety_systems')
    enable_emergency = LaunchConfiguration('enable_emergency_services')
    enable_smart_home = LaunchConfiguration('enable_smart_home')
    enable_video = LaunchConfiguration('enable_video_streaming')
    log_level = LaunchConfiguration('log_level')

    audio_sample_rate = LaunchConfiguration('audio_sample_rate')
    asr_model_path = LaunchConfiguration('asr_model_path')

    # ----- Core Integration Nodes (保持你的原始设计) -----
    core_nodes = [
        Node(
            package='elderly_companion',
            executable='fastapi_bridge_node.py',
            name='fastapi_bridge_node',
            output='screen',
            parameters=[{
                'fastapi.orchestrator_url': 'http://localhost:7010',
                'fastapi.timeout_seconds': 10.0,
            }]
        ),
        Node(
            package='elderly_companion',
            executable='enhanced_router_coordinator.py',
            name='enhanced_router_coordinator',
            output='screen',
            parameters=[{
                'router_agent.mode': mode,
                'deployment.target': deployment_target,
                'fastapi.enable_auto_start': enable_fastapi,
            }]
        )
    ]

    # ----- Audio Pipeline -----
    audio_nodes = [
        # VAD（稳定版，无torch/onnx依赖；接收 float32 PCM bytes）
        Node(
            package='elderly_companion',
            executable='silero_vad_node.py',
            name='silero_vad_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'audio.sample_rate': audio_sample_rate,
                'audio.channels': 1,
                'audio.encoding': 'f32le',
                'vad.frame_ms': 20,
                'vad.hop_ms': 10,
                'vad.threshold': 0.015,
                'vad.min_speech_ms': 200,
                'vad.max_sil_ms': 300,
                'resample.to_16k': True,
                'debug.log_energy': False,
            }],
            # 如需把你的麦克风话题映射到 /audio/raw_stream_in，请在这里加 remapping：
            # remappings=[('/audio/raw_stream_in', '/your_mic_topic')],
        ),
        # ASR（Zipformer2-CTC 优先；订阅 /audio/speech_segments）
        Node(
            package='elderly_companion',
            executable='speech_recognition_node.py',
            name='speech_recognition_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'asr.model_path': asr_model_path,
                'asr.language': 'zh-CN',
                'asr.sample_rate': audio_sample_rate,
                'asr.use_rknpu': PythonExpression(['"', deployment_target, '" == "rk3588"']),
                'asr.chunk_length': 0.1,
            }]
        ),
        # TTS（保留你的原TTS节点）
        Node(
            package='elderly_companion',
            executable='enhanced_tts_engine_node.py',
            name='enhanced_tts_engine_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'elderly.speech_rate_multiplier': 0.8,
                'language.primary': 'zh-CN',
            }]
        ),
        # Emotion（保留你的情感分析节点）
        Node(
            package='elderly_companion',
            executable='emotion_analyzer_node.py',
            name='emotion_analyzer_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'elderly.emotion_patterns.enabled': True,
            }]
        )
    ]

    # ----- Safety & Guard -----
    safety_nodes = [
        Node(
            package='elderly_companion',
            executable='enhanced_guard_engine.py',
            name='enhanced_guard_engine',
            output='screen',
            condition=IfCondition(enable_safety),
            parameters=[{
                'guard.wakewords': ['小安', '小安小安', 'hey buddy'],
                'guard.sos_keywords': ['救命', '不舒服', '急救', 'help', 'emergency'],
                'guard.geofence.enabled': False,
                'guard.geofence.allowed': [],
            }]
        ),
        Node(
            package='elderly_companion',
            executable='guard_fastapi_bridge_node.py',
            name='guard_fastapi_bridge_node',
            output='screen',
            condition=IfCondition(enable_safety),
            parameters=[{
                'fastapi.guard_url': 'http://localhost:7002',
                'enhanced_guard.enable_sos_enhancement': True,
            }]
        ),
        Node(
            package='elderly_companion',
            executable='safety_guard_node.py',
            name='safety_guard_node',
            output='screen',
            condition=IfCondition(enable_safety),
            parameters=[{
                'safety.emergency_response_time_ms': 100,
            }]
        )
    ]

    # ----- Communication -----
    communication_nodes = [
        Node(
            package='elderly_companion',
            executable='sip_voip_adapter_node.py',
            name='sip_voip_adapter_node',
            output='screen',
            condition=IfCondition(enable_emergency),
            parameters=[{
                'emergency.call_timeout_seconds': 45,
                'elderly.longer_ring_duration': True,
            }]
        ),
        Node(
            package='elderly_companion',
            executable='dialog_manager_node.py',
            name='dialog_manager_node',
            output='screen',
            parameters=[{
                'elderly.conversation_adaptations': True,
            }]
        )
    ]

    # ----- Smart Home -----
    smart_home_nodes = [
        Node(
            package='elderly_companion',
            executable='smart_home_backend_node.py',
            name='smart_home_backend_node',
            output='screen',
            condition=IfCondition(enable_smart_home),
            parameters=[{
                'elderly.simplified_controls': True,
                'safety.enable_emergency_automation': True,
            }]
        ),
        Node(
            package='elderly_companion',
            executable='mqtt_adapter_node.py',
            name='mqtt_adapter_node',
            output='screen',
            condition=IfCondition(enable_smart_home),
            parameters=[{
                'elderly.device_simplification': True,
            }]
        )
    ]

    # ----- Video -----
    video_nodes = [
        Node(
            package='elderly_companion',
            executable='webrtc_uplink_node.py',
            name='webrtc_uplink_node',
            output='screen',
            condition=IfCondition(enable_video),
            parameters=[{
                'webrtc.server_port': 8080,
                'emergency.auto_activate_streams': True,
            }]
        )
    ]

    # ----- LaunchDescription -----
    ld = LaunchDescription()

    # Args & banner
    for arg in launch_args:
        ld.add_action(arg)

    ld.add_action(LogInfo(
        msg=[
            '\n🤖 STARTING ELDERLY COMPANION ROBOT - MERGED LAUNCH\n',
            'Mode: ', mode, ' | Target: ', deployment_target, ' | SR: ', audio_sample_rate, '\n'
        ]
    ))

    # 启动顺序：Core → Audio → Safety → Comm → SmartHome → Video（与原始一致）
    for n in core_nodes:
        ld.add_action(n)

    ld.add_action(TimerAction(period=5.0, actions=audio_nodes))
    ld.add_action(TimerAction(period=10.0, actions=safety_nodes))
    ld.add_action(TimerAction(period=15.0, actions=communication_nodes))
    ld.add_action(TimerAction(period=20.0, actions=smart_home_nodes))
    ld.add_action(TimerAction(period=25.0, actions=video_nodes))

    ld.add_action(TimerAction(
        period=35.0,
        actions=[LogInfo(msg='\n🎉 ELDERLY COMPANION ROBOT SYSTEM READY!\n')]
    ))

    return ld
