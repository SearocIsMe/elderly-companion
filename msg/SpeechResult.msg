# Speech Recognition Result Message
# Used by the Router Agent to communicate speech recognition results

# Header with timestamp and frame info
std_msgs/Header header

# Recognized text
string text

# Confidence score (0.0 to 1.0)
float32 confidence

# Language detected
string language

# Emotion analysis data
EmotionData emotion

# Speaker location (if available from mic array)
geometry_msgs/Point speaker_location

# Audio metadata
float32 audio_duration_seconds
int32 sample_rate
bool voice_activity_detected