# Elderly Companion Robdog - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Elderly Companion Robdog system from development to production on RK3588 hardware.

## Prerequisites

### Hardware Requirements

#### RK3588 Development Board
- **Recommended**: ROCK 5B+ or equivalent RK3588S board
- **RAM**: Minimum 8GB LPDDR4/5
- **Storage**: 64GB+ eMMC or NVMe SSD
- **Network**: Gigabit Ethernet + Wi-Fi 6 + Optional 5G/4G module
- **Audio**: USB audio interface with mic array and speakers
- **Camera**: USB3.0 or MIPI CSI camera for emergency monitoring
- **Power**: 12V/5A DC supply with backup battery

#### Unitree Go2 Robot
- **Model**: Unitree Go2 Air/Pro/Edu
- **Network**: Ethernet connection to RK3588
- **SDK**: unitree_sdk2 compatible firmware
- **Safety**: Emergency stop hardware integration

#### Network Infrastructure
- **Router**: 5GHz Wi-Fi 6 with low latency
- **Internet**: Minimum 10Mbps upload for emergency video streaming
- **Backup**: 4G/5G fallback connection
- **Smart Home Hub**: Matter/Thread compatible hub

### Software Prerequisites

#### PC Development Environment
```bash
# Ubuntu 22.04 LTS required
lsb_release -a

# Required packages
sudo apt update
sudo apt install -y \
    ros-humble-desktop-full \
    python3-pip \
    git \
    docker.io \
    docker-compose \
    build-essential \
    cmake \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    mosquitto-clients \
    curl \
    wget
```

#### RK3588 Production Environment
```bash
# Ubuntu 22.04 LTS aarch64 required
# Pre-installed with RK3588 support

# Essential packages
sudo apt update
sudo apt install -y \
    ros-humble-base \
    python3-pip \
    git \
    systemd \
    network-manager \
    alsa-utils \
    v4l-utils \
    mosquitto \
    nginx
```

## Development Setup

### Step 1: Clone and Initialize Project
```bash
# Clone repository
git clone https://github.com/your-org/elderly-companion-robdog.git
cd elderly-companion-robdog

# Initialize development environment
chmod +x scripts/*.sh
./scripts/setup_dev_env.sh

# Verify ROS2 installation
source /opt/ros/humble/setup.bash
ros2 --version
```

### Step 2: Build Workspace
```bash
# Build ROS2 workspace
./scripts/build_workspace.sh

# Source workspace
source install/setup.bash

# Verify build
ros2 pkg list | grep elderly_companion
```

### Step 3: Configure Docker Development
```bash
# Build development container
docker-compose build ros2-dev

# Start development environment
docker-compose up -d

# Verify container
docker-compose ps
```

### Step 4: Test Development Setup
```bash
# Run integration tests
./scripts/run_integration_tests.sh

# Run safety tests (ALL MUST PASS)
./scripts/run_safety_tests.sh

# Check test results
echo "Exit code: $?"
```

## Production Deployment

### Phase 1: RK3588 System Preparation

#### 1.1 Flash Ubuntu 22.04 LTS
```bash
# Download Ubuntu 22.04 LTS for RK3588
wget https://github.com/radxa/debos-radxa/releases/download/20230215-1015/rock-5b-ubuntu-jammy-server-arm64-20230215-1015-gpt.img.xz

# Flash to eMMC/SD card using balenaEtcher or dd
sudo dd if=rock-5b-ubuntu-jammy-server-arm64-20230215-1015-gpt.img of=/dev/sdX bs=4M status=progress

# First boot configuration
sudo passwd ubuntu
sudo systemctl enable ssh
sudo ufw enable
```

#### 1.2 Install RK3588 Drivers and NPU Runtime
```bash
# Install RKNPU runtime
wget https://github.com/airockchip/rknpu2/releases/download/v2.0.0/rknpu2-rk3588-linux-aarch64-v2.0.0.tar.gz
tar -xzf rknpu2-rk3588-linux-aarch64-v2.0.0.tar.gz
cd rknpu2-rk3588-linux-aarch64-v2.0.0
sudo ./install.sh

# Verify NPU installation
cat /sys/class/devfreq/fde60000.npu/available_frequencies
```

#### 1.3 Configure Network
```bash
# Configure static IP for robot network
sudo nmcli con mod "Wired connection 1" \
    ipv4.addresses 192.168.1.100/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns 8.8.8.8 \
    ipv4.method manual

# Enable Wi-Fi for internet access
sudo nmcli dev wifi connect "YourSSID" password "YourPassword"

# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 8554/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

### Phase 2: Software Deployment

#### 2.1 Transfer Code to RK3588
```bash
# From development PC
rsync -avz --exclude='.git' --exclude='build' \
    . ubuntu@[RK3588_IP]:/opt/elderly-companion/

# On RK3588: Set permissions
sudo chown -R ubuntu:ubuntu /opt/elderly-companion
chmod +x /opt/elderly-companion/scripts/*.sh
chmod +x /opt/elderly-companion/deployment/rk3588/deploy.sh
```

#### 2.2 Run Deployment Script
```bash
# On RK3588
cd /opt/elderly-companion
sudo ./deployment/rk3588/deploy.sh

# The script will:
# - Install ROS2 Humble
# - Install Python dependencies
# - Build ROS2 workspace
# - Install RKNN models
# - Configure systemd services
# - Start services
```

#### 2.3 Verify Deployment
```bash
# Check service status
sudo systemctl status elderly-companion-router-agent
sudo systemctl status elderly-companion-action-agent
sudo systemctl status elderly-companion-privacy-storage

# Check ROS2 nodes
source /opt/elderly-companion/install/setup.bash
ros2 node list

# Check system health
curl http://localhost:8080/api/v1/health
```

### Phase 3: Hardware Integration

#### 3.1 Connect Unitree Go2
```bash
# Configure Ethernet connection to Go2
sudo nmcli con add type ethernet con-name go2-connection \
    ifname eth1 ip4 192.168.123.100/24

# Test Unitree SDK connection
cd /opt/elderly-companion
python3 -c "
import sys
sys.path.append('src/action_agent')
from nodes.unitree_go2_bridge_node import UnitreeGo2Bridge
bridge = UnitreeGo2Bridge()
print('Unitree Go2 connection successful')
"
```

#### 3.2 Configure Audio Hardware
```bash
# List audio devices
arecord -l
aplay -l

# Test audio capture
arecord -f cd -t wav -d 5 test.wav
aplay test.wav

# Configure ALSA
sudo tee /etc/asound.conf > /dev/null <<EOF
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOF
```

#### 3.3 Setup Camera for Emergency Monitoring
```bash
# List video devices
v4l2-ctl --list-devices

# Test camera
ffmpeg -f v4l2 -i /dev/video0 -t 5 -c:v libx264 test.mp4

# Configure GStreamer
export GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
gst-inspect-1.0 | grep webrtc
```

### Phase 4: Smart Home Integration

#### 4.1 Configure MQTT Broker
```bash
# Install and configure Mosquitto
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Configure authentication
sudo mosquitto_passwd -c /etc/mosquitto/passwd elderly_user
sudo systemctl restart mosquitto

# Test MQTT connectivity
mosquitto_pub -h localhost -u elderly_user -P password \
    -t test/topic -m "Hello from RobDog"
```

#### 4.2 Configure Smart Home Devices
```bash
# Configure Matter/Thread devices
# (Device-specific configuration required)

# Test smart home control
curl -X POST http://localhost:8080/api/v1/smarthome/control \
    -H "Content-Type: application/json" \
    -d '{
        "device_id": "living_room_light_01",
        "action": "turn_on",
        "parameters": {"brightness": 50}
    }'
```

#### 4.3 Setup Emergency Communication
```bash
# Configure SIP/VoIP (using Asterisk or FreeSWITCH)
sudo apt install asterisk

# Configure emergency contacts in system
# Edit /opt/elderly-companion/config/emergency_contacts.json
```

### Phase 5: Family App Deployment

#### 5.1 Mobile App Build
```bash
# Install React Native CLI
npm install -g @react-native-community/cli

# Build for Android
cd src/family_app
npm install
npx react-native run-android --variant=release

# Build for iOS (macOS required)
cd ios
pod install
cd ..
npx react-native run-ios --configuration Release
```

#### 5.2 Configure Push Notifications
```bash
# Firebase Cloud Messaging setup
# 1. Create Firebase project
# 2. Add Android/iOS apps
# 3. Download google-services.json / GoogleService-Info.plist
# 4. Configure notification service

# Test push notifications
curl -X POST https://fcm.googleapis.com/fcm/send \
    -H "Authorization: key=YOUR_SERVER_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "to": "DEVICE_TOKEN",
        "notification": {
            "title": "Emergency Alert",
            "body": "RobDog detected an emergency"
        }
    }'
```

## Configuration Management

### System Configuration

#### Router Agent Configuration
```yaml
# config/router_agent.yaml
audio_processor:
  sample_rate: 16000
  chunk_size: 1024
  vad_threshold: 0.5
  noise_reduction: true

speech_recognition:
  model_path: "models/sherpa-onnx-zh-en-rknpu.rknn"
  language: "auto"  # auto, zh-CN, en-US
  enable_emotion_analysis: true

safety_guard:
  emergency_response_time_ms: 200
  intent_validation_timeout_ms: 100
  safe_velocity_limit: 0.6  # m/s
  safe_acceleration_limit: 0.3  # m/s²

dialog_manager:
  response_timeout_seconds: 5
  context_window_size: 10
  enable_memory_bank: true
  privacy_mode: true
```

#### Action Agent Configuration
```yaml
# config/action_agent.yaml
motion_control:
  max_velocity: 0.6  # m/s (elderly-safe)
  max_acceleration: 0.3  # m/s²
  comfort_zone_radius: 1.5  # meters
  obstacle_detection_range: 2.0  # meters
  emergency_stop_time: 0.5  # seconds

unitree_integration:
  connection_type: "ethernet"
  ip_address: "192.168.123.161"
  control_frequency: 100  # Hz
  safety_check_frequency: 50  # Hz

navigation:
  slam_enabled: true
  path_planning_algorithm: "rrt_star"
  obstacle_avoidance: "dynamic_window_approach"
  localization_method: "wheel_odometry_imu"
```

### Security Configuration

#### SSL/TLS Certificates
```bash
# Generate production certificates
sudo mkdir -p /etc/elderly-companion/certs
cd /etc/elderly-companion/certs

# Generate CA key and certificate
sudo openssl genrsa -out ca-key.pem 4096
sudo openssl req -new -x509 -days 365 -key ca-key.pem -out ca-cert.pem

# Generate server key and certificate
sudo openssl genrsa -out server-key.pem 4096
sudo openssl req -new -key server-key.pem -out server-csr.pem
sudo openssl x509 -req -days 365 -in server-csr.pem -CA ca-cert.pem -CAkey ca-key.pem -out server-cert.pem

# Set proper permissions
sudo chmod 400 *.pem
sudo chown ubuntu:ubuntu *.pem
```

#### Privacy Configuration
```json
{
  "privacy_settings": {
    "data_retention_days": 30,
    "auto_delete_enabled": true,
    "encryption_enabled": true,
    "local_processing_only": true,
    "consent_management": {
      "required_for_memory_bank": true,
      "required_for_video_recording": true,
      "required_for_emotion_analysis": true,
      "family_access_level": "emergency_only"
    },
    "gdpr_compliance": {
      "right_to_erasure": true,
      "data_portability": true,
      "processing_transparency": true
    }
  }
}
```

## Production Deployment Steps

### Step 1: Environment Preparation
```bash
# 1.1 Update system
sudo apt update && sudo apt upgrade -y

# 1.2 Install ROS2 Humble
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install -y ros-humble-base python3-colcon-common-extensions

# 1.3 Install Python dependencies
pip3 install -r requirements.txt

# 1.4 Install RKNPU tools
wget https://github.com/airockchip/rknn-toolkit2/releases/download/v2.3.2/rknn_toolkit_lite2-2.3.2-cp310-cp310-linux_aarch64.whl
pip3 install rknn_toolkit_lite2-2.3.2-cp310-cp310-linux_aarch64.whl
```

### Step 2: Deploy Application
```bash
# 2.1 Run deployment script
cd /opt/elderly-companion
sudo ./deployment/rk3588/deploy.sh --production

# 2.2 Configure systemd services
sudo systemctl daemon-reload
sudo systemctl enable elderly-companion-router-agent
sudo systemctl enable elderly-companion-action-agent
sudo systemctl enable elderly-companion-privacy-storage

# 2.3 Start services
sudo systemctl start elderly-companion-router-agent
sudo systemctl start elderly-companion-action-agent
sudo systemctl start elderly-companion-privacy-storage
```

### Step 3: Verify Deployment
```bash
# 3.1 Check service status
systemctl status elderly-companion-*

# 3.2 Check ROS2 nodes
source /opt/elderly-companion/install/setup.bash
ros2 node list

# 3.3 Test API endpoints
curl http://localhost:8080/api/v1/health

# 3.4 Verify audio processing
rostopic echo /speech/result &
# Speak into microphone
pkill -f "rostopic echo"
```

### Step 4: Hardware Integration Testing
```bash
# 4.1 Test Unitree Go2 connection
ros2 topic echo /go2/state

# 4.2 Test camera streaming
gst-launch-1.0 v4l2src device=/dev/video0 ! \
    videoconvert ! x264enc ! rtph264pay ! \
    udpsink host=127.0.0.1 port=5000

# 4.3 Test audio input/output
arecord -f cd -t wav -d 3 test_audio.wav
aplay test_audio.wav

# 4.4 Test emergency response
curl -X POST http://localhost:8080/api/v1/emergency \
    -H "Content-Type: application/json" \
    -d '{"emergency_type": "test", "severity": 1}'
```

## Monitoring and Maintenance

### System Monitoring Setup

#### 1. Log Monitoring
```bash
# Install log aggregation
sudo apt install -y rsyslog logrotate

# Configure log rotation
sudo tee /etc/logrotate.d/elderly-companion > /dev/null <<EOF
/var/log/elderly-companion/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
EOF
```

#### 2. Performance Monitoring
```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Create monitoring script
sudo tee /usr/local/bin/robdog_monitor.sh > /dev/null <<'EOF'
#!/bin/bash
echo "=== RobDog System Monitor ===" 
echo "Timestamp: $(date)"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)"
echo "Memory Usage: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
echo "NPU Usage: $(cat /sys/class/devfreq/fde60000.npu/load)"
echo "Temperature: $(cat /sys/class/thermal/thermal_zone0/temp | awk '{print $1/1000 "°C"}')"
echo "ROS2 Nodes: $(ros2 node list | wc -l)"
echo "Active Services:"
systemctl --type=service --state=active | grep elderly-companion
EOF

chmod +x /usr/local/bin/robdog_monitor.sh
```

#### 3. Health Checks
```bash
# Create health check script
sudo tee /usr/local/bin/robdog_health_check.sh > /dev/null <<'EOF'
#!/bin/bash
HEALTH_URL="http://localhost:8080/api/v1/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "$(date): System healthy"
    exit 0
else
    echo "$(date): System unhealthy (HTTP $RESPONSE)"
    # Restart services if unhealthy
    sudo systemctl restart elderly-companion-router-agent
    exit 1
fi
EOF

chmod +x /usr/local/bin/robdog_health_check.sh

# Add to crontab for regular health checks
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/robdog_health_check.sh >> /var/log/elderly-companion/health.log") | crontab -
```

### Backup and Recovery

#### 1. Data Backup
```bash
# Create backup script
sudo tee /usr/local/bin/robdog_backup.sh > /dev/null <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/elderly-companion"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/elderly-companion/config/

# Backup privacy data
tar -czf $BACKUP_DIR/privacy_data_$DATE.tar.gz /opt/elderly-companion/data/

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/elderly-companion/

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "$(date): Backup completed to $BACKUP_DIR"
EOF

chmod +x /usr/local/bin/robdog_backup.sh

# Schedule daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/robdog_backup.sh") | crontab -
```

#### 2. System Recovery
```bash
# Create recovery script
sudo tee /usr/local/bin/robdog_recovery.sh > /dev/null <<'EOF'
#!/bin/bash
echo "Starting Elderly Companion RobDog recovery..."

# Stop all services
sudo systemctl stop elderly-companion-*

# Restore from latest backup
LATEST_CONFIG=$(ls -t /opt/backups/elderly-companion/config_*.tar.gz | head -1)
LATEST_DATA=$(ls -t /opt/backups/elderly-companion/privacy_data_*.tar.gz | head -1)

if [ -n "$LATEST_CONFIG" ]; then
    echo "Restoring configuration from $LATEST_CONFIG"
    sudo tar -xzf $LATEST_CONFIG -C /
fi

if [ -n "$LATEST_DATA" ]; then
    echo "Restoring privacy data from $LATEST_DATA"
    sudo tar -xzf $LATEST_DATA -C /
fi

# Restart services
sudo systemctl start elderly-companion-router-agent
sudo systemctl start elderly-companion-action-agent
sudo systemctl start elderly-companion-privacy-storage

echo "Recovery completed"
EOF

chmod +x /usr/local/bin/robdog_recovery.sh
```

## Security Hardening

### System Security
```bash
# 1. Configure automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# 2. Harden SSH
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# 3. Configure fail2ban
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 4. Setup firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8080/tcp  # API
sudo ufw allow 8554/tcp  # RTSP
sudo ufw allow 1883/tcp  # MQTT
sudo ufw --force enable
```

### Application Security
```bash
# 1. Set proper file permissions
sudo find /opt/elderly-companion -type f -name "*.py" -exec chmod 644 {} \;
sudo find /opt/elderly-companion -type f -name "*.sh" -exec chmod 755 {} \;
sudo chmod 600 /opt/elderly-companion/config/secrets.env

# 2. Configure AppArmor profiles
sudo apt install -y apparmor-utils
sudo aa-genprof /opt/elderly-companion/bin/router_agent

# 3. Setup log monitoring
sudo apt install -y logwatch
sudo logwatch --detail Med --service All --range today --mailto admin@elderly-companion.com
```

## Performance Tuning

### RK3588 Optimization
```bash
# 1. CPU Governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 2. NPU Performance Mode
echo performance | sudo tee /sys/class/devfreq/fde60000.npu/governor

# 3. Memory optimization
echo 1 | sudo tee /proc/sys/vm/overcommit_memory
echo 80 | sudo tee /proc/sys/vm/swappiness

# 4. Network tuning
echo 'net.core.rmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Application Tuning
```bash
# 1. ROS2 performance tuning
export RMW_IMPLEMENTATION=rmw_cyclonedx_cpp
export CYCLONEDX_URI=/opt/elderly-companion/config/cyclone_dds.xml

# 2. GStreamer optimization
export GST_DEBUG=2
export GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0

# 3. Audio latency optimization
echo "@audio - memlock unlimited" | sudo tee -a /etc/security/limits.conf
echo "@audio - nice -10" | sudo tee -a /etc/security/limits.conf
```

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Audio Processing Fails
```bash
# Symptoms: No speech recognition, silent robot
# Solution:
sudo usermod -a -G audio ubuntu
pulseaudio --start
pactl info

# Check audio devices
arecord -l
# Verify correct device in config
cat /opt/elderly-companion/config/router_agent.yaml | grep audio_device
```

#### Issue 2: Unitree Go2 Connection Lost
```bash
# Symptoms: Robot doesn't move, connection errors
# Solution:
ping 192.168.123.161
sudo systemctl restart NetworkManager
sudo systemctl restart elderly-companion-action-agent

# Check network interface
ip addr show eth1
```

#### Issue 3: Emergency Response Delayed
```bash
# Symptoms: >200ms emergency response time
# Solution:
sudo systemctl restart elderly-companion-router-agent
# Check CPU governor
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# Should show "performance"
```

#### Issue 4: NPU Model Loading Fails
```bash
# Symptoms: High CPU usage, slow inference
# Solution:
ls -la /opt/elderly-companion/models/*.rknn
sudo dmesg | grep npu
# Reinstall RKNPU runtime if needed
```

### Log Analysis
```bash
# View system logs
journalctl -u elderly-companion-router-agent -f
journalctl -u elderly-companion-action-agent -f

# View application logs
tail -f /var/log/elderly-companion/router_agent.log
tail -f /var/log/elderly-companion/action_agent.log

# Check ROS2 logs
ros2 log list
ros2 log view /router_agent_node
```

## Production Checklist

### Pre-Deployment Validation
- [ ] All unit tests pass (`./scripts/run_integration_tests.sh`)
- [ ] Safety tests pass (`./scripts/run_safety_tests.sh`)
- [ ] Emergency response time <200ms verified
- [ ] Audio processing functional with target hardware
- [ ] Unitree Go2 connection established
- [ ] Smart home devices discoverable
- [ ] Family app can connect and receive notifications
- [ ] Video streaming works under emergency conditions
- [ ] Privacy encryption functional
- [ ] System monitoring and alerting configured

### Post-Deployment Validation
- [ ] All systemd services running and enabled
- [ ] Health check API returning status 200
- [ ] ROS2 nodes all active and communicating
- [ ] Emergency contacts configured and tested
- [ ] Backup system functional
- [ ] Log rotation configured
- [ ] Performance within acceptable ranges
- [ ] Security hardening applied
- [ ] User acceptance testing completed

### Go-Live Checklist
- [ ] Family members trained on mobile app usage
- [ ] Emergency contact list configured and verified
- [ ] Smart home integration tested with actual devices
- [ ] Robot behavior tested in real home environment
- [ ] Privacy settings reviewed and approved by user
- [ ] 24/7 monitoring system operational
- [ ] Support contact information provided to family

## Maintenance Procedures

### Daily Maintenance
```bash
# Automated daily checks via cron
0 6 * * * /usr/local/bin/robdog_monitor.sh >> /var/log/elderly-companion/daily_check.log
0 2 * * * /usr/local/bin/robdog_backup.sh
*/15 * * * * /usr/local/bin/robdog_health_check.sh
```

### Weekly Maintenance
```bash
# Weekly maintenance script
sudo tee /usr/local/bin/robdog_weekly_maintenance.sh > /dev/null <<'EOF'
#!/bin/bash
echo "$(date): Starting weekly maintenance"

# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean temporary files
sudo apt autoremove -y
sudo apt autoclean

# Rotate logs
sudo logrotate -f /etc/logrotate.d/elderly-companion

# Check disk space
df -h

# Verify model integrity
sha256sum /opt/elderly-companion/models/*.rknn

# Test emergency systems
curl -X POST http://localhost:8080/api/v1/emergency \
    -H "Content-Type: application/json" \
    -d '{"emergency_type": "test", "severity": 1}'

echo "$(date): Weekly maintenance completed"
EOF

chmod +x /usr/local/bin/robdog_weekly_maintenance.sh

# Schedule weekly maintenance
(crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/local/bin/robdog_weekly_maintenance.sh >> /var/log/elderly-companion/maintenance.log") | crontab -
```

### Monthly Maintenance
- Model performance evaluation and retraining if needed
- Security audit and vulnerability assessment  
- User feedback collection and analysis
- Hardware health assessment
- Backup system verification
- Performance baseline review

## Support and Documentation

### Emergency Support Contacts
```json
{
  "technical_support": {
    "phone": "+1-XXX-XXX-XXXX",
    "email": "support@elderly-companion.com",
    "hours": "24/7"
  },
  "medical_integration": {
    "phone": "+1-XXX-XXX-XXXX", 
    "email": "medical@elderly-companion.com",
    "hours": "Business hours"
  }
}
```

### Documentation Links
- **API Reference**: `/docs/API_SPECIFICATION.md`
- **Architecture Overview**: `/docs/ARCHITECTURE.md`
- **User Guide**: `/docs/USER_GUIDE.md`
- **Safety Manual**: `/docs/SAFETY_GUIDE.md`
- **Privacy Policy**: `/docs/PRIVACY_POLICY.md`

### Training Materials
- **Family App Tutorial**: Video guide for family members
- **Caregiver Training**: Professional caregiver integration guide
- **Emergency Procedures**: Step-by-step emergency response guide
- **Maintenance Guide**: Technical maintenance procedures

---

## Appendices

### Appendix A: Network Port Reference
| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| 22 | TCP | SSH | Remote administration |
| 80 | TCP | HTTP | Web interface (redirects to HTTPS) |
| 443 | TCP | HTTPS | Secure web interface |
| 1883 | TCP | MQTT | Smart home messaging |
| 8080 | TCP | HTTP | Router Agent API |
| 8554 | TCP | RTSP | Video streaming |
| 9090-9092 | TCP | HTTP | Metrics endpoints |
| 33433 | UDP | DDS | ROS2 discovery |

### Appendix B: File System Layout
```
/opt/elderly-companion/
├── bin/                    # Compiled binaries
├── config/                 # Configuration files
├── data/                   # Privacy data storage
├── logs/                   # Application logs
├── models/                 # AI models (RKNN format)
├── scripts/               # Deployment scripts
└── install/               # ROS2 installation

/var/log/elderly-companion/
├── router_agent.log       # Router agent logs
├── action_agent.log       # Action agent logs
├── privacy_storage.log    # Privacy system logs
├── health.log            # Health check logs
└── maintenance.log       # Maintenance logs

/etc/elderly-companion/
├── certs/                # SSL certificates
├── secrets.env          # Environment secrets
└── emergency_contacts.json # Emergency contact configuration
```

### Appendix C: Emergency Response Procedures

#### Severity Level Definitions
1. **Level 1 (Low)**: General assistance request, no immediate danger
2. **Level 2 (Medium)**: Concerning behavior, family notification recommended
3. **Level 3 (High)**: Potential medical emergency, immediate family contact
4. **Level 4 (Critical)**: Life-threatening emergency, call emergency services

#### Response Time Requirements
- **Level 4**: <200ms detection, immediate 911 call
- **Level 3**: <500ms detection, family notification within 1 minute
- **Level 2**: <2 seconds detection, family notification within 5 minutes
- **Level 1**: <5 seconds detection, log for review

This deployment guide ensures safe, secure, and reliable operation of the Elderly Companion Robdog system in production environments.