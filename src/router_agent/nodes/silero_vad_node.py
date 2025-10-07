#!/usr/bin/env python3
"""
Silero VAD Node for Elderly Companion Robdog.

Advanced voice activity detection and noise reduction optimized for elderly speech patterns.
Uses Silero VAD v4.0 with spectral subtraction for noise reduction.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import torch
import torchaudio
import threading
import time
import queue
from typing import Optional, Tuple, List
from collections import deque
import os
import tempfile

# Audio processing imports
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("Warning: pyaudio not available, using mock audio input")

try:
    import scipy.signal
    import librosa
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy/librosa not available, limited audio processing")

# ROS2 message imports
#from audio_common_msgs.msg import AudioData
from std_msgs.msg import Header, Bool
from elderly_companion.msg import SpeechResult, EmotionData

class ElderlyAudioPreprocessor:
    """Audio preprocessing optimized for elderly speech patterns."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.frame_length = int(0.025 * sample_rate)  # 25ms frames
        self.hop_length = int(0.010 * sample_rate)    # 10ms hop
        
        # Elderly speech characteristics
        self.elderly_freq_range = (80, 8000)  # Reduced high-frequency range
        self.preemphasis_coeff = 0.97
        
        # Noise estimation buffer
        self.noise_buffer = deque(maxlen=50)  # Store 50 frames for noise estimation
        self.noise_spectrum = None
        self.alpha = 2.0  # Over-subtraction factor
        self.beta = 0.01  # Spectral floor factor
        
    def preprocess_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Preprocess audio for elderly speech optimization."""
        # Pre-emphasis filter to balance frequency spectrum
        audio_processed = self.apply_preemphasis(audio_data)
        
        # Noise reduction using spectral subtraction
        audio_processed = self.spectral_subtraction(audio_processed)
        
        # Frequency domain filtering for elderly speech
        audio_processed = self.elderly_frequency_filter(audio_processed)
        
        # Normalize volume
        audio_processed = self.normalize_audio(audio_processed)
        
        return audio_processed
    
    def apply_preemphasis(self, audio: np.ndarray) -> np.ndarray:
        """Apply pre-emphasis filter."""
        if len(audio) < 2:
            return audio
        return np.append(audio[0], audio[1:] - self.preemphasis_coeff * audio[:-1])
    
    def spectral_subtraction(self, audio: np.ndarray) -> np.ndarray:
        """Apply spectral subtraction for noise reduction."""
        if not SCIPY_AVAILABLE or len(audio) < self.frame_length:
            return audio
        
        try:
            # STFT
            f, t, stft = scipy.signal.stft(
                audio, 
                fs=self.sample_rate,
                window='hann',
                nperseg=self.frame_length,
                noverlap=self.frame_length//2
            )
            
            magnitude = np.abs(stft)
            phase = np.angle(stft)
            
            # Estimate noise spectrum from first few frames if not available
            if self.noise_spectrum is None or len(self.noise_buffer) < 10:
                self.noise_buffer.extend(magnitude[:, :5].T)  # First 5 frames
                if len(self.noise_buffer) >= 10:
                    self.noise_spectrum = np.mean(list(self.noise_buffer), axis=0)
            
            if self.noise_spectrum is not None:
                # Spectral subtraction
                noise_power = self.noise_spectrum ** 2
                signal_power = magnitude ** 2
                
                # Over-subtraction
                subtracted_power = signal_power - self.alpha * noise_power
                
                # Apply spectral floor
                spectral_floor = self.beta * signal_power
                enhanced_power = np.maximum(subtracted_power, spectral_floor)
                
                # Reconstruct magnitude
                enhanced_magnitude = np.sqrt(enhanced_power)
                
                # Reconstruct complex spectrum
                enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
                
                # ISTFT
                _, enhanced_audio = scipy.signal.istft(
                    enhanced_stft,
                    fs=self.sample_rate,
                    window='hann',
                    nperseg=self.frame_length,
                    noverlap=self.frame_length//2
                )
                
                return enhanced_audio.astype(np.float32)
                
        except Exception:
            pass
        
        return audio
    
    def elderly_frequency_filter(self, audio: np.ndarray) -> np.ndarray:
        """Apply frequency filtering optimized for elderly speech."""
        if not SCIPY_AVAILABLE:
            return audio
        
        try:
            # Design bandpass filter for elderly speech range
            nyquist = self.sample_rate / 2
            low = self.elderly_freq_range[0] / nyquist
            high = min(self.elderly_freq_range[1] / nyquist, 0.95)
            
            b, a = scipy.signal.butter(4, [low, high], btype='band')
            filtered_audio = scipy.signal.filtfilt(b, a, audio)
            
            return filtered_audio.astype(np.float32)
        except Exception:
            return audio
    
    def normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio amplitude."""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            # Gentle normalization to avoid clipping
            return audio * (0.8 / max_val)
        return audio


class SileroVADNode(Node):
    """
    Silero VAD Node with elderly-optimized voice activity detection.
    
    Features:
    - Silero VAD v4.0 for robust voice activity detection
    - Noise reduction using spectral subtraction
    - Elderly speech pattern optimization
    - Real-time audio streaming and processing
    - Voice activity segmentation and buffering
    """

    def __init__(self):
        super().__init__('silero_vad_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('audio.sample_rate', 16000),
                ('audio.chunk_duration_ms', 100),  # 100ms chunks
                ('audio.input_device_index', -1),  # Default device
                ('audio.channels', 1),
                ('vad.model_path', ''),  # Path to Silero VAD model
                ('vad.threshold', 0.5),
                ('vad.min_speech_duration_ms', 300),
                ('vad.max_speech_duration_ms', 30000),
                ('vad.min_silence_duration_ms', 500),
                ('vad.speech_pad_ms', 100),  # Padding around speech
                ('elderly.enable_optimization', True),
                ('elderly.speech_pace_multiplier', 1.3),
                ('elderly.volume_boost', 1.2),
                ('noise_reduction.enable', True),
                ('noise_reduction.strength', 2.0),
            ]
        )
        
        # Get parameters
        self.sample_rate = self.get_parameter('audio.sample_rate').value
        self.chunk_duration_ms = self.get_parameter('audio.chunk_duration_ms').value
        self.input_device = self.get_parameter('audio.input_device_index').value
        self.channels = self.get_parameter('audio.channels').value
        self.vad_threshold = self.get_parameter('vad.threshold').value
        self.min_speech_duration = self.get_parameter('vad.min_speech_duration_ms').value / 1000.0
        self.max_speech_duration = self.get_parameter('vad.max_speech_duration_ms').value / 1000.0
        self.min_silence_duration = self.get_parameter('vad.min_silence_duration_ms').value / 1000.0
        self.speech_pad_ms = self.get_parameter('vad.speech_pad_ms').value
        self.elderly_optimization = self.get_parameter('elderly.enable_optimization').value
        self.enable_noise_reduction = self.get_parameter('noise_reduction.enable').value
        
        # Audio processing setup
        self.chunk_size = int(self.chunk_duration_ms * self.sample_rate / 1000)
        self.speech_pad_samples = int(self.speech_pad_ms * self.sample_rate / 1000)
        
        # Initialize audio preprocessor
        self.preprocessor = ElderlyAudioPreprocessor(self.sample_rate)
        
        # Audio buffers and state
        self.audio_buffer = queue.Queue(maxsize=100)
        self.speech_buffer = []
        self.is_speaking = False
        self.speech_start_time = None
        self.last_speech_time = None
        self.silence_duration = 0.0
        
        # VAD model
        self.vad_model = None
        self.vad_available = False
        self.initialize_vad_model()
        
        # Audio stream
        self.audio_stream = None
        self.audio_thread = None
        self.running = False
        
        # QoS profiles
        realtime_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Publishers
        self.raw_audio_pub = self.create_publisher(
            Header,
            '/audio/raw_stream',
            realtime_qos
        )
        
        self.processed_audio_pub = self.create_publisher(
            Header,
            '/audio/processed_stream',
            realtime_qos
        )
        
        self.speech_segments_pub = self.create_publisher(
            Header,
            '/audio/speech_segments',
            reliable_qos
        )
        
        self.vad_status_pub = self.create_publisher(
            Bool,
            '/audio/voice_activity',
            realtime_qos
        )
        
        # Initialize and start audio processing
        self.initialize_audio_stream()
        self.start_audio_processing()
        
        self.get_logger().info("Silero VAD Node initialized - Voice activity detection active")

    def initialize_vad_model(self):
        """Initialize Silero VAD model."""
        try:
            model_path = self.get_parameter('vad.model_path').value
            
            if model_path and os.path.exists(model_path):
                # Load custom model
                self.vad_model = torch.jit.load(model_path)
                self.vad_available = True
                self.get_logger().info(f"Loaded custom Silero VAD model: {model_path}")
            else:
                # Try to load pre-trained Silero VAD
                try:
                    self.vad_model, utils = torch.hub.load(
                        repo_or_dir='snakers4/silero-vad',
                        model='silero_vad',
                        force_reload=False,
                        onnx=False
                    )
                    self.vad_available = True
                    self.get_logger().info("Loaded pre-trained Silero VAD model")
                except Exception as e:
                    self.get_logger().warning(f"Failed to load Silero VAD: {e}")
                    self.vad_available = False
            
            if self.vad_available:
                self.vad_model.eval()
                
        except Exception as e:
            self.get_logger().error(f"VAD model initialization error: {e}")
            self.vad_available = False

    def initialize_audio_stream(self):
        """Initialize PyAudio stream."""
        if not PYAUDIO_AVAILABLE:
            self.get_logger().warning("PyAudio not available - using mock audio input")
            return
        
        try:
            self.audio = pyaudio.PyAudio()
            
            # Find input device
            device_index = None
            if self.input_device >= 0:
                device_index = self.input_device
            
            self.audio_stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback,
                start=False
            )
            
            self.get_logger().info(f"Audio stream initialized: {self.sample_rate}Hz, {self.chunk_size} samples/chunk")
            
        except Exception as e:
            self.get_logger().error(f"Audio stream initialization error: {e}")
            self.audio_stream = None

    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for real-time audio input."""
        try:
            if status:
                self.get_logger().warning(f"Audio callback status: {status}")
            
            # Convert to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            
            # Add to processing queue
            if not self.audio_buffer.full():
                self.audio_buffer.put({
                    'data': audio_data,
                    'timestamp': time.time()
                })
            else:
                self.get_logger().warning("Audio buffer overflow - dropping frames")
            
        except Exception as e:
            self.get_logger().error(f"Audio callback error: {e}")
        
        return (None, pyaudio.paContinue)

    def start_audio_processing(self):
        """Start audio processing and streaming."""
        try:
            self.running = True
            
            # Start audio processing thread
            self.audio_thread = threading.Thread(
                target=self.audio_processing_loop,
                daemon=True
            )
            self.audio_thread.start()
            
            # Start audio stream
            if self.audio_stream:
                self.audio_stream.start_stream()
                self.get_logger().info("Audio stream started")
            else:
                # Start mock audio for testing
                self.start_mock_audio()
            
        except Exception as e:
            self.get_logger().error(f"Audio processing start error: {e}")

    def start_mock_audio(self):
        """Start mock audio input for testing."""
        def mock_audio_loop():
            while self.running:
                try:
                    # Generate silence with occasional "speech"
                    mock_data = np.random.normal(0, 0.001, self.chunk_size).astype(np.float32)
                    
                    # Simulate speech every 5 seconds
                    if int(time.time()) % 5 == 0:
                        mock_data += np.random.normal(0, 0.1, self.chunk_size).astype(np.float32)
                    
                    if not self.audio_buffer.full():
                        self.audio_buffer.put({
                            'data': mock_data,
                            'timestamp': time.time()
                        })
                    
                    time.sleep(self.chunk_duration_ms / 1000.0)
                    
                except Exception as e:
                    self.get_logger().error(f"Mock audio error: {e}")
                    break
        
        threading.Thread(target=mock_audio_loop, daemon=True).start()
        self.get_logger().info("Mock audio input started for testing")

    def audio_processing_loop(self):
        """Main audio processing loop."""
        while self.running:
            try:
                # Get audio chunk
                audio_chunk = self.audio_buffer.get(timeout=1.0)
                
                # Process audio chunk
                self.process_audio_chunk(audio_chunk)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Audio processing loop error: {e}")

    def process_audio_chunk(self, audio_chunk: dict):
        """Process individual audio chunk."""
        try:
            audio_data = audio_chunk['data']
            timestamp = audio_chunk['timestamp']
            
            # Publish raw audio
            self.publish_raw_audio(audio_data, timestamp)
            
            # Apply audio preprocessing if enabled
            if self.enable_noise_reduction:
                processed_audio = self.preprocessor.preprocess_audio(audio_data)
            else:
                processed_audio = audio_data
            
            # Publish processed audio
            self.publish_processed_audio(processed_audio, timestamp)
            
            # Perform voice activity detection
            voice_activity = self.detect_voice_activity(processed_audio)
            
            # Publish VAD status
            vad_msg = Bool()
            vad_msg.data = voice_activity
            self.vad_status_pub.publish(vad_msg)
            
            # Handle speech segmentation
            self.handle_speech_segmentation(processed_audio, voice_activity, timestamp)
            
        except Exception as e:
            self.get_logger().error(f"Audio chunk processing error: {e}")

    def detect_voice_activity(self, audio_data: np.ndarray) -> bool:
        """Detect voice activity using Silero VAD."""
        try:
            if not self.vad_available or len(audio_data) == 0:
                # Fallback to energy-based VAD
                return self.energy_based_vad(audio_data)
            
            # Ensure audio is the right length and format for Silero VAD
            audio_tensor = torch.tensor(audio_data).float()
            
            # Resample if needed (Silero VAD expects 16kHz)
            if self.sample_rate != 16000:
                audio_tensor = torchaudio.functional.resample(
                    audio_tensor.unsqueeze(0), 
                    self.sample_rate, 
                    16000
                ).squeeze(0)
            
            # Silero VAD expects at least 512 samples
            if len(audio_tensor) < 512:
                return False
            
            # Get VAD confidence
            with torch.no_grad():
                confidence = self.vad_model(audio_tensor, 16000).item()
            
            # Apply elderly speech optimization
            if self.elderly_optimization:
                # Lower threshold for elderly speech
                adjusted_threshold = self.vad_threshold * 0.8
            else:
                adjusted_threshold = self.vad_threshold
            
            return confidence > adjusted_threshold
            
        except Exception as e:
            self.get_logger().debug(f"VAD detection error: {e}")
            return self.energy_based_vad(audio_data)

    def energy_based_vad(self, audio_data: np.ndarray) -> bool:
        """Fallback energy-based voice activity detection."""
        if len(audio_data) == 0:
            return False
        
        # Calculate RMS energy
        rms_energy = np.sqrt(np.mean(audio_data ** 2))
        
        # Simple threshold-based detection
        energy_threshold = 0.01  # Adjust as needed
        if self.elderly_optimization:
            energy_threshold *= 0.7  # Lower threshold for elderly speech
        
        return rms_energy > energy_threshold

    def handle_speech_segmentation(self, audio_data: np.ndarray, voice_activity: bool, timestamp: float):
        """Handle speech segmentation and buffering."""
        try:
            current_time = timestamp
            
            if voice_activity:
                if not self.is_speaking:
                    # Start of speech
                    self.is_speaking = True
                    self.speech_start_time = current_time
                    self.speech_buffer = []
                    self.get_logger().debug("Speech started")
                
                # Add audio to speech buffer with padding
                if len(self.speech_buffer) == 0:
                    # Add some silence before speech starts
                    padding = np.zeros(self.speech_pad_samples, dtype=np.float32)
                    self.speech_buffer.extend(padding)
                
                self.speech_buffer.extend(audio_data)
                self.last_speech_time = current_time
                
            else:
                if self.is_speaking:
                    # Continue buffering for a short time after speech ends
                    if self.last_speech_time and (current_time - self.last_speech_time) < self.min_silence_duration:
                        self.speech_buffer.extend(audio_data)
                    else:
                        # End of speech - process the segment
                        speech_duration = current_time - self.speech_start_time
                        
                        if speech_duration >= self.min_speech_duration:
                            # Add padding at the end
                            padding = np.zeros(self.speech_pad_samples, dtype=np.float32)
                            self.speech_buffer.extend(padding)
                            
                            # Publish speech segment
                            self.publish_speech_segment(self.speech_buffer, self.speech_start_time)
                            self.get_logger().info(f"Speech segment captured: {speech_duration:.2f}s")
                        else:
                            self.get_logger().debug(f"Speech too short: {speech_duration:.2f}s")
                        
                        # Reset state
                        self.is_speaking = False
                        self.speech_buffer = []
                        self.speech_start_time = None
                        self.last_speech_time = None
                
                self.silence_duration = current_time - (self.last_speech_time or current_time)
            
            # Safety check for maximum speech duration
            if (self.is_speaking and self.speech_start_time and 
                (current_time - self.speech_start_time) > self.max_speech_duration):
                
                self.get_logger().warning(f"Maximum speech duration exceeded, forcing segment end")
                if len(self.speech_buffer) > 0:
                    self.publish_speech_segment(self.speech_buffer, self.speech_start_time)
                
                self.is_speaking = False
                self.speech_buffer = []
                
        except Exception as e:
            self.get_logger().error(f"Speech segmentation error: {e}")

    def publish_raw_audio(self, audio_data: np.ndarray, timestamp: float):
        """Publish raw audio data."""
        try:
            audio_msg = Header()
            audio_msg.header = Header()
            audio_msg.header.stamp = self.get_clock().now().to_msg()
            audio_msg.header.frame_id = "audio_input"
            
            audio_msg.data = audio_data.tobytes()
            audio_msg.channels = self.channels
            audio_msg.sample_rate = self.sample_rate
            audio_msg.encoding = "float32"
            
            self.raw_audio_pub.publish(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Raw audio publishing error: {e}")

    def publish_processed_audio(self, audio_data: np.ndarray, timestamp: float):
        """Publish processed audio data."""
        try:
            audio_msg.header = Header()
            audio_msg.header.stamp = self.get_clock().now().to_msg()
            audio_msg.header.frame_id = "audio_processed"
            
            audio_msg.data = audio_data.tobytes()
            audio_msg.channels = self.channels
            audio_msg.sample_rate = self.sample_rate
            audio_msg.encoding = "float32"
            
            self.processed_audio_pub.publish(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Processed audio publishing error: {e}")

    def publish_speech_segment(self, speech_buffer: List[float], start_time: float):
        """Publish complete speech segment."""
        try:
            if not speech_buffer:
                return
            
            audio_array = np.array(speech_buffer, dtype=np.float32)
            
            audio_msg.header = Header()
            audio_msg.header.stamp = self.get_clock().now().to_msg()
            audio_msg.header.frame_id = "speech_segment"
            
            audio_msg.data = audio_array.tobytes()
            audio_msg.channels = self.channels
            audio_msg.sample_rate = self.sample_rate
            audio_msg.encoding = "float32"
            
            self.speech_segments_pub.publish(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Speech segment publishing error: {e}")

    def __del__(self):
        """Clean up when node is destroyed."""
        try:
            self.running = False
            
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            
            if hasattr(self, 'audio') and self.audio:
                self.audio.terminate()
                
        except Exception:
            pass


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = SileroVADNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Silero VAD Node error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()