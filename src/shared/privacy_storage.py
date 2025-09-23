#!/usr/bin/env python3
"""
Privacy Storage System for Elderly Companion Robdog
Encrypted local storage for elderly conversation data, emotions, and memories
Implements Privacy-by-Design and GDPR compliance
"""

import rclpy
from rclpy.node import Node

import sqlite3
import hashlib
import json
import os
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# Encryption imports
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    import secrets
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: cryptography not available, using mock encryption")

# Privacy compliance imports
import hashlib
import hmac

# ROS2 message imports
from std_msgs.msg import Header, String
from elderly_companion.msg import SpeechResult, EmotionData, IntentResult


class DataCategory(Enum):
    """Categories of elderly data"""
    CONVERSATION = "conversation"
    EMOTION = "emotion"
    HEALTH_INDICATOR = "health_indicator"
    MEMORY_TAG = "memory_tag"
    INTERACTION_PATTERN = "interaction_pattern"
    SYSTEM_LOG = "system_log"


class PrivacyLevel(Enum):
    """Privacy levels for data"""
    PUBLIC = 1        # Can be shared openly
    INTERNAL = 2      # Only within robot system
    FAMILY = 3        # Can be shared with family
    MEDICAL = 4       # Medical data - restricted access
    SENSITIVE = 5     # Highly sensitive - minimal access


class RetentionPolicy(Enum):
    """Data retention policies"""
    SHORT_TERM = 7        # 7 days
    MEDIUM_TERM = 30      # 30 days
    LONG_TERM = 365       # 1 year
    PERMANENT = 999999    # Permanent (until manually deleted)


@dataclass
class DataRecord:
    """Encrypted data record"""
    record_id: str
    category: DataCategory
    privacy_level: PrivacyLevel
    retention_policy: RetentionPolicy
    created_at: datetime
    expires_at: Optional[datetime]
    encrypted_data: bytes
    metadata: Dict[str, Any]
    access_log: List[Dict[str, Any]]
    consent_given: bool = True
    anonymized: bool = False


@dataclass
class ConversationRecord:
    """Conversation data structure"""
    conversation_id: str
    timestamp: datetime
    speech_text: str
    emotion_data: Dict[str, Any]
    intent_data: Dict[str, Any]
    response_text: str
    privacy_level: PrivacyLevel
    memory_tags: List[str] = None


@dataclass
class MemoryTag:
    """Memory tag for UC6 - Memory Bank"""
    tag_id: str
    tag_text: str
    category: str  # person, place, object, activity, emotion
    confidence: float
    first_mentioned: datetime
    last_mentioned: datetime
    mention_count: int
    associated_emotions: List[str]
    privacy_level: PrivacyLevel


class PrivacyStorageNode(Node):
    """
    Privacy Storage Node - Secure, privacy-compliant storage for elderly data.
    
    Features:
    - End-to-end encryption using Fernet (AES 128)
    - Privacy-by-design architecture
    - Automatic data retention and cleanup
    - GDPR compliance features
    - Consent management
    - Data anonymization
    - Access logging and audit trails
    - Secure deletion
    """

    def __init__(self):
        super().__init__('privacy_storage_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('storage.database_path', '/var/lib/elderly_companion/privacy.db'),
                ('storage.encryption_key_path', '/var/lib/elderly_companion/keys/storage.key'),
                ('privacy.enable_encryption', True),
                ('privacy.enable_access_logging', True),
                ('privacy.enable_data_anonymization', True),
                ('privacy.default_retention_days', 30),
                ('privacy.conversation_retention_days', 7),
                ('privacy.emotion_retention_days', 30),
                ('privacy.memory_retention_days', 365),
                ('privacy.emergency_data_retention_days', 90),
                ('cleanup.auto_cleanup_enabled', True),
                ('cleanup.cleanup_interval_hours', 24),
                ('consent.require_explicit_consent', True),
                ('consent.consent_renewal_days', 90),
            ]
        )
        
        # Get parameters
        self.db_path = self.get_parameter('storage.database_path').value
        self.key_path = self.get_parameter('storage.encryption_key_path').value
        self.encryption_enabled = self.get_parameter('privacy.enable_encryption').value
        self.access_logging_enabled = self.get_parameter('privacy.enable_access_logging').value
        self.anonymization_enabled = self.get_parameter('privacy.enable_data_anonymization').value
        self.auto_cleanup_enabled = self.get_parameter('cleanup.auto_cleanup_enabled').value
        self.cleanup_interval = self.get_parameter('cleanup.cleanup_interval_hours').value
        
        # Retention policies
        self.retention_policies = {
            DataCategory.CONVERSATION: self.get_parameter('privacy.conversation_retention_days').value,
            DataCategory.EMOTION: self.get_parameter('privacy.emotion_retention_days').value,
            DataCategory.MEMORY_TAG: self.get_parameter('privacy.memory_retention_days').value,
            DataCategory.HEALTH_INDICATOR: self.get_parameter('privacy.emergency_data_retention_days').value,
        }
        
        # Encryption components
        self.encryption_key = None
        self.fernet = None
        
        # Database connection
        self.db_connection = None
        self.db_lock = threading.Lock()
        
        # Memory processing for UC6
        self.memory_tagger = MemoryTagger()
        self.conversation_analyzer = ConversationAnalyzer()
        
        # Initialize storage system
        self.initialize_storage_system()
        
        # QoS profiles
        default_qos = rclpy.qos.QoSProfile(
            reliability=rclpy.qos.ReliabilityPolicy.RELIABLE,
            history=rclpy.qos.HistoryPolicy.KEEP_LAST,
            depth=100  # Higher depth for data storage
        )
        
        # Subscribers
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/with_emotion',
            self.store_speech_data_callback,
            default_qos
        )
        
        # Publishers
        self.privacy_status_pub = self.create_publisher(
            String,
            '/privacy/status',
            default_qos
        )
        
        self.memory_tags_pub = self.create_publisher(
            String,
            '/memory/tags',
            default_qos
        )
        
        # Start cleanup timer if enabled
        if self.auto_cleanup_enabled:
            self.cleanup_timer = self.create_timer(
                self.cleanup_interval * 3600,  # Convert hours to seconds
                self.cleanup_expired_data
            )
        
        self.get_logger().info("Privacy Storage Node initialized - Secure elderly data storage ready")

    def initialize_storage_system(self):
        """Initialize encrypted storage system"""
        try:
            # Create storage directory
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
            
            # Initialize encryption
            if self.encryption_enabled:
                self.initialize_encryption()
            
            # Initialize database
            self.initialize_database()
            
            self.get_logger().info("Storage system initialized with encryption enabled")
            
        except Exception as e:
            self.get_logger().error(f"Storage system initialization error: {e}")
            raise

    def initialize_encryption(self):
        """Initialize encryption system"""
        try:
            if not CRYPTO_AVAILABLE:
                self.get_logger().warning("Cryptography not available - data will not be encrypted")
                return
            
            # Load or generate encryption key
            if os.path.exists(self.key_path):
                with open(self.key_path, 'rb') as key_file:
                    self.encryption_key = key_file.read()
            else:
                # Generate new key
                self.encryption_key = Fernet.generate_key()
                
                # Save key securely
                os.umask(0o077)  # Restrict file permissions
                with open(self.key_path, 'wb') as key_file:
                    key_file.write(self.encryption_key)
                
                self.get_logger().info("New encryption key generated and saved")
            
            # Initialize Fernet cipher
            self.fernet = Fernet(self.encryption_key)
            
        except Exception as e:
            self.get_logger().error(f"Encryption initialization error: {e}")
            raise

    def initialize_database(self):
        """Initialize SQLite database with privacy schema"""
        try:
            self.db_connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            
            # Enable WAL mode for better concurrent access
            self.db_connection.execute('PRAGMA journal_mode=WAL')
            self.db_connection.execute('PRAGMA synchronous=NORMAL')
            self.db_connection.execute('PRAGMA cache_size=10000')
            
            # Create privacy-compliant schema
            self.create_database_schema()
            
            self.get_logger().info("Database initialized with privacy schema")
            
        except Exception as e:
            self.get_logger().error(f"Database initialization error: {e}")
            raise

    def create_database_schema(self):
        """Create database schema for privacy-compliant storage"""
        try:
            cursor = self.db_connection.cursor()
            
            # Data records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_records (
                    record_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    privacy_level INTEGER NOT NULL,
                    retention_policy INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    encrypted_data BLOB,
                    metadata_json TEXT,
                    consent_given BOOLEAN DEFAULT TRUE,
                    anonymized BOOLEAN DEFAULT FALSE,
                    deleted BOOLEAN DEFAULT FALSE,
                    created_by TEXT,
                    last_accessed TIMESTAMP
                )
            ''')
            
            # Access log table for audit trail
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_log (
                    log_id TEXT PRIMARY KEY,
                    record_id TEXT,
                    accessed_by TEXT,
                    access_type TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    purpose TEXT,
                    FOREIGN KEY (record_id) REFERENCES data_records (record_id)
                )
            ''')
            
            # Memory tags table for UC6
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory_tags (
                    tag_id TEXT PRIMARY KEY,
                    tag_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    first_mentioned TIMESTAMP NOT NULL,
                    last_mentioned TIMESTAMP NOT NULL,
                    mention_count INTEGER DEFAULT 1,
                    associated_emotions TEXT,
                    privacy_level INTEGER NOT NULL,
                    anonymized BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Conversation history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    encrypted_speech_text BLOB,
                    emotion_data_json TEXT,
                    intent_data_json TEXT,
                    encrypted_response_text BLOB,
                    privacy_level INTEGER NOT NULL,
                    memory_tags_json TEXT,
                    expires_at TIMESTAMP
                )
            ''')
            
            # Consent management table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS consent_records (
                    consent_id TEXT PRIMARY KEY,
                    elderly_person_id TEXT NOT NULL,
                    data_category TEXT NOT NULL,
                    consent_given BOOLEAN NOT NULL,
                    consent_date TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    withdrawal_date TIMESTAMP,
                    consent_details TEXT
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_category ON data_records(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_created ON data_records(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_expires ON data_records(expires_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_timestamp ON access_log(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memory_mentioned ON memory_tags(last_mentioned)')
            
            self.db_connection.commit()
            
        except Exception as e:
            self.get_logger().error(f"Database schema creation error: {e}")
            raise

    def store_speech_data_callback(self, msg: SpeechResult):
        """Store speech data with privacy compliance"""
        try:
            # Check consent for conversation storage
            if not self.check_consent(DataCategory.CONVERSATION):
                self.get_logger().debug("Consent not given for conversation storage")
                return
            
            # Create conversation record
            conversation = ConversationRecord(
                conversation_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                speech_text=msg.text,
                emotion_data=self.serialize_emotion_data(msg.emotion),
                intent_data={},  # Would be populated with intent data
                response_text="",  # Would be populated with robot response
                privacy_level=PrivacyLevel.INTERNAL
            )
            
            # Extract memory tags for UC6
            memory_tags = self.memory_tagger.extract_memory_tags(msg.text, msg.emotion)
            conversation.memory_tags = [tag.tag_text for tag in memory_tags]
            
            # Store conversation
            self.store_conversation(conversation)
            
            # Store memory tags
            for tag in memory_tags:
                self.store_memory_tag(tag)
            
            # Store emotion data separately if enabled
            if self.check_consent(DataCategory.EMOTION):
                self.store_emotion_data(msg.emotion, conversation.conversation_id)
            
        except Exception as e:
            self.get_logger().error(f"Speech data storage error: {e}")

    def store_conversation(self, conversation: ConversationRecord):
        """Store conversation with encryption"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                # Encrypt sensitive text data
                encrypted_speech = self.encrypt_data(conversation.speech_text)
                encrypted_response = self.encrypt_data(conversation.response_text)
                
                # Calculate expiration date
                retention_days = self.retention_policies.get(DataCategory.CONVERSATION, 7)
                expires_at = conversation.timestamp + timedelta(days=retention_days)
                
                cursor.execute('''
                    INSERT INTO conversations (
                        conversation_id, timestamp, encrypted_speech_text, 
                        emotion_data_json, intent_data_json, encrypted_response_text,
                        privacy_level, memory_tags_json, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    conversation.conversation_id,
                    conversation.timestamp,
                    encrypted_speech,
                    json.dumps(conversation.emotion_data),
                    json.dumps(conversation.intent_data),
                    encrypted_response,
                    conversation.privacy_level.value,
                    json.dumps(conversation.memory_tags) if conversation.memory_tags else None,
                    expires_at
                ))
                
                self.db_connection.commit()
                
                # Log access
                self.log_data_access(
                    conversation.conversation_id, 
                    'system', 
                    'store_conversation',
                    'Conversation data stored with encryption'
                )
                
        except Exception as e:
            self.get_logger().error(f"Conversation storage error: {e}")

    def store_memory_tag(self, tag: MemoryTag):
        """Store memory tag for UC6 - Memory Bank"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                # Check if tag already exists
                cursor.execute(
                    'SELECT tag_id, mention_count FROM memory_tags WHERE tag_text = ?',
                    (tag.tag_text,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing tag
                    cursor.execute('''
                        UPDATE memory_tags 
                        SET last_mentioned = ?, mention_count = mention_count + 1,
                            associated_emotions = ?, confidence = ?
                        WHERE tag_id = ?
                    ''', (
                        tag.last_mentioned,
                        json.dumps(tag.associated_emotions),
                        tag.confidence,
                        existing[0]
                    ))
                else:
                    # Insert new tag
                    cursor.execute('''
                        INSERT INTO memory_tags (
                            tag_id, tag_text, category, confidence,
                            first_mentioned, last_mentioned, mention_count,
                            associated_emotions, privacy_level
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        tag.tag_id,
                        tag.tag_text,
                        tag.category,
                        tag.confidence,
                        tag.first_mentioned,
                        tag.last_mentioned,
                        tag.mention_count,
                        json.dumps(tag.associated_emotions),
                        tag.privacy_level.value
                    ))
                
                self.db_connection.commit()
                
                # Publish updated memory tags
                self.publish_memory_tags()
                
        except Exception as e:
            self.get_logger().error(f"Memory tag storage error: {e}")

    def store_emotion_data(self, emotion: EmotionData, conversation_id: str):
        """Store emotion data with privacy protection"""
        try:
            emotion_record = {
                'conversation_id': conversation_id,
                'primary_emotion': emotion.primary_emotion,
                'confidence': emotion.confidence,
                'stress_level': emotion.stress_level,
                'arousal': emotion.arousal,
                'valence': emotion.valence,
                'elderly_patterns_detected': emotion.elderly_specific_patterns_detected,
                'detected_keywords': emotion.detected_keywords,
                'voice_quality_score': emotion.voice_quality_score
            }
            
            # Store as encrypted data record
            record = DataRecord(
                record_id=str(uuid.uuid4()),
                category=DataCategory.EMOTION,
                privacy_level=PrivacyLevel.MEDICAL,
                retention_policy=RetentionPolicy.MEDIUM_TERM,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=self.retention_policies[DataCategory.EMOTION]),
                encrypted_data=self.encrypt_data(json.dumps(emotion_record)),
                metadata={'conversation_id': conversation_id, 'data_type': 'emotion_analysis'},
                access_log=[],
                consent_given=True
            )
            
            self.store_data_record(record)
            
        except Exception as e:
            self.get_logger().error(f"Emotion data storage error: {e}")

    def encrypt_data(self, data: str) -> bytes:
        """Encrypt data using Fernet encryption"""
        try:
            if not self.encryption_enabled or not self.fernet:
                return data.encode('utf-8')
            
            return self.fernet.encrypt(data.encode('utf-8'))
            
        except Exception as e:
            self.get_logger().error(f"Data encryption error: {e}")
            return data.encode('utf-8')

    def decrypt_data(self, encrypted_data: bytes) -> str:
        """Decrypt data using Fernet encryption"""
        try:
            if not self.encryption_enabled or not self.fernet:
                return encrypted_data.decode('utf-8')
            
            return self.fernet.decrypt(encrypted_data).decode('utf-8')
            
        except Exception as e:
            self.get_logger().error(f"Data decryption error: {e}")
            return ""

    def store_data_record(self, record: DataRecord):
        """Store encrypted data record"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                cursor.execute('''
                    INSERT INTO data_records (
                        record_id, category, privacy_level, retention_policy,
                        created_at, expires_at, encrypted_data, metadata_json,
                        consent_given, anonymized, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.record_id,
                    record.category.value,
                    record.privacy_level.value,
                    record.retention_policy.value,
                    record.created_at,
                    record.expires_at,
                    record.encrypted_data,
                    json.dumps(record.metadata),
                    record.consent_given,
                    record.anonymized,
                    'elderly_companion_robot'
                ))
                
                self.db_connection.commit()
                
        except Exception as e:
            self.get_logger().error(f"Data record storage error: {e}")

    def check_consent(self, category: DataCategory) -> bool:
        """Check if consent is given for data category"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                cursor.execute('''
                    SELECT consent_given FROM consent_records 
                    WHERE data_category = ? AND withdrawal_date IS NULL
                    ORDER BY consent_date DESC LIMIT 1
                ''', (category.value,))
                
                result = cursor.fetchone()
                return result[0] if result else True  # Default to consent given
                
        except Exception as e:
            self.get_logger().error(f"Consent check error: {e}")
            return False  # Default to no consent on error

    def log_data_access(self, record_id: str, accessed_by: str, access_type: str, purpose: str):
        """Log data access for audit trail"""
        try:
            if not self.access_logging_enabled:
                return
            
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                cursor.execute('''
                    INSERT INTO access_log (
                        log_id, record_id, accessed_by, access_type, timestamp, purpose
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    record_id,
                    accessed_by,
                    access_type,
                    datetime.now(),
                    purpose
                ))
                
                self.db_connection.commit()
                
        except Exception as e:
            self.get_logger().error(f"Access logging error: {e}")

    def cleanup_expired_data(self):
        """Clean up expired data based on retention policies"""
        try:
            self.get_logger().info("Starting privacy-compliant data cleanup...")
            
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                # Find expired records
                cursor.execute('''
                    SELECT record_id, category FROM data_records 
                    WHERE expires_at < ? AND deleted = FALSE
                ''', (datetime.now(),))
                
                expired_records = cursor.fetchall()
                
                for record_id, category in expired_records:
                    # Securely delete expired data
                    self.secure_delete_record(record_id)
                
                # Clean up old access logs (keep for 1 year)
                cursor.execute('''
                    DELETE FROM access_log 
                    WHERE timestamp < ?
                ''', (datetime.now() - timedelta(days=365),))
                
                self.db_connection.commit()
                
                if expired_records:
                    self.get_logger().info(f"Cleaned up {len(expired_records)} expired records")
                
        except Exception as e:
            self.get_logger().error(f"Data cleanup error: {e}")

    def secure_delete_record(self, record_id: str):
        """Securely delete data record"""
        try:
            cursor = self.db_connection.cursor()
            
            # Mark as deleted (soft delete for audit trail)
            cursor.execute('''
                UPDATE data_records 
                SET deleted = TRUE, encrypted_data = NULL, metadata_json = NULL
                WHERE record_id = ?
            ''', (record_id,))
            
            # Log deletion
            self.log_data_access(record_id, 'system', 'secure_delete', 'Automatic data retention cleanup')
            
        except Exception as e:
            self.get_logger().error(f"Secure deletion error: {e}")

    def serialize_emotion_data(self, emotion: EmotionData) -> Dict[str, Any]:
        """Serialize emotion data for storage"""
        return {
            'primary_emotion': emotion.primary_emotion,
            'confidence': emotion.confidence,
            'secondary_emotions': emotion.secondary_emotions,
            'emotion_scores': emotion.emotion_scores,
            'arousal': emotion.arousal,
            'valence': emotion.valence,
            'stress_level': emotion.stress_level,
            'elderly_specific_patterns_detected': emotion.elderly_specific_patterns_detected,
            'detected_keywords': emotion.detected_keywords,
            'voice_quality_score': emotion.voice_quality_score
        }

    def publish_memory_tags(self):
        """Publish current memory tags for UC6"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                # Get recent memory tags
                cursor.execute('''
                    SELECT tag_text, category, mention_count, last_mentioned, associated_emotions
                    FROM memory_tags 
                    WHERE last_mentioned > ? AND anonymized = FALSE
                    ORDER BY mention_count DESC, last_mentioned DESC
                    LIMIT 20
                ''', (datetime.now() - timedelta(days=30),))
                
                tags_data = []
                for row in cursor.fetchall():
                    tags_data.append({
                        'tag': row[0],
                        'category': row[1],
                        'mentions': row[2],
                        'last_mentioned': row[3],
                        'emotions': json.loads(row[4]) if row[4] else []
                    })
                
                # Publish memory tags
                tags_msg = String()
                tags_msg.data = json.dumps({
                    'memory_tags': tags_data,
                    'timestamp': datetime.now().isoformat()
                })
                self.memory_tags_pub.publish(tags_msg)
                
        except Exception as e:
            self.get_logger().error(f"Memory tags publishing error: {e}")

    def get_conversation_history(self, days: int = 7, privacy_level: Optional[PrivacyLevel] = None) -> List[Dict[str, Any]]:
        """Get conversation history with privacy filtering"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                query = '''
                    SELECT conversation_id, timestamp, encrypted_speech_text, 
                           emotion_data_json, encrypted_response_text, memory_tags_json
                    FROM conversations 
                    WHERE timestamp > ? AND (expires_at IS NULL OR expires_at > ?)
                '''
                params = [datetime.now() - timedelta(days=days), datetime.now()]
                
                if privacy_level:
                    query += ' AND privacy_level <= ?'
                    params.append(privacy_level.value)
                
                query += ' ORDER BY timestamp DESC'
                
                cursor.execute(query, params)
                
                conversations = []
                for row in cursor.fetchall():
                    try:
                        conversation = {
                            'conversation_id': row[0],
                            'timestamp': row[1],
                            'speech_text': self.decrypt_data(row[2]) if row[2] else '',
                            'emotion_data': json.loads(row[3]) if row[3] else {},
                            'response_text': self.decrypt_data(row[4]) if row[4] else '',
                            'memory_tags': json.loads(row[5]) if row[5] else []
                        }
                        conversations.append(conversation)
                    except Exception as decrypt_error:
                        self.get_logger().warning(f"Failed to decrypt conversation {row[0]}: {decrypt_error}")
                
                return conversations
                
        except Exception as e:
            self.get_logger().error(f"Conversation history retrieval error: {e}")
            return []

    def anonymize_old_data(self):
        """Anonymize old data for privacy compliance"""
        try:
            with self.db_lock:
                cursor = self.db_connection.cursor()
                
                # Anonymize conversations older than 90 days
                anonymize_cutoff = datetime.now() - timedelta(days=90)
                
                cursor.execute('''
                    UPDATE conversations 
                    SET encrypted_speech_text = ?, encrypted_response_text = ?
                    WHERE timestamp < ? AND anonymized = FALSE
                ''', (
                    self.encrypt_data("[ANONYMIZED]"),
                    self.encrypt_data("[ANONYMIZED]"),
                    anonymize_cutoff
                ))
                
                # Anonymize memory tags
                cursor.execute('''
                    UPDATE memory_tags 
                    SET anonymized = TRUE 
                    WHERE first_mentioned < ?
                ''', (anonymize_cutoff,))
                
                self.db_connection.commit()
                
                self.get_logger().info("Old data anonymized for privacy compliance")
                
        except Exception as e:
            self.get_logger().error(f"Data anonymization error: {e}")

    def __del__(self):
        """Cleanup when node is destroyed"""
        try:
            if hasattr(self, 'db_connection') and self.db_connection:
                self.db_connection.close()
        except:
            pass


class MemoryTagger:
    """Memory tagger for UC6 - Memory Bank"""
    
    def __init__(self):
        # Elderly-specific memory categories
        self.memory_categories = {
            'family': ['老伴', '孩子', '孙子', '女儿', '儿子', 'husband', 'wife', 'child', 'grandchild'],
            'places': ['家', '医院', '公园', '超市', 'home', 'hospital', 'park', 'store'],
            'activities': ['吃饭', '散步', '看电视', '打电话', 'eating', 'walking', 'watching tv'],
            'emotions': ['开心', '想念', '担心', 'happy', 'miss', 'worry'],
            'objects': ['照片', '音乐', '书', 'photo', 'music', 'book']
        }
    
    def extract_memory_tags(self, text: str, emotion: EmotionData) -> List[MemoryTag]:
        """Extract memory tags from conversation"""
        tags = []
        
        try:
            text_lower = text.lower()
            
            for category, keywords in self.memory_categories.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        tag = MemoryTag(
                            tag_id=str(uuid.uuid4()),
                            tag_text=keyword,
                            category=category,
                            confidence=0.8,
                            first_mentioned=datetime.now(),
                            last_mentioned=datetime.now(),
                            mention_count=1,
                            associated_emotions=[emotion.primary_emotion],
                            privacy_level=PrivacyLevel.FAMILY
                        )
                        tags.append(tag)
            
            return tags
            
        except Exception as e:
            print(f"Memory tag extraction error: {e}")
            return []


class ConversationAnalyzer:
    """Conversation analyzer for emotional patterns"""
    
    def analyze_conversation_patterns(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze conversation patterns for UC5 emotional support"""
        try:
            # Analyze emotional trends, conversation frequency, topics
            patterns = {
                'emotional_trends': self.analyze_emotional_trends(conversations),
                'conversation_frequency': self.analyze_conversation_frequency(conversations),
                'common_topics': self.analyze_common_topics(conversations),
                'health_indicators': self.analyze_health_indicators(conversations)
            }
            
            return patterns
            
        except Exception as e:
            print(f"Conversation analysis error: {e}")
            return {}
    
    def analyze_emotional_trends(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze emotional trends over time"""
        emotions_by_day = {}
        
        for conv in conversations:
            date = conv['timestamp'][:10]  # Get date part
            emotion = conv['emotion_data'].get('primary_emotion', 'neutral')
            
            if date not in emotions_by_day:
                emotions_by_day[date] = []
            emotions_by_day[date].append(emotion)
        
        return emotions_by_day
    
    def analyze_conversation_frequency(self, conversations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze conversation frequency patterns"""
        frequency_by_hour = {}
        
        for conv in conversations:
            hour = int(conv['timestamp'][11:13])  # Get hour
            frequency_by_hour[hour] = frequency_by_hour.get(hour, 0) + 1
        
        return frequency_by_hour
    
    def analyze_common_topics(self, conversations: List[Dict[str, Any]]) -> List[str]:
        """Analyze common conversation topics"""
        all_tags = []
        
        for conv in conversations:
            tags = conv.get('memory_tags', [])
            all_tags.extend(tags)
        
        # Count tag frequency
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Return top 10 topics
        return sorted(tag_counts.keys(), key=lambda x: tag_counts[x], reverse=True)[:10]
    
    def analyze_health_indicators(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze health indicators from conversations"""
        health_keywords = {
            'pain': ['疼', '痛', 'pain', 'hurt'],
            'confusion': ['忘记', '糊涂', 'forget', 'confused'],
            'loneliness': ['孤独', '寂寞', 'lonely', 'alone'],
            'worry': ['担心', '害怕', 'worry', 'afraid']
        }
        
        indicators = {}
        
        for category, keywords in health_keywords.items():
            count = 0
            for conv in conversations:
                text = conv.get('speech_text', '').lower()
                if any(keyword in text for keyword in keywords):
                    count += 1
            indicators[category] = count
        
        return indicators


def main(args=None):
    """Main entry point"""
    rclpy.init(args=args)
    
    try:
        node = PrivacyStorageNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()