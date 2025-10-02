#!/bin/bash

# Elderly Companion Robdog - Development Environment Setup Script
# This script sets up the complete development environment for the project

set -e

echo "🤖 Setting up Elderly Companion Robdog Development Environment"
echo "=============================================================="

# Check if running on Ubuntu 22.04
if ! grep -q "22.04" /etc/os-release; then
    echo "⚠️  Warning: This script is designed for Ubuntu 22.04 LTS"
    read -p "Continue anyway? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        exit 1
    fi
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "🔄 Please log out and log back in to use Docker without sudo"
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Install ROS2 Humble (native for better performance)
if ! command -v ros2 &> /dev/null; then
    echo "🤖 Installing ROS2 Humble..."
    
    # Add ROS2 repository
    sudo apt install software-properties-common -y
    
    # Fix for apt_pkg module error - reinstall python3-apt to ensure it's working
    echo "🔧 Fixing apt_pkg module issue..."
    sudo apt remove --purge python3-apt -y || true
    sudo apt install python3-apt -y || echo "⚠️  Warning: python3-apt installation failed"
    
    # Fix for apt_pkg module error
    if ! sudo add-apt-repository universe -y; then
        echo "⚠️  Warning: add-apt-repository failed, trying alternative method..."
        # Ensure universe repository is enabled via direct method
        sudo apt update
        # Try to fix the apt_pkg module issue
        if python3 -c "import apt_pkg" 2>/dev/null; then
            echo "✅ apt_pkg module is working"
            sudo add-apt-repository universe -y
        else
            echo "⚠️  Warning: apt_pkg module not available, using manual repository addition"
            # Add universe repository manually
            sudo add-apt-repository "deb http://archive.ubuntu.com/ubuntu $(lsb_release -sc) universe" -y || true
        fi
    fi
    
    # Continue with setup even if repository addition had issues
    echo "🔄 Continuing with package installation..."
    
    sudo apt update && sudo apt install curl -y
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    
    # Add ROS2 repository with error handling
    ROS2_REPO_LINE="deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main"
    if ! echo "$ROS2_REPO_LINE" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null; then
        echo "⚠️  Warning: Failed to add ROS2 repository, trying alternative method..."
        # Try alternative method to add ROS2 repository
        sudo mkdir -p /etc/apt/sources.list.d
        echo "$ROS2_REPO_LINE" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null || echo "⚠️  Warning: Failed to create ros2.list file"
    fi
    
    # Install ROS2 packages
    sudo apt update
    sudo apt install ros-humble-desktop-full -y
    sudo apt install python3-colcon-common-extensions -y
    sudo apt install python3-rosdep python3-vcstool -y
    
    # Initialize rosdep
    sudo rosdep init || true
    rosdep update
    
    # Add ROS2 to bashrc
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi

# Install Node.js 18 for Family App development
if ! command -v node &> /dev/null; then
    echo "📱 Installing Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Install Python development dependencies
echo "🐍 Installing Python dependencies..."
pip3 install --user \
    sherpa-onnx==1.12.14 \
    silero-vad==6.0.0 \
    transformers==4.21.3 \
    torch==2.0.1 \
    torchaudio==2.0.2 \
    numpy \
    scipy \
    scikit-learn \
    opencv-python \
    paho-mqtt \
    requests \
    fastapi \
    uvicorn \
    websockets \
    aiortc \
    aiofiles \
    cryptography \
    pydantic \
    sqlalchemy \
    alembic \
    pytest \
    pytest-asyncio \
    black \
    flake8 \
    mypy

# Create project directories
echo "📁 Creating project directory structure..."
mkdir -p src/{router_agent,action_agent,family_app,shared,tests}
mkdir -p config/{mqtt,mediamtx,ros2}
mkdir -p scripts/{build,deploy,test}
mkdir -p docker/{router_agent,action_agent}
mkdir -p docs/{api,architecture,user_guide}
mkdir -p deployment/{dev,staging,production}
mkdir -p data/{models,configs,logs}

# Create ROS2 workspace structure
echo "🤖 Setting up ROS2 workspace..."
mkdir -p src/router_agent/{launch,config,msg,srv,action}
mkdir -p src/action_agent/{launch,config,nodes}
mkdir -p src/shared/{msgs,srvs,interfaces}

# Set up Git hooks (if this is a git repository)
if [ -d ".git" ]; then
    echo "📝 Setting up Git hooks..."
    cp scripts/git-hooks/* .git/hooks/ 2>/dev/null || true
    chmod +x .git/hooks/* 2>/dev/null || true
fi

# Build Docker containers
echo "🐳 Building Docker containers..."
docker-compose build

# Create environment configuration
echo "⚙️  Creating environment configuration..."
cat > .env << EOF
# Elderly Companion Robdog Environment Configuration

# Development Environment
COMPOSE_PROJECT_NAME=robdog
DISPLAY=${DISPLAY}

# Database Configuration
POSTGRES_DB=robdog_dev
POSTGRES_USER=robdog
POSTGRES_PASSWORD=dev_password_123

# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# WebRTC Configuration
WEBRTC_HOST=localhost
WEBRTC_PORT=8888

# Security
JWT_SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Audio Configuration
AUDIO_SAMPLE_RATE=48000
AUDIO_CHANNELS=6
AUDIO_DEVICE=/dev/snd

# ROS2 Configuration
RMW_IMPLEMENTATION=rmw_cyclonedx_cpp
ROS_DOMAIN_ID=42

# Development flags
DEBUG=true
LOG_LEVEL=INFO
EOF

echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Log out and log back in (for Docker group membership)"
echo "2. Run: source ~/.bashrc"
echo "3. Run: docker-compose up -d"
echo "4. Run: ./scripts/build_workspace.sh"
echo "5. Start coding! 🚀"