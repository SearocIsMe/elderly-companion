# Elderly Companion Robdog

A comprehensive elderly care robotics system built on Unitree Go2 platform with RK3588 edge computing.

## System Overview

The Elderly Companion Robdog is an intelligent quadruped robot designed specifically for elderly care, featuring:

- **Router Agent (RK3588)**: AI-powered conversation and safety monitoring
- **Action Agent (ROS2)**: Motion control and navigation 
- **Family Care App**: Real-time monitoring and emergency alerts
- **Emergency Response**: <200ms response time for safety incidents

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│   Family Care   │    │   Router Agent   │    │  Action Agent  │
│   Mobile App    │◄──►│    (RK3588)      │◄──►│    (ROS2)      │
└─────────────────┘    └──────────────────┘    └────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌─────────────┐         ┌────────────────┐
                       │ Smart Home  │         │  Unitree Go2   │
                       │  Ecosystem  │         │   Platform     │
                       └─────────────┘         └────────────────┘
```

## Key Features

### Phase 1 (MVP)
- [x] Smart home voice control
- [x] Emergency response system
- [x] Emotional companionship AI
- [x] Family monitoring app

### Phase 2 (Advanced)
- [ ] Memory bank system
- [ ] Outdoor following capabilities
- [ ] Advanced emotion recognition

### Phase 3 (Community)
- [ ] Healthcare provider integration
- [ ] Community care ecosystem
- [ ] Predictive health monitoring

## Development Setup

### Prerequisites
- Ubuntu 22.04 LTS
- Docker & Docker Compose
- ROS 2 Humble Hawksbill
- Python 3.10+
- Node.js 18+

### Quick Start

#### Step 1: Setup Project (Host Machine)
```bash
# Clone the repository
git clone <repository-url>
cd elderly-companion

# Setup development environment (host)
./scripts/setup_dev_env.sh
```

#### Step 2: Start Services (Host Machine)
```bash
# Start all development services
docker-compose up -d

# Verify all containers are running
docker ps
```

You should see 5 containers running:
- `robdog-ros2-dev` - ROS2 development environment
- `robdog-mqtt` - MQTT broker (ports 1883, 9001)
- `robdog-mediamtx` - Media streaming (ports 1935, 8554, 8888-8889)
- `robdog-redis-dev` - Redis cache (port 6379)
- `robdog-ollama-dev` - Ollama LLM server (port 11434)

#### Step 3: Build ROS2 Workspace (Inside Container)
```bash
# Enter the ROS2 development container
docker exec -it robdog-ros2-dev bash

# Inside the container, build the workspace
cd /workspace
source /opt/ros/humble/setup.bash
./scripts/build_workspace.sh

# Exit the container
exit
```

#### Step 4: Run Tests (Inside Container)
```bash
# Enter the container and run tests
docker exec -it robdog-ros2-dev bash -c "cd /workspace && ./scripts/run_tests.sh"
```

#### Alternative: One-line Commands
```bash
# Build workspace (from host)
docker exec robdog-ros2-dev bash -c "cd /workspace && ./scripts/build_workspace.sh"

# Run tests (from host)
docker exec robdog-ros2-dev bash -c "cd /workspace && ./scripts/run_tests.sh"
```

### Troubleshooting

If you encounter container conflicts:
```bash
# Stop and remove all containers
docker-compose down

# Remove old containers if needed
docker container prune

# Restart services
docker-compose up -d
```


## Project Structure

```
elderly-companion/
├── src/                     # Source code
│   ├── router_agent/        # Router Agent (RK3588)
│   ├── action_agent/        # Action Agent (ROS2)
│   ├── family_app/          # Family Care Mobile App
│   ├── shared/              # Shared libraries and utilities
│   └── tests/               # Test suites
├── config/                  # Configuration files
├── scripts/                 # Build and deployment scripts
├── docker/                  # Docker containers
├── docs/                    # Documentation
└── deployment/              # Deployment manifests
```

## Safety & Privacy

This system is designed with **Safety-First** and **Privacy-by-Design** principles:

- Local AI processing (edge-first)
- End-to-end encryption for family communications
- <200ms emergency response time
- HIPAA-compliant data handling
- Elderly-optimized motion constraints

## Contributing

Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

For questions and support, please see [docs/SUPPORT.md](docs/SUPPORT.md).