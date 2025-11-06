import { WebPlugin } from '@capacitor/core';
import type { HealthKitPlugin } from './definitions';

export class HealthKitWeb extends WebPlugin implements HealthKitPlugin {
  async requestAuthorization(): Promise<{ success: boolean }> {
    throw this.unimplemented('HealthKit is not available on web');
  }

  async getLatestHeartRate(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthKit is not available on web');
  }

  async getLatestHeartRateVariability(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthKit is not available on web');
  }

  async getLatestOxygenSaturation(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthKit is not available on web');
  }

  async startBackgroundMonitoring(options: { enabled: boolean }): Promise<{ success: boolean }> {
    throw this.unimplemented('HealthKit is not available on web');
  }
}

