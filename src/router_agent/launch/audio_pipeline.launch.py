#!/usr/bin/env python3
"""
Launch file for the Elderly Companion Robdog Audio Processing Pipeline
Coordinates VAD, ASR, and Emotion Analysis nodes
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch.conditions import IfCondition


def generate_launch_description():
    """Generate launch description for audio processing pipeline"""
    
    # Declare launch arguments
    declare_use_rknpu = DeclareLaunchArgument(
        'use_rknpu',
        default_value='false',
        description='Use RK3588 NPU for acceleration'
    )
    
    declare_audio_device = DeclareLaunchArgument(
        'audio_device',
        default_value='-1',
        description='Audio device index (-1 for default)'
    )
    
    declare_log_level = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='Log level for nodes'
    )
    
    declare_elderly_mode = DeclareLaunchArgument(
        'elderly_mode',
        default_value='true',
        description='Enable elderly-specific processing'
    )
    
    # Get launch configurations
    use_rknpu = LaunchConfiguration('use_rknpu')
    audio_device = LaunchConfiguration('audio_device')
    log_level = LaunchConfiguration('log_level')
    elderly_mode = LaunchConfiguration('elderly_mode')
    
    # Audio Processor Node
    audio_processor_node = Node(
        package='router_agent',
        executable='audio_processor_node.py',
        name='audio_processor',
        namespace='elderly_companion',
        parameters=[
            {'audio.device_index': audio_device},
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
    )
    
    # Speech Recognition Node
    speech_recognition_node = Node(
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
            {'elderly.speech_patterns.enabled': elderly_mode},
            {'elderly.speech_patterns.slower_speech_multiplier': 1.5},
            {'elderly.vocabulary.medical_terms': True},
            {'elderly.vocabulary.daily_activities': True},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # Emotion Analyzer Node
    emotion_analyzer_node = Node(
        package='router_agent',
        executable='emotion_analyzer_node.py',
        name='emotion_analyzer',
        namespace='elderly_companion',
        parameters=[
            {'emotion.model_path': '/models/emotion/chinese-bert'},
            {'emotion.audio_model_path': '/models/emotion/audio-features'},
            {'emotion.use_gpu': False},
            {'emotion.confidence_threshold': 0.6},
            {'elderly.health_indicators.enabled': elderly_mode},
            {'elderly.stress_detection.enabled': elderly_mode},
            {'elderly.loneliness_detection.enabled': elderly_mode},
            {'audio.sample_rate': 16000},
            {'audio.n_mfcc': 13},
            {'analysis.window_size': 5.0},
        ],
        arguments=['--ros-args', '--log-level', log_level],
        output='screen',
        emulate_tty=True,
    )
    
    # Log startup information
    startup_log = LogInfo(
        msg=PythonExpression([
            '"Starting Elderly Companion Audio Processing Pipeline\\n"',
            '"  - Use RKNPU: ', use_rknpu, '\\n"',
            '"  - Audio Device: ', audio_device, '\\n"',
            '"  - Elderly Mode: ', elderly_mode, '\\n"',
            '"  - Log Level: ', log_level, '"'
        ])
    )
    
    return LaunchDescription([
        # Launch arguments
        declare_use_rknpu,
        declare_audio_device,
        declare_log_level,
        declare_elderly_mode,
        
        # Startup log
        startup_log,
        
        # Nodes
        audio_processor_node,
        speech_recognition_node,
        emotion_analyzer_node,
    ])