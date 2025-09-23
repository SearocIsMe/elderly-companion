# System Health Status Message
# Monitors the overall health of the elderly companion robot system

# Header with timestamp
std_msgs/Header header

# System component status
bool audio_system_ok
bool motion_system_ok
bool network_connected
bool camera_system_ok
bool ai_processing_ok

# Hardware metrics
float32 battery_level        # 0.0 to 1.0 (percentage)
float32 cpu_usage           # 0.0 to 1.0 (percentage)
float32 memory_usage        # 0.0 to 1.0 (percentage)
float32 gpu_usage           # 0.0 to 1.0 (percentage, for RK3588 NPU)
float32 temperature_celsius # System temperature
float32 disk_usage          # 0.0 to 1.0 (percentage)

# Network status
string network_type         # wifi, ethernet, cellular, none
int32 signal_strength       # dBm for wireless connections
float32 bandwidth_mbps      # Available bandwidth

# Active services and their status
string[] active_services
bool[] service_status       # true=healthy, false=degraded

# Emergency system status
bool emergency_system_ready
float32 emergency_response_time_ms  # Last measured response time

# Elderly-specific monitoring
bool fall_detection_active
bool voice_monitoring_active
bool family_connection_active

# System uptime
builtin_interfaces/Duration uptime

# Last error information
string last_error_message
builtin_interfaces/Time last_error_time

# Maintenance indicators
bool requires_maintenance
string[] maintenance_tasks
builtin_interfaces/Time next_scheduled_maintenance