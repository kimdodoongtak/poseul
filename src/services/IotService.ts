/**
 * IotService
 * 에어컨 제어 서버와 통신하는 서비스
 * 기존 안드로이드 IotService의 TypeScript 버전
 */

export type AirConditionerMode = 'COOL' | 'AIR_DRY' | 'AIR_CLEAN' | 'AUTO';
export type FanSpeed = 'HIGH' | 'MID' | 'LOW' | 'AUTO';

export interface AirConditionerState {
  power: boolean;
  targetTemperature: number;
  mode: AirConditionerMode;
  fanSpeed: FanSpeed;
  currentTemperature?: number;
  airQuality?: number;
}

export interface AirConditionerControlRequest {
  power?: boolean;
  targetTemperature?: number;
  mode?: AirConditionerMode;
  fanSpeed?: FanSpeed;
}

export interface AirConditionerStatusResponse {
  currentTemperature: number;
  airQuality: number;
  state: AirConditionerState;
}

class IotService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    // 환경 변수나 설정에서 가져올 수 있도록
    this.baseUrl = baseUrl || process.env.VITE_API_BASE_URL || 'http://localhost:8080';
  }

  /**
   * 에어컨 상태 조회
   * @returns 현재 에어컨 상태
   */
  async getStatus(): Promise<AirConditionerStatusResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/iot/status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: AirConditionerStatusResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to get IoT status:', error);
      throw error;
    }
  }

  /**
   * 에어컨 제어
   * @param control 제어 명령
   * @returns 성공 여부
   */
  async controlAirConditioner(
    control: AirConditionerControlRequest
  ): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/iot/control`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(control),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to control air conditioner:', error);
      throw error;
    }
  }

  /**
   * 전원 ON/OFF
   */
  async setPower(power: boolean): Promise<{ success: boolean }> {
    return this.controlAirConditioner({ power });
  }

  /**
   * 목표 온도 설정
   */
  async setTargetTemperature(temperature: number): Promise<{ success: boolean }> {
    return this.controlAirConditioner({ targetTemperature: temperature });
  }

  /**
   * 모드 설정
   */
  async setMode(mode: AirConditionerMode): Promise<{ success: boolean }> {
    return this.controlAirConditioner({ mode });
  }

  /**
   * 풍량 설정
   */
  async setFanSpeed(fanSpeed: FanSpeed): Promise<{ success: boolean }> {
    return this.controlAirConditioner({ fanSpeed });
  }
}

export default new IotService();

