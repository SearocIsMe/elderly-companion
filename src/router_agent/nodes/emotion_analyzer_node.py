#!/usr/bin/env python3
"""
Emotion Analyzer Node for Elderly Companion Robdog.

Analyzes emotional content from speech recognition results and audio features.
Specialized for elderly emotional patterns and health indicators.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import torch
import torch.nn.functional as F
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import librosa
import threading
import time
from typing import Optional, Dict, List, Tuple, Any
import json

# ROS2 message imports
from sensor_msgs.msg import Audio
from std_msgs.msg import Header
from elderly_companion.msg import SpeechResult, EmotionData


class EmotionAnalyzerNode(Node):
    """
    Emotion Analysis Node specialized for elderly care.
    
    Combines text-based emotion recognition with audio feature analysis
    to detect emotional states, stress levels, and health indicators.
    """

    def __init__(self):
        super().__init__('emotion_analyzer_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('emotion.model_path', '/models/emotion/chinese-bert'),
                ('emotion.audio_model_path', '/models/emotion/audio-features'),
                ('emotion.use_gpu', False),
                ('emotion.confidence_threshold', 0.6),
                ('elderly.health_indicators.enabled', True),
                ('elderly.stress_detection.enabled', True),
                ('elderly.loneliness_detection.enabled', True),
                ('audio.sample_rate', 16000),
                ('audio.n_mfcc', 13),
                ('audio.hop_length', 512),
                ('analysis.window_size', 5.0),  # seconds
            ]
        )
        
        # Get parameters
        self.model_path = self.get_parameter('emotion.model_path').value
        self.use_gpu = self.get_parameter('emotion.use_gpu').value
        self.confidence_threshold = self.get_parameter('emotion.confidence_threshold').value
        self.health_indicators_enabled = self.get_parameter('elderly.health_indicators.enabled').value
        self.stress_detection_enabled = self.get_parameter('elderly.stress_detection.enabled').value
        self.sample_rate = self.get_parameter('audio.sample_rate').value
        
        # Initialize emotion models
        self.get_logger().info("Loading emotion analysis models...")
        self.initialize_emotion_models()
        
        # Elderly-specific emotional patterns
        self.elderly_emotion_patterns = {
            'loneliness_indicators': [
                '孤独', '寂寞', '没人说话', '想念', '一个人', 'lonely', 'alone', 'miss'
            ],
            'pain_indicators': [
                '疼', '痛', '不舒服', '难受', '头晕', 'pain', 'hurt', 'ache', 'uncomfortable'
            ],
            'worry_indicators': [
                '担心', '害怕', '着急', '焦虑', 'worry', 'afraid', 'anxious', 'nervous'
            ],
            'happiness_indicators': [
                '开心', '高兴', '快乐', '满意', 'happy', 'glad', 'pleased', 'content'
            ],
            'confusion_indicators': [
                '糊涂', '不清楚', '忘记', '记不住', 'confused', 'forget', 'unclear'
            ]
        }
        
        # Audio feature cache for analysis
        self.audio_feature_cache = []
        self.max_cache_size = 10
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/recognized',
            self.analyze_speech_emotion_callback,
            default_qos
        )
        
        self.raw_audio_sub = self.create_subscription(
            Audio,
            '/audio/raw',
            self.analyze_audio_features_callback,
            default_qos
        )
        
        # Publishers
        self.emotion_result_pub = self.create_publisher(
            EmotionData,
            '/emotion/analysis',
            default_qos
        )
        
        self.enhanced_speech_result_pub = self.create_publisher(
            SpeechResult,
            '/speech/with_emotion',
            default_qos
        )
        
        self.get_logger().info("Emotion Analyzer Node initialized successfully")

    def initialize_emotion_models(self):
        """Initialize emotion analysis models."""
        try:
            # Initialize text-based emotion classifier
            self.get_logger().info("Loading text emotion classifier...")
            
            # Use a Chinese emotion classification model or multilingual model
            try:
                self.text_emotion_classifier = pipeline(
                    "text-classification",
                    model="j-hartmann/emotion-english-distilroberta-base",
                    device=0 if self.use_gpu else -1
                )
                self.get_logger().info("Text emotion classifier loaded successfully")
            except Exception as e:
                self.get_logger().warning(f"Failed to load advanced emotion model: {e}")
                self.text_emotion_classifier = None
            
            # Initialize audio feature analyzer
            self.initialize_audio_analyzer()
            
        except Exception as e:
            self.get_logger().error(f"Failed to initialize emotion models: {e}")
            self.text_emotion_classifier = None

    def initialize_audio_analyzer(self):
        """Initialize audio feature analysis components."""
        try:
            # Audio feature extraction parameters
            self.audio_params = {
                'sr': self.sample_rate,
                'n_mfcc': 13,
                'hop_length': 512,
                'n_fft': 2048
            }
            
            self.get_logger().info("Audio feature analyzer initialized")
            
        except Exception as e:
            self.get_logger().error(f"Audio analyzer initialization failed: {e}")

    def analyze_speech_emotion_callback(self, msg: SpeechResult):
        """Analyze emotion from speech recognition results."""
        try:
            self.get_logger().debug(f"Analyzing emotion for text: '{msg.text}'")
            
            # Perform text-based emotion analysis
            emotion_data = self.analyze_text_emotion(msg.text)
            
            # Enhance with elderly-specific patterns
            self.enhance_with_elderly_patterns(emotion_data, msg.text)
            
            # Add timing information
            emotion_data.timestamp = self.get_clock().now().to_msg()
            
            # Create enhanced speech result
            enhanced_result = SpeechResult()
            enhanced_result.header = msg.header
            enhanced_result.text = msg.text
            enhanced_result.confidence = msg.confidence
            enhanced_result.language = msg.language
            enhanced_result.emotion = emotion_data
            enhanced_result.voice_activity_detected = msg.voice_activity_detected
            enhanced_result.audio_duration_seconds = msg.audio_duration_seconds
            enhanced_result.sample_rate = msg.sample_rate
            enhanced_result.speaker_location = msg.speaker_location
            
            # Publish results
            self.emotion_result_pub.publish(emotion_data)
            self.enhanced_speech_result_pub.publish(enhanced_result)
            
            # Log significant emotional states
            if emotion_data.stress_level > 0.7:
                self.get_logger().warning(f"High stress detected: {emotion_data.stress_level:.2f}")
            if emotion_data.primary_emotion in ['sad', 'fear', 'anger']:
                self.get_logger().info(f"Negative emotion detected: {emotion_data.primary_emotion}")
            
        except Exception as e:
            self.get_logger().error(f"Speech emotion analysis error: {e}")

    def analyze_text_emotion(self, text: str) -> EmotionData:
        """Analyze emotion from text content."""
        emotion_data = EmotionData()
        
        try:
            if not text or len(text.strip()) < 2:
                emotion_data.primary_emotion = "neutral"
                emotion_data.confidence = 0.0
                return emotion_data
            
            if self.text_emotion_classifier:
                # Use transformer model for emotion classification
                results = self.text_emotion_classifier(text)
                
                if results and len(results) > 0:
                    top_result = results[0]
                    emotion_data.primary_emotion = top_result['label'].lower()
                    emotion_data.confidence = float(top_result['score'])
                    
                    # Map to elderly-care relevant emotions
                    emotion_data.primary_emotion = self.map_to_elderly_emotions(
                        emotion_data.primary_emotion
                    )
                else:
                    emotion_data.primary_emotion = "neutral"
                    emotion_data.confidence = 0.5
            else:
                # Fallback to pattern-based emotion detection
                emotion_data = self.pattern_based_emotion_analysis(text)
            
            # Calculate valence and arousal
            self.calculate_emotional_dimensions(emotion_data)
            
        except Exception as e:
            self.get_logger().error(f"Text emotion analysis error: {e}")
            emotion_data.primary_emotion = "neutral"
            emotion_data.confidence = 0.0
        
        return emotion_data

    def pattern_based_emotion_analysis(self, text: str) -> EmotionData:
        """Provide fallback pattern-based emotion analysis."""
        emotion_data = EmotionData()
        text_lower = text.lower()
        
        # Check for specific emotional patterns
        emotion_scores = {
            'happy': 0.0,
            'sad': 0.0,
            'angry': 0.0,
            'fear': 0.0,
            'surprised': 0.0,
            'neutral': 0.5
        }
        
        # Happiness patterns
        happy_patterns = ['开心', '高兴', '快乐', '好', '满意', 'happy', 'good', 'great', 'wonderful']
        for pattern in happy_patterns:
            if pattern in text_lower:
                emotion_scores['happy'] += 0.3
        
        # Sadness patterns
        sad_patterns = ['难过', '伤心', '痛苦', '失望', 'sad', 'hurt', 'disappointed', 'upset']
        for pattern in sad_patterns:
            if pattern in text_lower:
                emotion_scores['sad'] += 0.4
        
        # Fear/worry patterns
        fear_patterns = ['害怕', '担心', '焦虑', '紧张', 'afraid', 'worry', 'anxious', 'scared']
        for pattern in fear_patterns:
            if pattern in text_lower:
                emotion_scores['fear'] += 0.4
        
        # Anger patterns
        anger_patterns = ['生气', '愤怒', '烦躁', '不满', 'angry', 'mad', 'frustrated', 'annoyed']
        for pattern in anger_patterns:
            if pattern in text_lower:
                emotion_scores['angry'] += 0.4
        
        # Find dominant emotion
        max_emotion = max(emotion_scores.keys(), key=lambda k: emotion_scores[k])
        max_score = emotion_scores[max_emotion]
        
        emotion_data.primary_emotion = max_emotion
        emotion_data.confidence = min(max_score, 1.0)
        
        return emotion_data

    def map_to_elderly_emotions(self, emotion: str) -> str:
        """Map general emotions to elderly-care specific categories."""
        emotion_mapping = {
            'joy': 'happy',
            'happiness': 'happy',
            'sadness': 'sad',
            'fear': 'concerned',
            'anger': 'frustrated',
            'surprise': 'surprised',
            'disgust': 'uncomfortable',
            'neutral': 'neutral'
        }
        
        return emotion_mapping.get(emotion, emotion)

    def enhance_with_elderly_patterns(self, emotion_data: EmotionData, text: str):
        """Enhance emotion analysis with elderly-specific patterns."""
        try:
            text_lower = text.lower()
            
            # Check for loneliness indicators
            loneliness_score = 0.0
            for indicator in self.elderly_emotion_patterns['loneliness_indicators']:
                if indicator in text_lower:
                    loneliness_score += 0.3
            
            # Check for pain/discomfort indicators
            pain_score = 0.0
            for indicator in self.elderly_emotion_patterns['pain_indicators']:
                if indicator in text_lower:
                    pain_score += 0.4
            
            # Check for worry indicators
            worry_score = 0.0
            for indicator in self.elderly_emotion_patterns['worry_indicators']:
                if indicator in text_lower:
                    worry_score += 0.3
            
            # Check for confusion indicators
            confusion_score = 0.0
            for indicator in self.elderly_emotion_patterns['confusion_indicators']:
                if indicator in text_lower:
                    confusion_score += 0.4
            
            # Update emotion data based on elderly patterns
            emotion_data.elderly_specific_patterns_detected = (
                loneliness_score > 0 or pain_score > 0 or 
                worry_score > 0 or confusion_score > 0
            )
            
            # Adjust stress level based on detected patterns
            stress_factors = pain_score + worry_score + confusion_score
            emotion_data.stress_level = min(stress_factors, 1.0)
            
            # Add detected keywords
            detected_keywords = []
            if loneliness_score > 0:
                detected_keywords.append("loneliness_indicators")
            if pain_score > 0:
                detected_keywords.append("pain_indicators")
            if worry_score > 0:
                detected_keywords.append("worry_indicators")
            if confusion_score > 0:
                detected_keywords.append("confusion_indicators")
            
            emotion_data.detected_keywords = detected_keywords
            
            # Override primary emotion if strong elderly patterns detected
            if pain_score > 0.4:
                emotion_data.primary_emotion = "uncomfortable"
                emotion_data.confidence = max(emotion_data.confidence, pain_score)
            elif loneliness_score > 0.3:
                emotion_data.primary_emotion = "lonely"
                emotion_data.confidence = max(emotion_data.confidence, loneliness_score)
            elif confusion_score > 0.4:
                emotion_data.primary_emotion = "confused"
                emotion_data.confidence = max(emotion_data.confidence, confusion_score)
            
        except Exception as e:
            self.get_logger().error(f"Elderly pattern enhancement error: {e}")

    def calculate_emotional_dimensions(self, emotion_data: EmotionData):
        """Calculate valence and arousal dimensions."""
        try:
            emotion = emotion_data.primary_emotion
            
            # Valence scale: -1.0 (negative) to 1.0 (positive)
            # Arousal scale: 0.0 (calm) to 1.0 (excited)
            
            emotion_dimensions = {
                'happy': {'valence': 0.8, 'arousal': 0.6},
                'sad': {'valence': -0.6, 'arousal': 0.3},
                'angry': {'valence': -0.7, 'arousal': 0.8},
                'fear': {'valence': -0.8, 'arousal': 0.7},
                'concerned': {'valence': -0.4, 'arousal': 0.6},
                'surprised': {'valence': 0.1, 'arousal': 0.8},
                'neutral': {'valence': 0.0, 'arousal': 0.3},
                'uncomfortable': {'valence': -0.6, 'arousal': 0.5},
                'lonely': {'valence': -0.7, 'arousal': 0.2},
                'confused': {'valence': -0.3, 'arousal': 0.4},
                'frustrated': {'valence': -0.5, 'arousal': 0.7}
            }
            
            dimensions = emotion_dimensions.get(emotion, {'valence': 0.0, 'arousal': 0.3})
            emotion_data.valence = dimensions['valence']
            emotion_data.arousal = dimensions['arousal']
            
        except Exception as e:
            self.get_logger().error(f"Emotional dimension calculation error: {e}")
            emotion_data.valence = 0.0
            emotion_data.arousal = 0.3

    def analyze_audio_features_callback(self, msg: Audio):
        """Analyze emotion from audio features."""
        try:
            # Extract audio data
            audio_data = np.frombuffer(msg.data, dtype=np.float32)
            
            if len(audio_data) < self.sample_rate * 0.5:  # Minimum 0.5 seconds
                return
            
            # Extract audio features for emotion analysis
            features = self.extract_audio_emotion_features(audio_data)
            
            # Add to cache for temporal analysis
            self.audio_feature_cache.append({
                'features': features,
                'timestamp': self.get_clock().now()
            })
            
            # Maintain cache size
            if len(self.audio_feature_cache) > self.max_cache_size:
                self.audio_feature_cache.pop(0)
            
        except Exception as e:
            self.get_logger().error(f"Audio feature analysis error: {e}")

    def extract_audio_emotion_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract emotion-relevant features from audio."""
        try:
            features = {}
            
            # Basic acoustic features
            features['rms_energy'] = float(np.sqrt(np.mean(audio_data**2)))
            features['zero_crossing_rate'] = float(np.mean(librosa.feature.zero_crossing_rate(audio_data)))
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)
            features['spectral_centroid'] = float(np.mean(spectral_centroids))
            
            # MFCC features
            mfccs = librosa.feature.mfcc(y=audio_data, sr=self.sample_rate, n_mfcc=13)
            features['mfcc_mean'] = float(np.mean(mfccs))
            features['mfcc_std'] = float(np.std(mfccs))
            
            # Pitch-related features
            try:
                pitches, magnitudes = librosa.piptrack(y=audio_data, sr=self.sample_rate)
                pitch_values = pitches[magnitudes > np.median(magnitudes)]
                if len(pitch_values) > 0:
                    features['pitch_mean'] = float(np.mean(pitch_values))
                    features['pitch_std'] = float(np.std(pitch_values))
                else:
                    features['pitch_mean'] = 0.0
                    features['pitch_std'] = 0.0
            except:
                features['pitch_mean'] = 0.0
                features['pitch_std'] = 0.0
            
            return features
            
        except Exception as e:
            self.get_logger().error(f"Audio feature extraction error: {e}")
            return {}


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = EmotionAnalyzerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()