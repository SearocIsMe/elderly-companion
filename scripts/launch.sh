#!/bin/bash
# Enhanced Elderly Companion - Launch Script  
# Launches the complete system with FastAPI services

set -e

echo "🚀 LAUNCHING ENHANCED ELDERLY COMPANION SYSTEM"
echo "==============================================="

# Check if workspace is built
if [ ! -f "install/setup.bash" ]; then
    echo "❌ Workspace not built. Run ./scripts/build.sh first"
    exit 1
fi

# 1. Start FastAPI services if available
echo "🔧 Starting FastAPI services..."
DOCKER_COMPOSE_FILE="src/router_agent/router_agent/docker/docker-compose.pc.yml"

if [ -f "$DOCKER_COMPOSE_FILE" ] && command -v docker-compose &> /dev/null; then
    echo "Starting Docker services..."
    cd src/router_agent/router_agent/docker
    docker compose -f docker-compose.pc.yml up -d || echo "⚠️ Docker services failed, continuing..."
    cd ../../../..
    sleep 5
    
    # Test services
    echo "🔍 Testing FastAPI services..."
    for service in localhost:7010/health localhost:7002/health localhost:7001/health localhost:7003/health; do
        if curl -s "http://$service" &> /dev/null; then
            echo "✅ Service http://$service is ready"
        else
            echo "⚠️ Service http://$service not responding"
        fi
    done
else
    echo "⚠️ Docker not available, running without FastAPI services"
fi

# 2. Setup clean environment (avoiding conda conflicts)
echo "🔧 Setting up clean environment..."
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# 3. Source workspace
echo "📦 Sourcing workspace..."
source install/setup.bash

# 4. Launch system
echo ""
echo "✅ Launching Enhanced Elderly Companion System..."
echo "   📢 Expected: Some nodes may show warnings for missing optional packages"
echo "   📢 This is normal - core functionality will work with mock implementations"
echo ""

# Launch with hybrid mode (both text and audio if available)
ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=hybrid