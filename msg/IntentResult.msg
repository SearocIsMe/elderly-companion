# Intent Classification Result Message
# Contains the classified intent and parameters from speech processing

# Header with timestamp
std_msgs/Header header

# Classified intent type
string intent_type  # smart_home, emergency, follow, chat, memory, health_check

# Intent parameters as key-value pairs
string[] parameter_names
string[] parameter_values

# Confidence score for intent classification (0.0 to 1.0)
float32 confidence

# Safety approval status
bool safety_approved

# Reasoning for approval/rejection
string reasoning

# Priority level (0=low, 1=normal, 2=high, 3=critical)
int32 priority_level

# Requires confirmation from user
bool requires_confirmation

# Estimated execution time in seconds
float32 estimated_duration

# Associated emotion context
EmotionData emotional_context

# Context preservation for multi-turn conversations
string conversation_id
string[] context_history