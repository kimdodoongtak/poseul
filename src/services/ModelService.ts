/**
 * ModelService
 * 온도 예측 모델 서버와 통신하는 서비스
 * 기존 안드로이드 ModelService의 TypeScript 버전
 */

import { Capacitor } from '@capacitor/core';

export interface TemperaturePredictionRequest {
  heartRate: number;
  hrv: number;
  bmi: number;
  oxygenSaturation: number;
  gender: 'MALE' | 'FEMALE';
  age: number;
}

export interface TemperaturePredictionResponse {
  success: boolean;
  predictedTemperature: number;
  temperatureCategory: string; // '적정', '추움', '더움'
  inputData?: any;
  error?: string;
}

class ModelService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    if (baseUrl) {
      this.baseUrl = baseUrl;
    } else if (import.meta.env.VITE_API_BASE_URL) {
      this.baseUrl = import.meta.env.VITE_API_BASE_URL;
    } else {
      // 플랫폼별 기본 URL 설정
      if (Capacitor.isNativePlatform()) {
        // 안드로이드 에뮬레이터 또는 실제 기기
        if (Capacitor.getPlatform() === 'android') {
          // 에뮬레이터: 10.0.2.2, 실제 기기: 컴퓨터 IP 주소 필요
          // 기본값으로 에뮬레이터 사용 (실제 기기는 환경 변수로 설정)
          this.baseUrl = 'http://10.0.2.2:5000';
        } else if (Capacitor.getPlatform() === 'ios') {
          // iOS 시뮬레이터: localhost, 실제 기기: 컴퓨터 IP 주소 필요
          this.baseUrl = 'http://localhost:5000';
        } else {
          this.baseUrl = 'http://localhost:5000';
        }
      } else {
        // 웹 개발 환경
        this.baseUrl = 'http://localhost:5000';
      }
    }
  }

  /**
   * 체온 예측 요청
   * @param request 예측에 필요한 데이터
   * @returns 예측된 온도와 상태
   */
  async predictTemperature(
    request: TemperaturePredictionRequest
  ): Promise<TemperaturePredictionResponse> {
    try {
      // 서버가 기대하는 형식으로 변환
      const serverRequest = {
        hr_mean: request.heartRate,
        hrv_sdnn: request.hrv,
        bmi: request.bmi,
        mean_sa02: request.oxygenSaturation,
        gender: request.gender === 'MALE' ? 'M' : 'F',
        age: request.age,
      };

      const response = await fetch(`${this.baseUrl}/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(serverRequest),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // 서버 응답을 앱 형식으로 변환
      const statusMap: { [key: string]: string } = {
        '적정': 'COMFORTABLE',
        '추움': 'COLD',
        '더움': 'HOT',
      };

      return {
        success: data.success || true,
        predictedTemperature: data.predicted_temperature,
        temperatureCategory: data.temperature_category,
        inputData: data.input_data,
      };
    } catch (error: any) {
      console.error('Temperature prediction failed:', error);
      return {
        success: false,
        predictedTemperature: 0,
        temperatureCategory: '',
        error: error.message || '예측 실패',
      };
    }
  }

  /**
   * 서버 상태 확인 (모델 테스트)
   * @returns 서버 상태
   */
  async testModel(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: data.model_loaded || false,
        message: data.model_loaded
          ? '서버가 정상적으로 작동 중입니다. 모델이 로드되었습니다.'
          : '서버는 작동 중이지만 모델이 로드되지 않았습니다.',
      };
    } catch (error: any) {
      console.error('Model test failed:', error);
      return {
        success: false,
        message: `서버 연결 실패: ${error.message || '서버에 연결할 수 없습니다.'}`,
      };
    }
  }
}

export default new ModelService();

