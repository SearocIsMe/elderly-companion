# Emergency Alert Message
# Critical alerts for elderly safety situations

# Header with timestamp
std_msgs/Header header

# Emergency type classification
string emergency_type  # medical, fall, sos, security, system_failure

# Severity level (1=low, 2=medium, 3=high, 4=critical)
int32 severity_level

# Alert description
string description

# Location information
geometry_msgs/Pose robot_location
string location_description  # "living room", "bedroom", etc.

# Elderly person status
bool person_detected
geometry_msgs/Pose person_location
bool person_responsive

# Sensor data that triggered alert
string[] triggering_sensors
float32[] sensor_readings

# Audio context
SpeechResult last_speech  # Last heard speech before emergency
bool distress_detected_in_voice

# Visual context (if camera available)
sensor_msgs/Image[] emergency_images
bool fall_detected_visually

# Automated response status
bool emergency_call_initiated
string emergency_contact_reached  # phone number or "none"
builtin_interfaces/Time call_start_time

# Family notification status
bool family_notified
string[] notified_contacts
builtin_interfaces/Time notification_time

# Action taken by robot
string[] actions_taken  # "moved_to_person", "called_911", "activated_speaker"
bool robot_assistance_active

# Follow-up required
bool requires_human_intervention
string[] recommended_actions
int32 estimated_response_time_minutes

# External service integration
string incident_id  # For tracking with external services
bool healthcare_provider_notified
bool emergency_services_contacted