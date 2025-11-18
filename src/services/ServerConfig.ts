/**
 * 서버 URL 설정 관리
 * 자동으로 서버 IP를 감지하여 사용
 */

const SERVER_URL_KEY = 'server_url';

// 동기 버전 (기본값 반환용)
let cachedServerUrl: string | null = null;

/**
 * 서버 URL 가져오기 (동기 버전 - 빠른 접근용)
 * 우선순위: 캐시 > localStorage > 환경 변수 > 기본값
 */
export function getServerUrl(): string {
  // 캐시된 URL이 있으면 사용
  if (cachedServerUrl) {
    return cachedServerUrl;
  }
  
  // localStorage에서 가져오기
  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem(SERVER_URL_KEY);
    if (savedUrl) {
      cachedServerUrl = savedUrl;
      return savedUrl;
    }
  }
  
  // 환경 변수에서 가져오기
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) {
    const envUrl = import.meta.env.VITE_API_BASE_URL;
    cachedServerUrl = envUrl;
    return envUrl;
  }
  
  // 플랫폼별 기본값
  if (typeof window !== 'undefined') {
    try {
      // 안드로이드에서는 이미 로드된 Capacitor 사용
      if ((window as any).Capacitor) {
        const Capacitor = (window as any).Capacitor;
        if (Capacitor.isNativePlatform()) {
          if (Capacitor.getPlatform() === 'android') {
            const defaultUrl = 'http://10.0.2.2:3000';
            cachedServerUrl = defaultUrl;
            return defaultUrl;
          } else if (Capacitor.getPlatform() === 'ios') {
            const defaultUrl = 'http://localhost:3000';
            cachedServerUrl = defaultUrl;
            return defaultUrl;
          }
        }
      }
    } catch (error) {
      // Capacitor 접근 실패 시 기본값 사용
      console.error('Capacitor 접근 실패:', error);
    }
  }
  
  // 웹 개발 환경 기본값
  const defaultUrl = 'http://localhost:3000';
  cachedServerUrl = defaultUrl;
  return defaultUrl;
}

/**
 * 서버 URL 자동 감지 및 업데이트 (비동기)
 * 연결 실패 시 여러 IP를 시도하여 자동으로 찾음
 */
export async function autoDetectServerUrl(): Promise<string> {
  // 1. 저장된 URL이 있으면 먼저 확인 (빠른 확인)
  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem(SERVER_URL_KEY);
    if (savedUrl) {
      // 잘못된 IP 대역이면 즉시 제거하고 자동 감지 시작
      if (savedUrl.includes('192.168.0.143') || savedUrl.includes('192.168.68.74')) {
        console.log('⚠️ 잘못된 URL 감지, 자동 감지 시작:', savedUrl);
        localStorage.removeItem(SERVER_URL_KEY);
        cachedServerUrl = null;
      } else {
        try {
          const response = await fetch(`${savedUrl}/health`, { 
            method: 'GET',
            signal: AbortSignal.timeout(1000) // 1초로 단축
          });
          if (response.ok) {
            const data = await response.json();
            // 서버가 자신의 IP를 알려주면 그것을 사용
            if (data.server_url) {
              if (data.server_url !== savedUrl) {
                localStorage.setItem(SERVER_URL_KEY, data.server_url);
                cachedServerUrl = data.server_url;
                console.log('✅ 서버가 알려준 IP로 업데이트:', data.server_url);
              }
              return data.server_url;
            }
            cachedServerUrl = savedUrl;
            return savedUrl;
          }
        } catch (error) {
          // 저장된 URL이 실패하면 자동 감지 시도
          console.log('⚠️ 저장된 URL 실패, 자동 감지 시작:', savedUrl, error);
          // 실패한 URL을 localStorage에서 제거하여 다음에는 자동 감지부터 시작
          localStorage.removeItem(SERVER_URL_KEY);
          cachedServerUrl = null;
        }
      }
    }
  }
  
  // 2. 환경 변수 확인
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) {
    const envUrl = import.meta.env.VITE_API_BASE_URL;
    try {
      const response = await fetch(`${envUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      if (response.ok) {
        const data = await response.json();
        const serverUrl = data.server_url || envUrl;
        if (typeof window !== 'undefined') {
          localStorage.setItem(SERVER_URL_KEY, serverUrl);
        }
        cachedServerUrl = serverUrl;
        return serverUrl;
      }
    } catch {
      // 환경 변수 URL도 실패
    }
  }
  
  // 3. 자동 감지: 일반적인 IP 대역 시도 (효율적으로)
  if (typeof window !== 'undefined') {
    let platform = 'web';
    try {
      // 안드로이드에서는 이미 로드된 Capacitor 사용
      if ((window as any).Capacitor) {
        const Capacitor = (window as any).Capacitor;
        platform = Capacitor.getPlatform();
      } else {
        // 동적 import 시도 (안전하게)
        try {
          const { Capacitor } = await import('@capacitor/core');
          platform = Capacitor.getPlatform();
        } catch {
          // 동적 import 실패 시 기본값 사용
          platform = 'web';
        }
      }
    } catch (error) {
      console.error('플랫폼 감지 실패:', error);
      platform = 'web';
    }
    
    // 시도할 IP 목록 (일반적인 로컬 네트워크 대역만)
    const ipCandidates: string[] = [];
    
    if (platform === 'android') {
      ipCandidates.push('http://10.0.2.2:3000'); // 에뮬레이터
      // 현재 서버 IP 우선 시도 (192.168.50.27)
      ipCandidates.push('http://192.168.50.27:3000');
      // 일반적인 로컬 네트워크 IP 대역
      const commonIPs = [1, 27, 50, 100, 200, 254];
      for (const subnet of [50, 0, 1]) {
        for (const ip of commonIPs) {
          const url = `http://192.168.${subnet}.${ip}:3000`;
          if (!ipCandidates.includes(url)) {
            ipCandidates.push(url);
          }
        }
      }
    } else if (platform === 'ios') {
      ipCandidates.push('http://localhost:3000'); // 시뮬레이터
      // 현재 서버 IP 우선 시도 (192.168.50.27)
      ipCandidates.push('http://192.168.50.27:3000');
      const commonIPs = [1, 27, 50, 68, 74, 100, 200, 254];
      for (const subnet of [50, 0, 1, 68]) {
        for (const ip of commonIPs) {
          const url = `http://192.168.${subnet}.${ip}:3000`;
          if (!ipCandidates.includes(url)) {
            ipCandidates.push(url);
          }
        }
      }
    } else {
      ipCandidates.push('http://localhost:3000');
      // 웹에서도 현재 서버 IP 시도
      ipCandidates.push('http://192.168.50.27:3000');
    }
    
    // 병렬로 여러 IP 시도 (첫 번째 성공한 응답 즉시 반환)
    const promises = ipCandidates.map(async (url) => {
      try {
        const response = await fetch(`${url}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(800) // 800ms로 단축
        });
        if (response.ok) {
          const data = await response.json();
          const serverUrl = data.server_url || url;
          // 성공한 URL을 localStorage에 저장
          if (typeof window !== 'undefined') {
            localStorage.setItem(SERVER_URL_KEY, serverUrl);
          }
          cachedServerUrl = serverUrl;
          console.log('✅ 서버 자동 감지 성공:', serverUrl);
          return serverUrl;
        }
      } catch {
        // 실패한 IP는 무시
      }
      return null;
    });
    
    // Promise.race로 첫 번째 완료된 응답 확인 (성공/실패 모두 포함)
    try {
      const result = await Promise.race(promises);
      if (result) {
        return result;
      }
    } catch {
      // 첫 번째가 실패한 경우 계속 진행
    }
    
    // 모든 시도 결과 확인
    const results = await Promise.allSettled(promises);
    const successResult = results.find(r => 
      r.status === 'fulfilled' && r.value !== null
    );
    if (successResult && successResult.status === 'fulfilled') {
      return successResult.value;
    }
  }
  
  // 4. 기본값 반환
  const defaultUrl = getServerUrl();
  return defaultUrl;
}

/**
 * 서버 URL 저장
 */
export function setServerUrl(url: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(SERVER_URL_KEY, url);
  }
}

/**
 * 서버 URL 초기화 (기본값으로 되돌림)
 */
export function resetServerUrl(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(SERVER_URL_KEY);
  }
}

