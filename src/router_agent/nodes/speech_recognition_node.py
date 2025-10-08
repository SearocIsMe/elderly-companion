#!/usr/bin/env python3
"""
Speech Recognition Node for Elderly Companion Robdog.

Handles Automatic Speech Recognition (ASR) using sherpa-onnx (v1.12.14) with
priority support for Zipformer2-CTC (asr-zip-zh-en) and fallback to Transducer.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import threading
import time
from typing import Optional, List, Dict, Any
import os
import glob
import json

# Speech recognition imports
import sherpa_onnx
import soundfile as sf
import tempfile

# ROS2 message imports
#from audio_common_msgs.msg import AudioData
from std_msgs.msg import Header
from elderly_companion.msg import SpeechResult, EmotionData
from elderly_companion.srv import ProcessSpeech


class SpeechRecognitionNode(Node):
    """
    Speech Recognition Node using sherpa-onnx for elderly-optimized ASR.

    Supports Zipformer2-CTC (zh-en) as the primary online model and
    falls back to Transducer if needed.
    """

    def __init__(self):
        super().__init__('speech_recognition_node')

        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # 改为你的 zipformer-ctc 目录（含 tokens.txt & model.onnx）
                ('asr.model_path', '/models/asr-zip-zh-en'),
                ('asr.language', 'zh-CN'),
                ('asr.sample_rate', 16000),
                ('asr.use_rknpu', False),        # 无 .rknn 时使用 CPU
                ('asr.chunk_length', 0.1),       # 100ms chunks
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
            Header,
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
            'daily':   ['吃饭', '睡觉', '散步', '看电视', '打电话', '家人', '朋友'],
            'emotional': ['开心', '难过', '担心', '害怕', '孤独', '想念']
        }

        self.get_logger().info("Speech Recognition Node initialized successfully")

    # --------------------------
    # Model initialization
    # --------------------------
    def initialize_asr_model(self):
        """Initialize sherpa-onnx OnlineRecognizer with priority for Zipformer2-CTC."""
        try:
            self.get_logger().info(f"Initializing ASR with sherpa-onnx v{sherpa_onnx.__version__}")

            # Detect model type by files in model_path
            tokens = os.path.join(self.model_path, "tokens.txt")
            zip_ctc = os.path.join(self.model_path, "model.onnx")
            enc = self._find_one(self.model_path, "encoder-*.onnx")
            dec = self._find_one(self.model_path, "decoder-*.onnx")
            joi = self._find_one(self.model_path, "joiner-*.onnx")

            if os.path.isfile(tokens) and os.path.isfile(zip_ctc):
                self.get_logger().info("Detected Zipformer2-CTC (tokens.txt + model.onnx)")
                self.recognizer = self._create_recognizer_zipformer_ctc(tokens, zip_ctc, provider="cpu")
            elif enc and dec and joi and os.path.isfile(tokens):
                self.get_logger().info("Detected Transducer (encoder/decoder/joiner)")
                self.recognizer = self._create_recognizer_transducer(tokens, enc, dec, joi, provider="cpu")
            else:
                raise RuntimeError(
                    "Model files not recognized. Expected Zipformer2-CTC (tokens.txt + model.onnx) "
                    "or Transducer (encoder/decoder/joiner + tokens.txt)"
                )

            if self.recognizer is None:
                raise RuntimeError("Failed to create recognizer")

            self.get_logger().info(f"ASR model loaded successfully (RKNPU: {self.use_rknpu})")

        except Exception as e:
            self.get_logger().error(f"Failed to initialize ASR model: {e}")
            self.initialize_fallback_model()

    def _find_one(self, path: str, pattern: str) -> Optional[str]:
        g = sorted(glob.glob(os.path.join(path, pattern)))
        return g[0] if g else None

    # Preferred: Zipformer2-CTC (asr-zip-zh-en)
    def _create_recognizer_zipformer_ctc(self, tokens: str, model: str, provider: str = "cpu"):
        """
        Create OnlineRecognizer for Zipformer2-CTC.
        Tries the dedicated factory first; if not available, falls back to a config-based ctor.
        """
        # Try 1: factory method available in 1.12.x
        if hasattr(sherpa_onnx, "OnlineRecognizer") and hasattr(sherpa_onnx.OnlineRecognizer, "from_zipformer2_ctc"):
            self.get_logger().info("Using OnlineRecognizer.from_zipformer2_ctc(...)")
            return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
                tokens=tokens,
                model=model,
                num_threads=4,
                provider=provider,
                decoding_method="greedy_search",
                sample_rate=self.sample_rate,
                feature_dim=80,
            )

        # Try 2: config-based constructor (compatible fallback)
        self.get_logger().info("Using OnlineRecognizer(...) with Zipformer2-CTC config fallback")

        # Some releases expose config classes; guard with getattr to avoid attribute errors
        FeatureConfig = getattr(sherpa_onnx, "FeatureConfig", None)
        OnlineModelConfig = getattr(sherpa_onnx, "OnlineModelConfig", None)
        Zipformer2CtcModelConfig = getattr(sherpa_onnx, "Zipformer2CtcModelConfig", None)
        OnlineRecognizerConfig = getattr(sherpa_onnx, "OnlineRecognizerConfig", None)

        if not all([FeatureConfig, OnlineModelConfig, Zipformer2CtcModelConfig, OnlineRecognizerConfig]):
            raise RuntimeError("Zipformer2-CTC factory not found and config classes unavailable in current build")

        feat_cfg = FeatureConfig(sample_rate=self.sample_rate, feature_dim=80)
        zfc_cfg = Zipformer2CtcModelConfig(
            model=model,
            tokens=tokens,
            num_threads=4,
            provider=provider,
        )
        mdl_cfg = OnlineModelConfig(zipformer2_ctc=zfc_cfg)
        rec_cfg = OnlineRecognizerConfig(
            feat_config=feat_cfg,
            model_config=mdl_cfg,
            decoding_method="greedy_search",
        )
        return sherpa_onnx.OnlineRecognizer(rec_cfg)

    # Fallback: Transducer path if your dir is encoder/decoder/joiner based
    def _create_recognizer_transducer(self, tokens: str, encoder: str, decoder: str, joiner: str, provider: str = "cpu"):
        self.get_logger().info("Creating Transducer OnlineRecognizer (greedy_search)")
        # Prefer factory:
        if hasattr(sherpa_onnx.OnlineRecognizer, "from_transducer"):
            return sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=tokens,
                encoder=encoder,
                decoder=decoder,
                joiner=joiner,
                num_threads=2,
                provider=provider,
                decoding_method="greedy_search",
                sample_rate=self.sample_rate,
                feature_dim=80,
            )
        # Otherwise direct ctor (older API kept for compatibility)
        return sherpa_onnx.OnlineRecognizer(
            tokens=tokens,
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            num_threads=2,
            provider=provider,
            decoding_method="greedy_search",
            sample_rate=self.sample_rate,
            feature_dim=80,
        )

    def create_cpu_recognizer_v1_12(self):
        """Kept for API compatibility; now routed by initialize_asr_model()."""
        # The logic is handled in initialize_asr_model()
        return self.recognizer

    def create_rknpu_recognizer_v1_12(self):
        """
        Create RKNPU recognizer if you have .rknn models; otherwise, use CPU.
        (No .rknn provided here; so we log and fallback to CPU in initialize_asr_model()).
        """
        self.get_logger().warn("RKNPU requested but .rknn files not provided; using CPU path")
        return self.recognizer

    def initialize_fallback_model(self):
        """Very conservative fallback: try to load whatever is present."""
        try:
            tokens = os.path.join(self.model_path, "tokens.txt")
            zip_ctc = os.path.join(self.model_path, "model.onnx")
            if os.path.isfile(tokens) and os.path.isfile(zip_ctc):
                self.get_logger().warn("Fallback: trying Zipformer2-CTC minimal")
                self.recognizer = self._create_recognizer_zipformer_ctc(tokens, zip_ctc, provider="cpu")
                return
            enc = self._find_one(self.model_path, "encoder-*.onnx")
            dec = self._find_one(self.model_path, "decoder-*.onnx")
            joi = self._find_one(self.model_path, "joiner-*.onnx")
            if enc and dec and joi and os.path.isfile(tokens):
                self.get_logger().warn("Fallback: trying Transducer minimal")
                self.recognizer = self._create_recognizer_transducer(tokens, enc, dec, joi, provider="cpu")
                return
            raise RuntimeError("No recognizable model files for fallback")
        except Exception as e:
            self.get_logger().error(f"Fallback failed: {e}")
            self.recognizer = None

    # --------------------------
    # Streaming pipeline
    # --------------------------
    def process_audio_callback(self, msg):
        """Process incoming audio messages (float32 PCM)."""
        try:
            self.get_logger().debug("Received audio for speech recognition")
            audio_data = np.frombuffer(msg.data, dtype=np.float32)
            result = self.recognize_speech(audio_data, msg.header)
            if result:
                self.speech_result_pub.publish(result)
        except Exception as e:
            self.get_logger().error(f"Audio processing callback error: {e}")

    def recognize_speech(self, audio_data: np.ndarray, header: Header) -> Optional[SpeechResult]:
        """Perform streaming recognition on audio data."""
        try:
            start_time = time.time()

            if self.recognizer is None or len(audio_data) == 0:
                return None

            # Create stream for online recognition
            stream = self.recognizer.create_stream()

            # Process audio in chunks
            chunk_dur = float(self.get_parameter('asr.chunk_length').value)
            chunk_size = max(1, int(self.sample_rate * chunk_dur))

            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) == 0:
                    continue
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                stream.accept_waveform(self.sample_rate, chunk)

                # 可选：在流式场景中执行中间解码
                while self.recognizer.is_ready(stream):
                    self.recognizer.decode_stream(stream)

            # Finalize
            stream.input_finished()
            while self.recognizer.is_ready(stream):
                self.recognizer.decode_stream(stream)
            result_text = self.recognizer.get_result(stream).text

            processing_time = (time.time() - start_time) * 1000.0  # ms
            is_emergency = self.detect_emergency_keywords(result_text)

            speech_result = self.create_speech_result(
                result_text,
                header,
                processing_time,
                is_emergency,
                len(audio_data) / self.sample_rate
            )
            self.get_logger().info(f"[ASR] '{result_text}' (emergency: {is_emergency})")
            return speech_result

        except Exception as e:
            self.get_logger().error(f"Speech recognition error: {e}")
            return self.create_error_result(header, str(e))

    # --------------------------
    # Utilities (unchanged)
    # --------------------------
    def create_fallback_recognition_result(self, audio_data: np.ndarray, header: Header) -> SpeechResult:
        duration = len(audio_data) / self.sample_rate
        if np.mean(np.abs(audio_data)) > 0.1:
            result_text = "[Speech detected - model not loaded]"
            confidence = 0.5
        else:
            result_text = "[Low audio detected]"
            confidence = 0.2
        return self.create_speech_result(result_text, header, 50.0, False, duration)

    def create_speech_result(self, text: str, header: Header, processing_time: float,
                             is_emergency: bool, duration: float) -> SpeechResult:
        result = SpeechResult()
        result.header = header
        result.text = text
        result.confidence = 0.8 if text and len(text) > 3 else 0.3
        result.language = self.language
        result.voice_activity_detected = len(text) > 0
        result.audio_duration_seconds = duration
        result.sample_rate = self.sample_rate

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
        if not text:
            return False
        text_lower = text.lower()
        for lang_keywords in self.emergency_keywords.values():
            for keyword in lang_keywords:
                if keyword.lower() in text_lower:
                    self.get_logger().warning(f"Emergency keyword detected: {keyword}")
                    return True
        return False

    def detect_elderly_patterns(self, text: str) -> bool:
        if not text or not self.elderly_patterns_enabled:
            return False
        text_lower = text.lower()
        for _, words in self.elderly_vocabulary.items():
            for word in words:
                if word in text_lower:
                    return True
        return False

    def create_error_result(self, header: Header, error_msg: str) -> SpeechResult:
        result = SpeechResult()
        result.header = header
        result.text = f"[Recognition Error: {error_msg}]"
        result.confidence = 0.0
        result.language = self.language
        result.voice_activity_detected = False
        result.audio_duration_seconds = 0.0
        result.sample_rate = self.sample_rate

        emotion_data = EmotionData()
        emotion_data.primary_emotion = "neutral"
        emotion_data.confidence = 0.0
        emotion_data.timestamp = self.get_clock().now().to_msg()

        result.emotion = emotion_data
        return result

    def process_speech_service_callback(self, request, response):
        try:
            self.get_logger().info("Speech recognition service called")
            audio_data = np.frombuffer(request.audio_data.data, dtype=np.float32)
            header = Header()
            header.stamp = self.get_clock().now().to_msg()
            header.frame_id = "speech_recognition"
            speech_result = self.recognize_speech(audio_data, header)
            if speech_result:
                response.processing_successful = True
                response.speech_result = speech_result
                response.processing_time_ms = 100.0
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
