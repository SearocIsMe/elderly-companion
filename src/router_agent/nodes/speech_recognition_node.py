#!/usr/bin/env python3
"""
Speech Recognition Node for Elderly Companion Robdog.

Handles Automatic Speech Recognition (ASR) using sherpa-onnx with RKNPU optimization.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import threading
import time
from typing import Optional, List, Dict, Any
import os

# Speech recognition imports
import sherpa_onnx
import soundfile as sf
import tempfile

# ROS2 message imports
from sensor_msgs.msg import Audio
from std_msgs.msg import Header
from elderly_companion.msg import SpeechResult, EmotionData
from elderly_companion.srv import ProcessSpeech


class SpeechRecognitionNode(Node):
    """
    Speech Recognition Node using sherpa-onnx for elderly-optimized ASR.
    
    Supports both Chinese and English recognition with elderly speech patterns.
    """

    def __init__(self):
        super().__init__('speech_recognition_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('asr.model_path', '/models/sherpa-onnx/chinese-english'),
                ('asr.language', 'zh-CN'),
                ('asr.sample_rate', 16000),
                ('asr.use_rknpu', True),
                ('asr.chunk_length', 0.1),  # 100ms chunks
                ('asr.max_active_paths', 4),
                ('elderly.speech_patterns.enabled', True),
                ('elderly.speech_patterns.slower_speech_multiplier', 1.5),
                ('elderly.vocabulary.medical_terms', True),
                ('elderly.vocabulary.daily_activities', True),
            ]
        )
        
        # Get parameters
        self.model_path = self.get_parameter('asr.model_path').value
        self.language = self.get_parameter('asr.language').value
        self.sample_rate = self.get_parameter('asr.sample_rate').value
        self.use_rknpu = self.get_parameter('asr.use_rknpu').value
        self.elderly_patterns_enabled = self.get_parameter('elderly.speech_patterns.enabled').value
        
        # Initialize ASR model
        self.get_logger().info(f"Loading sherpa-onnx ASR model from: {self.model_path}")
        self.initialize_asr_model()
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.audio_sub = self.create_subscription(
            Audio,
            '/audio/speech_segments',
            self.process_audio_callback,
            default_qos
        )
        
        # Publishers
        self.speech_result_pub = self.create_publisher(
            SpeechResult,
            '/speech/recognized',
            default_qos
        )
        
        # Services
        self.asr_service = self.create_service(
            ProcessSpeech,
            '/speech_recognition/process',
            self.process_speech_service_callback
        )
        
        # Emergency keywords for priority processing
        self.emergency_keywords = {
            'zh-CN': ['救命', '急救', '帮助', '不舒服', '痛', '摔倒', '头晕', '胸痛'],
            'en-US': ['help', 'emergency', 'pain', 'hurt', 'fell', 'dizzy', 'chest pain', 'cant breathe']
        }
        
        # Elderly-specific vocabulary enhancements
        self.elderly_vocabulary = {
            'medical': ['血压', '心脏', '药物', '医生', '医院', '不舒服', '疼痛'],
            'daily': ['吃饭', '睡觉', '散步', '看电视', '打电话', '家人', '朋友'],
            'emotional': ['开心', '难过', '担心', '害怕', '孤独', '想念']
        }
        
        self.get_logger().info("Speech Recognition Node initialized successfully")

    def initialize_asr_model(self):
        """Initialize the sherpa-onnx ASR model."""
        try:
            # Configure ASR model based on deployment target
            if self.use_rknpu:
                # RK3588 NPU optimized configuration
                config = self.create_rknpu_config()
            else:
                # CPU configuration for development
                config = self.create_cpu_config()
            
            # Create recognizer
            self.recognizer = sherpa_onnx.OnlineRecognizer(config)
            
            # Test the model
            if self.recognizer is None:
                raise RuntimeError("Failed to create recognizer")
            
            self.get_logger().info(f"ASR model loaded successfully (RKNPU: {self.use_rknpu})")
            
        except Exception as e:
            self.get_logger().error(f"Failed to initialize ASR model: {e}")
            # Fallback to a basic configuration
            self.initialize_fallback_model()

    def create_rknpu_config(self):
        """Create RKNPU-optimized configuration for RK3588."""
        config = sherpa_onnx.OnlineRecognizerConfig(
            feat_config=sherpa_onnx.FeatureConfig(
                sample_rate=self.sample_rate,
                feature_dim=80,
            ),
            model_config=sherpa_onnx.OnlineModelConfig(
                transducer=sherpa_onnx.OnlineTransducerModelConfig(
                    encoder_filename=os.path.join(self.model_path, "encoder.rknn"),
                    decoder_filename=os.path.join(self.model_path, "decoder.rknn"),
                    joiner_filename=os.path.join(self.model_path, "joiner.rknn"),
                ),
                tokens=os.path.join(self.model_path, "tokens.txt"),
                provider="rknpu",
                model_type="transducer",
                modeling_unit="cjkchar",
                bpe_vocab="",
            ),
            decoder_config=sherpa_onnx.OnlineRecognizerDecoderConfig(
                decoding_method="greedy_search",
                max_active_paths=4,
            ),
            enable_endpoint=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=300,
        )
        return config

    def create_cpu_config(self):
        """Create CPU configuration for development."""
        config = sherpa_onnx.OnlineRecognizerConfig(
            feat_config=sherpa_onnx.FeatureConfig(
                sample_rate=self.sample_rate,
                feature_dim=80,
            ),
            model_config=sherpa_onnx.OnlineModelConfig(
                transducer=sherpa_onnx.OnlineTransducerModelConfig(
                    encoder_filename=os.path.join(self.model_path, "encoder.onnx"),
                    decoder_filename=os.path.join(self.model_path, "decoder.onnx"),
                    joiner_filename=os.path.join(self.model_path, "joiner.onnx"),
                ),
                tokens=os.path.join(self.model_path, "tokens.txt"),
                provider="cpu",
                model_type="transducer",
                modeling_unit="cjkchar",
            ),
            decoder_config=sherpa_onnx.OnlineRecognizerDecoderConfig(
                decoding_method="greedy_search",
                max_active_paths=4,
            ),
            enable_endpoint=True,
        )
        return config

    def initialize_fallback_model(self):
        """Initialize a fallback model for testing."""
        self.get_logger().warning("Using fallback speech recognition model")
        # Create a mock recognizer for development
        self.recognizer = None

    def process_audio_callback(self, msg: Audio):
        """Process incoming audio messages."""
        try:
            self.get_logger().debug("Received audio for speech recognition")
            
            # Convert audio data
            audio_data = np.frombuffer(msg.data, dtype=np.float32)
            
            # Process with ASR
            result = self.recognize_speech(audio_data, msg.header)
            
            if result:
                self.speech_result_pub.publish(result)
                
        except Exception as e:
            self.get_logger().error(f"Audio processing callback error: {e}")

    def recognize_speech(self, audio_data: np.ndarray, header: Header) -> Optional[SpeechResult]:
        """Perform speech recognition on audio data."""
        try:
            start_time = time.time()
            
            if self.recognizer is None:
                # Fallback recognition for development
                return self.create_fallback_recognition_result(audio_data, header)
            
            # Resample audio if needed
            if len(audio_data) == 0:
                return None
            
            # Create stream for online recognition
            stream = self.recognizer.create_stream()
            
            # Process audio in chunks
            chunk_size = int(self.sample_rate * 0.1)  # 100ms chunks
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) > 0:
                    # Pad if necessary
                    if len(chunk) < chunk_size:
                        chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                    
                    stream.accept_waveform(self.sample_rate, chunk)
            
            # Get final result
            stream.input_finished()
            result_text = self.recognizer.get_result(stream).text
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms
            
            # Check for emergency keywords
            is_emergency = self.detect_emergency_keywords(result_text)
            
            # Create speech result
            speech_result = self.create_speech_result(
                result_text, 
                header, 
                processing_time,
                is_emergency,
                len(audio_data) / self.sample_rate
            )
            
            self.get_logger().info(f"Recognition result: '{result_text}' (emergency: {is_emergency})")
            
            return speech_result
            
        except Exception as e:
            self.get_logger().error(f"Speech recognition error: {e}")
            return self.create_error_result(header, str(e))

    def create_fallback_recognition_result(self, audio_data: np.ndarray, header: Header) -> SpeechResult:
        """Create a fallback result for development/testing."""
        # Simulate recognition result
        duration = len(audio_data) / self.sample_rate
        
        # Simple pattern detection based on audio characteristics
        if np.mean(np.abs(audio_data)) > 0.1:
            result_text = "[Speech detected - model not loaded]"
            confidence = 0.5
        else:
            result_text = "[Low audio detected]"
            confidence = 0.2
        
        return self.create_speech_result(result_text, header, 50.0, False, duration)

    def create_speech_result(self, text: str, header: Header, processing_time: float,
                           is_emergency: bool, duration: float) -> SpeechResult:
        """Create a SpeechResult message."""
        result = SpeechResult()
        result.header = header
        result.text = text
        result.confidence = 0.8 if text and len(text) > 3 else 0.3
        result.language = self.language
        result.voice_activity_detected = len(text) > 0
        result.audio_duration_seconds = duration
        result.sample_rate = self.sample_rate
        
        # Create basic emotion data (will be enhanced by emotion analyzer)
        emotion_data = EmotionData()
        emotion_data.primary_emotion = "urgent" if is_emergency else "neutral"
        emotion_data.confidence = 0.9 if is_emergency else 0.5
        emotion_data.timestamp = self.get_clock().now().to_msg()
        emotion_data.elderly_specific_patterns_detected = self.detect_elderly_patterns(text)
        
        if is_emergency:
            emotion_data.stress_level = 0.9
            emotion_data.arousal = 0.8
            emotion_data.valence = -0.5
        else:
            emotion_data.stress_level = 0.2
            emotion_data.arousal = 0.4
            emotion_data.valence = 0.1
        
        result.emotion = emotion_data
        
        return result

    def detect_emergency_keywords(self, text: str) -> bool:
        """Detect emergency keywords in recognized text."""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Check for emergency keywords in both languages
        for lang_keywords in self.emergency_keywords.values():
            for keyword in lang_keywords:
                if keyword.lower() in text_lower:
                    self.get_logger().warning(f"Emergency keyword detected: {keyword}")
                    return True
        
        return False

    def detect_elderly_patterns(self, text: str) -> bool:
        """Detect elderly-specific speech patterns."""
        if not text or not self.elderly_patterns_enabled:
            return False
        
        # Check for elderly vocabulary
        text_lower = text.lower()
        
        for category, words in self.elderly_vocabulary.items():
            for word in words:
                if word in text_lower:
                    return True
        
        return False

    def create_error_result(self, header: Header, error_msg: str) -> SpeechResult:
        """Create an error result."""
        result = SpeechResult()
        result.header = header
        result.text = f"[Recognition Error: {error_msg}]"
        result.confidence = 0.0
        result.language = self.language
        result.voice_activity_detected = False
        result.audio_duration_seconds = 0.0
        result.sample_rate = self.sample_rate
        
        # Create error emotion data
        emotion_data = EmotionData()
        emotion_data.primary_emotion = "neutral"
        emotion_data.confidence = 0.0
        emotion_data.timestamp = self.get_clock().now().to_msg()
        
        result.emotion = emotion_data
        
        return result

    def process_speech_service_callback(self, request, response):
        """Handle service callback for speech processing."""
        try:
            self.get_logger().info("Speech recognition service called")
            
            # Extract and process audio
            audio_data = np.frombuffer(request.audio_data.data, dtype=np.float32)
            
            # Create header
            header = Header()
            header.stamp = self.get_clock().now().to_msg()
            header.frame_id = "speech_recognition"
            
            # Perform recognition
            speech_result = self.recognize_speech(audio_data, header)
            
            if speech_result:
                response.processing_successful = True
                response.speech_result = speech_result
                response.processing_time_ms = 100.0  # Placeholder
                response.audio_quality_score = 0.8
                response.voice_print_matched = False
                response.requires_clarification = False
            else:
                response.processing_successful = False
                response.error_message = "Recognition failed"
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Speech recognition service error: {e}")
            response.processing_successful = False
            response.error_message = str(e)
            return response


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = SpeechRecognitionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()