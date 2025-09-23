/**
 * Dashboard Screen for Elderly Companion Family App
 * Main monitoring interface for family members
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  RefreshControl,
  Alert,
  Dimensions,
} from 'react-native';
import {
  Card,
  Title,
  Paragraph,
  Button,
  Chip,
  Avatar,
  Surface,
  Divider,
  Badge,
} from 'react-native-paper';
import { LineChart } from 'react-native-chart-kit';

import { EmergencyService, EmergencyAlert } from '../services/EmergencyService';
import { RobotConnectionService } from '../services/RobotConnectionService';

interface RobotStatus {
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

interface ElderlyStatus {
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

const DashboardScreen: React.FC = () => {
  const [robotStatus, setRobotStatus] = useState<RobotStatus>({
    online: false,
    batteryLevel: 0,
    currentLocation: 'Unknown',
    currentActivity: 'Standby',
    lastUpdateTime: '',
    systemHealth: {
      audioSystem: false,
      motionSystem: false,
      networkConnection: false,
      emergencySystem: false,
    },
  });

  const [elderlyStatus, setElderlyStatus] = useState<ElderlyStatus>({
    lastInteraction: '',
    currentMood: 'neutral',
    activityLevel: 'normal',
    healthIndicators: {
      stressLevel: 0,
      communicationFrequency: 0,
      mobilityLevel: 0,
    },
    dailyStats: {
      conversationsToday: 0,
      emergenciesThisWeek: 0,
      lastHealthCheck: '',
    },
  });

  const [activeEmergencies, setActiveEmergencies] = useState<EmergencyAlert[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [moodData, setMoodData] = useState<number[]>([]);

  useEffect(() => {
    initializeDashboard();
    setupRealTimeUpdates();
  }, []);

  const initializeDashboard = async () => {
    try {
      // Load initial data
      await loadRobotStatus();
      await loadElderlyStatus();
      await loadActiveEmergencies();
      await loadMoodTrends();
    } catch (error) {
      console.error('❌ Dashboard initialization error:', error);
    }
  };

  const setupRealTimeUpdates = () => {
    // Set up real-time updates from robot system
    const statusInterval = setInterval(loadRobotStatus, 30000); // Every 30 seconds
    const elderlyInterval = setInterval(loadElderlyStatus, 60000); // Every minute

    // Emergency alert subscription
    const unsubscribeEmergency = EmergencyService.onEmergencyAlert((alert) => {
      setActiveEmergencies(prev => [alert, ...prev]);
    });

    // Cleanup on unmount
    return () => {
      clearInterval(statusInterval);
      clearInterval(elderlyInterval);
      unsubscribeEmergency();
    };
  };

  const loadRobotStatus = async () => {
    try {
      const status = await RobotConnectionService.getRobotStatus();
      setRobotStatus(status || robotStatus);
    } catch (error) {
      console.error('❌ Robot status loading error:', error);
    }
  };

  const loadElderlyStatus = async () => {
    try {
      const status = await RobotConnectionService.getElderlyStatus();
      setElderlyStatus(status || elderlyStatus);
    } catch (error) {
      console.error('❌ Elderly status loading error:', error);
    }
  };

  const loadActiveEmergencies = async () => {
    try {
      const alerts = EmergencyService.getActiveAlerts();
      setActiveEmergencies(alerts);
    } catch (error) {
      console.error('❌ Active emergencies loading error:', error);
    }
  };

  const loadMoodTrends = async () => {
    try {
      // Mock mood trend data - would be loaded from robot
      const mockData = [65, 70, 68, 75, 72, 80, 78]; // Last 7 days mood scores
      setMoodData(mockData);
    } catch (error) {
      console.error('❌ Mood trends loading error:', error);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await initializeDashboard();
    setRefreshing(false);
  };

  const handleEmergencyAction = (alert: EmergencyAlert) => {
    Alert.alert(
      '🚨 Emergency Action',
      `Emergency: ${alert.description}`,
      [
        {
          text: 'View Video',
          onPress: () => EmergencyService.openVideoStream(alert),
        },
        {
          text: 'Call 911',
          onPress: () => EmergencyService.callEmergencyServices(alert),
          style: 'destructive',
        },
        {
          text: "I'm Coming",
          onPress: () => EmergencyService.acknowledgeEmergency(alert),
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const getBatteryColor = (level: number): string => {
    if (level > 0.6) return '#4CAF50'; // Green
    if (level > 0.3) return '#FF9800'; // Orange
    return '#F44336'; // Red
  };

  const getMoodColor = (mood: string): string => {
    const moodColors = {
      happy: '#4CAF50',
      neutral: '#2196F3',
      sad: '#FF9800',
      worried: '#F44336',
      lonely: '#9C27B0',
    };
    return moodColors[mood as keyof typeof moodColors] || '#757575';
  };

  const getActivityIcon = (activity: string): string => {
    const activityIcons = {
      'Standby': 'robot-outline',
      'Following': 'walk-outline',
      'Chatting': 'chatbubble-outline',
      'Emergency': 'alert-circle',
      'Smart Home': 'home-outline',
    };
    return activityIcons[activity as keyof typeof activityIcons] || 'help-outline';
  };

  const screenWidth = Dimensions.get('window').width;

  const chartConfig = {
    backgroundColor: '#ffffff',
    backgroundGradientFrom: '#ffffff',
    backgroundGradientTo: '#ffffff',
    decimalPlaces: 0,
    color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
    labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
    style: {
      borderRadius: 16,
    },
    propsForDots: {
      r: '6',
      strokeWidth: '2',
      stroke: '#2E7D32',
    },
  };

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Emergency Alerts Section */}
      {activeEmergencies.length > 0 && (
        <Card style={[styles.card, styles.emergencyCard]}>
          <Card.Content>
            <Title style={styles.emergencyTitle}>🚨 Active Emergencies</Title>
            {activeEmergencies.slice(0, 3).map((alert) => (
              <Surface key={alert.id} style={styles.emergencyItem}>
                <View style={styles.emergencyHeader}>
                  <Chip
                    icon="alert-circle"
                    mode="flat"
                    textStyle={{ color: '#FFFFFF' }}
                    style={[
                      styles.severityChip,
                      { backgroundColor: alert.severity >= 3 ? '#D32F2F' : '#FF9800' },
                    ]}
                  >
                    {alert.type.toUpperCase()}
                  </Chip>
                  <Paragraph style={styles.emergencyTime}>
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </Paragraph>
                </View>
                <Paragraph style={styles.emergencyDescription}>
                  {alert.description}
                </Paragraph>
                <Button
                  mode="contained"
                  onPress={() => handleEmergencyAction(alert)}
                  style={styles.emergencyButton}
                  buttonColor="#D32F2F"
                >
                  Take Action
                </Button>
              </Surface>
            ))}
          </Card.Content>
        </Card>
      )}

      {/* Robot Status Section */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.statusHeader}>
            <Avatar.Icon
              size={50}
              icon="robot"
              style={[
                styles.statusIcon,
                { backgroundColor: robotStatus.online ? '#4CAF50' : '#F44336' },
              ]}
            />
            <View style={styles.statusInfo}>
              <Title>Robot Status</Title>
              <Paragraph>
                {robotStatus.online ? '🟢 Online' : '🔴 Offline'} • 
                Battery: {Math.round(robotStatus.batteryLevel * 100)}%
              </Paragraph>
            </View>
            <Badge
              style={[
                styles.batteryBadge,
                { backgroundColor: getBatteryColor(robotStatus.batteryLevel) },
              ]}
            >
              {Math.round(robotStatus.batteryLevel * 100)}%
            </Badge>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.statusGrid}>
            <View style={styles.statusItem}>
              <Paragraph style={styles.statusLabel}>Location</Paragraph>
              <Paragraph style={styles.statusValue}>{robotStatus.currentLocation}</Paragraph>
            </View>
            <View style={styles.statusItem}>
              <Paragraph style={styles.statusLabel}>Activity</Paragraph>
              <Paragraph style={styles.statusValue}>{robotStatus.currentActivity}</Paragraph>
            </View>
          </View>

          {/* System Health Indicators */}
          <View style={styles.healthGrid}>
            {Object.entries(robotStatus.systemHealth).map(([system, healthy]) => (
              <Chip
                key={system}
                icon={healthy ? 'check-circle' : 'alert-circle'}
                mode="flat"
                textStyle={{ fontSize: 12 }}
                style={[
                  styles.healthChip,
                  { backgroundColor: healthy ? '#E8F5E8' : '#FFEBEE' },
                ]}
              >
                {system.replace(/([A-Z])/g, ' $1').trim()}
              </Chip>
            ))}
          </View>
        </Card.Content>
      </Card>

      {/* Elderly Person Status */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.statusHeader}>
            <Avatar.Icon
              size={50}
              icon="account"
              style={[
                styles.statusIcon,
                { backgroundColor: getMoodColor(elderlyStatus.currentMood) },
              ]}
            />
            <View style={styles.statusInfo}>
              <Title>Elderly Status</Title>
              <Paragraph>
                Mood: {elderlyStatus.currentMood} • 
                Activity: {elderlyStatus.activityLevel}
              </Paragraph>
            </View>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Title style={styles.statNumber}>
                {elderlyStatus.dailyStats.conversationsToday}
              </Title>
              <Paragraph style={styles.statLabel}>Conversations Today</Paragraph>
            </View>
            <View style={styles.statItem}>
              <Title style={styles.statNumber}>
                {elderlyStatus.dailyStats.emergenciesThisWeek}
              </Title>
              <Paragraph style={styles.statLabel}>Emergencies This Week</Paragraph>
            </View>
          </View>

          <Paragraph style={styles.lastInteraction}>
            Last interaction: {elderlyStatus.lastInteraction || 'No recent interaction'}
          </Paragraph>
        </Card.Content>
      </Card>

      {/* Mood Trend Chart */}
      <Card style={styles.card}>
        <Card.Content>
          <Title>Weekly Mood Trend</Title>
          {moodData.length > 0 && (
            <LineChart
              data={{
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [
                  {
                    data: moodData,
                    strokeWidth: 3,
                  },
                ],
              }}
              width={screenWidth - 60} // from react-native
              height={200}
              yAxisSuffix=""
              yAxisInterval={1}
              chartConfig={chartConfig}
              bezier
              style={styles.chart}
            />
          )}
          <Paragraph style={styles.chartDescription}>
            Mood score based on daily interactions (0-100)
          </Paragraph>
        </Card.Content>
      </Card>

      {/* Quick Actions */}
      <Card style={styles.card}>
        <Card.Content>
          <Title>Quick Actions</Title>
          
          <View style={styles.actionGrid}>
            <Button
              mode="contained"
              icon="video"
              onPress={() => {/* Navigate to video call */}}
              style={styles.actionButton}
            >
              Video Call
            </Button>
            
            <Button
              mode="outlined"
              icon="message-text"
              onPress={() => {/* Send message to robot */}}
              style={styles.actionButton}
            >
              Send Message
            </Button>
            
            <Button
              mode="outlined"
              icon="medical-bag"
              onPress={() => {/* Check health */}}
              style={styles.actionButton}
            >
              Health Check
            </Button>
            
            <Button
              mode="contained"
              icon="alert"
              onPress={() => EmergencyService.testEmergencySystem()}
              style={[styles.actionButton, styles.testButton]}
              buttonColor="#FF9800"
            >
              Test Emergency
            </Button>
          </View>
        </Card.Content>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
    padding: 16,
  },
  card: {
    marginBottom: 16,
    elevation: 4,
  },
  emergencyCard: {
    borderLeftWidth: 4,
    borderLeftColor: '#D32F2F',
  },
  emergencyTitle: {
    color: '#D32F2F',
    fontWeight: 'bold',
  },
  emergencyItem: {
    padding: 12,
    marginVertical: 8,
    borderRadius: 8,
    backgroundColor: '#FFEBEE',
  },
  emergencyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  severityChip: {
    height: 24,
  },
  emergencyTime: {
    fontSize: 12,
    color: '#666',
  },
  emergencyDescription: {
    marginBottom: 12,
    fontWeight: '500',
  },
  emergencyButton: {
    marginTop: 8,
  },
  statusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  statusIcon: {
    marginRight: 16,
  },
  statusInfo: {
    flex: 1,
  },
  batteryBadge: {
    color: '#FFFFFF',
  },
  divider: {
    marginVertical: 16,
  },
  statusGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statusItem: {
    flex: 1,
  },
  statusLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  statusValue: {
    fontSize: 16,
    fontWeight: '600',
  },
  healthGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 16,
  },
  healthChip: {
    margin: 4,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginVertical: 16,
  },
  statItem: {
    alignItems: 'center',
  },
  statNumber: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2E7D32',
  },
  statLabel: {
    fontSize: 12,
    textAlign: 'center',
    color: '#666',
  },
  lastInteraction: {
    textAlign: 'center',
    fontStyle: 'italic',
    color: '#666',
    marginTop: 8,
  },
  chart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  chartDescription: {
    textAlign: 'center',
    fontSize: 12,
    color: '#666',
    marginTop: 8,
  },
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  actionButton: {
    width: '48%',
    marginBottom: 12,
  },
  testButton: {
    width: '100%',
  },
});

export default DashboardScreen;