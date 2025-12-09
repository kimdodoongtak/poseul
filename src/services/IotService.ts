/**
 * IotService
 * 에어컨 제어 서버와 통신하는 서비스
 * 기존 안드로이드 IotService의 TypeScript 버전
 */

import { Capacitor } from '@capacitor/core';
import { getServerUrl } from './ServerConfig';

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
  
  // baseUrl을 외부에서 접근할 수 있도록 getter 추가
  getBaseUrl(): string {
    return this.baseUrl;
  }

  constructor(baseUrl?: string) {
    if (baseUrl && baseUrl !== '') {
      this.baseUrl = baseUrl;
    } else {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      const url = getServerUrl();
      if (url && url !== '') {
        this.baseUrl = url;
      } else {
        // 빈 URL인 경우 기본값 설정 (나중에 autoDetectServerUrl로 업데이트됨)
        this.baseUrl = '';
      }
    }
  }
  
  /**
   * 서버 URL 업데이트 (동적으로 변경 가능)
   */
  updateBaseUrl(newUrl: string): void {
    this.baseUrl = newUrl;
  }

  /**
   * 에어컨 상태 조회
   * @returns 현재 에어컨 상태
   */
  async getStatus(): Promise<AirConditionerStatusResponse> {
    try {
      // baseUrl이 비어있으면 에러
      if (!this.baseUrl || this.baseUrl === '') {
        throw new Error('서버 URL이 설정되지 않았습니다. 서버 URL을 자동 감지하거나 수동으로 설정해주세요.');
      }
      
      console.log(`IoT 상태 조회 요청: ${this.baseUrl}/air_conditioner/state`);
      
      // 타임아웃 설정 (10초로 증가하여 서버 시작 시간 고려)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      // 현재 로그인한 사용자의 user_id 가져오기
      let user_id = 'default';
      try {
        const { getCurrentUser } = await import('./AuthService');
        const user = await getCurrentUser();
        user_id = user.id;
        console.log(`✅ 사용자 정보 가져오기 성공: user_id=${user_id}`);
      } catch (error) {
        console.error('❌ 사용자 정보 가져오기 실패, default 사용:', error);
        // 에러가 발생해도 계속 진행 (default user_id 사용)
      }
      
      const response = await fetch(`${this.baseUrl}/air_conditioner/state?user_id=${encodeURIComponent(user_id)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.error || `HTTP error! status: ${response.status}`;
        
        // 404 에러는 등록되지 않았음을 의미
        if (response.status === 404) {
          // 등록 상태 초기화
          if (typeof window !== 'undefined') {
            localStorage.removeItem('iot_device_registered');
            localStorage.removeItem('thinq_pat_token');
            localStorage.removeItem('thinq_device_id');
            localStorage.removeItem('thinq_device_name');
            console.log('🔄 404 에러 감지 - 등록 상태 초기화');
          }
          throw new Error('등록된 디바이스가 없습니다. PAT 토큰을 다시 등록해주세요.');
        }
        
        throw new Error(errorMessage);
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
        currentTemperature: state.currentTemperature ?? 0,
        airQuality: state.airQuality ?? 0,
        state: {
          power: state.power ?? false,
          targetTemperature: state.targetTemperature ?? 0,
          mode: (state.mode as AirConditionerMode) || 'AUTO',
          fanSpeed: (state.fanSpeed as FanSpeed) || 'AUTO',
          currentTemperature: state.currentTemperature,
          airQuality: state.airQuality,
        },
      };
      console.log('IoT 상태 변환 결과:', JSON.stringify(result, null, 2));
      return result;
    } catch (error: any) {
      console.error('Failed to get IoT status:', error);
      console.error('Error details:', {
        name: error?.name,
        message: error?.message,
        stack: error?.stack,
        toString: error?.toString()
      });
      console.error('Request URL:', `${this.baseUrl}/air_conditioner/state`);
      // 네트워크 에러인지 확인
      if (error.name === 'AbortError') {
        // Railway 서버 타임아웃 시 로컬 서버로 자동 전환 안내
        const errorMsg = `서버 응답 시간 초과 (10초). 서버가 실행 중인지 확인해주세요. (URL: ${this.baseUrl})`;
        console.error('❌ 서버 타임아웃:', errorMsg);
        // Railway URL이면 로컬 서버로 전환 제안
        if (this.baseUrl.includes('railway')) {
          console.warn('⚠️ Railway 서버 응답 없음. 로컬 서버 사용을 권장합니다.');
        }
        throw new Error(errorMsg);
      } else if (error.message?.includes('Failed to fetch') || error.message?.includes('Mixed Content') || !error.message) {
        const errorMsg = error?.message || error?.toString() || '알 수 없는 네트워크 오류';
        throw new Error(`서버에 연결할 수 없습니다. (${errorMsg}) 서버가 실행 중인지 확인해주세요. (URL: ${this.baseUrl})`);
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
      
      // 타임아웃 설정 (10초로 증가하여 서버 시작 시간 고려)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      // 현재 로그인한 사용자의 user_id 가져오기
      let user_id = 'default';
      try {
        const { getCurrentUser } = await import('./AuthService');
        const user = await getCurrentUser();
        user_id = user.id;
        console.log(`✅ 사용자 정보 가져오기 성공: user_id=${user_id}`);
      } catch (error) {
        console.error('❌ 사용자 정보 가져오기 실패, default 사용:', error);
        // 에러가 발생해도 계속 진행 (default user_id 사용)
      }
      
      const response = await fetch(`${this.baseUrl}/air_conditioner/control?user_id=${encodeURIComponent(user_id)}`, {
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
      
      // 타임아웃 에러 처리
      if (error.name === 'AbortError') {
        return {
          success: false,
          message: '서버 응답 시간 초과. 서버가 실행 중인지 확인해주세요.',
        };
      }
      
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

  /**
   * 온도 임계값 저장 (12시간 유효)
   */
  async saveTemperatureThreshold(targetTemperature: number): Promise<{ success: boolean; message?: string }> {
    try {
      // 인증 헤더 추가
      const { getAuthHeaders } = await import('./AuthService');
      const authHeaders = getAuthHeaders();
      const authHeaderValue = (authHeaders as Record<string, string>)['Authorization'];
      
      console.log(`🌡️ 온도 임계값 저장 요청: ${this.baseUrl}/air_conditioner/temperature_threshold`, { 
        target_temperature: targetTemperature,
        url: `${this.baseUrl}/air_conditioner/temperature_threshold`,
        hasAuth: !!authHeaderValue
      });
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (authHeaderValue) {
        (headers as Record<string, string>)['Authorization'] = authHeaderValue;
      }
      
      const response = await fetch(`${this.baseUrl}/air_conditioner/temperature_threshold`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ target_temperature: targetTemperature }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      console.log(`🌡️ 온도 임계값 저장 응답 상태: ${response.status} ${response.statusText}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`❌ 온도 임계값 저장 실패: ${response.status} - ${errorText}`);
        let errorData: any = {};
        try {
          errorData = JSON.parse(errorText);
        } catch (e) {
          // JSON 파싱 실패 시 빈 객체 사용
        }
        throw new Error(errorData.detail || errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('✅ 온도 임계값 저장 응답:', data);
      
      if (!data.success) {
        throw new Error(data.error || '임계값 저장 실패');
      }

      return {
        success: true,
        message: data.message || '임계값 저장 성공',
      };
    } catch (error: any) {
      console.error('❌ Failed to save temperature threshold:', error);
      
      if (error.name === 'AbortError') {
        return {
          success: false,
          message: '서버 응답 시간 초과. 서버가 실행 중인지 확인해주세요.',
        };
      }
      
      return {
        success: false,
        message: error.message || '임계값 저장 실패',
      };
    }
  }
}

const iotServiceInstance = new IotService();

// getBaseUrl을 외부에서 접근할 수 있도록 export
export function getIotServiceBaseUrl(): string {
  return iotServiceInstance.getBaseUrl();
}

export default iotServiceInstance;

