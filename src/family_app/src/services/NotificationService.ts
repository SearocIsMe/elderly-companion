/**
 * Notification Service for Elderly Companion Family App
 * Handles push notifications, local notifications, and emergency alerts
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import messaging from '@react-native-firebase/messaging';
import PushNotification from 'react-native-push-notification';

export interface NotificationPayload {
  title: string;
  body: string;
  data?: Record<string, any>;
  priority?: 'high' | 'normal';
  emergency?: boolean;
}

class NotificationServiceClass {
  private initialized = false;

  /**
   * Initialize notification service
   */
  async initialize(): Promise<void> {
    try {
      console.log('🔔 Initializing Notification Service...');
      
      // Configure local notifications
      PushNotification.configure({
        onRegister: (token) => {
          console.log('📱 Push notification token:', token);
        },
        onNotification: (notification) => {
          console.log('📨 Local notification:', notification);
        },
        permissions: {
          alert: true,
          badge: true,
          sound: true,
        },
        popInitialNotification: true,
        requestPermissions: true,
      });

      // Request notification permissions
      await this.requestPermissions();
      
      this.initialized = true;
      console.log('✅ Notification Service initialized');
    } catch (error) {
      console.error('❌ Notification Service initialization failed:', error);
      throw error;
    }
  }

  /**
   * Request notification permissions
   */
  private async requestPermissions(): Promise<boolean> {
    try {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (enabled) {
        console.log('✅ Notification permissions granted');
        
        // Get FCM token
        const token = await messaging().getToken();
        await AsyncStorage.setItem('fcm_token', token);
        
        return true;
      } else {
        console.warn('⚠️ Notification permissions denied');
        return false;
      }
    } catch (error) {
      console.error('❌ Permission request error:', error);
      return false;
    }
  }

  /**
   * Send emergency notification
   */
  async sendEmergencyNotification(payload: NotificationPayload): Promise<void> {
    try {
      // High priority local notification for emergencies
      PushNotification.localNotification({
        title: payload.title,
        message: payload.body,
        priority: 'high',
        vibrate: true,
        vibration: 1000,
        playSound: true,
        soundName: 'emergency_alert.mp3',
        importance: 'high',
        allowWhileIdle: true,
        ignoreInForeground: false,
        userInfo: payload.data,
      });

      console.log('🚨 Emergency notification sent');
    } catch (error) {
      console.error('❌ Emergency notification error:', error);
    }
  }

  /**
   * Send regular notification
   */
  async sendNotification(payload: NotificationPayload): Promise<void> {
    try {
      PushNotification.localNotification({
        title: payload.title,
        message: payload.body,
        priority: payload.priority || 'normal',
        userInfo: payload.data,
      });

      console.log('📨 Notification sent');
    } catch (error) {
      console.error('❌ Notification error:', error);
    }
  }

  /**
   * Clear all notifications
   */
  clearAllNotifications(): void {
    PushNotification.cancelAllLocalNotifications();
  }

  /**
   * Get FCM token
   */
  async getFCMToken(): Promise<string | null> {
    try {
      return await AsyncStorage.getItem('fcm_token');
    } catch (error) {
      console.error('❌ FCM token retrieval error:', error);
      return null;
    }
  }
}

export const NotificationService = new NotificationServiceClass();