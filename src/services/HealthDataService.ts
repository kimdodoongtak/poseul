/**
 * HealthDataService
 * iOS HealthKit 데이터를 서버에 저장하고 안드로이드에서 가져오는 서비스
 */

import { Capacitor } from '@capacitor/core';

export interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

export interface HealthDataResponse {
  success: boolean;
  data?: {
    heartRate?: { value: number; date: string };
    hrv?: { value: number; date: string };
    oxygenSaturation?: { value: number; date: string };
  };
  error?: string;
}

class HealthDataService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    if (baseUrl) {
      this.baseUrl = baseUrl;
    } else if (import.meta.env.VITE_API_BASE_URL) {
      this.baseUrl = import.meta.env.VITE_API_BASE_URL;
    } else {
      // 플랫폼별 기본 URL 설정
      if (Capacitor.isNativePlatform()) {
        if (Capacitor.getPlatform() === 'android') {
          this.baseUrl = 'http://10.0.2.2:3000';
        } else if (Capacitor.getPlatform() === 'ios') {
          this.baseUrl = 'http://localhost:3000';
        } else {
          this.baseUrl = 'http://localhost:3000';
        }
      } else {
        this.baseUrl = 'http://localhost:3000';
      }
    }
  }

  /**
   * 건강 데이터를 서버에 저장 (iOS에서 호출)
   */
  async saveHealthData(healthData: HealthData): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/health_data/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(healthData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: data.success || true,
        message: data.message || '건강 데이터 저장 성공',
      };
    } catch (error: any) {
      console.error('Health data save failed:', error);
      return {
        success: false,
        message: error.message || '건강 데이터 저장 실패',
      };
    }
  }

  /**
   * 서버에서 최신 건강 데이터 가져오기 (안드로이드에서 호출)
   */
  async getLatestHealthData(): Promise<HealthDataResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/health_data/latest`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || '건강 데이터 조회 실패');
      }

      return {
        success: true,
        data: data.data || {},
      };
    } catch (error: any) {
      console.error('Health data fetch failed:', error);
      return {
        success: false,
        error: error.message || '건강 데이터 조회 실패',
      };
    }
  }
}

export default new HealthDataService();

