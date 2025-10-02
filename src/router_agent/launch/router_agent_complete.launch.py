#!/usr/bin/env python3
"""
Complete Router Agent Launch File.

Launches the full Router Agent (RK3588) architecture for elderly companion:
- Audio Processing Pipeline (VAD -> ASR -> Emotion Analysis)
- Dialog Manager (AI-powered conversation)
- Safety Monitoring System
- Router Agent Coordinator (Main orchestrator)
- TTS Output System

Supports both text and microphone+speaker interfaces.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, GroupAction
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch.conditions import IfCondition, UnlessCondition


def generate_launch_description():
    """Generate complete Router Agent launch description."""
    
    # Declare launch arguments
    declare_mode = DeclareLaunchArgument(
        'mode',
        default_value='hybrid',
        description='Router Agent mode: text_only, audio_only, hybrid'
    )
    
    declare_enable_audio = DeclareLaunchArgument(
        'enable_audio',
        default_value='true',
        description='Enable audio processing (microphone + speaker)'
    )
    
    declare_enable_safety = DeclareLaunchArgument(
        'enable_safety',
        default_value='true',
        description='Enable safety monitoring system'
    )
    
    declare_use_rknpu = DeclareLaunchArgument(
        'use_rknpu',
        default_value='false',
        description='Use RK3588 NPU for acceleration'
    )
    
    declare_log_level = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='Log level for all nodes'
    )
    
    # Get launch configurations
    mode = LaunchConfiguration('mode')
    enable_audio = LaunchConfiguration('enable_audio')
    enable_safety = LaunchConfiguration('enable_safety')
    use_rknpu = LaunchConfiguration('use_rknpu')
    log_level = LaunchConfiguration('log_level')
    
    # Audio processing condition
    audio_condition = IfCondition(
        PythonExpression([
            "'", enable_audio, "' == 'true' and '", mode, "' in ['audio_only', 'hybrid']"
        ])
    )
    
    # Router Agent Coordinator (Main orchestrator)
    router_agent_coordinator = Node(
        package='router_agent',
        executable='router_agent_coordinator.py',
        name='router_agent_coordinator',
        namespace='elderly_companion',
        parameters=[
            {'router_agent.mode': mode},
            {'router_agent.enable_safety_monitoring': enable_safety},
            {'router_agent.enable_conversation_logging': True},
            {'router_agent.response_timeout_seconds': 10.0},
            {'audio.enable_microphone': enable_audio},
            {'audio.enable_speaker': enable_audio},
            {'text.enable_console_interface': True},
            {'text.enable_web_interface': False},
            {'safety.emergency_response_time_ms': 200},
            {'ai.conversation_model': 'local'},
            {'ai.safety_level': 'elderly_care'},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # Audio Processing Pipeline (conditional)
    audio_pipeline_group = GroupAction(
        condition=audio_condition,
        actions=[
            # Audio Processor Node
            Node(
                package='router_agent',
                executable='audio_processor_node.py',
                name='audio_processor',
                namespace='elderly_companion',
                parameters=[
                    {'audio.device_index': -1},  # Default device
                    {'audio.sample_rate': 48000},
                    {'audio.channels': 6},
                    {'audio.chunk_size': 4800},
                    {'vad.threshold': 0.7},
                    {'vad.min_silence_duration_ms': 300},
                    {'processing.max_audio_length_seconds': 30.0},
                    {'processing.emergency_keywords': ['help', 'emergency', '救命', '急救']},
                ],
                arguments=['--ros-args', '--log-level', log_level],
                output='screen',
                emulate_tty=True,
            ),
            
            # Speech Recognition Node
            Node(
                package='router_agent',
                executable='speech_recognition_node.py',
                name='speech_recognition',
                namespace='elderly_companion',
                parameters=[
                    {'asr.model_path': '/models/sherpa-onnx/chinese-english'},
                    {'asr.language': 'zh-CN'},
                    {'asr.sample_rate': 16000},
                    {'asr.use_rknpu': use_rknpu},
                    {'asr.chunk_length': 0.1},
                    {'asr.max_active_paths': 4},
                    {'elderly.speech_patterns.enabled': True},
                    {'elderly.speech_patterns.slower_speech_multiplier': 1.5},
                    {'elderly.vocabulary.medical_terms': True},
                    {'elderly.vocabulary.daily_activities': True},
                ],
                arguments=['--ros-args', '--log-level', log_level],
                output='screen',
                emulate_tty=True,
            ),
            
            # Emotion Analyzer Node
            Node(
                package='router_agent',
                executable='emotion_analyzer_node.py',
                name='emotion_analyzer',
                namespace='elderly_companion',
                parameters=[
                    {'emotion.model_path': '/models/emotion/chinese-bert'},
                    {'emotion.audio_model_path': '/models/emotion/audio-features'},
                    {'emotion.use_gpu': False},
                    {'emotion.confidence_threshold': 0.6},
                    {'elderly.health_indicators.enabled': True},
                    {'elderly.stress_detection.enabled': True},
                    {'elderly.loneliness_detection.enabled': True},
                    {'audio.sample_rate': 16000},
                    {'audio.n_mfcc': 13},
                    {'analysis.window_size': 5.0},
                ],
                arguments=['--ros-args', '--log-level', log_level],
                output='screen',
                emulate_tty=True,
            ),
        ]
    )
    
    # Dialog Manager Node (AI-powered conversation)
    dialog_manager = Node(
        package='router_agent',
        executable='dialog_manager_node.py',
        name='dialog_manager',
        namespace='elderly_companion',
        parameters=[
            {'dialog.max_conversation_length': 50},
            {'dialog.context_timeout_minutes': 30},
            {'dialog.response_delay_seconds': 1.0},
            {'elderly.preferred_language': 'zh-CN'},
            {'elderly.communication_style': 'formal'},
            {'elderly.response_speed': 'slow'},
            {'templates.enable_personalization': True},
            {'templates.comfort_frequency': 0.3},
            {'memory.enable_conversation_history': True},
            {'memory.max_history_days': 30},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # Safety Guard Node (conditional)
    safety_guard = Node(
        package='router_agent',
        executable='safety_guard_node.py',
        name='safety_guard',
        namespace='elderly_companion',
        condition=IfCondition(enable_safety),
        parameters=[
            {'safety.emergency_response_time_ms': 200},
            {'safety.elderly_motion_limits.max_linear_velocity': 0.6},
            {'safety.elderly_motion_limits.max_angular_velocity': 1.0},
            {'safety.comfort_zone.min_distance': 1.0},
            {'safety.health_monitoring.enabled': True},
            {'safety.fall_detection.enabled': True},
            {'safety.emergency_escalation.enabled': True},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # TTS Engine Node (conditional - for audio output)
    tts_engine = Node(
        package='router_agent',
        executable='tts_engine_node.py',
        name='tts_engine',
        namespace='elderly_companion',
        condition=audio_condition,
        parameters=[
            {'tts.engine': 'pyttsx3'},  # or 'festival', 'espeak', 'azure'
            {'tts.voice_id': 'zh'},
            {'tts.rate': 150},  # Slower for elderly
            {'tts.volume': 0.8},
            {'tts.elderly_optimized': True},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # MQTT Adapter Node (for smart home integration)
    mqtt_adapter = Node(
        package='router_agent',
        executable='mqtt_adapter_node.py',
        name='mqtt_adapter',
        namespace='elderly_companion',
        parameters=[
            {'mqtt.broker_host': 'localhost'},
            {'mqtt.broker_port': 1883},
            {'mqtt.client_id': 'elderly_companion_router'},
            {'mqtt.keepalive': 60},
            {'smart_home.enable_device_control': True},
            {'smart_home.emergency_integration': True},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # Log startup information
    startup_log = LogInfo(
        msg=PythonExpression([
            '"🤖 Starting Elderly Companion Router Agent\\n"',
            '"  Mode: ', mode, '\\n"',
            '"  Audio Enabled: ', enable_audio, '\\n"',
            '"  Safety Monitoring: ', enable_safety, '\\n"',
            '"  RKNPU Acceleration: ', use_rknpu, '\\n"',
            '"  Log Level: ', log_level, '\\n"',
            '"\\n📋 System Architecture:\\n"',
            '"  🎤 Audio Pipeline -> 🧠 Dialog Manager -> 🛡️ Safety Guard\\n"',
            '"  🔄 Router Agent Coordinator orchestrates all components\\n"',
            '"  📱 Supports text and voice interfaces\\n"',
            '"  🚨 <200ms emergency response time\\n"'
        ])
    )
    
    return LaunchDescription([
        # Launch arguments
        declare_mode,
        declare_enable_audio,
        declare_enable_safety,
        declare_use_rknpu,
        declare_log_level,
        
        # Startup information
        startup_log,
        
        # Core nodes (always running)
        router_agent_coordinator,
        dialog_manager,
        mqtt_adapter,
        
        # Conditional nodes
        audio_pipeline_group,  # Only if audio enabled
        safety_guard,          # Only if safety enabled
        tts_engine,           # Only if audio enabled
    ])