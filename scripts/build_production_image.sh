#!/bin/bash
"""
Production Build Script - Build executables on host, copy to container.

This script builds the ROS2 workspace on the host machine and creates
a production container with pre-compiled binaries.
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏗️  Building Elderly Companion Production Image${NC}"
echo "=============================================="

# Check if ROS2 is available on host
if ! command -v ros2 &> /dev/null; then
    echo -e "${RED}❌ ROS2 not found on host machine${NC}"
    echo "Please install ROS2 Humble: https://docs.ros.org/en/humble/Installation/"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}📂 Project root: $PROJECT_ROOT${NC}"

# Step 1: Build workspace on host
echo -e "${GREEN}🔨 Step 1: Building ROS2 workspace on host...${NC}"
cd "$PROJECT_ROOT"

# Source ROS2
source /opt/ros/humble/setup.bash

# Build workspace
./scripts/build_workspace.sh

# Check if build was successful
if [ ! -d "install" ]; then
    echo -e "${RED}❌ Build failed - no install directory found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Workspace build completed${NC}"

# Step 2: Create production directory structure
echo -e "${GREEN}📦 Step 2: Preparing production build...${NC}"

PROD_DIR="$PROJECT_ROOT/production_build"
rm -rf "$PROD_DIR"
mkdir -p "$PROD_DIR"

# Copy built executables and libraries
cp -r install "$PROD_DIR/"
cp -r src "$PROD_DIR/"
cp package.xml "$PROD_DIR/"
cp CMakeLists.txt "$PROD_DIR/"

# Copy production requirements
cp requirements.txt "$PROD_DIR/"

echo -e "${GREEN}✅ Production files prepared${NC}"

# Step 3: Build production container
echo -e "${GREEN}🐳 Step 3: Building production container...${NC}"

# Create production Dockerfile if it doesn't exist
if [ ! -f "docker/production/Dockerfile" ]; then
    echo -e "${YELLOW}📝 Creating production Dockerfile...${NC}"
    mkdir -p docker/production
    cat > docker/production/Dockerfile << 'EOF'
# Production Dockerfile - Uses pre-compiled binaries
FROM ros:humble-ros-base-jammy

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-rosdep \
    ros-humble-nav2-common \
    ros-humble-nav2-msgs \
    ros-humble-tf2 \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-rosbridge-library \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

# Create workspace directory
WORKDIR /workspace

# Copy pre-compiled binaries and source
COPY production_build/ /workspace/

# Source ROS2 setup
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /workspace/install/setup.bash" >> ~/.bashrc

# Set entrypoint
COPY docker/production/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
EOF
fi

# Create entrypoint script
cat > docker/production/entrypoint.sh << 'EOF'
#!/bin/bash
set -e

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash

# Execute the command
exec "$@"
EOF

# Build the production image
docker build -f docker/production/Dockerfile -t elderly-companion:latest .

echo -e "${GREEN}✅ Production container built successfully${NC}"

# Step 4: Test the production container
echo -e "${GREEN}🧪 Step 4: Testing production container...${NC}"

# Test if ROS2 nodes can be found in the container
docker run --rm elderly-companion:latest ros2 pkg list | grep elderly_companion

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Production container test passed${NC}"
else
    echo -e "${RED}❌ Production container test failed${NC}"
    exit 1
fi

# Cleanup
rm -rf "$PROD_DIR"

echo ""
echo -e "${GREEN}🎉 Production build completed successfully!${NC}"
echo ""
echo "To run the production container:"
echo "  docker run -it elderly-companion:latest"
echo ""
echo "To run specific nodes:"
echo "  docker run --rm elderly-companion:latest ros2 run elderly_companion <node_name>"
echo ""