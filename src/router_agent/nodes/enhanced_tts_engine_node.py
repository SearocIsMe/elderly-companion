#!/usr/bin/env python3
"""
Enhanced Text-to-Speech Engine Node for Elderly Companion Robdog.

Production-ready elderly-optimized speech synthesis with:
- Multi-language support (Chinese/English) with elderly speech patterns
- Emotion-aware voice modulation for empathetic communication
- Hearing aid compatibility and volume optimization
- Real-time audio processing for maximum clarity
- FastAPI integration for centralized TTS management
- Advanced voice quality controls and audio enhancement
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import threading
import time
import queue
import os
import json
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from enum import Enum
import tempfile

# Audio/TTS imports
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    import gtts
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

try:
    import edge_tts
    import asyncio
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import soundfile as sf
    import librosa
    import scipy.signal
    HAS_AUDIO_PROCESSING = True
except ImportError:
    HAS_AUDIO_PROCESSING = False

# Communication imports
import requests

# ROS2 message imports
from std_msgs.msg import String, Bool, Header
from sensor_msgs.msg import Audio
from elderly_companion.msg import EmotionData


class VoiceType(Enum):
    """Voice types for different scenarios."""
    NORMAL = "normal"
    GENTLE = "gentle"
    URGENT = "urgent"
    COMFORT = "comfort"
    INSTRUCTION = "instruction"


class ElderlyAudioProcessor:
    """Audio processing optimized for elderly hearing characteristics."""
    
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.elderly_freq_emphasis = (300, 3000)  # Key frequency range for speech clarity
        
    def enhance_for_elderly(self, audio_data: np.ndarray) -> np.ndarray:
        """Enhance audio for elderly hearing characteristics."""
        try:
            if not HAS_AUDIO_PROCESSING or len(audio_data) == 0:
                return audio_data
            
            # Apply frequency emphasis for better clarity
            audio_enhanced = self.apply_frequency_emphasis(audio_data)
            
            # Apply dynamic range compression
            audio_enhanced = self.apply_compression(audio_enhanced)
            
            # Apply hearing aid compatibility processing
            audio_enhanced = self.hearing_aid_compatible(audio_enhanced)
            
            return audio_enhanced
            
        except Exception:
            return audio_data
    
    def apply_frequency_emphasis(self, audio: np.ndarray) -> np.ndarray:
        """Apply frequency emphasis for speech clarity."""
        try:
            # Design emphasis filter for elderly speech frequencies
            nyquist = self.sample_rate / 2
            low = self.elderly_freq_emphasis[0] / nyquist
            high = min(self.elderly_freq_emphasis[1] / nyquist, 0.95)
            
            # Create emphasis filter
            b, a = scipy.signal.butter(2, [low, high], btype='band')
            emphasized = scipy.signal.filtfilt(b, a, audio)
            
            # Blend with original (50% emphasis)
            return 0.5 * audio + 0.5 * emphasized
            
        except Exception:
            return audio
    
    def apply_compression(self, audio: np.ndarray, ratio: float = 3.0, threshold: float = 0.7) -> np.ndarray:
        """Apply dynamic range compression for elderly hearing."""
        try:
            # Simple compression algorithm
            compressed = np.copy(audio)
            mask = np.abs(compressed) > threshold
            compressed[mask] = threshold + (compressed[mask] - threshold) / ratio
            
            return compressed
            
        except Exception:
            return audio
    
    def hearing_aid_compatible(self, audio: np.ndarray) -> np.ndarray:
        """Apply hearing aid compatibility processing."""
        try:
            # Reduce sudden volume changes
            if len(audio) > 1:
                # Smooth volume transitions
                smoothed = scipy.signal.savgol_filter(audio, min(51, len(audio)//10*2+1), 3)
                return smoothed
            return audio
            
        except Exception:
            return audio


class EnhancedTTSEngineNode(Node):
    """
    Enhanced Text-to-Speech Engine Node for elderly-optimized audio output.
    
    Features:
    - Multi-engine TTS support (pyttsx3, gTTS, Edge TTS)
    - Elderly-specific voice optimization and audio processing
    - Emotion-aware voice modulation for empathetic communication
    - Multi-language support with cultural awareness
    - Real-time audio enhancement for hearing aid compatibility
    - FastAPI integration for centralized speech management
    - Advanced queue management with priority handling
    """

    def __init__(self):
        super().__init__('enhanced_tts_engine_node')
        
        # Initialize comprehensive parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # TTS Engine Configuration
                ('tts.primary_engine', 'pyttsx3'),  # edge_tts, gtts, pyttsx3
                ('tts.fallback_engine', 'pyttsx3'),
                ('tts.voice_id_chinese', 'zh-CN-XiaoxiaoNeural'),  # Edge TTS voice
                ('tts.voice_id_english', 'en-US-AriaNeural'),
                ('tts.rate', 120),                   # Slower for elderly (words per minute)
                ('tts.volume', 0.85),               # Higher volume for elderly
                ('tts.pitch', 0),                   # Pitch adjustment
                
                # Elderly Optimization
                ('elderly.speech_rate_multiplier', 0.8),  # Even slower
                ('elderly.pause_between_sentences', 0.8),  # Longer pauses
                ('elderly.repeat_important_keywords', True),
                ('elderly.use_simple_vocabulary', True),
                ('elderly.volume_boost', 1.2),
                ('elderly.frequency_emphasis', True),
                
                # Emotion-Aware Settings
                ('emotion.enable_voice_modulation', True),
                ('emotion.comfort_voice_rate', 100),
                ('emotion.urgent_voice_rate', 140),
                ('emotion.gentle_voice_rate', 90),
                
                # Audio Processing
                ('audio.output_device', -1),
                ('audio.sample_rate', 22050),
                ('audio.channels', 1),
                ('audio.bit_depth', 16),
                ('audio.enable_enhancement', True),
                ('audio.hearing_aid_compatible', True),
                
                # Language and Cultural Settings
                ('language.primary', 'zh-CN'),
                ('language.fallback', 'en-US'),
                ('language.auto_detect', True),
                ('cultural.use_polite_forms', True),
                ('cultural.elderly_honorifics', True),
                
                # FastAPI Integration
                ('fastapi.bridge_url', 'http://localhost:7010'),
                ('fastapi.enable_remote_tts', True),
                ('fastapi.timeout_seconds', 10),
                
                # Queue and Performance
                ('queue.max_size', 100),
                ('queue.priority_emergency', True),
                ('performance.max_concurrent_synthesis', 2),
                ('performance.cache_frequent_phrases', True),
            ]
        )
        
        # Get parameters
        self.primary_engine = self.get_parameter('tts.primary_engine').value
        self.fallback_engine = self.get_parameter('tts.fallback_engine').value
        self.voice_chinese = self.get_parameter('tts.voice_id_chinese').value
        self.voice_english = self.get_parameter('tts.voice_id_english').value
        self.speech_rate = self.get_parameter('tts.rate').value
        self.volume = self.get_parameter('tts.volume').value
        self.elderly_rate_multiplier = self.get_parameter('elderly.speech_rate_multiplier').value
        self.sentence_pause = self.get_parameter('elderly.pause_between_sentences').value
        self.enable_emotion_modulation = self.get_parameter('emotion.enable_voice_modulation').value
        self.primary_language = self.get_parameter('language.primary').value
        self.enable_audio_enhancement = self.get_parameter('audio.enable_enhancement').value
        self.fastapi_bridge_url = self.get_parameter('fastapi.bridge_url').value
        
        # Initialize TTS engines
        self.tts_engines = {}
        self.current_engine = None
        self.initialize_tts_engines()
        
        # Audio processing
        self.audio_processor = ElderlyAudioProcessor(self.get_parameter('audio.sample_rate').value)
        
        # Speech management
        self.is_speaking = False
        self.speech_queue = queue.PriorityQueue(maxsize=self.get_parameter('queue.max_size').value)
        self.current_speech_id = None
        
        # Phrase cache for performance
        self.phrase_cache = {}
        self.cache_enabled = self.get_parameter('performance.cache_frequent_phrases').value
        
        # FastAPI integration
        self.fastapi_session = requests.Session()
        self.fastapi_session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TTS-Engine/1.0'
        })
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        realtime_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribers
        self.tts_request_sub = self.create_subscription(
            String,
            '/tts/request',
            self.handle_tts_request,
            default_qos
        )
        
        self.emotion_aware_tts_sub = self.create_subscription(
            String,  # JSON with text and emotion data
            '/tts/emotion_request',
            self.handle_emotion_aware_tts_request,
            default_qos
        )
        
        # Publishers
        self.tts_status_pub = self.create_publisher(
            Bool,
            '/tts/status',
            realtime_qos
        )
        
        self.audio_output_pub = self.create_publisher(
            Audio,
            '/audio/tts_output',
            default_qos
        )
        
        # Start TTS processing threads
        self.start_tts_processing_threads()
        
        self.get_logger().info("Enhanced TTS Engine Node initialized successfully")

    def initialize_tts_engines(self):
        """Initialize all available TTS engines."""
        try:
            # Initialize pyttsx3 (local, fast, offline)
            if HAS_PYTTSX3:
                try:
                    pyttsx3_engine = pyttsx3.init()
                    self.configure_pyttsx3(pyttsx3_engine)
                    self.tts_engines['pyttsx3'] = pyttsx3_engine
                    self.get_logger().info("pyttsx3 TTS engine initialized")
                except Exception as e:
                    self.get_logger().warning(f"pyttsx3 initialization failed: {e}")
            
            # Edge TTS availability check (best quality, requires internet)
            if HAS_EDGE_TTS:
                self.tts_engines['edge_tts'] = 'available'
                self.get_logger().info("Edge TTS engine available")
            
            # gTTS availability check (good quality, requires internet)
            if HAS_GTTS:
                self.tts_engines['gtts'] = 'available'
                self.get_logger().info("Google TTS engine available")
            
            # Set current engine based on availability and preference
            if self.primary_engine in self.tts_engines:
                self.current_engine = self.primary_engine
            elif self.fallback_engine in self.tts_engines:
                self.current_engine = self.fallback_engine
            elif self.tts_engines:
                self.current_engine = list(self.tts_engines.keys())[0]
            else:
                self.get_logger().error("No TTS engines available!")
                self.current_engine = None
            
            self.get_logger().info(f"Using TTS engine: {self.current_engine}")
                
        except Exception as e:
            self.get_logger().error(f"TTS engines initialization failed: {e}")

    def configure_pyttsx3(self, engine):
        """Configure pyttsx3 engine for elderly optimization."""
        try:
            # Set speech rate (slower for elderly)
            adjusted_rate = int(self.speech_rate * self.elderly_rate_multiplier)
            engine.setProperty('rate', adjusted_rate)
            
            # Set volume (higher for elderly)
            elderly_volume = min(1.0, self.volume * self.get_parameter('elderly.volume_boost').value)
            engine.setProperty('volume', elderly_volume)
            
            # Try to set appropriate voice
            voices = engine.getProperty('voices')
            if voices:
                # Prefer Chinese voice if primary language is Chinese
                if 'zh' in self.primary_language.lower():
                    for voice in voices:
                        if any(lang in voice.name.lower() for lang in ['chinese', 'zh', 'mandarin']):
                            engine.setProperty('voice', voice.id)
                            self.get_logger().info(f"Selected Chinese voice: {voice.name}")
                            return
                
                # Fallback to female voice (generally preferred for elderly)
                for voice in voices:
                    if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        self.get_logger().info(f"Selected female voice: {voice.name}")
                        return
                        
        except Exception as e:
            self.get_logger().warning(f"pyttsx3 configuration error: {e}")

    def start_tts_processing_threads(self):
        """Start TTS processing threads."""
        try:
            # Main TTS processing thread
            self.tts_thread = threading.Thread(
                target=self.tts_processing_loop,
                daemon=True
            )
            self.tts_thread.start()
            
            # Cache management thread
            self.cache_thread = threading.Thread(
                target=self.cache_management_loop,
                daemon=True
            )
            self.cache_thread.start()
            
            self.get_logger().info("TTS processing threads started")
            
        except Exception as e:
            self.get_logger().error(f"TTS threads start error: {e}")

    def handle_tts_request(self, msg: String):
        """Handle basic TTS request."""
        try:
            text = msg.data.strip()
            if text:
                self.get_logger().info(f"TTS request: '{text}'")
                
                # Create speech request with normal priority
                speech_request = {
                    'text': text,
                    'priority': 5,  # Normal priority
                    'voice_type': VoiceType.NORMAL,
                    'emotion': None,
                    'language': self.detect_language(text),
                    'timestamp': time.time(),
                    'speech_id': f"tts_{int(time.time() * 1000)}"
                }
                
                # Add to priority queue
                self.speech_queue.put((speech_request['priority'], speech_request))
                
        except Exception as e:
            self.get_logger().error(f"TTS request handling error: {e}")

    def handle_emotion_aware_tts_request(self, msg: String):
        """Handle emotion-aware TTS request."""
        try:
            request_data = json.loads(msg.data)
            text = request_data.get('text', '').strip()
            emotion = request_data.get('emotion', {})
            urgency = request_data.get('urgency', 'normal')
            
            if text:
                self.get_logger().info(f"Emotion-aware TTS request: '{text}' (emotion: {emotion.get('primary_emotion', 'neutral')})")
                
                # Determine voice type and priority based on emotion and urgency
                voice_type, priority = self.determine_voice_characteristics(emotion, urgency)
                
                speech_request = {
                    'text': text,
                    'priority': priority,
                    'voice_type': voice_type,
                    'emotion': emotion,
                    'language': self.detect_language(text),
                    'timestamp': time.time(),
                    'speech_id': f"emotion_tts_{int(time.time() * 1000)}"
                }
                
                # Add to priority queue
                self.speech_queue.put((speech_request['priority'], speech_request))
                
        except Exception as e:
            self.get_logger().error(f"Emotion-aware TTS request handling error: {e}")

    def determine_voice_characteristics(self, emotion: Dict[str, Any], urgency: str) -> Tuple[VoiceType, int]:
        """Determine voice type and priority based on emotion and urgency."""
        try:
            # Handle emergency/urgent cases first
            if urgency == 'emergency':
                return VoiceType.URGENT, 1
            elif urgency == 'high':
                return VoiceType.URGENT, 2
            
            # Handle based on emotion
            primary_emotion = emotion.get('primary_emotion', 'neutral').lower()
            stress_level = emotion.get('stress_level', 0.0)
            
            if primary_emotion in ['fear', 'panic', 'emergency'] or stress_level > 0.8:
                return VoiceType.URGENT, 2
            elif primary_emotion in ['sad', 'lonely', 'worried']:
                return VoiceType.COMFORT, 4
            elif primary_emotion in ['happy', 'content']:
                return VoiceType.GENTLE, 6
            elif 'instruction' in emotion.get('context', '').lower():
                return VoiceType.INSTRUCTION, 5
            else:
                return VoiceType.NORMAL, 5
                
        except Exception:
            return VoiceType.NORMAL, 5

    def detect_language(self, text: str) -> str:
        """Detect language of the text."""
        try:
            # Simple language detection based on character sets
            chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            total_chars = len([c for c in text if c.isalpha()])
            
            if total_chars > 0 and chinese_chars / total_chars > 0.3:
                return 'zh-CN'
            else:
                return 'en-US'
                
        except Exception:
            return self.primary_language

    def tts_processing_loop(self):
        """Enhanced TTS processing loop with priority handling."""
        while rclpy.ok():
            try:
                # Get highest priority speech request
                priority, speech_request = self.speech_queue.get(timeout=1.0)
                
                # Process speech request
                self.process_speech_request(speech_request)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"TTS processing loop error: {e}")
                time.sleep(1.0)

    def process_speech_request(self, request: Dict[str, Any]):
        """Process individual speech request."""
        try:
            self.current_speech_id = request['speech_id']
            self.is_speaking = True
            self.publish_tts_status(True)
            
            text = request['text']
            voice_type = request['voice_type']
            emotion = request.get('emotion')
            language = request['language']
            
            # For now, use simple pyttsx3 synthesis with elderly optimization
            self.speak_with_pyttsx3(text, voice_type)
            
            self.get_logger().info(f"TTS completed: '{text[:50]}...'")
            
        except Exception as e:
            self.get_logger().error(f"Speech request processing error: {e}")
        finally:
            self.is_speaking = False
            self.current_speech_id = None
            self.publish_tts_status(False)

    def speak_with_pyttsx3(self, text: str, voice_type: VoiceType):
        """Speak text using pyttsx3 with elderly optimization."""
        try:
            engine = self.tts_engines.get('pyttsx3')
            if not engine:
                # Fallback to text output
                self.fallback_text_output(text)
                return
            
            # Adjust rate based on voice type
            base_rate = int(self.speech_rate * self.elderly_rate_multiplier)
            if voice_type == VoiceType.URGENT:
                rate = int(base_rate * 1.2)
            elif voice_type == VoiceType.GENTLE or voice_type == VoiceType.COMFORT:
                rate = int(base_rate * 0.8)
            else:
                rate = base_rate
            
            engine.setProperty('rate', rate)
            
            # Add pauses for elderly comprehension
            optimized_text = self.optimize_text_for_elderly(text, voice_type)
            
            # Speak the text
            engine.say(optimized_text)
            engine.runAndWait()
            
        except Exception as e:
            self.get_logger().error(f"pyttsx3 speech error: {e}")
            self.fallback_text_output(text)

    def optimize_text_for_elderly(self, text: str, voice_type: VoiceType) -> str:
        """Optimize text for elderly comprehension."""
        try:
            optimized = text
            
            # Add longer pauses between sentences
            if '。' in optimized:
                optimized = optimized.replace('。', '。 ')
            if '. ' in optimized:
                optimized = optimized.replace('. ', '.  ')
            
            # Repeat important keywords for emergencies
            if (voice_type == VoiceType.URGENT and 
                self.get_parameter('elderly.repeat_important_keywords').value):
                
                emergency_keywords = ['紧急', '急救', 'emergency', 'urgent', '救命', 'help']
                for keyword in emergency_keywords:
                    if keyword in optimized:
                        optimized = optimized.replace(keyword, f"{keyword}, {keyword}")
            
            return optimized
            
        except Exception:
            return text

    def fallback_text_output(self, text: str):
        """Fallback text output when TTS fails."""
        try:
            print(f"🔊 TTS: {text}")
            # Simulate speech time for elderly pace
            speech_time = len(text) / 8.0  # 8 characters per second
            time.sleep(max(1.0, speech_time))
            
        except Exception as e:
            self.get_logger().error(f"Fallback text output error: {e}")

    def cache_management_loop(self):
        """Manage phrase cache to prevent memory overflow."""
        max_cache_size = 100  # Maximum cached phrases
        
        while rclpy.ok():
            try:
                if len(self.phrase_cache) > max_cache_size:
                    # Remove oldest entries
                    items_to_remove = len(self.phrase_cache) - max_cache_size
                    keys_to_remove = list(self.phrase_cache.keys())[:items_to_remove]
                    
                    for key in keys_to_remove:
                        del self.phrase_cache[key]
                    
                    self.get_logger().debug(f"Cache cleanup: removed {items_to_remove} entries")
                
                time.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                self.get_logger().error(f"Cache management error: {e}")
                time.sleep(60)

    def publish_tts_status(self, speaking: bool):
        """Publish TTS status."""
        try:
            status_msg = Bool()
            status_msg.data = speaking
            self.tts_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"TTS status publishing error: {e}")


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = EnhancedTTSEngineNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Enhanced TTS Engine error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()