
#!/bin/bash
# Fix conflicting ROS repository key configuration
# Resolving conflicting ROS repository configuration

echo "Step 1: Remove problematic .sources file..."
sudo rm -f /etc/apt/sources.list.d/ros2.sources
echo -e "\nStep 2: Create properly formatted repository entry..."
echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg arch=amd64] http://packages.ros.org/ros2/ubuntu jammy main" | sudo tee /etc/apt/sources.list.d/ros2.list
echo -e "\nStep 3: Verify repository configuration..."
cat /etc/apt/sources.list.d/ros2.list
echo -e "\nStep 4: Clean and update package lists..."
sudo apt clean
sudo rm -rf /var/lib/apt/lists/*
sudo apt update
echo -e "\nStep 5: Install net-tools..."
sudo apt install -y net-tools