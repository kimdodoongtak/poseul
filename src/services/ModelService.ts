/**
 * ModelService
 * 온도 예측 모델 서버와 통신하는 서비스
 * 기존 안드로이드 ModelService의 TypeScript 버전
 */

export interface TemperaturePredictionRequest {
  heartRate: number;
  hrv: number;
  bmi: number;
  oxygenSaturation: number;
  gender: 'MALE' | 'FEMALE';
  age: number;
}

export interface TemperaturePredictionResponse {
  predictedTemperature: number;
  status: 'COMFORTABLE' | 'COLD' | 'HOT';
  timestamp: string;
}

class ModelService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    // 환경 변수나 설정에서 가져올 수 있도록
    this.baseUrl = baseUrl || process.env.VITE_API_BASE_URL || 'http://localhost:8080';
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
      const response = await fetch(`${this.baseUrl}/api/model/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: TemperaturePredictionResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Temperature prediction failed:', error);
      throw error;
    }
  }

  /**
   * 모델 테스트
   * @returns 테스트 결과
   */
  async testModel(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/model/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Model test failed:', error);
      throw error;
    }
  }
}

export default new ModelService();

