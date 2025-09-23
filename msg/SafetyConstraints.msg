# Safety Constraints Message
# Defines safety limitations and constraints for robot actions

# Header with timestamp
std_msgs/Header header

# Motion safety constraints
float32 max_linear_velocity    # m/s - maximum safe linear speed
float32 max_angular_velocity   # rad/s - maximum safe angular speed
float32 max_acceleration       # m/s² - maximum safe acceleration
float32 min_obstacle_distance  # m - minimum distance to maintain from obstacles
float32 comfort_zone_radius    # m - preferred distance to maintain around elderly person

# Environmental constraints
string[] forbidden_areas       # Areas robot should not enter
geometry_msgs/Polygon[] no_go_zones  # Geometric areas to avoid
float32 max_slope_degrees      # Maximum slope robot can safely navigate
bool stairs_detected          # Whether stairs are present in area

# Elderly-specific constraints  
bool elderly_present           # Whether elderly person is detected nearby
geometry_msgs/Pose elderly_position  # Last known position of elderly person
float32 elderly_mobility_level # 0.0 (wheelchair) to 1.0 (fully mobile)
bool elderly_requires_assistance # Special care mode active

# Time-based constraints
builtin_interfaces/Time constraint_start_time
builtin_interfaces/Time constraint_end_time
bool night_mode_active         # Reduced activity during sleep hours
bool quiet_hours_active        # Reduced noise/movement

# Emergency override capabilities
bool emergency_override_enabled  # Can override constraints in emergency
string[] emergency_permissions   # Additional permissions during emergency
float32 emergency_response_time_limit  # Maximum time to reach elderly in emergency

# Interaction constraints
float32 max_interaction_distance  # Maximum distance for voice interaction
float32 min_personal_space       # Minimum personal space to maintain
bool physical_contact_allowed    # Whether gentle contact is permitted
bool audio_recording_permitted   # Privacy constraint for audio

# System-level constraints
float32 battery_reserve_level    # Minimum battery level to maintain for emergencies
bool maintenance_mode_active     # Reduced functionality during maintenance
string[] disabled_features       # Features currently disabled for safety
int32 max_continuous_operation_hours  # Maximum operation time before rest

# External constraints from family/caregivers
bool family_override_active      # Family has set additional constraints
string[] family_restrictions     # Specific restrictions from family
builtin_interfaces/Time last_family_update  # When constraints were last updated