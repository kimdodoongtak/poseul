/**
 * ModelService
 * 온도 예측 모델 서버와 통신하는 서비스
 * 기존 안드로이드 ModelService의 TypeScript 버전
 */

import { Capacitor } from '@capacitor/core';
import { getServerUrl } from './ServerConfig';

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
    } else {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      this.baseUrl = getServerUrl();
    }
  }
  
  /**
   * 서버 URL 업데이트 (동적으로 변경 가능)
   */
  updateBaseUrl(newUrl: string): void {
    this.baseUrl = newUrl;
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

      console.log(`온도 예측 요청: ${this.baseUrl}/predict`);
      
      // 타임아웃 설정 (15초 - 모델 예측은 시간이 걸릴 수 있음)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const response = await fetch(`${this.baseUrl}/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(serverRequest),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

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
      console.error('Request URL:', `${this.baseUrl}/predict`);
      
      if (error.name === 'AbortError') {
        return {
          success: false,
          predictedTemperature: 0,
          temperatureCategory: '',
          error: '서버 응답 시간 초과 (15초). 서버가 실행 중인지 확인해주세요.',
        };
      }
      
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
      console.log(`모델 테스트 요청: ${this.baseUrl}/health`);
      
      // 타임아웃 설정 (10초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

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
      console.error('Request URL:', `${this.baseUrl}/health`);
      
      if (error.name === 'AbortError') {
        return {
          success: false,
          message: `서버 응답 시간 초과 (10초). 서버가 실행 중인지 확인해주세요. (URL: ${this.baseUrl})`,
        };
      }
      
      return {
        success: false,
        message: `서버 연결 실패: ${error.message || '서버에 연결할 수 없습니다.'} (URL: ${this.baseUrl})`,
      };
    }
  }
}

export default new ModelService();

