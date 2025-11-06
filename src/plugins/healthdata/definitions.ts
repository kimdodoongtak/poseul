export interface HealthDataPlugin {
  requestAuthorization(): Promise<{ success: boolean }>;
  getLatestHeartRate(): Promise<{ value: number; date: string } | null>;
  getLatestHeartRateVariability(): Promise<{ value: number; date: string } | null>;
  getLatestOxygenSaturation(): Promise<{ value: number; date: string } | null>;
  startBackgroundMonitoring(options: { enabled: boolean }): Promise<{ success: boolean }>;
}

