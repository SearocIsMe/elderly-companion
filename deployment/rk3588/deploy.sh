#!/bin/bash

# Elderly Companion Robdog - RK3588 Deployment Script
# Deploys the complete system to RK3588 production hardware with RKNN optimization

set -e

echo "🚀 Deploying Elderly Companion Robot to RK3588"
echo "=============================================="

# Configuration
RK3588_HOST=${1:-"192.168.123.15"}
RK3588_USER=${2:-"elderly"}
DEPLOYMENT_DIR="/opt/elderly_companion"
MODELS_DIR="/opt/elderly_companion/models"
CONFIG_DIR="/opt/elderly_companion/config"
LOGS_DIR="/var/log/elderly_companion"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if RK3588 is reachable
check_rk3588_connection() {
    echo_info "Checking RK3588 connection..."
    
    if ping -c 1 -W 3 $RK3588_HOST > /dev/null 2>&1; then
        echo_success "RK3588 is reachable at $RK3588_HOST"
    else
        echo_error "Cannot reach RK3588 at $RK3588_HOST"
        echo "Please check:"
        echo "  1. RK3588 is powered on and connected to network"
        echo "  2. IP address is correct"
        echo "  3. SSH is enabled on RK3588"
        exit 1
    fi
}

# Function to check RK3588 system requirements
check_system_requirements() {
    echo_info "Checking RK3588 system requirements..."
    
    ssh ${RK3588_USER}@${RK3588_HOST} << 'EOF'
        # Check Ubuntu version
        if ! grep -q "22.04" /etc/os-release; then
            echo "❌ Ubuntu 22.04 LTS required"
            exit 1
        fi
        
        # Check available disk space (minimum 8GB)
        AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
        if [ $AVAILABLE_SPACE -lt 8388608 ]; then  # 8GB in KB
            echo "❌ Insufficient disk space. Need at least 8GB free"
            exit 1
        fi
        
        # Check RAM (minimum 4GB)
        TOTAL_RAM=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        if [ $TOTAL_RAM -lt 4194304 ]; then  # 4GB in KB
            echo "❌ Insufficient RAM. Need at least 4GB"
            exit 1
        fi
        
        # Check NPU availability
        if [ ! -e /dev/rknpu ]; then
            echo "⚠️ RKNPU device not found - AI acceleration may not work"
        fi
        
        echo "✅ System requirements check passed"
EOF
    
    if [ $? -ne 0 ]; then
        echo_error "System requirements check failed"
        exit 1
    fi
    
    echo_success "RK3588 system requirements verified"
}

# Function to prepare deployment package
prepare_deployment_package() {
    echo_info "Preparing deployment package..."
    
    # Create temporary deployment directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_DIR="$TEMP_DIR/elderly_companion_package"
    
    mkdir -p $PACKAGE_DIR/{src,config,scripts,models,systemd}
    
    # Copy source code
    echo_info "Packaging source code..."
    cp -r src/* $PACKAGE_DIR/src/
    cp -r config/* $PACKAGE_DIR/config/
    cp -r scripts/* $PACKAGE_DIR/scripts/
    
    # Copy configuration files
    cp docker-compose.yml $PACKAGE_DIR/
    cp package.xml $PACKAGE_DIR/
    cp CMakeLists.txt $PACKAGE_DIR/
    
    # Copy deployment-specific files
    cp deployment/rk3588/*.service $PACKAGE_DIR/systemd/ 2>/dev/null || true
    cp deployment/rk3588/install_*.sh $PACKAGE_DIR/scripts/ 2>/dev/null || true
    
    # Create deployment manifest
    cat > $PACKAGE_DIR/deployment_manifest.json << EOF
{
    "package_name": "elderly_companion_robdog",
    "version": "0.1.0",
    "target_platform": "rk3588",
    "deployment_timestamp": "$(date -Iseconds)",
    "deployment_id": "$(uuidgen)",
    "components": [
        "router_agent",
        "action_agent", 
        "privacy_storage",
        "webrtc_streamer"
    ],
    "models": [
        "sherpa-onnx-chinese-english.rknn",
        "emotion-classification.rknn"
    ],
    "system_requirements": {
        "min_ram_gb": 4,
        "min_storage_gb": 8,
        "requires_npu": true,
        "ubuntu_version": "22.04"
    }
}
EOF
    
    # Create deployment archive
    cd $TEMP_DIR
    tar -czf elderly_companion_rk3588_$(date +%Y%m%d_%H%M%S).tar.gz elderly_companion_package/
    
    DEPLOYMENT_PACKAGE="$TEMP_DIR/elderly_companion_rk3588_$(date +%Y%m%d_%H%M%S).tar.gz"
    echo_success "Deployment package created: $DEPLOYMENT_PACKAGE"
    
    echo $DEPLOYMENT_PACKAGE
}

# Function to convert models to RKNN format
convert_models_to_rknn() {
    echo_info "Converting AI models to RKNN format for NPU acceleration..."
    
    # Create models conversion script
    cat > /tmp/convert_models.py << 'EOF'
#!/usr/bin/env python3

import os
import sys
from rknn import RKNN

def convert_sherpa_onnx_models():
    """Convert sherpa-onnx models to RKNN format"""
    try:
        print("Converting sherpa-onnx ASR models...")
        
        # Initialize RKNN
        rknn = RKNN(verbose=True)
        
        # Configure for RK3588
        rknn.config(
            mean_values=[[0, 0, 0]],
            std_values=[[1, 1, 1]],
            target_platform='rk3588',
            optimization_level=3,
            quantized_dtype='asymmetric_quantized-u8',
            quantized_algorithm='mmse'
        )
        
        # Convert encoder model
        if os.path.exists('/models/sherpa-onnx/encoder.onnx'):
            print("Converting encoder.onnx to encoder.rknn...")
            ret = rknn.load_onnx('/models/sherpa-onnx/encoder.onnx')
            if ret != 0:
                print("Load encoder model failed!")
                return False
            
            ret = rknn.build(do_quantization=True)
            if ret != 0:
                print("Build encoder model failed!")
                return False
            
            ret = rknn.export_rknn('/models/sherpa-onnx/encoder.rknn')
            if ret != 0:
                print("Export encoder model failed!")
                return False
        
        # Convert decoder model
        if os.path.exists('/models/sherpa-onnx/decoder.onnx'):
            print("Converting decoder.onnx to decoder.rknn...")
            rknn.load_onnx('/models/sherpa-onnx/decoder.onnx')
            rknn.build(do_quantization=True)
            rknn.export_rknn('/models/sherpa-onnx/decoder.rknn')
        
        # Convert joiner model  
        if os.path.exists('/models/sherpa-onnx/joiner.onnx'):
            print("Converting joiner.onnx to joiner.rknn...")
            rknn.load_onnx('/models/sherpa-onnx/joiner.onnx')
            rknn.build(do_quantization=True)
            rknn.export_rknn('/models/sherpa-onnx/joiner.rknn')
        
        rknn.release()
        print("✅ Sherpa-ONNX models converted to RKNN format")
        return True
        
    except Exception as e:
        print(f"❌ Model conversion error: {e}")
        return False

def convert_emotion_model():
    """Convert emotion recognition model to RKNN format"""
    try:
        print("Converting emotion recognition model...")
        
        rknn = RKNN(verbose=True)
        rknn.config(target_platform='rk3588')
        
        if os.path.exists('/models/emotion/emotion_classifier.onnx'):
            rknn.load_onnx('/models/emotion/emotion_classifier.onnx')
            rknn.build(do_quantization=True)
            rknn.export_rknn('/models/emotion/emotion_classifier.rknn')
            print("✅ Emotion model converted to RKNN format")
        
        rknn.release()
        return True
        
    except Exception as e:
        print(f"❌ Emotion model conversion error: {e}")
        return False

if __name__ == "__main__":
    success = True
    success &= convert_sherpa_onnx_models()
    success &= convert_emotion_model()
    
    if success:
        print("✅ All models converted successfully")
        sys.exit(0)
    else:
        print("❌ Model conversion failed")
        sys.exit(1)
EOF
    
    # Run model conversion (would need actual models)
    echo_warning "Model conversion script created (requires actual model files)"
}

# Function to deploy to RK3588
deploy_to_rk3588() {
    echo_info "Deploying to RK3588..."
    
    PACKAGE_PATH=$1
    
    # Copy deployment package to RK3588
    echo_info "Copying deployment package to RK3588..."
    scp $PACKAGE_PATH ${RK3588_USER}@${RK3588_HOST}:/tmp/
    
    PACKAGE_NAME=$(basename $PACKAGE_PATH)
    
    # Execute deployment on RK3588
    ssh ${RK3588_USER}@${RK3588_HOST} << EOF
        set -e
        
        echo "📦 Extracting deployment package..."
        cd /tmp
        tar -xzf $PACKAGE_NAME
        
        echo "🔧 Installing system dependencies..."
        sudo apt update
        sudo apt install -y \\
            python3-pip \\
            python3-venv \\
            sqlite3 \\
            alsa-utils \\
            pulseaudio \\
            gstreamer1.0-tools \\
            gstreamer1.0-plugins-base \\
            gstreamer1.0-plugins-good \\
            gstreamer1.0-plugins-bad \\
            gstreamer1.0-plugins-ugly \\
            libgstreamer1.0-dev \\
            libgstreamer-plugins-base1.0-dev
        
        echo "🤖 Installing ROS2 Humble..."
        if ! command -v ros2 &> /dev/null; then
            curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
            echo "deb [arch=\$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu \$(. /etc/os-release && echo \$UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
            sudo apt update
            sudo apt install -y ros-humble-desktop-full
            sudo apt install -y python3-colcon-common-extensions
        fi
        
        echo "🧠 Installing AI runtime libraries..."
        # Install RKNN runtime
        if [ ! -f /usr/lib/librknnrt.so ]; then
            echo "Installing RKNN runtime..."
            # This would install the actual RKNN runtime
            # wget https://github.com/airockchip/rknn-toolkit2/releases/...
            # sudo dpkg -i rknn_runtime_package.deb
            echo "⚠️ RKNN runtime installation placeholder"
        fi
        
        echo "🐍 Setting up Python environment..."
        cd elderly_companion_package
        python3 -m pip install --user \\
            sherpa-onnx==1.12.14 \\
            silero-vad==6.0.0 \\
            transformers==4.21.3 \\
            torch==2.0.1 \\
            torchaudio==2.0.2 \\
            numpy \\
            scipy \\
            scikit-learn \\
            opencv-python \\
            paho-mqtt \\
            requests \\
            fastapi \\
            uvicorn \\
            websockets \\
            aiortc \\
            aiofiles \\
            cryptography \\
            pydantic \\
            sqlalchemy \\
            aiohttp
        
        echo "📁 Creating deployment directories..."
        sudo mkdir -p $DEPLOYMENT_DIR $MODELS_DIR $CONFIG_DIR $LOGS_DIR
        sudo chown -R \$USER:\$USER $DEPLOYMENT_DIR $LOGS_DIR
        
        echo "📋 Copying application files..."
        cp -r src/* $DEPLOYMENT_DIR/
        cp -r config/* $CONFIG_DIR/
        cp -r scripts/* $DEPLOYMENT_DIR/scripts/
        
        echo "⚙️ Installing systemd services..."
        if [ -d systemd ]; then
            sudo cp systemd/*.service /etc/systemd/system/
            sudo systemctl daemon-reload
        fi
        
        echo "🔧 Setting up ROS2 workspace..."
        cd $DEPLOYMENT_DIR
        
        # Source ROS2
        source /opt/ros/humble/setup.bash
        
        # Build workspace
        colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
        
        echo "🔐 Setting up security and permissions..."
        # Create elderly companion user if not exists
        if ! id "elderly_companion" &>/dev/null; then
            sudo useradd -r -s /bin/false elderly_companion
        fi
        
        # Set proper permissions
        sudo chown -R elderly_companion:elderly_companion $DEPLOYMENT_DIR
        sudo chmod 750 $DEPLOYMENT_DIR
        sudo chmod 640 $CONFIG_DIR/*.conf
        
        echo "🗄️ Setting up database..."
        sudo -u elderly_companion sqlite3 $DEPLOYMENT_DIR/data/privacy.db < deployment/sql/init_privacy_db.sql
        
        echo "🚀 Starting services..."
        sudo systemctl enable elderly-companion-router-agent
        sudo systemctl enable elderly-companion-action-agent
        sudo systemctl enable elderly-companion-privacy-storage
        
        sudo systemctl start elderly-companion-router-agent
        sudo systemctl start elderly-companion-action-agent
        sudo systemctl start elderly-companion-privacy-storage
        
        echo "✅ Deployment completed successfully!"
        
        echo "📊 Service Status:"
        sudo systemctl status elderly-companion-router-agent --no-pager -l
        sudo systemctl status elderly-companion-action-agent --no-pager -l
        sudo systemctl status elderly-companion-privacy-storage --no-pager -l
EOF
    
    if [ $? -eq 0 ]; then
        echo_success "RK3588 deployment completed successfully"
    else
        echo_error "RK3588 deployment failed"
        exit 1
    fi
}

# Function to verify deployment
verify_deployment() {
    echo_info "Verifying deployment on RK3588..."
    
    ssh ${RK3588_USER}@${RK3588_HOST} << 'EOF'
        echo "🔍 Checking service status..."
        
        # Check if services are running
        if ! systemctl is-active --quiet elderly-companion-router-agent; then
            echo "❌ Router Agent service not running"
            exit 1
        fi
        
        if ! systemctl is-active --quiet elderly-companion-action-agent; then
            echo "❌ Action Agent service not running"  
            exit 1
        fi
        
        if ! systemctl is-active --quiet elderly-companion-privacy-storage; then
            echo "❌ Privacy Storage service not running"
            exit 1
        fi
        
        echo "🧪 Running basic functionality tests..."
        
        # Test ROS2 node communication
        source /opt/elderly_companion/install/setup.bash
        timeout 10s ros2 topic list | grep -q elderly_companion
        if [ $? -ne 0 ]; then
            echo "❌ ROS2 topics not found"
            exit 1
        fi
        
        # Test database connectivity
        if [ ! -f /opt/elderly_companion/data/privacy.db ]; then
            echo "❌ Privacy database not found"
            exit 1
        fi
        
        # Test RKNN models (if available)
        if [ -f /opt/elderly_companion/models/sherpa-onnx/encoder.rknn ]; then
            echo "✅ RKNN models found"
        else
            echo "⚠️ RKNN models not found - using CPU fallback"
        fi
        
        echo "✅ Deployment verification passed"
EOF
    
    if [ $? -eq 0 ]; then
        echo_success "Deployment verification passed"
        return 0
    else
        echo_error "Deployment verification failed"
        return 1
    fi
}

# Function to create monitoring dashboard
setup_monitoring() {
    echo_info "Setting up system monitoring..."
    
    ssh ${RK3588_USER}@${RK3588_HOST} << 'EOF'
        # Install monitoring tools
        sudo apt install -y htop iotop nethogs
        
        # Create monitoring script
        cat > /opt/elderly_companion/scripts/monitor_system.sh << 'MONITOR_EOF'
#!/bin/bash

echo "🤖 Elderly Companion Robot - System Monitor"
echo "=========================================="

echo "📊 System Resources:"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
echo "Memory Usage: $(free | grep Mem | awk '{printf("%.1f%%", $3/$2 * 100.0)}')"
echo "Disk Usage: $(df -h / | awk 'NR==2 {print $5}')"
echo "Temperature: $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000"°C"}' || echo "N/A")"

echo ""
echo "🤖 Service Status:"
systemctl is-active elderly-companion-router-agent && echo "✅ Router Agent: Running" || echo "❌ Router Agent: Stopped"
systemctl is-active elderly-companion-action-agent && echo "✅ Action Agent: Running" || echo "❌ Action Agent: Stopped"
systemctl is-active elderly-companion-privacy-storage && echo "✅ Privacy Storage: Running" || echo "❌ Privacy Storage: Stopped"

echo ""
echo "📡 Network Status:"
ping -c 1 8.8.8.8 > /dev/null 2>&1 && echo "✅ Internet: Connected" || echo "❌ Internet: Disconnected"

echo ""
echo "🗄️ Database Status:"
if [ -f /opt/elderly_companion/data/privacy.db ]; then
    DB_SIZE=$(ls -lh /opt/elderly_companion/data/privacy.db | awk '{print $5}')
    echo "✅ Privacy Database: $DB_SIZE"
else
    echo "❌ Privacy Database: Not found"
fi

echo ""
echo "📈 Recent Logs (last 10 lines):"
sudo journalctl -u elderly-companion-router-agent --no-pager -n 5 | tail -5
MONITOR_EOF

        chmod +x /opt/elderly_companion/scripts/monitor_system.sh
        
        # Create monitoring cron job
        (crontab -l 2>/dev/null; echo "*/5 * * * * /opt/elderly_companion/scripts/monitor_system.sh >> /var/log/elderly_companion/system_monitor.log 2>&1") | crontab -
        
        echo "✅ System monitoring configured"
EOF
}

# Function to create backup system
setup_backup_system() {
    echo_info "Setting up backup system..."
    
    ssh ${RK3588_USER}@${RK3588_HOST} << 'EOF'
        # Create backup script
        cat > /opt/elderly_companion/scripts/backup_system.sh << 'BACKUP_EOF'
#!/bin/bash

BACKUP_DIR="/opt/elderly_companion/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="elderly_companion_backup_$TIMESTAMP.tar.gz"

echo "📦 Creating system backup..."

mkdir -p $BACKUP_DIR

# Backup essential data
tar -czf $BACKUP_DIR/$BACKUP_FILE \
    /opt/elderly_companion/data/privacy.db \
    /opt/elderly_companion/config/ \
    /var/log/elderly_companion/ \
    --exclude='*.log' \
    --exclude='*.tmp'

# Keep only last 7 backups
cd $BACKUP_DIR
ls -t elderly_companion_backup_*.tar.gz | tail -n +8 | xargs -r rm

echo "✅ Backup created: $BACKUP_FILE"
BACKUP_EOF

        chmod +x /opt/elderly_companion/scripts/backup_system.sh
        
        # Schedule daily backups
        (crontab -l 2>/dev/null; echo "0 2 * * * /opt/elderly_companion/scripts/backup_system.sh") | crontab -
        
        echo "✅ Backup system configured"
EOF
}

# Main deployment workflow
main() {
    echo_info "Starting Elderly Companion Robot deployment to RK3588..."
    
    # Pre-deployment checks
    check_rk3588_connection
    check_system_requirements
    
    # Prepare deployment
    echo_info "Preparing deployment package..."
    PACKAGE_PATH=$(prepare_deployment_package)
    
    # Convert models to RKNN
    convert_models_to_rknn
    
    # Deploy to RK3588
    deploy_to_rk3588 $PACKAGE_PATH
    
    # Verify deployment
    if verify_deployment; then
        echo_success "✅ Deployment successful!"
        
        # Setup monitoring and backup
        setup_monitoring
        setup_backup_system
        
        echo ""
        echo "🎉 Elderly Companion Robot deployed successfully to RK3588!"
        echo ""
        echo "📋 Next Steps:"
        echo "  1. Configure emergency contacts in /opt/elderly_companion/config/emergency_contacts.json"
        echo "  2. Set up smart home device connections"
        echo "  3. Install and configure Family Care App on family member devices"
        echo "  4. Run safety validation tests: /opt/elderly_companion/scripts/run_safety_tests.sh"
        echo "  5. Conduct elderly user acceptance testing"
        echo ""
        echo "📞 Support: Check /var/log/elderly_companion/ for system logs"
        echo "🔧 Monitoring: /opt/elderly_companion/scripts/monitor_system.sh"
        echo "💾 Backup: /opt/elderly_companion/scripts/backup_system.sh"
        
    else
        echo_error "❌ Deployment verification failed"
        echo "Please check the logs and try again"
        exit 1
    fi
    
    # Cleanup
    rm -f $PACKAGE_PATH
}

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 [RK3588_IP] [USERNAME]"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy to default IP (192.168.123.15) with user 'elderly'"
    echo "  $0 192.168.1.100                     # Deploy to specific IP"
    echo "  $0 192.168.1.100 myuser             # Deploy to specific IP with custom user"
    echo ""
    echo "Prerequisites:"
    echo "  - RK3588 running Ubuntu 22.04 LTS"
    echo "  - SSH access configured"
    echo "  - At least 8GB free disk space"
    echo "  - At least 4GB RAM"
    exit 0
fi

# Run main deployment
main "$@"