/**
 * IotService
 * 에어컨 제어 서버와 통신하는 서비스
 * 기존 안드로이드 IotService의 TypeScript 버전
 */

import { Capacitor } from '@capacitor/core';

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
    if (baseUrl) {
      this.baseUrl = baseUrl;
    } else if (process.env.VITE_API_BASE_URL) {
      this.baseUrl = process.env.VITE_API_BASE_URL;
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
   * 에어컨 상태 조회
   * @returns 현재 에어컨 상태
   */
  async getStatus(): Promise<AirConditionerStatusResponse> {
    try {
      console.log(`IoT 상태 조회 요청: ${this.baseUrl}/air_conditioner/state`);
      
      // 타임아웃 설정 (5초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${this.baseUrl}/air_conditioner/state`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      let data;
      try {
        data = await response.json();
        console.log('IoT 상태 조회 응답:', JSON.stringify(data, null, 2));
      } catch (parseError) {
        console.error('응답 파싱 실패:', parseError);
        throw new Error('서버 응답을 파싱할 수 없습니다.');
      }
      
      if (!data || typeof data !== 'object') {
        throw new Error('서버 응답이 유효하지 않습니다.');
      }
      
      if (!data.success) {
        throw new Error(data.error || '상태 조회 실패');
      }

      // 서버 응답이 유효한지 확인
      if (!data.state || typeof data.state !== 'object') {
        throw new Error('서버 응답에 상태 정보가 없습니다.');
      }

      // 서버 응답을 앱 형식으로 변환
      const state = data.state;
      const result = {
        currentTemperature: state.current_temperature ?? 0,
        airQuality: state.air_quality?.pm2 || state.air_quality?.pm10 || 0,
        state: {
          power: state.power_on || false,
          targetTemperature: state.target_temperature ?? 0,
          mode: (state.job_mode as AirConditionerMode) || 'AUTO',
          fanSpeed: (state.wind_strength as FanSpeed) || 'AUTO',
          currentTemperature: state.current_temperature,
          airQuality: state.air_quality?.pm2 || state.air_quality?.pm10,
        },
      };
      console.log('IoT 상태 변환 결과:', JSON.stringify(result, null, 2));
      return result;
    } catch (error: any) {
      console.error('Failed to get IoT status:', error);
      // 네트워크 에러인지 확인
      if (error.name === 'AbortError') {
        throw new Error('서버 응답 시간 초과. 서버가 실행 중인지 확인해주세요.');
      } else if (error.message?.includes('Failed to fetch') || error.message?.includes('Mixed Content')) {
        throw new Error('서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
      }
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
      // 서버가 기대하는 형식으로 변환
      const serverRequest: any = {};
      
      if (control.power !== undefined) {
        serverRequest.action = 'set_power';
        serverRequest.power_on = control.power;
      } else if (control.targetTemperature !== undefined) {
        serverRequest.action = 'set_temperature';
        serverRequest.target_temperature = control.targetTemperature;
        serverRequest.unit = 'C';
      } else if (control.mode) {
        serverRequest.action = 'set_mode';
        serverRequest.mode = control.mode;
      } else if (control.fanSpeed) {
        serverRequest.action = 'set_wind_strength';
        serverRequest.strength = control.fanSpeed;
      }

      console.log(`IoT 제어 요청: ${this.baseUrl}/air_conditioner/control`, serverRequest);
      const response = await fetch(`${this.baseUrl}/air_conditioner/control`, {
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
      console.log('IoT 제어 응답:', data);
      
      if (!data.success) {
        throw new Error(data.error || '제어 실패');
      }

      return {
        success: true,
        message: data.message || '제어 성공',
      };
    } catch (error: any) {
      console.error('Failed to control air conditioner:', error);
      return {
        success: false,
        message: error.message || '제어 실패',
      };
    }
  }

  /**
   * 전원 ON/OFF
   */
  async setPower(power: boolean): Promise<{ success: boolean; message?: string }> {
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

