/**
 * Robot Connection Service for Elderly Companion Family App
 * Handles real-time communication with the robot system via WebSocket and MQTT
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { io, Socket } from 'socket.io-client';

export interface RobotStatus {
  online: boolean;
  batteryLevel: number;
  currentLocation: string;
  currentActivity: string;
  lastUpdateTime: string;
  systemHealth: {
    audioSystem: boolean;
    motionSystem: boolean;
    networkConnection: boolean;
    emergencySystem: boolean;
  };
}

export interface ElderlyStatus {
  lastInteraction: string;
  currentMood: string;
  activityLevel: string;
  healthIndicators: {
    stressLevel: number;
    communicationFrequency: number;
    mobilityLevel: number;
  };
  dailyStats: {
    conversationsToday: number;
    emergenciesThisWeek: number;
    lastHealthCheck: string;
  };
}

export interface RobotCommand {
  type: 'check_status' | 'send_message' | 'emergency_test' | 'health_check';
  parameters?: Record<string, any>;
  timestamp: string;
}

class RobotConnectionServiceClass {
  private socket: Socket | null = null;
  private connected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectInterval = 5000; // 5 seconds

  private statusCallbacks: Set<(status: RobotStatus) => void> = new Set();
  private elderlyStatusCallbacks: Set<(status: ElderlyStatus) => void> = new Set();
  private emergencyCallbacks: Set<(alert: any) => void> = new Set();

  /**
   * Initialize robot connection service
   */
  async initialize(): Promise<void> {
    try {
      console.log('🤖 Initializing Robot Connection Service...');
      
      // Get robot connection settings
      const robotConfig = await this.loadRobotConfig();
      
      // Establish WebSocket connection
      await this.connectToRobot(robotConfig);
      
      console.log('✅ Robot Connection Service initialized');
    } catch (error) {
      console.error('❌ Robot Connection Service initialization failed:', error);
      throw error;
    }
  }

  /**
   * Load robot configuration
   */
  private async loadRobotConfig(): Promise<any> {
    try {
      const config = await AsyncStorage.getItem('robot_config');
      if (config) {
        return JSON.parse(config);
      }
      
      // Default configuration
      return {
        serverUrl: 'ws://192.168.1.100:8080', // Robot's WebSocket server
        mqttBroker: '192.168.1.100:1883',
        robotId: 'elderly_companion_001',
        familyId: 'family_001',
        apiKey: 'family_api_key_placeholder'
      };
    } catch (error) {
      console.error('❌ Robot config loading error:', error);
      return {};
    }
  }

  /**
   * Connect to robot via WebSocket
   */
  private async connectToRobot(config: any): Promise<void> {
    try {
      const socketUrl = config.serverUrl || 'ws://localhost:8080';
      
      this.socket = io(socketUrl, {
        transports: ['websocket'],
        timeout: 10000,
        reconnection: true,
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectInterval,
        auth: {
          familyId: config.familyId,
          robotId: config.robotId,
          apiKey: config.apiKey
        }
      });

      this.setupSocketEventHandlers();
      
    } catch (error) {
      console.error('❌ Robot connection error:', error);
      throw error;
    }
  }

  /**
   * Setup Socket.IO event handlers
   */
  private setupSocketEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('✅ Connected to robot');
      this.connected = true;
      this.reconnectAttempts = 0;
      
      // Subscribe to robot data streams
      this.socket?.emit('subscribe', {
        topics: ['robot_status', 'elderly_status', 'emergency_alerts', 'health_updates']
      });
    });

    this.socket.on('disconnect', (reason) => {
      console.log(`❌ Disconnected from robot: ${reason}`);
      this.connected = false;
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ Robot connection error:', error);
      this.reconnectAttempts++;
      
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('❌ Max reconnection attempts reached');
      }
    });

    // Robot status updates
    this.socket.on('robot_status', (data: RobotStatus) => {
      this.statusCallbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Status callback error:', error);
        }
      });
    });

    // Elderly status updates
    this.socket.on('elderly_status', (data: ElderlyStatus) => {
      this.elderlyStatusCallbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Elderly status callback error:', error);
        }
      });
    });

    // Emergency alerts
    this.socket.on('emergency_alert', (data: any) => {
      console.log('🚨 Emergency alert received from robot:', data);
      
      this.emergencyCallbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Emergency callback error:', error);
        }
      });
    });

    // Health updates
    this.socket.on('health_update', (data: any) => {
      console.log('🏥 Health update received:', data);
      // Handle health updates
    });

    // Robot responses
    this.socket.on('command_response', (data: any) => {
      console.log('🤖 Robot command response:', data);
      // Handle command responses
    });
  }

  /**
   * Subscribe to robot status updates
   */
  onRobotStatusUpdate(callback: (status: RobotStatus) => void): () => void {
    this.statusCallbacks.add(callback);
    
    return () => {
      this.statusCallbacks.delete(callback);
    };
  }

  /**
   * Subscribe to elderly status updates
   */
  onElderlyStatusUpdate(callback: (status: ElderlyStatus) => void): () => void {
    this.elderlyStatusCallbacks.add(callback);
    
    return () => {
      this.elderlyStatusCallbacks.delete(callback);
    };
  }

  /**
   * Subscribe to emergency alerts
   */
  onEmergencyAlert(callback: (alert: any) => void): () => void {
    this.emergencyCallbacks.add(callback);
    
    return () => {
      this.emergencyCallbacks.delete(callback);
    };
  }

  /**
   * Get current robot status
   */
  async getRobotStatus(): Promise<RobotStatus | null> {
    try {
      if (!this.connected || !this.socket) {
        return this.getMockRobotStatus();
      }

      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Robot status request timeout'));
        }, 5000);

        this.socket?.emit('get_robot_status', {}, (response: any) => {
          clearTimeout(timeout);
          if (response.success) {
            resolve(response.data);
          } else {
            reject(new Error(response.error));
          }
        });
      });
    } catch (error) {
      console.error('❌ Robot status request error:', error);
      return this.getMockRobotStatus();
    }
  }

  /**
   * Get current elderly status
   */
  async getElderlyStatus(): Promise<ElderlyStatus | null> {
    try {
      if (!this.connected || !this.socket) {
        return this.getMockElderlyStatus();
      }

      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Elderly status request timeout'));
        }, 5000);

        this.socket?.emit('get_elderly_status', {}, (response: any) => {
          clearTimeout(timeout);
          if (response.success) {
            resolve(response.data);
          } else {
            reject(new Error(response.error));
          }
        });
      });
    } catch (error) {
      console.error('❌ Elderly status request error:', error);
      return this.getMockElderlyStatus();
    }
  }

  /**
   * Send command to robot
   */
  async sendCommand(command: RobotCommand): Promise<boolean> {
    try {
      if (!this.connected || !this.socket) {
        console.warn('⚠️ Robot not connected, command not sent');
        return false;
      }

      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          resolve(false);
        }, 10000);

        this.socket?.emit('robot_command', command, (response: any) => {
          clearTimeout(timeout);
          resolve(response.success || false);
        });
      });
    } catch (error) {
      console.error('❌ Command sending error:', error);
      return false;
    }
  }

  /**
   * Send emergency response
   */
  async sendEmergencyResponse(response: any): Promise<boolean> {
    try {
      if (!this.connected || !this.socket) {
        console.warn('⚠️ Robot not connected, emergency response not sent');
        return false;
      }

      this.socket.emit('emergency_response', response);
      return true;
    } catch (error) {
      console.error('❌ Emergency response sending error:', error);
      return false;
    }
  }

  /**
   * Get mock robot status for development
   */
  private getMockRobotStatus(): RobotStatus {
    return {
      online: true,
      batteryLevel: 0.75,
      currentLocation: 'Living Room',
      currentActivity: 'Standby',
      lastUpdateTime: new Date().toISOString(),
      systemHealth: {
        audioSystem: true,
        motionSystem: true,
        networkConnection: true,
        emergencySystem: true,
      },
    };
  }

  /**
   * Get mock elderly status for development
   */
  private getMockElderlyStatus(): ElderlyStatus {
    return {
      lastInteraction: new Date().toISOString(),
      currentMood: 'neutral',
      activityLevel: 'normal',
      healthIndicators: {
        stressLevel: 0.3,
        communicationFrequency: 0.7,
        mobilityLevel: 0.8,
      },
      dailyStats: {
        conversationsToday: 8,
        emergenciesThisWeek: 0,
        lastHealthCheck: new Date().toISOString(),
      },
    };
  }

  /**
   * Check connection status
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Disconnect from robot
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.connected = false;
    }
  }
}

export const RobotConnectionService = new RobotConnectionServiceClass();