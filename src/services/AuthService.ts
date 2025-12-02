/**
 * 인증 관련 서비스
 * 회원가입, 로그인, 토큰 관리 등을 담당
 */

import { getServerUrl } from './ServerConfig';

const TOKEN_KEY = 'auth_token';
const USER_NO_KEY = 'user_no';
const USER_ID_KEY = 'user_id';

export interface RegisterData {
  id: string;
  password: string;
  device?: string;  // IoT 디바이스 정보 (선택적)
}

export interface LoginData {
  id: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_no: number;
}

/**
 * 회원가입
 */
export async function register(data: RegisterData): Promise<AuthResponse> {
  const baseUrl = getServerUrl();
  
  if (!baseUrl) {
    throw new Error('서버 URL을 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
  }
  
  try {
    // 타임아웃 설정 (10초)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    
    const response = await fetch(`${baseUrl}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = '회원가입에 실패했습니다.';
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorData.error || JSON.stringify(errorData) || errorMessage;
      } catch (parseError) {
        // JSON 파싱 실패 시 상태 코드로 메시지 생성
        errorMessage = `회원가입 실패 (상태 코드: ${response.status})`;
      }
      throw new Error(errorMessage);
    }

    const result: AuthResponse = await response.json();
    
    // 토큰 저장
    saveAuthData(result);
    
    return result;
  } catch (error: any) {
    // 네트워크 오류 처리
    if (error.name === 'AbortError') {
      throw new Error('요청 시간이 초과되었습니다. 서버가 응답하지 않거나 네트워크 연결이 느립니다.');
    }
    if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
      throw new Error('서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
    }
    throw error;
  }
}

/**
 * 로그인
 */
export async function login(data: LoginData): Promise<AuthResponse> {
  let baseUrl = getServerUrl();
  
  console.log('🔵 login - 서버 URL:', baseUrl);
  
  // iOS에서 localhost이거나 빈 문자열인 경우 자동 감지
  if (!baseUrl || baseUrl === '' || (baseUrl.includes('localhost') && typeof window !== 'undefined')) {
    try {
      const { Capacitor } = await import('@capacitor/core');
      if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
        console.log('⚠️ login - iOS에서 localhost 감지 또는 URL 없음, 자동 감지 시도');
        const { autoDetectServerUrl } = await import('./ServerConfig');
        const detectedUrl = await autoDetectServerUrl();
        if (detectedUrl && detectedUrl !== '') {
          baseUrl = detectedUrl;
          console.log('✅ login - 자동 감지된 서버 URL:', baseUrl);
        } else {
          throw new Error('서버 URL 자동 감지 실패');
        }
      }
    } catch (e) {
      console.error('❌ login - 자동 감지 실패:', e);
    }
  }
  
  if (!baseUrl) {
    console.error('❌ login - 서버 URL을 찾을 수 없음');
    throw new Error('서버 URL을 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
  }
  
  const loginUrl = `${baseUrl}/auth/login`;
  console.log('🔵 login - 요청 URL:', loginUrl);
  console.log('🔵 login - 요청 데이터:', { id: data.id, password: '***' });
  
  try {
    // 타임아웃 설정 (10초)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    
    console.log('🔵 login - fetch 시작...');
    const response = await fetch(loginUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    console.log('🔵 login - 응답 받음:', response.status, response.statusText);

    if (!response.ok) {
      console.error('❌ login - 응답 실패:', response.status, response.statusText);
      let errorData;
      try {
        errorData = await response.json();
        console.error('❌ login - 에러 데이터:', errorData);
      } catch (parseError) {
        console.error('❌ login - JSON 파싱 실패:', parseError);
        const text = await response.text().catch(() => '');
        console.error('❌ login - 응답 텍스트:', text);
        errorData = { detail: `로그인에 실패했습니다. (상태 코드: ${response.status})` };
      }
      throw new Error(errorData.detail || '로그인에 실패했습니다.');
    }

    const result: AuthResponse = await response.json();
    console.log('🔵 login - 서버 응답 파싱 완료:', {
      hasAccessToken: !!result?.access_token,
      hasUserNo: !!result?.user_no,
      tokenType: result?.token_type
    });
    
    // 응답 검증
    if (!result || !result.access_token) {
      console.error('❌ login - 서버 응답에 access_token이 없음:', result);
      throw new Error('서버 응답에 토큰이 포함되지 않았습니다.');
    }
    
    if (!result.access_token.trim()) {
      console.error('❌ login - access_token이 비어있음');
      throw new Error('서버 응답의 토큰이 비어있습니다.');
    }
    
    console.log('✅ login - 서버 응답 검증 완료, 토큰 저장 시작:', result.access_token.substring(0, 20) + '...');
    
    // localStorage 사용 가능 여부 확인
    try {
      const testKey = '__localStorage_test__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);
      console.log('✅ login - localStorage 사용 가능 확인');
    } catch (storageError) {
      console.error('❌ login - localStorage 사용 불가:', storageError);
      throw new Error('브라우저 저장소를 사용할 수 없습니다. 브라우저 설정을 확인해주세요.');
    }
    
    // 토큰 저장
    try {
      saveAuthData(result);
      console.log('✅ login - saveAuthData() 호출 완료');
    } catch (saveError: any) {
      console.error('❌ login - saveAuthData() 실패:', saveError);
      throw new Error(saveError.message || '토큰 저장에 실패했습니다.');
    }
  
    // 저장 확인 (즉시 확인)
    const savedToken = localStorage.getItem(TOKEN_KEY);
    console.log('🔵 login - localStorage에서 토큰 확인:', savedToken ? `있음 (길이: ${savedToken.length})` : '없음');
    
    if (!savedToken) {
      console.error('❌ login - localStorage에 토큰이 저장되지 않음');
      // 재시도
      try {
        localStorage.setItem(TOKEN_KEY, result.access_token);
        localStorage.setItem(USER_NO_KEY, result.user_no.toString());
        const retryToken = localStorage.getItem(TOKEN_KEY);
        if (!retryToken) {
          throw new Error('토큰 저장 재시도도 실패했습니다.');
        }
        console.log('✅ login - 토큰 저장 재시도 성공');
      } catch (retryError) {
        console.error('❌ login - 토큰 저장 재시도 실패:', retryError);
        throw new Error('토큰 저장에 실패했습니다. 브라우저 저장소를 확인해주세요.');
      }
    }
    
    console.log('✅ login - 토큰 저장 확인 완료');
    return result;
  } catch (error: any) {
    console.error('❌ login - 에러 발생:', error);
    console.error('❌ login - 에러 이름:', error.name);
    console.error('❌ login - 에러 메시지:', error.message);
    if (error.stack) {
      console.error('❌ login - 에러 스택:', error.stack);
    }
    console.error('❌ login - 시도한 URL:', `${baseUrl}/auth/login`);
    
    // 네트워크 오류 처리 - 자동 감지 재시도
    if (error.name === 'AbortError' || error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError') || error.message?.includes('load failed')) {
      console.error('❌ login - 네트워크 연결 실패, 자동 감지 재시도:', baseUrl);
      
      // iOS에서 자동 감지 재시도
      try {
        const { Capacitor } = await import('@capacitor/core');
        if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
          console.log('🔄 login - iOS에서 서버 URL 자동 감지 재시도...');
          const { autoDetectServerUrl } = await import('./ServerConfig');
          const detectedUrl = await autoDetectServerUrl();
          
          if (detectedUrl && detectedUrl !== '' && detectedUrl !== baseUrl) {
            console.log('✅ login - 새로운 서버 URL 감지됨, 재시도:', detectedUrl);
            baseUrl = detectedUrl;
            
            // 재시도
            const retryController = new AbortController();
            const retryTimeoutId = setTimeout(() => retryController.abort(), 10000);
            
            const retryResponse = await fetch(`${baseUrl}/auth/login`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify(data),
              signal: retryController.signal,
            });
            
            clearTimeout(retryTimeoutId);
            
            if (!retryResponse.ok) {
              const errorData = await retryResponse.json().catch(() => ({ detail: '로그인에 실패했습니다.' }));
              throw new Error(errorData.detail || '로그인에 실패했습니다.');
            }
            
            const result: AuthResponse = await retryResponse.json();
            console.log('✅ login - 재시도 성공, 토큰 저장 시작');
            
            // 토큰 저장 로직 (기존 코드와 동일)
            if (!result || !result.access_token) {
              throw new Error('서버 응답에 토큰이 포함되지 않았습니다.');
            }
            
            saveAuthData(result);
            return result;
          }
        }
      } catch (retryError: any) {
        console.error('❌ login - 자동 감지 재시도 실패:', retryError);
      }
      
      // 자동 감지 실패 시 원래 에러 메시지
      if (error.name === 'AbortError') {
        throw new Error('요청 시간이 초과되었습니다. 서버가 응답하지 않거나 네트워크 연결이 느립니다.');
      }
      throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (URL: ${baseUrl})`);
    }
    throw error;
  }
}

/**
 * 로그아웃
 */
export function logout(): void {
  // 로그아웃 전에 이벤트 발생
  window.dispatchEvent(new CustomEvent('authStateChanged', { detail: { authenticated: false } }));
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_NO_KEY);
  localStorage.removeItem(USER_ID_KEY);
}

/**
 * 인증 데이터 저장
 */
function saveAuthData(authData: AuthResponse): void {
  if (!authData.access_token || authData.access_token.trim() === '') {
    console.error('❌ saveAuthData - access_token이 없거나 비어있음:', authData);
    throw new Error('토큰이 서버 응답에 포함되지 않았습니다.');
  }
  localStorage.setItem(TOKEN_KEY, authData.access_token);
  localStorage.setItem(USER_NO_KEY, authData.user_no.toString());
  // user_id는 getCurrentUser()를 통해 가져옴
  console.log('✅ saveAuthData - 토큰 저장 완료:', authData.access_token.substring(0, 20) + '...');
  
  // 로그인 상태 변경 이벤트 발생 (모든 페이지에서 동기화)
  // 약간의 지연을 두어 localStorage가 완전히 저장된 후 이벤트 발생
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('authStateChanged', { detail: { authenticated: true } }));
    console.log('✅ saveAuthData - 로그인 상태 변경 이벤트 발생');
  }, 50);
}

/**
 * 저장된 토큰 가져오기
 */
export function getToken(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      console.log('🔍 getToken - 토큰 없음');
    } else {
      console.log(`🔍 getToken - 토큰 있음 (길이: ${token.length})`);
    }
    return token;
  } catch (error) {
    console.error('❌ getToken - localStorage 접근 실패:', error);
    return null;
  }
}

/**
 * 저장된 사용자 번호 가져오기
 */
export function getUserNo(): number | null {
  const userNo = localStorage.getItem(USER_NO_KEY);
  return userNo ? parseInt(userNo, 10) : null;
}

/**
 * 로그인 상태 확인
 */
export function isAuthenticated(): boolean {
  try {
    const token = getToken();
    const isAuth = token !== null && token.trim() !== '';
    console.log(`🔍 isAuthenticated - 결과: ${isAuth}, 토큰: ${token ? `있음 (길이: ${token.length})` : '없음'}`);
    return isAuth;
  } catch (error) {
    console.error('❌ isAuthenticated - 오류:', error);
    return false;
  }
}

/**
 * 인증 헤더 가져오기 (API 요청용)
 */
export function getAuthHeaders(): HeadersInit {
  const token = getToken();
  if (!token) {
    console.warn('⚠️ getAuthHeaders - 토큰이 없음');
    return {
      'Content-Type': 'application/json',
    };
  }
  
  console.log(`✅ getAuthHeaders - 토큰 포함 (길이: ${token.length})`);
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

/**
 * 현재 사용자 정보 조회
 */
export async function getCurrentUser(): Promise<{ user_no: number; id: string }> {
  const baseUrl = getServerUrl();
  const token = getToken();
  
  if (!token) {
    throw new Error('로그인이 필요합니다.');
  }
  
  const response = await fetch(`${baseUrl}/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    if (response.status === 401) {
      // 401 에러가 발생해도 토큰을 삭제하지 않음 (다른 페이지에서 사용 중일 수 있음)
      console.warn('⚠️ getCurrentUser - 401 Unauthorized, 토큰 검증 실패');
      throw new Error('로그인이 필요하거나 토큰이 유효하지 않습니다.');
    }
    throw new Error('사용자 정보를 가져올 수 없습니다.');
  }

  return await response.json();
}

/**
 * 사용자별 IoT 디바이스 등록 정보 조회
 */
export async function getIotDeviceStatus(): Promise<{
  success: boolean;
  registered: boolean;
  deviceId?: string;
  deviceName?: string;
  modelName?: string;
  patToken?: string;
  message?: string;
}> {
  const baseUrl = getServerUrl();
  const token = getToken();
  
  if (!token) {
    console.warn('⚠️ getIotDeviceStatus - 토큰이 없음');
    return {
      success: false,
      registered: false,
      message: '로그인이 필요합니다.'
    };
  }
  
  console.log(`🔵 getIotDeviceStatus - API 호출 시작, 토큰: ${token.substring(0, 20)}...`);
  
  try {
    const headers = getAuthHeaders();
    console.log(`🔵 getIotDeviceStatus - 요청 헤더:`, headers);
    
    const response = await fetch(`${baseUrl}/iot/device-status/by-user-no`, {
      method: 'GET',
      headers: headers,
    });
    
    console.log(`🔵 getIotDeviceStatus - 응답 상태: ${response.status}`);

    if (!response.ok) {
      if (response.status === 401) {
        // 401 에러가 발생해도 토큰을 삭제하지 않음 (다른 페이지에서 사용 중일 수 있음)
        // 대신 에러 메시지만 반환
        console.warn('⚠️ getIotDeviceStatus - 401 Unauthorized, 토큰 검증 실패');
        console.warn(`⚠️ getIotDeviceStatus - 현재 토큰: ${token ? `있음 (길이: ${token.length})` : '없음'}`);
        return {
          success: false,
          registered: false,
          message: '로그인이 필요하거나 토큰이 유효하지 않습니다.'
        };
      }
      return {
        success: false,
        registered: false,
        message: '디바이스 등록 상태를 조회할 수 없습니다.'
      };
    }

    return await response.json();
  } catch (error: any) {
    console.error('IoT 디바이스 등록 상태 조회 실패:', error);
    return {
      success: false,
      registered: false,
      message: error.message || '디바이스 등록 상태 조회에 실패했습니다.'
    };
  }
}

