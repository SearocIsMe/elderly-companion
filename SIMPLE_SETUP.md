# Enhanced Elderly Companion Robot - Complete Setup Guide

A comprehensive guide from git clone to deployment and testing.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)  
3. [System Dependencies](#system-dependencies)
4. [Code Setup](#code-setup)
5. [Python Dependencies](#python-dependencies)
6. [Build Application](#build-application)
7. [Deployment](#deployment)
8. [Running System](#running-system)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04 LTS (for PC) or compatible Linux (for RK3588)
- **Python**: 3.10+
- **ROS2**: Humble Hawksbill
- **Docker**: Latest stable version
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 10GB free space

### Hardware Requirements
- **PC Development**: x86_64 with GPU support optional
- **RK3588 Board**: Rockchip RK3588 development board
- **Audio**: USB microphone and speaker (or 3.5mm audio)
- **Network**: WiFi or Ethernet connection

---

## 2. Environment Setup

### 2.1 Install ROS2 Humble

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install ROS2 Humble
sudo apt install software-properties-common -y
sudo add-apt-repository universe -y
sudo apt update

# Install ROS2 packages
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-humble-desktop -y
sudo apt install python3-colcon-common-extensions -y

# Source ROS2 (add to ~/.bashrc for permanent)
source /opt/ros/humble/setup.bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### 2.2 Install Docker and Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

---

## 3. System Dependencies

### 3.1 Audio System Dependencies

```bash
# Audio development libraries (required for pyaudio)
sudo apt install -y \
    portaudio19-dev \
    libpulse-dev \
    alsa-utils \
    libasound2-dev \
    libsndfile1-dev \
    libjack-jackd2-dev

# Additional audio tools
sudo apt install -y \
    pavucontrol \
    audacity \
    pulseaudio \
    pulseaudio-utils
```

### 3.2 Build and Development Tools

```bash
# Essential build tools
sudo apt install -y \
    build-essential \
    cmake \
    git \
    python3-dev \
    python3-pip \
    python3-venv \
    curl \
    wget \
    unzip

# Additional development tools
sudo apt install -y \
    vim \
    htop \
    tree \
    dos2unix
```

### 3.3 SIP/VoIP Dependencies (Optional)

```bash
# SIP/VoIP libraries (for emergency calling)
sudo apt install -y \
    libpjproject-dev \
    libssl-dev \
    libsrtp2-dev
```

### 3.4 Computer Vision Dependencies (Optional)

```bash
# OpenCV and image processing
sudo apt install -y \
    libopencv-dev \
    python3-opencv \
    libgtk-3-dev
```

---

## 4. Code Setup

### 4.1 Clone Repository

```bash
# Clone the repository
git clone <repository-url> elderly-companion
cd elderly-companion

# Verify project structure
tree -L 2
```

### 4.2 Handle Conda Conflicts (Important!)

If you have Anaconda/Miniconda installed:

```bash
# Temporarily deactivate conda
conda deactivate

# Or use a clean environment approach
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

**Note**: The system works best with system Python to avoid ROS2 conflicts.

---

## 5. Python Dependencies

### 5.1 Install Core Dependencies

```bash
# Update pip
sudo python3 -m pip install --upgrade pip

# Install essential packages first
sudo python3 -m pip install \
    requests \
    pyyaml \
    numpy \
    scipy

# Install audio packages (after system dependencies)
sudo python3 -m pip install \
    soundfile \
    librosa \
    pyaudio \
    speechrecognition \
    pyttsx3
```

### 5.2 Install All Dependencies

** Install the torchaudio in conda and system **
```
# Ubuntu/Debian系统
sudo apt update
sudo apt install python3-torchaudio

# 或者使用conda（如果您使用conda环境）
conda install -c pytorch torchaudio

```

```bash

# 安装TTS相关依赖
sudo apt install -y espeak espeak-ng
pip install pyttsx3


# Install all dependencies from requirements.txt (with conflict resolution)
sudo python3 -m pip install -r requirements.txt --ignore-installed

# Alternative: If above fails due to distutils conflicts
sudo python3 -m pip install -r requirements.txt --force-reinstall --no-deps
sudo python3 -m pip install -r requirements.txt  # Install dependencies separately
```

**Note**: Some packages may fail due to missing system dependencies or conflicts with system packages.

#### 5.2.1 Handling Package Conflicts

If you encounter "distutils installed project" errors:

```bash
# Method 1: Skip problematic packages and install manually
pip install -r requirements.txt --ignore-installed sympy

# Method 2: Use virtual environment (recommended for development)
python3 -m venv elderly_companion_env
source elderly_companion_env/bin/activate
pip install -r requirements.txt

# Method 3: Force reinstall specific conflicting packages
sudo python3 -m pip install --force-reinstall --no-deps sympy==1.12
```

---

## 6. Build Application

### 6.1 Build ROS2 Workspace

```bash
# Make build script executable
chmod +x scripts/build.sh

# Run the build
./scripts/build.sh
```

### 6.2 Manual Build (if script fails)

```bash
# Clean previous builds
rm -rf build/ install/ log/ .colcon_build

# Build with colcon
source /opt/ros/humble/setup.bash
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

# Source the workspace
source install/setup.bash
```

---

## 7. Deployment

### 7.1 PC Development Deployment

```bash
# 1. Source workspace
source install/setup.bash

# 2. Start FastAPI services
cd src/router_agent/docker
docker compose -f docker-compose.pc.yml up -d
cd ../../..

# 3. Verify services
curl http://localhost:7010/health  # Orchestrator
curl http://localhost:7002/health  # Guard  
curl http://localhost:7001/health  # Intent
curl http://localhost:7003/health  # Adapters
```

### 7.2 RK3588 Board Deployment

```bash
# 1. Copy deployment files to RK3588
scp -r deployment/rk3588/* user@rk3588-board:/opt/elderly-companion/

# 2. On RK3588 board, install services
sudo cp deployment/rk3588/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 3. Enable and start services
sudo systemctl enable elderly-companion-router-agent.service
sudo systemctl start elderly-companion-router-agent.service

# 4. Check status
sudo systemctl status elderly-companion-router-agent.service
```

### 7.3 Production Deployment

```bash
# Use production Docker compose
cd src/router_agent/docker
docker compose -f docker-compose.pc.gpu.yml up -d

# Or for full production
docker compose -f docker-compose.production.yml up -d
```

---

## 8. Running System

### 8.1 Quick Launch

```bash
# Make launch script executable
chmod +x scripts/launch.sh

# Launch the complete system
./scripts/launch.sh
```

### 8.2 Manual Launch

```bash
# 1. Source workspace
source install/setup.bash

# 2. Launch ROS2 system
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=hybrid
```

### 8.3 Launch Modes

```bash
# Text-only mode (console only)
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=text_only

# Audio-only mode (voice interaction)
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=audio_only

# Hybrid mode (both text and audio)
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=hybrid

# Emergency mode (emergency response only)
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=emergency
```

---

## 9. Testing

### 9.1 Basic System Test

```bash
# In the running system console:
You: hello
Robot: 你好！我是您的智能陪护机器人，有什么可以帮助您的吗？

You: status
# Shows system health and component status

You: help
Robot: 我检测到您可能需要帮助，正在为您联系相关人员...
```

### 9.2 Emergency Response Test

```bash
# Test emergency keyword detection
You: help I need assistance
Robot: 紧急情况已确认！正在立即联系帮助...

You: emergency
# Triggers emergency response protocol
```

### 9.3 Smart Home Test

```bash
# Test smart home commands
You: turn on the lights
Robot: 好的，正在为您开启灯光...

You: adjust the temperature
Robot: 好的，正在为您调节温度...
```

### 9.4 Health Monitoring Test

```bash
# Check system health
You: health
# Shows detailed component health status

# Check component status  
ros2 topic echo /router_agent/system_status
```

### 9.5 FastAPI Integration Test

```bash
# Test FastAPI services directly
curl -X POST http://localhost:7010/asr_text \
  -H "Content-Type: application/json" \
  -d '{"text": "turn on lights"}'

# Expected response includes intent, guard decision, and adapter routing
```

---

## 10. Troubleshooting

### 10.1 Common Issues

#### Package Not Found Error
```bash
# Solution: Ensure correct package name
ros2 pkg list | grep elderly_companion
# Should show: elderly_companion

# Re-source workspace
source install/setup.bash
```

#### Conda/ROS2 Conflicts
```bash
# Solution: Use system Python
conda deactivate
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

#### ROS2 Build Errors (ModuleNotFoundError: No module named 'em')
```bash
# This error occurs when using conda environments with ROS2
# Solution 1: Install missing ROS2 Python dependencies in conda environment
pip install empy catkin_pkg lark setuptools wheel argcomplete

# Solution 2: Ensure all ROS2 dependencies are installed
pip install colcon-common-extensions colcon-ros

# Solution 3: If still failing, deactivate conda and use system Python
conda deactivate
export PATH="/usr/bin:/usr/local/bin:$PATH"
./scripts/build.sh

# Solution 4: Install ROS2 Python packages specifically
sudo apt install python3-colcon-common-extensions python3-rosdep
pip install --upgrade setuptools wheel
```

#### ROS2 Build Errors (AttributeError: module 'em' has no attribute 'BUFFERED_OPT')
```bash
# This error indicates empy version incompatibility with ROS2 Humble
# Solution 1: Install specific empy version compatible with ROS2 Humble
pip uninstall empy
pip install empy==3.3.4

# Solution 2: Use system empy package instead
pip uninstall empy
sudo apt install python3-empy

# Solution 3: Complete clean reinstall of ROS2 dependencies
pip uninstall empy catkin_pkg lark setuptools wheel argcomplete
sudo apt install python3-empy python3-catkin-pkg python3-lark
pip install setuptools wheel argcomplete

# Solution 4: Force use of system Python with ROS2
conda deactivate
sudo apt install python3-colcon-common-extensions
export PATH="/usr/bin:/usr/local/bin:$PATH"
./scripts/build.sh
```

#### Audio Package Installation Failures
```bash
# Solution: Install system dependencies first
sudo apt install portaudio19-dev python3-dev build-essential
sudo python3 -m pip install pyaudio
```

#### Line Ending Issues (WSL)
```bash
# Solution: Fix line endings
find src/router_agent/nodes -name "*.py" -exec dos2unix {} \;
./scripts/build.sh
```

#### FastAPI Services Not Starting
```bash
# Solution: Check Docker
docker --version
docker-compose --version

# Restart Docker daemon
sudo systemctl restart docker

# Check ports
netstat -tulpn | grep -E ':(7001|7002|7003|7010)'
```

### 10.2 Performance Optimization

#### For PC Development
- Use GPU acceleration if available
- Increase memory allocation for Docker
- Use SSD storage for better I/O

#### For RK3588 Board  
- Enable NPU acceleration
- Optimize memory usage
- Use appropriate deployment configuration

### 10.3 Monitoring and Logs

```bash
# View ROS2 logs
ros2 topic echo /router_agent/system_status

# View Docker logs
docker compose logs -f

# View system resources
htop
nvidia-smi  # If GPU available
```

---

## 🎉 Success Indicators

When everything is working correctly, you should see:

- ✅ All ROS2 nodes launching without critical errors
- ✅ FastAPI services responding to health checks
- ✅ Console showing "Ready for conversation..."
- ✅ Text input and response working
- ✅ Emergency response system active
- ✅ Smart home integration responding
- ⚠️ Some warnings for missing optional packages (normal)

The Enhanced Elderly Companion Robot system is now ready for elderly care assistance with comprehensive safety monitoring, emergency response, smart home integration, and family communication features.