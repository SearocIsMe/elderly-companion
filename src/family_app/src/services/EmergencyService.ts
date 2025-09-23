/**
 * Emergency Service for Elderly Companion Family App
 * Handles emergency alerts, notifications, and response coordination
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert, Linking } from 'react-native';
import { NotificationService } from './NotificationService';
import { RobotConnectionService } from './RobotConnectionService';

export interface EmergencyAlert {
  id: string;
  type: 'medical' | 'fall' | 'sos' | 'security' | 'system_failure';
  severity: 1 | 2 | 3 | 4;
  timestamp: string;
  description: string;
  location?: string;
  elderlyPersonStatus?: {
    responsive: boolean;
    position?: { x: number; y: number };
    lastSeen?: string;
  };
  robotStatus?: {
    position?: { x: number; y: number };
    batteryLevel?: number;
    connectionStatus: 'connected' | 'disconnected';
  };
  videoStreamUrl?: string;
  audioRecordingUrl?: string;
  emergencyContacts?: {
    contacted: string[];
    responded: string[];
    eta?: string;
  };
  resolved: boolean;
  resolvedBy?: string;
  resolvedAt?: string;
}

export interface EmergencyResponse {
  alertId: string;
  responseType: 'acknowledged' | 'en_route' | 'resolved';
  responderId: string;
  responderName: string;
  timestamp: string;
  notes?: string;
  eta?: string;
}

class EmergencyServiceClass {
  private activeAlerts: Map<string, EmergencyAlert> = new Map();
  private alertHistory: EmergencyAlert[] = [];
  private emergencyCallbacks: Set<(alert: EmergencyAlert) => void> = new Set();

  /**
   * Initialize emergency service
   */
  async initialize(): Promise<void> {
    try {
      console.log('🚨 Initializing Emergency Service...');
      
      // Load any pending emergencies from storage
      await this.loadPendingEmergencies();
      
      // Set up real-time connection to robot emergency system
      await this.setupEmergencyConnection();
      
      console.log('✅ Emergency Service initialized');
    } catch (error) {
      console.error('❌ Emergency Service initialization failed:', error);
      throw error;
    }
  }

  /**
   * Register callback for emergency alerts
   */
  onEmergencyAlert(callback: (alert: EmergencyAlert) => void): () => void {
    this.emergencyCallbacks.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.emergencyCallbacks.delete(callback);
    };
  }

  /**
   * Handle incoming emergency alert
   */
  async handleEmergencyAlert(alertData: any): Promise<void> {
    try {
      const alert: EmergencyAlert = {
        id: alertData.id || `emergency_${Date.now()}`,
        type: alertData.type || 'medical',
        severity: alertData.severity || 3,
        timestamp: alertData.timestamp || new Date().toISOString(),
        description: alertData.description || 'Emergency detected by robot',
        location: alertData.location,
        elderlyPersonStatus: alertData.elderlyPersonStatus,
        robotStatus: alertData.robotStatus,
        videoStreamUrl: alertData.videoStreamUrl,
        audioRecordingUrl: alertData.audioRecordingUrl,
        emergencyContacts: alertData.emergencyContacts,
        resolved: false,
      };

      // Store alert
      this.activeAlerts.set(alert.id, alert);
      await this.saveAlertsToStorage();

      // Notify all registered callbacks
      this.emergencyCallbacks.forEach(callback => {
        try {
          callback(alert);
        } catch (error) {
          console.error('Emergency callback error:', error);
        }
      });

      // Show immediate notification
      await this.showEmergencyNotification(alert);

      // Log emergency
      console.log(`🚨 EMERGENCY ALERT: ${alert.type} (Severity: ${alert.severity})`);
      
    } catch (error) {
      console.error('❌ Emergency alert handling error:', error);
    }
  }

  /**
   * Show emergency notification to user
   */
  private async showEmergencyNotification(alert: EmergencyAlert): Promise<void> {
    try {
      const severityText = ['Low', 'Medium', 'High', 'CRITICAL'][alert.severity - 1];
      const emergencyIcon = this.getEmergencyIcon(alert.type);
      
      Alert.alert(
        `${emergencyIcon} EMERGENCY ALERT`,
        `${alert.description}\n\nType: ${alert.type.toUpperCase()}\nSeverity: ${severityText}\nTime: ${new Date(alert.timestamp).toLocaleString()}`,
        [
          {
            text: 'View Live Video',
            onPress: () => this.openVideoStream(alert),
            style: 'default'
          },
          {
            text: 'Call Emergency Services',
            onPress: () => this.callEmergencyServices(alert),
            style: 'destructive'
          },
          {
            text: "I'm On My Way",
            onPress: () => this.acknowledgeEmergency(alert),
            style: 'default'
          }
        ],
        { cancelable: false }
      );

      // Also send local notification
      await NotificationService.sendEmergencyNotification({
        title: `${emergencyIcon} Emergency Alert`,
        body: alert.description,
        data: { alertId: alert.id, emergency: 'true' }
      });

    } catch (error) {
      console.error('❌ Emergency notification display error:', error);
    }
  }

  /**
   * Get appropriate icon for emergency type
   */
  private getEmergencyIcon(type: string): string {
    const icons = {
      medical: '🏥',
      fall: '🆘',
      sos: '🚨',
      security: '🔒',
      system_failure: '⚠️'
    };
    return icons[type as keyof typeof icons] || '🚨';
  }

  /**
   * Open video stream for emergency
   */
  async openVideoStream(alert: EmergencyAlert): Promise<void> {
    try {
      if (alert.videoStreamUrl) {
        const supported = await Linking.canOpenURL(alert.videoStreamUrl);
        if (supported) {
          await Linking.openURL(alert.videoStreamUrl);
        } else {
          Alert.alert('Error', 'Cannot open video stream');
        }
      } else {
        Alert.alert('Video Unavailable', 'No video stream available for this emergency');
      }
    } catch (error) {
      console.error('❌ Video stream opening error:', error);
      Alert.alert('Error', 'Failed to open video stream');
    }
  }

  /**
   * Call emergency services
   */
  async callEmergencyServices(alert: EmergencyAlert): Promise<void> {
    try {
      const emergencyNumber = '911'; // Would be configurable based on location
      const phoneUrl = `tel:${emergencyNumber}`;
      
      const supported = await Linking.canOpenURL(phoneUrl);
      if (supported) {
        await Linking.openURL(phoneUrl);
        
        // Log the emergency call
        console.log(`📞 Emergency services called for alert: ${alert.id}`);
        
        // Update alert with emergency services contact info
        const updatedAlert = {
          ...alert,
          emergencyContacts: {
            ...alert.emergencyContacts,
            contacted: [...(alert.emergencyContacts?.contacted || []), emergencyNumber]
          }
        };
        
        this.activeAlerts.set(alert.id, updatedAlert);
        await this.saveAlertsToStorage();
        
      } else {
        Alert.alert('Error', 'Cannot make phone calls on this device');
      }
    } catch (error) {
      console.error('❌ Emergency services call error:', error);
      Alert.alert('Error', 'Failed to call emergency services');
    }
  }

  /**
   * Acknowledge emergency and indicate response
   */
  async acknowledgeEmergency(alert: EmergencyAlert): Promise<void> {
    try {
      const response: EmergencyResponse = {
        alertId: alert.id,
        responseType: 'acknowledged',
        responderId: 'family_member', // Would be actual user ID
        responderName: 'Family Member', // Would be actual user name
        timestamp: new Date().toISOString(),
        notes: 'Family member acknowledged emergency and responding'
      };

      // Send acknowledgment to robot system
      await RobotConnectionService.sendEmergencyResponse(response);

      // Show ETA input
      Alert.prompt(
        'Emergency Response',
        'How long until you arrive? (minutes)',
        [
          {
            text: 'Cancel',
            style: 'cancel'
          },
          {
            text: 'Send ETA',
            onPress: (etaMinutes) => {
              if (etaMinutes) {
                this.updateEmergencyETA(alert.id, etaMinutes);
              }
            }
          }
        ],
        'plain-text',
        '15'
      );

      console.log(`✅ Emergency acknowledged: ${alert.id}`);
      
    } catch (error) {
      console.error('❌ Emergency acknowledgment error:', error);
      Alert.alert('Error', 'Failed to acknowledge emergency');
    }
  }

  /**
   * Update emergency ETA
   */
  async updateEmergencyETA(alertId: string, etaMinutes: string): Promise<void> {
    try {
      const alert = this.activeAlerts.get(alertId);
      if (!alert) return;

      const eta = new Date(Date.now() + parseInt(etaMinutes) * 60000).toISOString();
      
      const response: EmergencyResponse = {
        alertId: alertId,
        responseType: 'en_route',
        responderId: 'family_member',
        responderName: 'Family Member',
        timestamp: new Date().toISOString(),
        eta: eta
      };

      await RobotConnectionService.sendEmergencyResponse(response);
      
      // Update local alert
      const updatedAlert = {
        ...alert,
        emergencyContacts: {
          ...alert.emergencyContacts,
          responded: [...(alert.emergencyContacts?.responded || []), 'family_member']
        }
      };
      
      this.activeAlerts.set(alertId, updatedAlert);
      await this.saveAlertsToStorage();

    } catch (error) {
      console.error('❌ ETA update error:', error);
    }
  }

  /**
   * Resolve emergency alert
   */
  async resolveEmergency(alertId: string, resolverName: string, notes?: string): Promise<void> {
    try {
      const alert = this.activeAlerts.get(alertId);
      if (!alert) return;

      const resolvedAlert = {
        ...alert,
        resolved: true,
        resolvedBy: resolverName,
        resolvedAt: new Date().toISOString()
      };

      // Move to history
      this.alertHistory.unshift(resolvedAlert);
      this.activeAlerts.delete(alertId);

      // Send resolution to robot
      const response: EmergencyResponse = {
        alertId: alertId,
        responseType: 'resolved',
        responderId: 'family_member',
        responderName: resolverName,
        timestamp: new Date().toISOString(),
        notes: notes
      };

      await RobotConnectionService.sendEmergencyResponse(response);
      await this.saveAlertsToStorage();

      console.log(`✅ Emergency resolved: ${alertId}`);
      
    } catch (error) {
      console.error('❌ Emergency resolution error:', error);
    }
  }

  /**
   * Get active emergency alerts
   */
  getActiveAlerts(): EmergencyAlert[] {
    return Array.from(this.activeAlerts.values()).sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }

  /**
   * Get emergency alert history
   */
  getAlertHistory(): EmergencyAlert[] {
    return this.alertHistory.slice(0, 50); // Last 50 alerts
  }

  /**
   * Load pending emergencies from storage
   */
  private async loadPendingEmergencies(): Promise<void> {
    try {
      const pendingData = await AsyncStorage.getItem('pending_emergency');
      if (pendingData) {
        const emergency = JSON.parse(pendingData);
        await this.handleEmergencyAlert(emergency);
        await AsyncStorage.removeItem('pending_emergency');
      }

      // Load active alerts
      const alertsData = await AsyncStorage.getItem('active_alerts');
      if (alertsData) {
        const alerts = JSON.parse(alertsData);
        alerts.forEach((alert: EmergencyAlert) => {
          this.activeAlerts.set(alert.id, alert);
        });
      }

    } catch (error) {
      console.error('❌ Pending emergencies loading error:', error);
    }
  }

  /**
   * Save alerts to storage
   */
  private async saveAlertsToStorage(): Promise<void> {
    try {
      const activeAlerts = Array.from(this.activeAlerts.values());
      await AsyncStorage.setItem('active_alerts', JSON.stringify(activeAlerts));
      await AsyncStorage.setItem('alert_history', JSON.stringify(this.alertHistory.slice(0, 50)));
    } catch (error) {
      console.error('❌ Alerts storage error:', error);
    }
  }

  /**
   * Setup emergency connection
   */
  private async setupEmergencyConnection(): Promise<void> {
    try {
      // Subscribe to emergency alerts from robot
      RobotConnectionService.onEmergencyAlert((alertData) => {
        this.handleEmergencyAlert(alertData);
      });

    } catch (error) {
      console.error('❌ Emergency connection setup error:', error);
    }
  }

  /**
   * Initiate emergency call
   */
  async initiateEmergencyCall(emergencyData: any): Promise<void> {
    try {
      const phoneNumber = '911'; // Would be configurable
      const phoneUrl = `tel:${phoneNumber}`;
      
      const supported = await Linking.canOpenURL(phoneUrl);
      if (supported) {
        await Linking.openURL(phoneUrl);
      } else {
        Alert.alert('Error', 'Cannot make phone calls on this device');
      }
    } catch (error) {
      console.error('❌ Emergency call initiation error:', error);
    }
  }

  /**
   * Test emergency system
   */
  async testEmergencySystem(): Promise<void> {
    try {
      const testAlert: EmergencyAlert = {
        id: `test_${Date.now()}`,
        type: 'medical',
        severity: 2,
        timestamp: new Date().toISOString(),
        description: 'Emergency system test - this is not a real emergency',
        resolved: false,
        location: 'Test location'
      };

      await this.handleEmergencyAlert(testAlert);
      
      // Auto-resolve test alert after 30 seconds
      setTimeout(() => {
        this.resolveEmergency(testAlert.id, 'System Test');
      }, 30000);

    } catch (error) {
      console.error('❌ Emergency system test error:', error);
    }
  }
}

export const EmergencyService = new EmergencyServiceClass();