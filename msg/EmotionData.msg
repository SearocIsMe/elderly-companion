# Emotion Analysis Data Message
# Contains emotion recognition results from speech analysis

# Primary emotion detected
string primary_emotion  # happy, sad, angry, neutral, concerned, excited, fearful

# Confidence score for primary emotion (0.0 to 1.0)
float32 confidence

# Secondary emotions with scores
string[] secondary_emotions
float32[] emotion_scores

# Arousal level (0.0 to 1.0, low to high energy)
float32 arousal

# Valence level (-1.0 to 1.0, negative to positive)
float32 valence

# Stress indicator (0.0 to 1.0)
float32 stress_level

# Timestamp of analysis
builtin_interfaces/Time timestamp

# Additional metadata
bool elderly_specific_patterns_detected
string[] detected_keywords  # emotion-related keywords found
float32 voice_quality_score  # clarity, health indicators