#!/usr/bin/env python3
"""
Audio Processor Node for Elderly Companion Robdog.

Coordinates the audio processing pipeline: VAD -> ASR -> Emotion Detection -> Intent Classification.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import threading
import queue
import time
from typing import Optional, Dict, Any

# Audio processing imports
import torch
import torchaudio
import sounddevice as sd
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

# ROS2 message imports
from sensor_msgs.msg import Audio
from std_msgs.msg import Header
from elderly_companion.msg import SpeechResult, EmotionData, IntentResult
from elderly_companion.srv import ProcessSpeech


class AudioProcessorNode(Node):
    """
    Main audio processing node for the elderly companion robot.
    
    Handles continuous audio capture, VAD, and coordinates downstream processing.
    """

    def __init__(self):
        super().__init__('audio_processor_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('audio.sample_rate', 48000),
                ('audio.channels', 6),
                ('audio.chunk_size', 4800),  # 100ms at 48kHz
                ('audio.device_index', -1),  # Default device
                ('vad.threshold', 0.7),
                ('vad.min_silence_duration_ms', 300),
                ('vad.speech_pad_ms', 30),
                ('processing.max_audio_length_seconds', 30.0),
                ('processing.emergency_keywords', ['help', 'emergency', '救命', '急救']),
            ]
        )
        
        # Get parameters
        self.sample_rate = self.get_parameter('audio.sample_rate').value
        self.channels = self.get_parameter('audio.channels').value
        self.chunk_size = self.get_parameter('audio.chunk_size').value
        self.device_index = self.get_parameter('audio.device_index').value
        self.vad_threshold = self.get_parameter('vad.threshold').value
        self.emergency_keywords = self.get_parameter('processing.emergency_keywords').value
        
        # Initialize audio system
        self.audio_queue = queue.Queue(maxsize=100)
        self.is_recording = False
        self.current_speech_buffer = []
        
        # Initialize VAD model
        self.get_logger().info("Loading Silero VAD model...")
        self.vad_model = load_silero_vad()
        
        # QoS profiles
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Publishers
        self.raw_audio_pub = self.create_publisher(
            Audio, 
            '/audio/raw', 
            sensor_qos
        )
        
        self.speech_result_pub = self.create_publisher(
            SpeechResult,
            '/speech/result',
            10
        )
        
        # Services
        self.process_speech_service = self.create_service(
            ProcessSpeech,
            '/router_agent/process_speech',
            self.process_speech_callback
        )
        
        # Initialize audio stream
        self.start_audio_stream()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self.audio_processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.get_logger().info("Audio Processor Node initialized successfully")

    def start_audio_stream(self):
        """Initialize and start the audio input stream."""
        try:
            # Query available audio devices
            devices = sd.query_devices()
            self.get_logger().info(f"Available audio devices: {len(devices)}")
            
            # Use specified device or default
            device = self.device_index if self.device_index >= 0 else None
            
            # Start audio stream
            self.stream = sd.InputStream(
                channels=self.channels,
                samplerate=self.sample_rate,
                device=device,
                blocksize=self.chunk_size,
                callback=self.audio_callback,
                dtype=np.float32
            )
            
            self.stream.start()
            self.get_logger().info(f"Audio stream started: {self.sample_rate}Hz, {self.channels} channels")
            
        except Exception as e:
            self.get_logger().error(f"Failed to start audio stream: {e}")
            raise

    def audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Handle callback for audio stream - called for each audio chunk."""
        if status:
            self.get_logger().warning(f"Audio stream status: {status}")
        
        try:
            # Convert to mono for VAD (use first channel)
            mono_audio = indata[:, 0] if self.channels > 1 else indata.flatten()
            
            # Add to processing queue
            timestamp = self.get_clock().now()
            audio_data = {
                'data': mono_audio.copy(),
                'timestamp': timestamp,
                'frames': frames
            }
            
            if not self.audio_queue.full():
                self.audio_queue.put(audio_data)
            
            # Publish raw audio for debugging/monitoring
            self.publish_raw_audio(indata, timestamp)
            
        except Exception as e:
            self.get_logger().error(f"Error in audio callback: {e}")

    def publish_raw_audio(self, audio_data: np.ndarray, timestamp):
        """Publish raw audio data."""
        try:
            audio_msg = Audio()
            audio_msg.header = Header()
            audio_msg.header.stamp = timestamp.to_msg()
            audio_msg.header.frame_id = "audio_frame"
            
            # Convert to the format expected by Audio message
            audio_msg.data = audio_data.flatten().astype(np.float32).tobytes()
            
            self.raw_audio_pub.publish(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Failed to publish raw audio: {e}")

    def audio_processing_loop(self):
        """Run main audio processing loop in separate thread."""
        self.get_logger().info("Audio processing loop started")
        
        while rclpy.ok():
            try:
                # Get audio chunk with timeout
                audio_data = self.audio_queue.get(timeout=1.0)
                
                # Process with VAD
                self.process_vad(audio_data)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Error in audio processing loop: {e}")

    def process_vad(self, audio_data: Dict[str, Any]):
        """Process audio chunk with Voice Activity Detection."""
        try:
            audio_chunk = audio_data['data']
            timestamp = audio_data['timestamp']
            
            # Convert to tensor for Silero VAD
            audio_tensor = torch.from_numpy(audio_chunk)
            
            # Get VAD prediction
            speech_prob = self.vad_model(audio_tensor, self.sample_rate).item()
            
            # Check if speech is detected
            if speech_prob > self.vad_threshold:
                if not self.is_recording:
                    # Start of speech detected
                    self.is_recording = True
                    self.current_speech_buffer = [audio_chunk]
                    self.speech_start_time = timestamp
                    self.get_logger().debug("Speech start detected")
                else:
                    # Continue recording speech
                    self.current_speech_buffer.append(audio_chunk)
            else:
                if self.is_recording:
                    # End of speech detected
                    self.is_recording = False
                    self.process_complete_speech()
                    
        except Exception as e:
            self.get_logger().error(f"VAD processing error: {e}")

    def process_complete_speech(self):
        """Process complete speech segment."""
        try:
            if not self.current_speech_buffer:
                return
            
            # Concatenate speech chunks
            complete_speech = np.concatenate(self.current_speech_buffer)
            
            # Check for minimum speech duration (avoid processing very short sounds)
            duration = len(complete_speech) / self.sample_rate
            if duration < 0.5:  # Minimum 500ms
                self.get_logger().debug(f"Speech too short: {duration:.2f}s")
                return
            
            self.get_logger().info(f"Processing speech segment: {duration:.2f}s")
            
            # Create audio message for downstream processing
            audio_msg = Audio()
            audio_msg.header = Header()
            audio_msg.header.stamp = self.speech_start_time.to_msg()
            audio_msg.header.frame_id = "speech_frame"
            audio_msg.data = complete_speech.astype(np.float32).tobytes()
            
            # Call speech recognition service (will be implemented in speech_recognition_node.py)
            self.call_speech_recognition_service(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Complete speech processing error: {e}")
        finally:
            self.current_speech_buffer = []

    def call_speech_recognition_service(self, audio_msg: Audio):
        """Call the speech recognition service."""
        try:
            # This will be connected to the speech recognition node
            # For now, we'll create a placeholder result
            self.create_placeholder_speech_result(audio_msg)
            
        except Exception as e:
            self.get_logger().error(f"Speech recognition service call failed: {e}")

    def create_placeholder_speech_result(self, audio_msg: Audio):
        """Create a placeholder speech result for testing."""
        try:
            # Create basic speech result
            speech_result = SpeechResult()
            speech_result.header = audio_msg.header
            speech_result.text = "[Speech detected - recognition pending]"
            speech_result.confidence = 0.0
            speech_result.language = "zh-CN"
            speech_result.voice_activity_detected = True
            speech_result.audio_duration_seconds = len(audio_msg.data) / (4 * self.sample_rate)  # 4 bytes per float32
            speech_result.sample_rate = self.sample_rate
            
            # Create placeholder emotion data
            emotion_data = EmotionData()
            emotion_data.primary_emotion = "neutral"
            emotion_data.confidence = 0.0
            emotion_data.timestamp = self.get_clock().now().to_msg()
            emotion_data.elderly_specific_patterns_detected = False
            
            speech_result.emotion = emotion_data
            
            # Publish result
            self.speech_result_pub.publish(speech_result)
            self.get_logger().info("Published placeholder speech result")
            
        except Exception as e:
            self.get_logger().error(f"Failed to create placeholder result: {e}")

    def process_speech_callback(self, request, response):
        """Handle service callback for processing speech."""
        try:
            self.get_logger().info("Processing speech service called")
            
            # Extract audio data
            audio_data = np.frombuffer(request.audio_data.data, dtype=np.float32)
            
            # TODO: Implement actual speech processing
            # For now, return a placeholder response
            response.processing_successful = True
            response.processing_time_ms = 100.0
            response.audio_quality_score = 0.8
            response.voice_print_matched = False
            response.requires_clarification = False
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Process speech callback error: {e}")
            response.processing_successful = False
            response.error_message = str(e)
            return response

    def __del__(self):
        """Clean up when node is destroyed."""
        try:
            if hasattr(self, 'stream') and self.stream.active:
                self.stream.stop()
                self.stream.close()
        except:
            pass


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = AudioProcessorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()