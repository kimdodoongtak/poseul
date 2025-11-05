import { WebPlugin } from '@capacitor/core';
import type { HealthDataPlugin } from './definitions';

export class HealthDataWeb extends WebPlugin implements HealthDataPlugin {
  async requestAuthorization(): Promise<{ success: boolean }> {
    throw this.unimplemented('HealthData is not available on web');
  }

  async getLatestHeartRate(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthData is not available on web');
  }

  async getLatestHeartRateVariability(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthData is not available on web');
  }

  async getLatestOxygenSaturation(): Promise<{ value: number; date: string } | null> {
    throw this.unimplemented('HealthData is not available on web');
  }

  async startBackgroundMonitoring(options: { enabled: boolean }): Promise<{ success: boolean }> {
    throw this.unimplemented('HealthData is not available on web');
  }
}

