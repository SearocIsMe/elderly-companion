import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Provider as PaperProvider, MD3LightTheme } from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { Alert, Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import messaging from '@react-native-firebase/messaging';
import { Ionicons } from '@expo/vector-icons';

// Screen imports
import DashboardScreen from './src/screens/DashboardScreen';
import EmergencyScreen from './src/screens/EmergencyScreen';
import HealthScreen from './src/screens/HealthScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import VideoCallScreen from './src/screens/VideoCallScreen';

// Service imports
import { NotificationService } from './src/services/NotificationService';
import { RobotConnectionService } from './src/services/RobotConnectionService';
import { EmergencyService } from './src/services/EmergencyService';

// Context imports
import { AppProvider } from './src/context/AppContext';

const Tab = createBottomTabNavigator();

// Custom theme for elderly care app
const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#2E7D32',      // Calming green
    secondary: '#FF5722',    // Emergency orange
    surface: '#F5F5F5',     // Light background
    background: '#FFFFFF',
    error: '#D32F2F',       // Clear error red
  },
};

export default function App() {
  const [isInitialized, setIsInitialized] = useState(false);
  const [emergencyAlert, setEmergencyAlert] = useState<any>(null);

  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      console.log('🚀 Initializing Elderly Companion Family App...');

      // Initialize notification service
      await NotificationService.initialize();
      
      // Initialize robot connection
      await RobotConnectionService.initialize();
      
      // Set up emergency notifications
      await setupEmergencyNotifications();
      
      // Check permissions
      await checkAndRequestPermissions();
      
      setIsInitialized(true);
      console.log('✅ App initialization complete');
      
    } catch (error) {
      console.error('❌ App initialization failed:', error);
      Alert.alert(
        'Initialization Error',
        'Failed to initialize the app. Please restart and try again.',
        [{ text: 'OK' }]
      );
    }
  };

  const setupEmergencyNotifications = async () => {
    try {
      // Request permission for notifications
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (!enabled) {
        console.warn('⚠️ Notification permission not granted');
        return;
      }

      // Get FCM token
      const fcmToken = await messaging().getToken();
      console.log('📱 FCM Token:', fcmToken);
      
      // Save token for robot to use
      await AsyncStorage.setItem('fcm_token', fcmToken);

      // Handle foreground messages
      messaging().onMessage(async remoteMessage => {
        console.log('📨 Foreground notification:', remoteMessage);
        
        if (remoteMessage.data?.emergency === 'true') {
          handleEmergencyNotification(remoteMessage);
        }
      });

      // Handle background/quit state messages
      messaging().setBackgroundMessageHandler(async remoteMessage => {
        console.log('📨 Background notification:', remoteMessage);
        
        if (remoteMessage.data?.emergency === 'true') {
          // Store emergency for when app opens
          await AsyncStorage.setItem('pending_emergency', JSON.stringify(remoteMessage));
        }
      });

    } catch (error) {
      console.error('❌ Emergency notification setup failed:', error);
    }
  };

  const handleEmergencyNotification = (notification: any) => {
    const emergencyData = {
      type: notification.data?.emergency_type || 'unknown',
      severity: parseInt(notification.data?.severity || '1'),
      timestamp: notification.data?.timestamp || new Date().toISOString(),
      description: notification.body || 'Emergency detected',
      videoStreamUrl: notification.data?.video_stream_url,
    };

    setEmergencyAlert(emergencyData);

    // Show immediate alert
    Alert.alert(
      '🚨 EMERGENCY ALERT',
      `${emergencyData.description}\n\nType: ${emergencyData.type}\nSeverity: ${emergencyData.severity}/4`,
      [
        {
          text: 'View Details',
          onPress: () => {
            // Navigate to emergency screen
            // This would be handled by navigation ref
          }
        },
        {
          text: 'Call Now',
          onPress: () => {
            EmergencyService.initiateEmergencyCall(emergencyData);
          }
        }
      ],
      { cancelable: false }
    );
  };

  const checkAndRequestPermissions = async () => {
    try {
      // This would check and request necessary permissions
      // - Camera (for video calls)
      // - Microphone (for voice calls)
      // - Notifications
      // - Location (if needed)
      console.log('✅ Permissions checked');
    } catch (error) {
      console.error('❌ Permission check failed:', error);
    }
  };

  if (!isInitialized) {
    // Loading screen would go here
    return null;
  }

  return (
    <AppProvider>
      <PaperProvider theme={theme}>
        <NavigationContainer>
          <StatusBar style="auto" />
          
          <Tab.Navigator
            screenOptions={({ route }) => ({
              tabBarIcon: ({ focused, color, size }) => {
                let iconName: keyof typeof Ionicons.glyphMap;

                if (route.name === 'Dashboard') {
                  iconName = focused ? 'home' : 'home-outline';
                } else if (route.name === 'Emergency') {
                  iconName = focused ? 'alert-circle' : 'alert-circle-outline';
                } else if (route.name === 'Health') {
                  iconName = focused ? 'fitness' : 'fitness-outline';
                } else if (route.name === 'Video') {
                  iconName = focused ? 'videocam' : 'videocam-outline';
                } else if (route.name === 'Settings') {
                  iconName = focused ? 'settings' : 'settings-outline';
                } else {
                  iconName = 'ellipse';
                }

                return <Ionicons name={iconName} size={size} color={color} />;
              },
              tabBarActiveTintColor: theme.colors.primary,
              tabBarInactiveTintColor: 'gray',
              tabBarStyle: {
                backgroundColor: theme.colors.surface,
                borderTopColor: theme.colors.outline,
              },
              headerStyle: {
                backgroundColor: theme.colors.primary,
              },
              headerTintColor: '#FFFFFF',
              headerTitleStyle: {
                fontWeight: 'bold',
              },
            })}
          >
            <Tab.Screen 
              name="Dashboard" 
              component={DashboardScreen}
              options={{ 
                title: '首页',
                headerTitle: 'Elderly Companion Monitor'
              }}
            />
            <Tab.Screen 
              name="Emergency" 
              component={EmergencyScreen}
              options={{ 
                title: '紧急',
                headerTitle: 'Emergency Status',
                tabBarBadge: emergencyAlert ? '!' : undefined,
                tabBarBadgeStyle: { backgroundColor: theme.colors.error }
              }}
            />
            <Tab.Screen 
              name="Health" 
              component={HealthScreen}
              options={{ 
                title: '健康',
                headerTitle: 'Health Monitoring'
              }}
            />
            <Tab.Screen 
              name="Video" 
              component={VideoCallScreen}
              options={{ 
                title: '视频',
                headerTitle: 'Video Communication'
              }}
            />
            <Tab.Screen 
              name="Settings" 
              component={SettingsScreen}
              options={{ 
                title: '设置',
                headerTitle: 'Settings'
              }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </PaperProvider>
    </AppProvider>
  );
}