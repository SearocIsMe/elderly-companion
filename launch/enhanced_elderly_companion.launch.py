#!/usr/bin/env python3
"""
Enhanced Elderly Companion Complete System Launch File.

Launches the complete integrated elderly companion system with:
- Audio Pipeline: Silero VAD → ASR → Emotion Analysis → Enhanced Guard  
- Core Logic: FastAPI Services (Guard → Intent → Orchestrator → Adapters)
- Communication: SIP/VoIP Emergency Calling + SMS/Email Notifications
- Smart Home: MQTT/Home Assistant Integration + Elderly Care Automation
- Video: WebRTC Streaming to Family Frontend
- Safety: Advanced Guard Engine + Emergency Response Protocols
- Output: Enhanced TTS with Elderly Optimization
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    ExecuteProcess, 
    GroupAction,
    LogInfo,
    TimerAction
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for complete elderly companion system."""
    
    # Launch arguments
    launch_args = [
        DeclareLaunchArgument('mode', default_value='hybrid', description='Operation mode'),
        DeclareLaunchArgument('deployment_target', default_value='development', description='Deployment target'),
        DeclareLaunchArgument('enable_fastapi_services', default_value='true', description='Enable FastAPI services'),
        DeclareLaunchArgument('enable_audio_pipeline', default_value='true', description='Enable audio pipeline'),
        DeclareLaunchArgument('enable_safety_systems', default_value='true', description='Enable safety systems'),
        DeclareLaunchArgument('enable_emergency_services', default_value='true', description='Enable emergency services'),
        DeclareLaunchArgument('enable_smart_home', default_value='true', description='Enable smart home'),
        DeclareLaunchArgument('enable_video_streaming', default_value='true', description='Enable video streaming'),
        DeclareLaunchArgument('log_level', default_value='INFO', description='Log level')
    ]
    
    # Get configurations
    mode = LaunchConfiguration('mode')
    deployment_target = LaunchConfiguration('deployment_target')
    enable_fastapi = LaunchConfiguration('enable_fastapi_services')
    enable_audio = LaunchConfiguration('enable_audio_pipeline')
    enable_safety = LaunchConfiguration('enable_safety_systems')
    enable_emergency = LaunchConfiguration('enable_emergency_services')
    enable_smart_home = LaunchConfiguration('enable_smart_home')
    enable_video = LaunchConfiguration('enable_video_streaming')
    log_level = LaunchConfiguration('log_level')
    
    # Core Integration Nodes
    core_nodes = [
        Node(
            package='router_agent',
            executable='fastapi_bridge_node.py',
            name='fastapi_bridge_node',
            output='screen',
            parameters=[{
                'fastapi.orchestrator_url': 'http://localhost:7010',
                'fastapi.timeout_seconds': 10.0,
            }]
        ),
        Node(
            package='router_agent',
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
    
    # Audio Pipeline Nodes
    audio_nodes = [
        Node(
            package='router_agent',
            executable='silero_vad_node.py',
            name='silero_vad_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'audio.sample_rate': 16000,
                'elderly.enable_optimization': True,
            }]
        ),
        Node(
            package='router_agent',
            executable='speech_recognition_node.py',
            name='speech_recognition_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'asr.language': 'zh-CN',
                'asr.use_rknpu': PythonExpression(['"', deployment_target, '" == "rk3588"']),
            }]
        ),
        Node(
            package='router_agent',
            executable='enhanced_tts_engine_node.py',
            name='enhanced_tts_engine_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'elderly.speech_rate_multiplier': 0.8,
                'language.primary': 'zh-CN',
            }]
        ),
        Node(
            package='router_agent',
            executable='emotion_analyzer_node.py',
            name='emotion_analyzer_node',
            output='screen',
            condition=IfCondition(enable_audio),
            parameters=[{
                'elderly.emotion_patterns.enabled': True,
            }]
        )
    ]
    
    # Safety and Guard Nodes
    safety_nodes = [
        Node(
            package='router_agent',
            executable='enhanced_guard_engine.py',
            name='enhanced_guard_engine',
            output='screen',
            condition=IfCondition(enable_safety),
            parameters=[{
                'guard.enable_wakeword_detection': True,
                'guard.enable_sos_detection': True,
                'elderly.adaptations.enabled': True,
            }]
        ),
        Node(
            package='router_agent',
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
            package='router_agent',
            executable='safety_guard_node.py',
            name='safety_guard_node',
            output='screen',
            condition=IfCondition(enable_safety),
            parameters=[{
                'safety.emergency_response_time_ms': 100,
            }]
        )
    ]
    
    # Communication Nodes
    communication_nodes = [
        Node(
            package='router_agent',
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
            package='router_agent',
            executable='dialog_manager_node.py',
            name='dialog_manager_node',
            output='screen',
            parameters=[{
                'elderly.conversation_adaptations': True,
            }]
        )
    ]
    
    # Smart Home Nodes
    smart_home_nodes = [
        Node(
            package='router_agent',
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
            package='router_agent',
            executable='mqtt_adapter_node.py',
            name='mqtt_adapter_node',
            output='screen',
            condition=IfCondition(enable_smart_home),
            parameters=[{
                'elderly.device_simplification': True,
            }]
        )
    ]
    
    # Video Streaming Nodes
    video_nodes = [
        Node(
            package='router_agent',
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
    
    # Build launch description
    ld = LaunchDescription()
    
    # Add arguments
    for arg in launch_args:
        ld.add_action(arg)
    
    # Add startup message
    ld.add_action(LogInfo(
        msg=[
            '\n🤖 STARTING ELDERLY COMPANION ROBOT - ENHANCED SYSTEM\n',
            'Mode: ', mode, ' | Target: ', deployment_target, '\n'
        ]
    ))
    
    # Add core nodes first
    for node in core_nodes:
        ld.add_action(node)
    
    # Add other node groups with delays
    ld.add_action(TimerAction(period=5.0, actions=audio_nodes))
    ld.add_action(TimerAction(period=10.0, actions=safety_nodes))
    ld.add_action(TimerAction(period=15.0, actions=communication_nodes))
    ld.add_action(TimerAction(period=20.0, actions=smart_home_nodes))
    ld.add_action(TimerAction(period=25.0, actions=video_nodes))
    
    # Add completion message
    ld.add_action(TimerAction(
        period=35.0,
        actions=[LogInfo(msg='\n🎉 ELDERLY COMPANION ROBOT SYSTEM READY!\n')]
    ))
    
    return ld