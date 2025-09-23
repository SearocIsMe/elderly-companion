FROM osrf/ros:humble-desktop-full

# Install additional dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    git \
    curl \
    wget \
    build-essential \
    cmake \
    libasound2-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3 \
    gstreamer1.0-qt5 \
    gstreamer1.0-pulseaudio \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for elderly companion system
RUN pip3 install \
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

# Install additional ROS2 packages
RUN apt-get update && apt-get install -y \
    ros-humble-nav2-bringup \
    ros-humble-navigation2 \
    ros-humble-nav2-map-server \
    ros-humble-nav2-amcl \
    ros-humble-turtlebot3* \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-cartographer \
    ros-humble-cartographer-ros \
    ros-humble-robot-localization \
    ros-humble-rmw-cyclonedx-cpp \
    ros-humble-rosbridge-suite \
    ros-humble-mqtt-client \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace
WORKDIR /workspace

# Initialize rosdep
RUN rosdep init || true
RUN rosdep update

# Set up ROS2 environment
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /workspace/install/setup.bash" >> ~/.bashrc || true

# Set default RMW implementation
ENV RMW_IMPLEMENTATION=rmw_cyclonedx_cpp

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /workspace/install/setup.bash ]; then\n\
    source /workspace/install/setup.bash\n\
fi\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]