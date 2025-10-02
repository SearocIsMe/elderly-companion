#!/usr/bin/env python3
"""
Enhanced Safety/Privacy Guard Engine for Elderly Companion Robdog.

Advanced Guard system with:
- Wakeword Detection with elderly speech adaptation
- GeoFence Security Monitor with behavioral analysis
- SOS Keywords Detection with multilingual support
- Implicit Command Recognition with contextual memory
- Privacy Protection Layer
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import threading
import time
import json
import math
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict

# ROS2 message imports
from std_msgs.msg import Header, String
from geometry_msgs.msg import Point, Pose
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult, HealthStatus, 
    EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ValidateIntent

# AI/ML imports
try:
    import torch
    import torch.nn as nn
    import torchaudio
    from transformers import pipeline
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False


class WakewordType(Enum):
    """Types of wakewords detected."""
    PRIMARY = "primary"           # 小伴, robot, companion
    EMERGENCY = "emergency"       # 救命, help, 紧急
    ATTENTION = "attention"       # 听着, listen, 注意
    IMPLICIT = "implicit"         # Context-derived attention


class GeofenceStatus(Enum):
    """Geofence status levels."""
    SAFE = "safe"
    WARNING = "warning"
    VIOLATION = "violation"
    EMERGENCY = "emergency"


class SOSCategory(Enum):
    """SOS detection categories."""
    EXPLICIT = "explicit"         # Direct SOS calls
    MEDICAL = "medical"          # Medical distress
    FALL = "fall"                # Fall detection
    CONFUSION = "confusion"      # Cognitive distress
    EMOTIONAL = "emotional"      # Emotional distress


@dataclass
class WakewordResult:
    """Wakeword detection result."""
    detected: bool
    wake_type: WakewordType
    confidence: float
    keyword: str
    timestamp: datetime
    speech_clarity: float
    elderly_adaptation_applied: bool


@dataclass
class GeofenceEvent:
    """Geofence monitoring event."""
    timestamp: datetime
    person_location: Point
    robot_location: Point
    zone_id: str
    status: GeofenceStatus
    behavior_anomaly_score: float
    duration_seconds: float
    

@dataclass
class SOSEvent:
    """SOS detection event."""
    timestamp: datetime
    category: SOSCategory
    confidence: float
    keywords: List[str]
    emotional_indicators: Dict[str, float]
    contextual_clues: List[str]
    urgency_level: int  # 1-4


@dataclass
class ImplicitCommand:
    """Implicit command recognition result."""
    command_type: str
    confidence: float
    context_window: List[str]
    emotional_trigger: str
    inferred_parameters: Dict[str, Any]
    requires_confirmation: bool


@dataclass
class ConversationMemory:
    """Episodic conversation memory."""
    conversation_id: str
    interactions: deque = field(default_factory=lambda: deque(maxlen=50))
    emotion_timeline: List[Tuple[datetime, str]] = field(default_factory=list)
    topic_evolution: List[str] = field(default_factory=list)
    behavioral_patterns: Dict[str, Any] = field(default_factory=dict)
    safety_incidents: List[str] = field(default_factory=list)


class EnhancedWakewordEngine:
    """Enhanced wakeword detection with elderly speech adaptation."""
    
    def __init__(self, logger):
        self.logger = logger
        self.wake_patterns = {
            WakewordType.PRIMARY: {
                'chinese': ['小伴', '机器人', '小机器人', '伴侣'],
                'english': ['companion', 'robot', 'buddy', 'helper'],
                'mixed': ['小robot', 'companion伴']
            },
            WakewordType.EMERGENCY: {
                'chinese': ['救命', '救我', '帮帮我', '紧急情况'],
                'english': ['help', 'emergency', 'urgent', 'crisis'],
                'distress': ['sos', 'mayday', '急救']
            },
            WakewordType.ATTENTION: {
                'chinese': ['听着', '注意', '看这里', '专心'],
                'english': ['listen', 'attention', 'focus', 'hear me'],
                'gentle': ['请听', 'please listen', '麻烦你']
            }
        }
        
        self.confidence_thresholds = {
            WakewordType.PRIMARY: 0.85,
            WakewordType.EMERGENCY: 0.75,  # Lower threshold for emergencies
            WakewordType.ATTENTION: 0.80
        }
        
        # Elderly speech adaptation parameters
        self.elderly_adaptations = {
            'clarity_compensation': 0.15,     # Reduce threshold for unclear speech
            'pace_tolerance': 0.2,            # Allow slower speech patterns
            'volume_normalization': True,     # Normalize for hearing aids
            'frequency_adjustment': True      # Adjust for age-related frequency loss
        }
        
        # Initialize models
        self.initialize_detection_models()
    
    def initialize_detection_models(self):
        """Initialize wakeword detection models."""
        try:
            if TORCH_AVAILABLE:
                # Load elderly-optimized wakeword model
                self.wakeword_model = self.load_elderly_wakeword_model()
                self.speech_clarity_estimator = self.load_clarity_model()
            else:
                self.logger.warning("PyTorch not available, using pattern matching")
                self.wakeword_model = None
                self.speech_clarity_estimator = None
                
        except Exception as e:
            self.logger.error(f"Wakeword model initialization error: {e}")
            self.wakeword_model = None
    
    def load_elderly_wakeword_model(self):
        """Load elderly-optimized wakeword detection model."""
        # In production, this would load an RKNPU-optimized model
        # For development, return mock model
        return None
    
    def load_clarity_model(self):
        """Load speech clarity estimation model."""
        # Speech clarity model for elderly adaptation
        return None
    
    def detect_wakeword(self, audio_data: np.ndarray, text: str, emotion: EmotionData) -> WakewordResult:
        """Detect wakewords with elderly speech adaptation."""
        try:
            text_lower = text.lower()
            best_match = None
            best_confidence = 0.0
            best_type = WakewordType.PRIMARY
            
            # Check all wakeword types
            for wake_type, patterns in self.wake_patterns.items():
                for lang_patterns in patterns.values():
                    for pattern in lang_patterns:
                        if pattern in text_lower:
                            # Calculate base confidence
                            confidence = self.calculate_pattern_confidence(pattern, text_lower)
                            
                            # Apply elderly adaptations
                            adapted_confidence = self.apply_elderly_adaptations(
                                confidence, audio_data, emotion
                            )
                            
                            if adapted_confidence > best_confidence:
                                best_confidence = adapted_confidence
                                best_match = pattern
                                best_type = wake_type
            
            # Check if confidence meets threshold
            threshold = self.confidence_thresholds.get(best_type, 0.85)
            detected = best_confidence >= threshold
            
            # Estimate speech clarity
            clarity_score = self.estimate_speech_clarity(audio_data, text)
            
            return WakewordResult(
                detected=detected,
                wake_type=best_type,
                confidence=best_confidence,
                keyword=best_match or "",
                timestamp=datetime.now(),
                speech_clarity=clarity_score,
                elderly_adaptation_applied=True
            )
            
        except Exception as e:
            self.logger.error(f"Wakeword detection error: {e}")
            return WakewordResult(
                detected=False,
                wake_type=WakewordType.PRIMARY,
                confidence=0.0,
                keyword="",
                timestamp=datetime.now(),
                speech_clarity=0.0,
                elderly_adaptation_applied=False
            )
    
    def calculate_pattern_confidence(self, pattern: str, text: str) -> float:
        """Calculate pattern matching confidence."""
        # Simple implementation - in production would use more sophisticated matching
        if pattern in text:
            # Exact match gets high confidence
            return 0.9
        
        # Fuzzy matching for partial matches
        pattern_words = pattern.split()
        text_words = text.split()
        matches = sum(1 for word in pattern_words if word in text_words)
        return (matches / len(pattern_words)) * 0.8
    
    def apply_elderly_adaptations(self, base_confidence: float, audio_data: np.ndarray, emotion: EmotionData) -> float:
        """Apply elderly-specific adaptations to confidence score."""
        adapted_confidence = base_confidence
        
        # Clarity compensation
        if emotion.voice_quality_score < 0.7:
            adapted_confidence += self.elderly_adaptations['clarity_compensation']
        
        # Stress level consideration
        if emotion.stress_level > 0.6:
            adapted_confidence += 0.1  # Boost confidence for stressed speech
        
        # Volume normalization consideration
        if audio_data is not None and len(audio_data) > 0:
            volume_level = np.mean(np.abs(audio_data))
            if volume_level < 0.1:  # Very quiet speech
                adapted_confidence += 0.1
        
        return min(adapted_confidence, 1.0)
    
    def estimate_speech_clarity(self, audio_data: np.ndarray, text: str) -> float:
        """Estimate speech clarity for elderly adaptation."""
        try:
            if audio_data is None or len(audio_data) == 0:
                return 0.5  # Default neutral score
            
            # Simple clarity estimation based on audio features
            # In production, would use trained clarity model
            signal_energy = np.mean(audio_data ** 2)
            signal_to_noise = signal_energy / (np.var(audio_data) + 1e-8)
            
            # Text coherence factor
            text_coherence = len(text.split()) / max(len(text), 1)
            
            clarity_score = min(signal_to_noise * text_coherence * 0.1, 1.0)
            return clarity_score
            
        except Exception as e:
            self.logger.error(f"Speech clarity estimation error: {e}")
            return 0.5


class GeoFenceSecurityMonitor:
    """Advanced geofence monitoring with behavioral pattern analysis."""
    
    def __init__(self, logger):
        self.logger = logger
        self.safe_zones = {
            'bedroom': {
                'center': Point(x=2.5, y=3.0, z=0.0),
                'radius': 2.0,
                'priority': 'high',
                'allowed_behaviors': ['rest', 'sleep', 'personal_care']
            },
            'living_room': {
                'center': Point(x=0.0, y=0.0, z=0.0),
                'radius': 3.5,
                'priority': 'medium',
                'allowed_behaviors': ['social', 'tv', 'reading', 'meals']
            },
            'bathroom': {
                'center': Point(x=-1.5, y=2.0, z=0.0),
                'radius': 1.5,
                'priority': 'critical',
                'allowed_behaviors': ['personal_care', 'hygiene']
            },
            'kitchen': {
                'center': Point(x=1.0, y=-2.0, z=0.0),
                'radius': 2.0,
                'priority': 'medium',
                'allowed_behaviors': ['cooking', 'eating', 'cleaning']
            }
        }
        
        self.behavior_history = deque(maxlen=100)
        self.location_history = deque(maxlen=50)
        self.anomaly_threshold = 0.7
        self.intrusion_timeout = 30  # seconds
        
        # Behavioral pattern tracking
        self.normal_patterns = self.initialize_normal_patterns()
        
    def initialize_normal_patterns(self) -> Dict[str, Any]:
        """Initialize normal behavioral patterns for elderly person."""
        return {
            'daily_routine': {
                'morning': {'zones': ['bedroom', 'bathroom', 'kitchen'], 'duration': timedelta(hours=3)},
                'afternoon': {'zones': ['living_room', 'kitchen'], 'duration': timedelta(hours=4)},
                'evening': {'zones': ['living_room', 'bedroom'], 'duration': timedelta(hours=4)}
            },
            'movement_patterns': {
                'normal_speed': 0.5,  # m/s
                'max_duration_per_zone': timedelta(hours=2),
                'min_zone_transition_time': timedelta(minutes=5)
            },
            'emergency_indicators': {
                'rapid_movement': 1.5,  # m/s
                'prolonged_stillness': timedelta(hours=3),
                'unusual_zone_sequence': 0.8  # Anomaly threshold
            }
        }
    
    def monitor_geofence(self, person_location: Point, robot_location: Point, 
                        behavior_context: str = "") -> GeofenceEvent:
        """Monitor geofence status with behavioral analysis."""
        try:
            # Determine current zone
            current_zone = self.get_current_zone(person_location)
            
            # Calculate behavior anomaly score
            anomaly_score = self.analyze_behavioral_anomaly(
                person_location, behavior_context
            )
            
            # Determine geofence status
            status = self.determine_geofence_status(
                person_location, current_zone, anomaly_score
            )
            
            # Calculate duration in current location
            duration = self.calculate_location_duration(person_location)
            
            # Create geofence event
            event = GeofenceEvent(
                timestamp=datetime.now(),
                person_location=person_location,
                robot_location=robot_location,
                zone_id=current_zone or "unknown",
                status=status,
                behavior_anomaly_score=anomaly_score,
                duration_seconds=duration
            )
            
            # Update location history
            self.location_history.append({
                'timestamp': datetime.now(),
                'location': person_location,
                'zone': current_zone,
                'behavior_context': behavior_context
            })
            
            return event
            
        except Exception as e:
            self.logger.error(f"Geofence monitoring error: {e}")
            return GeofenceEvent(
                timestamp=datetime.now(),
                person_location=person_location,
                robot_location=robot_location,
                zone_id="error",
                status=GeofenceStatus.WARNING,
                behavior_anomaly_score=0.5,
                duration_seconds=0.0
            )
    
    def get_current_zone(self, location: Point) -> Optional[str]:
        """Determine which zone the person is currently in."""
        for zone_id, zone_info in self.safe_zones.items():
            center = zone_info['center']
            radius = zone_info['radius']
            
            distance = math.sqrt(
                (location.x - center.x) ** 2 + 
                (location.y - center.y) ** 2
            )
            
            if distance <= radius:
                return zone_id
        
        return None  # Outside all safe zones
    
    def analyze_behavioral_anomaly(self, location: Point, behavior_context: str) -> float:
        """Analyze behavioral patterns for anomalies."""
        try:
            if len(self.location_history) < 3:
                return 0.0  # Not enough data
            
            # Analyze movement speed
            speed_anomaly = self.analyze_movement_speed()
            
            # Analyze zone transition patterns
            transition_anomaly = self.analyze_zone_transitions()
            
            # Analyze duration in zones
            duration_anomaly = self.analyze_zone_duration()
            
            # Combine anomaly scores
            total_anomaly = (speed_anomaly + transition_anomaly + duration_anomaly) / 3
            
            return min(total_anomaly, 1.0)
            
        except Exception as e:
            self.logger.error(f"Behavioral anomaly analysis error: {e}")
            return 0.0
    
    def analyze_movement_speed(self) -> float:
        """Analyze movement speed for anomalies."""
        if len(self.location_history) < 2:
            return 0.0
        
        recent_locations = list(self.location_history)[-5:]  # Last 5 locations
        speeds = []
        
        for i in range(1, len(recent_locations)):
            prev_loc = recent_locations[i-1]
            curr_loc = recent_locations[i]
            
            distance = math.sqrt(
                (curr_loc['location'].x - prev_loc['location'].x) ** 2 +
                (curr_loc['location'].y - prev_loc['location'].y) ** 2
            )
            
            time_diff = (curr_loc['timestamp'] - prev_loc['timestamp']).total_seconds()
            if time_diff > 0:
                speed = distance / time_diff
                speeds.append(speed)
        
        if not speeds:
            return 0.0
        
        avg_speed = np.mean(speeds)
        normal_speed = self.normal_patterns['movement_patterns']['normal_speed']
        
        # Anomaly if too fast or too slow
        if avg_speed > normal_speed * 2:
            return 0.8  # Moving too fast
        elif avg_speed < normal_speed * 0.1:
            return 0.6  # Moving too slow (potential issue)
        
        return 0.0
    
    def analyze_zone_transitions(self) -> float:
        """Analyze zone transition patterns for anomalies."""
        if len(self.location_history) < 3:
            return 0.0
        
        # Get recent zone sequence
        zones = [loc['zone'] for loc in list(self.location_history)[-10:] if loc['zone']]
        
        if len(zones) < 3:
            return 0.0
        
        # Check for unusual patterns
        # Example: Rapid zone switching might indicate confusion
        unique_zones = len(set(zones))
        if unique_zones > 4:  # Too many zone changes
            return 0.7
        
        # Check for emergency zone patterns (e.g., bathroom -> kitchen -> bathroom rapidly)
        zone_changes = sum(1 for i in range(1, len(zones)) if zones[i] != zones[i-1])
        if zone_changes > 6:  # Too many transitions
            return 0.6
        
        return 0.0
    
    def analyze_zone_duration(self) -> float:
        """Analyze time spent in zones for anomalies."""
        if not self.location_history:
            return 0.0
        
        current_zone = self.location_history[-1]['zone']
        if not current_zone:
            return 0.0
        
        # Calculate time in current zone
        zone_start_time = None
        for loc in reversed(self.location_history):
            if loc['zone'] != current_zone:
                break
            zone_start_time = loc['timestamp']
        
        if zone_start_time:
            duration = datetime.now() - zone_start_time
            max_duration = self.normal_patterns['movement_patterns']['max_duration_per_zone']
            
            if duration > max_duration:
                return 0.5  # Staying too long in one zone
        
        return 0.0
    
    def determine_geofence_status(self, location: Point, zone: Optional[str], 
                                 anomaly_score: float) -> GeofenceStatus:
        """Determine overall geofence status."""
        if zone is None:
            return GeofenceStatus.VIOLATION  # Outside all safe zones
        
        if anomaly_score > 0.8:
            return GeofenceStatus.EMERGENCY
        elif anomaly_score > 0.6:
            return GeofenceStatus.WARNING
        else:
            return GeofenceStatus.SAFE
    
    def calculate_location_duration(self, location: Point) -> float:
        """Calculate duration at current location."""
        if not self.location_history:
            return 0.0
        
        # Find when person arrived at this general location
        current_time = datetime.now()
        arrival_time = current_time
        
        for loc_data in reversed(self.location_history):
            loc = loc_data['location']
            distance = math.sqrt(
                (location.x - loc.x) ** 2 + (location.y - loc.y) ** 2
            )
            
            if distance > 1.0:  # 1 meter threshold
                break
            arrival_time = loc_data['timestamp']
        
        return (current_time - arrival_time).total_seconds()


class SOSKeywordsDetector:
    """Advanced SOS detection with multilingual implicit recognition."""
    
    def __init__(self, logger):
        self.logger = logger
        
        # SOS pattern database
        self.sos_patterns = {
            SOSCategory.EXPLICIT: {
                'chinese': ['救命', 'SOS', '求救', '报警', '叫救护车'],
                'english': ['help', 'sos', 'emergency', 'call ambulance', 'call police'],
                'universal': ['911', '120', '110', 'mayday']
            },
            SOSCategory.MEDICAL: {
                'chinese': ['心脏病', '中风', '呼吸困难', '胸痛', '头晕', '站不起来'],
                'english': ['heart attack', 'stroke', 'cant breathe', 'chest pain', 'dizzy', 'cant stand'],
                'symptoms': ['pain', '疼', 'hurt', '难受', 'sick', '不舒服']
            },
            SOSCategory.FALL: {
                'chinese': ['摔倒', '跌倒', '起不来', '腿断了', '爬不起来'],
                'english': ['fallen', 'fell down', 'cant get up', 'broken leg', 'cant stand'],
                'indicators': ['地上', 'on floor', 'ground', '地面']
            },
            SOSCategory.CONFUSION: {
                'chinese': ['迷路', '不记得', '找不到', '糊涂', '不知道在哪'],
                'english': ['lost', 'confused', 'cant find', 'dont remember', 'where am i'],
                'cognitive': ['memory', '记忆', 'forget', '忘记']
            },
            SOSCategory.EMOTIONAL: {
                'chinese': ['害怕', '孤独', '想家人', '难过', '绝望'],
                'english': ['scared', 'afraid', 'lonely', 'miss family', 'desperate'],
                'distress': ['crying', '哭', 'upset', '伤心']
            }
        }
        
        # Context clues that enhance SOS detection
        self.context_enhancers = {
            'urgency_words': ['快', '马上', '立刻', 'quickly', 'immediately', 'now'],
            'pain_intensifiers': ['非常', '很', '太', 'very', 'extremely', 'so much'],
            'time_indicators': ['现在', '刚才', '一直', 'now', 'just', 'always'],
            'location_words': ['这里', '房间', 'here', 'room', 'bathroom', '卫生间']
        }
        
        # Initialize multilingual model
        self.multilingual_model = self.initialize_multilingual_model()
    
    def initialize_multilingual_model(self):
        """Initialize multilingual emotion and distress detection model."""
        try:
            if TORCH_AVAILABLE:
                # In production, load fine-tuned multilingual BERT for elderly distress
                return None  # Mock for development
            return None
        except Exception as e:
            self.logger.error(f"Multilingual model initialization error: {e}")
            return None
    
    def detect_sos(self, text: str, emotion: EmotionData, 
                   conversation_context: List[str] = None) -> Optional[SOSEvent]:
        """Detect SOS with multilingual implicit recognition."""
        try:
            text_lower = text.lower()
            detected_categories = []
            confidence_scores = []
            detected_keywords = []
            contextual_clues = []
            
            # Check all SOS categories
            for category, patterns in self.sos_patterns.items():
                category_confidence = 0.0
                category_keywords = []
                
                # Check patterns in all languages
                for lang_patterns in patterns.values():
                    for pattern in lang_patterns:
                        if pattern in text_lower:
                            confidence = self.calculate_sos_confidence(
                                pattern, text_lower, emotion, conversation_context
                            )
                            if confidence > category_confidence:
                                category_confidence = confidence
                            category_keywords.append(pattern)
                
                # Apply emotional context enhancement
                enhanced_confidence = self.enhance_with_emotional_context(
                    category_confidence, category, emotion
                )
                
                if enhanced_confidence > 0.6:  # SOS threshold
                    detected_categories.append(category)
                    confidence_scores.append(enhanced_confidence)
                    detected_keywords.extend(category_keywords)
            
            # Check for contextual clues
            contextual_clues = self.find_contextual_clues(text_lower)
            
            # If SOS detected, create event
            if detected_categories:
                # Use highest confidence category
                max_idx = confidence_scores.index(max(confidence_scores))
                primary_category = detected_categories[max_idx]
                primary_confidence = confidence_scores[max_idx]
                
                # Determine urgency level
                urgency = self.calculate_urgency_level(primary_category, primary_confidence, emotion)
                
                return SOSEvent(
                    timestamp=datetime.now(),
                    category=primary_category,
                    confidence=primary_confidence,
                    keywords=detected_keywords,
                    emotional_indicators={
                        'stress_level': emotion.stress_level,
                        'primary_emotion': emotion.primary_emotion,
                        'arousal': emotion.arousal,
                        'valence': emotion.valence
                    },
                    contextual_clues=contextual_clues,
                    urgency_level=urgency
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"SOS detection error: {e}")
            return None
    
    def calculate_sos_confidence(self, keyword: str, text: str, emotion: EmotionData,
                                context: List[str] = None) -> float:
        """Calculate SOS detection confidence."""
        base_confidence = 0.7 if keyword in text else 0.0
        
        # Enhance with emotional indicators
        if emotion.stress_level > 0.7:
            base_confidence += 0.2
        
        if emotion.primary_emotion in ['fear', 'pain', 'distress']:
            base_confidence += 0.15
        
        # Context enhancement
        if context:
            context_text = ' '.join(context).lower()
            if any(enhancer in context_text for enhancer in self.context_enhancers['urgency_words']):
                base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def enhance_with_emotional_context(self, base_confidence: float, category: SOSCategory, 
                                     emotion: EmotionData) -> float:
        """Enhance SOS confidence with emotional context."""
        enhanced = base_confidence
        
        if category == SOSCategory.MEDICAL:
            if emotion.stress_level > 0.8:
                enhanced += 0.2
            if emotion.primary_emotion == 'pain':
                enhanced += 0.15
        
        elif category == SOSCategory.FALL:
            if emotion.arousal > 0.7:  # High arousal might indicate sudden event
                enhanced += 0.15
        
        elif category == SOSCategory.EMOTIONAL:
            if emotion.valence < -0.5:  # Very negative emotion
                enhanced += 0.1
        
        return min(enhanced, 1.0)
    
    def find_contextual_clues(self, text: str) -> List[str]:
        """Find contextual clues that support SOS detection."""
        clues = []
        
        for category, words in self.context_enhancers.items():
            for word in words:
                if word in text:
                    clues.append(f"{category}:{word}")
        
        return clues
    
    def calculate_urgency_level(self, category: SOSCategory, confidence: float, 
                               emotion: EmotionData) -> int:
        """Calculate urgency level (1-4)."""
        base_urgency = {
            SOSCategory.EXPLICIT: 4,
            SOSCategory.MEDICAL: 4,
            SOSCategory.FALL: 3,
            SOSCategory.CONFUSION: 2,
            SOSCategory.EMOTIONAL: 1
        }
        
        urgency = base_urgency.get(category, 1)
        
        # Adjust based on confidence and emotion
        if confidence > 0.9 and emotion.stress_level > 0.8:
            urgency = min(urgency + 1, 4)
        
        return urgency


class ImplicitCommandRecognizer:
    """Advanced implicit command recognition with contextual memory."""
    
    def __init__(self, logger):
        self.logger = logger
        self.context_window_size = 10
        self.conversation_context = deque(maxlen=self.context_window_size)
        
        # Implicit command patterns
        self.implicit_patterns = {
            'temperature_control': {
                'triggers': ['冷', '热', '温度', 'cold', 'hot', 'temperature', '空调'],
                'context_clues': ['不舒服', 'uncomfortable', '调节', 'adjust', '开', '关'],
                'commands': ['increase_temperature', 'decrease_temperature', 'adjust_ac'],
                'confidence_boost': 0.3
            },
            'lighting_control': {
                'triggers': ['暗', '亮', '看不清', 'dark', 'bright', 'cant see', '灯'],
                'context_clues': ['眼睛', 'eyes', '开灯', 'turn on light', '关灯'],
                'commands': ['increase_brightness', 'turn_on_lights', 'adjust_lighting'],
                'confidence_boost': 0.4
            },
            'assistance_request': {
                'triggers': ['帮我', '协助', 'help me', 'assist', '不会', 'dont know how'],
                'context_clues': ['做', 'do', '怎么', 'how to', '教我', 'teach me'],
                'commands': ['provide_assistance', 'explain_procedure', 'guide_action'],
                'confidence_boost': 0.2
            },
            'social_interaction': {
                'triggers': ['孤独', '无聊', 'lonely', 'bored', '聊天', 'talk'],
                'context_clues': ['陪我', 'stay with me', '说话', 'speak', '故事', 'story'],
                'commands': ['start_conversation', 'tell_story', 'provide_companionship'],
                'confidence_boost': 0.25
            }
        }
        
        # Emotional triggers for implicit commands
        self.emotional_triggers = {
            'comfort_needed': ['sad', 'lonely', 'worried', 'afraid'],
            'assistance_needed': ['confused', 'frustrated', 'helpless'],
            'health_concern': ['pain', 'uncomfortable', 'tired', 'sick']
        }
    
    def recognize_implicit_command(self, text: str, emotion: EmotionData,
                                 speaker_location: Point = None) -> Optional[ImplicitCommand]:
        """Recognize implicit commands from conversation context."""
        try:
            text_lower = text.lower()
            
            # Add current input to context
            self.conversation_context.append({
                'text': text,
                'emotion': emotion.primary_emotion,
                'timestamp': datetime.now(),
                'stress_level': emotion.stress_level
            })
            
            # Analyze context for implicit commands
            best_command = None
            best_confidence = 0.0
            
            for command_type, pattern_info in self.implicit_patterns.items():
                confidence = self.calculate_implicit_confidence(
                    text_lower, pattern_info, emotion
                )
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_command = command_type
            
            # Check emotional triggers
            emotional_command = self.check_emotional_triggers(emotion)
            if emotional_command and emotional_command[1] > best_confidence:
                best_command = emotional_command[0]
                best_confidence = emotional_command[1]
            
            # Only return if confidence is high enough
            if best_confidence > 0.6:
                pattern_info = self.implicit_patterns.get(best_command, {})
                
                return ImplicitCommand(
                    command_type=best_command,
                    confidence=best_confidence,
                    context_window=[ctx['text'] for ctx in list(self.conversation_context)[-5:]],
                    emotional_trigger=emotion.primary_emotion,
                    inferred_parameters=self.infer_command_parameters(
                        best_command, text, emotion
                    ),
                    requires_confirmation=best_confidence < 0.8
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Implicit command recognition error: {e}")
            return None
    
    def calculate_implicit_confidence(self, text: str, pattern_info: Dict[str, Any],
                                    emotion: EmotionData) -> float:
        """Calculate confidence for implicit command detection."""
        confidence = 0.0
        
        # Check trigger words
        trigger_matches = sum(1 for trigger in pattern_info['triggers'] if trigger in text)
        if trigger_matches > 0:
            confidence += 0.4 * (trigger_matches / len(pattern_info['triggers']))
        
        # Check context clues
        context_matches = sum(1 for clue in pattern_info['context_clues'] if clue in text)
        if context_matches > 0:
            confidence += 0.3 * (context_matches / len(pattern_info['context_clues']))
        
        # Apply confidence boost
        if trigger_matches > 0 or context_matches > 0:
            confidence += pattern_info.get('confidence_boost', 0.0)
        
        # Enhance with conversation history
        confidence += self.analyze_conversation_history(pattern_info)
        
        return min(confidence, 1.0)
    
    def analyze_conversation_history(self, pattern_info: Dict[str, Any]) -> float:
        """Analyze conversation history for pattern reinforcement."""
        if len(self.conversation_context) < 2:
            return 0.0
        
        # Look for related topics in recent context
        recent_texts = [ctx['text'].lower() for ctx in list(self.conversation_context)[-3:]]
        history_text = ' '.join(recent_texts)
        
        related_mentions = sum(1 for trigger in pattern_info['triggers'] 
                             if trigger in history_text)
        
        if related_mentions > 1:
            return 0.15  # Pattern reinforcement bonus
        
        return 0.0
    
    def check_emotional_triggers(self, emotion: EmotionData) -> Optional[Tuple[str, float]]:
        """Check for emotion-triggered implicit commands."""
        for trigger_type, emotions in self.emotional_triggers.items():
            if emotion.primary_emotion in emotions:
                confidence = 0.5 + (emotion.arousal * 0.3)
                
                command_map = {
                    'comfort_needed': 'social_interaction',
                    'assistance_needed': 'assistance_request',
                    'health_concern': 'health_monitoring'
                }
                
                command = command_map.get(trigger_type)
                if command:
                    return (command, confidence)
        
        return None
    
    def infer_command_parameters(self, command_type: str, text: str, 
                               emotion: EmotionData) -> Dict[str, Any]:
        """Infer parameters for implicit commands."""
        parameters = {}
        
        if command_type == 'temperature_control':
            if any(word in text for word in ['冷', 'cold']):
                parameters['action'] = 'increase_temperature'
                parameters['adjustment'] = 2  # degrees
            elif any(word in text for word in ['热', 'hot']):
                parameters['action'] = 'decrease_temperature'
                parameters['adjustment'] = 2
        
        elif command_type == 'lighting_control':
            if any(word in text for word in ['暗', 'dark', '看不清']):
                parameters['action'] = 'increase_brightness'
                parameters['adjustment'] = 30  # percent
            elif any(word in text for word in ['亮', 'bright', '太亮']):
                parameters['action'] = 'decrease_brightness'
                parameters['adjustment'] = 20
        
        elif command_type == 'social_interaction':
            parameters['interaction_type'] = 'conversation'
            if emotion.valence < -0.3:
                parameters['mood'] = 'comfort_needed'
            else:
                parameters['mood'] = 'general_chat'
        
        return parameters


class EnhancedGuardEngine(Node):
    """Enhanced Safety/Privacy Guard Engine - Main Integration Node."""
    
    def __init__(self):
        super().__init__('enhanced_guard_engine')
        
        # Initialize sub-components
        self.wakeword_engine = EnhancedWakewordEngine(self.get_logger())
        self.geofence_monitor = GeoFenceSecurityMonitor(self.get_logger())
        self.sos_detector = SOSKeywordsDetector(self.get_logger())
        self.implicit_recognizer = ImplicitCommandRecognizer(self.get_logger())
        
        # Conversation memory management
        self.conversation_memories: Dict[str, ConversationMemory] = {}
        self.current_conversation_id: Optional[str] = None
        
        # Enhanced safety state
        self.guard_active = True
        self.privacy_mode = True
        self.emergency_response_active = False
        
        # Performance tracking
        self.processing_times = deque(maxlen=100)
        self.detection_stats = {
            'wakeword_detections': 0,
            'sos_detections': 0,
            'implicit_commands': 0,
            'geofence_violations': 0
        }
        
        # QoS profiles
        critical_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50
        )
        
        # Subscribers
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/with_emotion',
            self.process_speech_with_guard,
            critical_qos
        )
        
        # Publishers
        self.guard_analysis_pub = self.create_publisher(
            String,
            '/guard/analysis',
            critical_qos
        )
        
        self.enhanced_intent_pub = self.create_publisher(
            IntentResult,
            '/guard/enhanced_intent',
            critical_qos
        )
        
        self.geofence_alert_pub = self.create_publisher(
            String,
            '/guard/geofence_alert',
            critical_qos
        )
        
        self.sos_alert_pub = self.create_publisher(
            EmergencyAlert,
            '/guard/sos_alert',
            critical_qos
        )
        
        # Start monitoring threads
        self.start_monitoring_threads()
        
        self.get_logger().info("Enhanced Guard Engine initialized - Advanced safety monitoring active")
    
    def process_speech_with_guard(self, msg: SpeechResult):
        """Process speech input through enhanced Guard analysis."""
        start_time = time.time()
        
        try:
            self.get_logger().info(f"Guard processing: '{msg.text}'")
            
            # Extract audio data if available
            audio_data = None  # Would extract from msg in production
            
            # 1. Wakeword Detection
            wakeword_result = self.wakeword_engine.detect_wakeword(
                audio_data, msg.text, msg.emotion
            )
            
            # 2. SOS Detection
            conversation_context = self.get_conversation_context()
            sos_result = self.sos_detector.detect_sos(
                msg.text, msg.emotion, conversation_context
            )
            
            # 3. Implicit Command Recognition
            implicit_command = self.implicit_recognizer.recognize_implicit_command(
                msg.text, msg.emotion, msg.speaker_location
            )
            
            # 4. Geofence Monitoring
            if msg.speaker_location:
                robot_location = Point(x=0.0, y=0.0, z=0.0)  # Would get actual robot position
                geofence_event = self.geofence_monitor.monitor_geofence(
                    msg.speaker_location, robot_location, msg.text
                )
            else:
                geofence_event = None
            
            # 5. Create comprehensive Guard analysis
            guard_analysis = self.create_guard_analysis(
                msg, wakeword_result, sos_result, implicit_command, geofence_event
            )
            
            # 6. Publish results
            self.publish_guard_results(guard_analysis)
            
            # 7. Handle emergency situations
            if sos_result and sos_result.urgency_level >= 3:
                self.handle_emergency_sos(sos_result, msg)
            
            # 8. Update conversation memory
            self.update_conversation_memory(msg, guard_analysis)
            
            # Track performance
            processing_time = (time.time() - start_time) * 1000  # ms
            self.processing_times.append(processing_time)
            
            if processing_time > 200:  # Emergency response requirement
                self.get_logger().warning(f"Guard processing time exceeded: {processing_time:.1f}ms")
            
        except Exception as e:
            self.get_logger().error(f"Guard processing error: {e}")
    
    def get_conversation_context(self) -> List[str]:
        """Get recent conversation context."""
        if not self.current_conversation_id:
            return []
        
        memory = self.conversation_memories.get(self.current_conversation_id)
        if memory:
            return [interaction['text'] for interaction in list(memory.interactions)[-5:]]
        
        return []
    
    def create_guard_analysis(self, speech_msg: SpeechResult, wakeword: WakewordResult,
                            sos: Optional[SOSEvent], implicit: Optional[ImplicitCommand],
                            geofence: Optional[GeofenceEvent]) -> Dict[str, Any]:
        """Create comprehensive Guard analysis."""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'speech_input': speech_msg.text,
            'confidence': speech_msg.confidence,
            'emotion': {
                'primary': speech_msg.emotion.primary_emotion,
                'stress_level': speech_msg.emotion.stress_level,
                'arousal': speech_msg.emotion.arousal,
                'valence': speech_msg.emotion.valence
            },
            'wakeword': {
                'detected': wakeword.detected,
                'type': wakeword.wake_type.value if wakeword.detected else None,
                'confidence': wakeword.confidence,
                'keyword': wakeword.keyword
            },
            'sos_detection': {
                'detected': sos is not None,
                'category': sos.category.value if sos else None,
                'confidence': sos.confidence if sos else 0.0,
                'urgency_level': sos.urgency_level if sos else 0
            },
            'implicit_command': {
                'detected': implicit is not None,
                'command_type': implicit.command_type if implicit else None,
                'confidence': implicit.confidence if implicit else 0.0,
                'requires_confirmation': implicit.requires_confirmation if implicit else False
            },
            'geofence': {
                'status': geofence.status.value if geofence else 'unknown',
                'zone': geofence.zone_id if geofence else None,
                'anomaly_score': geofence.behavior_anomaly_score if geofence else 0.0
            },
            'safety_assessment': self.calculate_overall_safety_assessment(
                wakeword, sos, implicit, geofence
            )
        }
        
        return analysis
    
    def calculate_overall_safety_assessment(self, wakeword: WakewordResult,
                                          sos: Optional[SOSEvent],
                                          implicit: Optional[ImplicitCommand],
                                          geofence: Optional[GeofenceEvent]) -> Dict[str, Any]:
        """Calculate overall safety assessment."""
        safety_level = "safe"
        risk_score = 0.0
        recommendations = []
        
        # Emergency conditions
        if sos and sos.urgency_level >= 3:
            safety_level = "emergency"
            risk_score = 0.9
            recommendations.append("immediate_emergency_response")
        
        # Geofence violations
        elif geofence and geofence.status == GeofenceStatus.EMERGENCY:
            safety_level = "high_risk"
            risk_score = 0.8
            recommendations.append("check_person_status")
        
        # High anomaly behavior
        elif geofence and geofence.behavior_anomaly_score > 0.7:
            safety_level = "moderate_risk"
            risk_score = 0.6
            recommendations.append("monitor_closely")
        
        # Implicit assistance needs
        elif implicit and implicit.confidence > 0.8:
            safety_level = "assistance_needed"
            risk_score = 0.3
            recommendations.append("provide_assistance")
        
        return {
            'level': safety_level,
            'risk_score': risk_score,
            'recommendations': recommendations,
            'requires_attention': risk_score > 0.5
        }
    
    def publish_guard_results(self, analysis: Dict[str, Any]):
        """Publish Guard analysis results."""
        try:
            # Publish general analysis
            analysis_msg = String()
            analysis_msg.data = json.dumps(analysis)
            self.guard_analysis_pub.publish(analysis_msg)
            
            # Publish enhanced intent if implicit command detected
            if analysis['implicit_command']['detected']:
                intent_msg = self.create_enhanced_intent_message(analysis)
                self.enhanced_intent_pub.publish(intent_msg)
            
            # Publish geofence alerts if needed
            if analysis['geofence']['status'] in ['warning', 'violation', 'emergency']:
                geofence_msg = String()
                geofence_msg.data = json.dumps({
                    'status': analysis['geofence']['status'],
                    'zone': analysis['geofence']['zone'],
                    'anomaly_score': analysis['geofence']['anomaly_score'],
                    'timestamp': analysis['timestamp']
                })
                self.geofence_alert_pub.publish(geofence_msg)
            
        except Exception as e:
            self.get_logger().error(f"Guard results publishing error: {e}")
    
    def create_enhanced_intent_message(self, analysis: Dict[str, Any]) -> IntentResult:
        """Create enhanced intent message from Guard analysis."""
        intent = IntentResult()
        intent.header = Header()
        intent.header.stamp = self.get_clock().now().to_msg()
        intent.header.frame_id = "enhanced_guard"
        
        implicit = analysis['implicit_command']
        intent.intent_type = implicit['command_type']
        intent.confidence = implicit['confidence']
        intent.requires_confirmation = implicit['requires_confirmation']
        
        # Add Guard context
        intent.conversation_id = self.current_conversation_id or "guard_session"
        intent.safety_validated = True
        intent.guard_enhanced = True
        
        return intent
    
    def handle_emergency_sos(self, sos_event: SOSEvent, speech_msg: SpeechResult):
        """Handle emergency SOS detection."""
        try:
            self.get_logger().critical(f"EMERGENCY SOS DETECTED: {sos_event.category.value}")
            
            # Create emergency alert
            alert = EmergencyAlert()
            alert.header = Header()
            alert.header.stamp = self.get_clock().now().to_msg()
            alert.header.frame_id = "enhanced_guard"
            
            alert.emergency_type = sos_event.category.value
            alert.severity_level = sos_event.urgency_level
            alert.description = f"SOS detected: {', '.join(sos_event.keywords)}"
            
            if speech_msg.speaker_location:
                alert.person_location = Pose()
                alert.person_location.position = speech_msg.speaker_location
            
            alert.last_speech = speech_msg
            alert.requires_human_intervention = True
            
            # Publish emergency alert
            self.sos_alert_pub.publish(alert)
            
            # Update stats
            self.detection_stats['sos_detections'] += 1
            self.emergency_response_active = True
            
        except Exception as e:
            self.get_logger().error(f"Emergency SOS handling error: {e}")
    
    def update_conversation_memory(self, speech_msg: SpeechResult, analysis: Dict[str, Any]):
        """Update episodic conversation memory."""
        try:
            # Create or get conversation memory
            if not self.current_conversation_id:
                self.current_conversation_id = f"guard_conv_{int(time.time())}"
                self.conversation_memories[self.current_conversation_id] = ConversationMemory(
                    conversation_id=self.current_conversation_id
                )
            
            memory = self.conversation_memories[self.current_conversation_id]
            
            # Add interaction
            interaction = {
                'timestamp': datetime.now(),
                'text': speech_msg.text,
                'emotion': speech_msg.emotion.primary_emotion,
                'guard_analysis': analysis,
                'safety_level': analysis['safety_assessment']['level']
            }
            memory.interactions.append(interaction)
            
            # Update emotion timeline
            memory.emotion_timeline.append((
                datetime.now(), 
                speech_msg.emotion.primary_emotion
            ))
            
            # Track safety incidents
            if analysis['safety_assessment']['risk_score'] > 0.7:
                memory.safety_incidents.append(
                    f"{datetime.now().isoformat()}: {analysis['safety_assessment']['level']}"
                )
            
        except Exception as e:
            self.get_logger().error(f"Conversation memory update error: {e}")
    
    def start_monitoring_threads(self):
        """Start background monitoring threads."""
        # Performance monitoring thread
        performance_thread = threading.Thread(
            target=self.performance_monitoring_loop, 
            daemon=True
        )
        performance_thread.start()
        
        # Memory cleanup thread
        cleanup_thread = threading.Thread(
            target=self.memory_cleanup_loop,
            daemon=True
        )
        cleanup_thread.start()
    
    def performance_monitoring_loop(self):
        """Monitor Guard performance continuously."""
        while rclpy.ok():
            try:
                if self.processing_times:
                    avg_time = np.mean(list(self.processing_times))
                    max_time = max(self.processing_times)
                    
                    if avg_time > 150:  # 150ms average warning
                        self.get_logger().warning(f"Guard avg processing time: {avg_time:.1f}ms")
                    
                    if max_time > 200:  # 200ms max critical
                        self.get_logger().error(f"Guard max processing time exceeded: {max_time:.1f}ms")
                
                # Log detection statistics
                self.get_logger().info(f"Guard stats: {self.detection_stats}")
                
                time.sleep(60)  # Monitor every minute
                
            except Exception as e:
                self.get_logger().error(f"Performance monitoring error: {e}")
                time.sleep(30)
    
    def memory_cleanup_loop(self):
        """Clean up old conversation memories."""
        while rclpy.ok():
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                # Clean up old conversations
                to_remove = []
                for conv_id, memory in self.conversation_memories.items():
                    if memory.interactions and memory.interactions[-1]['timestamp'] < cutoff_time:
                        to_remove.append(conv_id)
                
                for conv_id in to_remove:
                    del self.conversation_memories[conv_id]
                    if self.current_conversation_id == conv_id:
                        self.current_conversation_id = None
                
                if to_remove:
                    self.get_logger().info(f"Cleaned up {len(to_remove)} old conversation memories")
                
                time.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                self.get_logger().error(f"Memory cleanup error: {e}")
                time.sleep(1800)  # Retry in 30 minutes on error
    
    def get_guard_statistics(self) -> Dict[str, Any]:
        """Get Guard performance statistics."""
        return {
            'detection_stats': self.detection_stats,
            'avg_processing_time_ms': np.mean(list(self.processing_times)) if self.processing_times else 0,
            'max_processing_time_ms': max(self.processing_times) if self.processing_times else 0,
            'active_conversations': len(self.conversation_memories),
            'emergency_active': self.emergency_response_active,
            'guard_status': 'active' if self.guard_active else 'inactive'
        }


def main(args=None):
    """Run the Enhanced Guard Engine."""
    rclpy.init(args=args)
    
    try:
        node = EnhancedGuardEngine()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Enhanced Guard Engine error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()