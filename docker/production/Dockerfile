# Production Dockerfile - Router Agent with Pre-compiled Binaries
# Uses pre-compiled ROS2 workspace for faster deployment

FROM ros:humble-ros-base-jammy

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-rosdep \
    ros-humble-std-msgs \
    ros-humble-builtin-interfaces \
    ros-humble-rosidl-default-runtime \
    alsa-utils \
    pulseaudio \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python runtime dependencies
RUN pip3 install \
    "empy==3.3.4" \
    speechrecognition \
    pyttsx3 \
    numpy \
    pyyaml

# Create workspace directory
WORKDIR /workspace

# Copy all project files to workspace
COPY . /workspace/

# Ensure Python scripts are executable
RUN chmod +x /workspace/simple_chat_loop.py
RUN chmod +x /workspace/router_agent_chat_test.py

# Create ROS2 environment setup script
RUN echo '#!/bin/bash' > /workspace/setup_env.sh && \
    echo 'source /opt/ros/humble/setup.bash' >> /workspace/setup_env.sh && \
    echo '[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash || echo "Workspace not built yet"' >> /workspace/setup_env.sh && \
    chmod +x /workspace/setup_env.sh

# Source ROS2 setup in bashrc
RUN echo "source /workspace/setup_env.sh" >> ~/.bashrc

# Set entrypoint
COPY docker/production/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports for communication
EXPOSE 11434 1883 8554

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
