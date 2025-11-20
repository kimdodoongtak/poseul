/**
 * 서버 URL 설정 관리
 * 자동으로 서버 IP를 감지하여 사용
 */

const SERVER_URL_KEY = 'server_url';

// 하드코딩된 서버 IP (우선 사용)
const HARDCODED_SERVER_IP = '192.168.68.72';
const HARDCODED_SERVER_URL = `http://${HARDCODED_SERVER_IP}:3000`;

// 동기 버전 (기본값 반환용)
let cachedServerUrl: string | null = null;

/**
 * 서버 URL 가져오기 (동기 버전 - 빠른 접근용)
 * 우선순위: 하드코딩된 IP > 캐시 > localStorage > 환경 변수 > 기본값
 */
export function getServerUrl(): string {
  // 하드코딩된 서버 URL 우선 사용
  if (HARDCODED_SERVER_URL) {
    cachedServerUrl = HARDCODED_SERVER_URL;
    return HARDCODED_SERVER_URL;
  }
  
  // 캐시된 URL이 있으면 사용 (단, 10.0.2.2는 제외)
  if (cachedServerUrl && !cachedServerUrl.includes('10.0.2.2')) {
    // iOS에서 localhost인 경우 빈 문자열 반환하여 자동 감지 유도
    if (cachedServerUrl.includes('localhost') && typeof window !== 'undefined') {
      try {
        if ((window as any).Capacitor) {
          const Capacitor = (window as any).Capacitor;
          if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
            console.log('⚠️ iOS에서 localhost 감지, 자동 감지 필요');
            return '';
          }
        }
      } catch (e) {
        // 무시
      }
    }
    return cachedServerUrl;
  }
  
  // localStorage에서 가져오기 (10.0.2.2는 제외)
  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem(SERVER_URL_KEY);
    if (savedUrl && !savedUrl.includes('10.0.2.2')) {
      // iOS에서 localhost인 경우 제외
      if (savedUrl.includes('localhost')) {
        try {
          if ((window as any).Capacitor) {
            const Capacitor = (window as any).Capacitor;
            if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
              console.log('⚠️ 저장된 localhost URL 감지, 자동 감지 필요');
              localStorage.removeItem(SERVER_URL_KEY);
              return '';
            }
          }
        } catch (e) {
          // 무시
        }
      }
      cachedServerUrl = savedUrl;
      return savedUrl;
    } else if (savedUrl && savedUrl.includes('10.0.2.2')) {
      // 10.0.2.2가 저장되어 있으면 제거
      console.log('🗑️ 에뮬레이터용 URL 감지, 제거:', savedUrl);
      localStorage.removeItem(SERVER_URL_KEY);
      cachedServerUrl = null;
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
            // iOS에서는 localhost가 기기 자체를 가리키므로 빈 문자열 반환하여 자동 감지 유도
            return '';
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
  // 0. 하드코딩된 서버 URL 우선 확인
  try {
    const response = await fetch(`${HARDCODED_SERVER_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    if (response.ok) {
      const data = await response.json();
      const serverUrl = data.server_url || HARDCODED_SERVER_URL;
      if (typeof window !== 'undefined') {
        localStorage.setItem(SERVER_URL_KEY, serverUrl);
      }
      cachedServerUrl = serverUrl;
      console.log('✅ 하드코딩된 서버 URL 연결 성공:', serverUrl);
      return serverUrl;
    }
  } catch (error) {
    console.log(`⚠️ 하드코딩된 서버 URL (${HARDCODED_SERVER_URL}) 연결 실패, 다른 IP 시도...`);
  }
  
  // 1. 저장된 URL이 있으면 먼저 확인 (빠른 확인)
  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem(SERVER_URL_KEY);
    if (savedUrl) {
      // 잘못된 IP 대역이면 즉시 제거하고 자동 감지 시작
      // 10.0.2.2는 에뮬레이터용이므로 실제 기기에서는 작동하지 않음
      if (savedUrl.includes('192.168.0.143') || savedUrl.includes('192.168.68.74') || savedUrl.includes('10.0.2.2')) {
        console.log('⚠️ 잘못된 URL 감지 (에뮬레이터용 또는 잘못된 IP), 자동 감지 시작:', savedUrl);
        localStorage.removeItem(SERVER_URL_KEY);
        cachedServerUrl = null;
      } else {
        // 유효한 URL이면 health 체크 후 서버가 알려준 IP로 업데이트
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
    
    // 시도할 IP 목록 (더 넓은 범위로 자동 감지)
    const ipCandidates: string[] = [];
    
    if (platform === 'android') {
      // 실제 기기에서는 10.0.2.2가 작동하지 않으므로, 실제 IP를 먼저 시도
      // 하드코딩된 서버 IP 최우선 시도
      ipCandidates.push(HARDCODED_SERVER_URL);
      // 현재 서버 IP 최우선 시도 (172.30.1.1 - 사용자 컴퓨터 IP)
      ipCandidates.push('http://172.30.1.1:3000');
      // 이전 서버 IP도 시도 (192.168.50.27)
      ipCandidates.push('http://192.168.50.27:3000');
      
      // 172.30.x.x 대역도 시도
      const commonIPs172 = [1, 2, 10, 20, 100, 200, 254];
      for (const ip of commonIPs172) {
        const url = `http://172.30.1.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 일반적인 로컬 네트워크 IP 대역 (더 넓은 범위)
      const subnets = [0, 1, 50, 68, 100, 192];
      const commonIPs = [1, 2, 10, 20, 27, 50, 68, 74, 100, 101, 200, 254];
      for (const subnet of subnets) {
        for (const ip of commonIPs) {
          const url = `http://192.168.${subnet}.${ip}:3000`;
          if (!ipCandidates.includes(url)) {
            ipCandidates.push(url);
          }
        }
      }
      
      // 마지막에 에뮬레이터용 IP 시도 (실제 기기에서는 실패할 것)
      ipCandidates.push('http://10.0.2.2:3000');
    } else if (platform === 'ios') {
      // 하드코딩된 서버 IP 최우선 시도
      ipCandidates.push(HARDCODED_SERVER_URL);
      // 현재 서버 IP 최우선 시도 (172.30.1.1 - 사용자 컴퓨터 IP)
      ipCandidates.push('http://172.30.1.1:3000');
      // 이전 서버 IP도 시도 (192.168.50.27)
      ipCandidates.push('http://192.168.50.27:3000');
      // 일반적인 서브넷 대역을 먼저 시도 (더 넓은 범위)
      const subnets = [0, 1, 50, 68, 100, 192];
      const commonIPs = [1, 2, 10, 20, 27, 50, 68, 74, 100, 101, 200, 254];
      for (const subnet of subnets) {
        for (const ip of commonIPs) {
          const url = `http://192.168.${subnet}.${ip}:3000`;
          if (!ipCandidates.includes(url)) {
            ipCandidates.push(url);
          }
        }
      }
      // 시뮬레이터를 위한 localhost는 마지막에만 추가 (실제 기기에서는 실패하지만 시뮬레이터에서는 작동)
      ipCandidates.push('http://localhost:3000');
    } else {
      ipCandidates.push('http://localhost:3000');
      // 하드코딩된 서버 IP 최우선 시도
      ipCandidates.push(HARDCODED_SERVER_URL);
      // 웹에서도 현재 서버 IP 최우선 시도 (172.30.1.1)
      ipCandidates.push('http://172.30.1.1:3000');
      // 이전 서버 IP도 시도
      ipCandidates.push('http://192.168.50.27:3000');
      // 웹에서도 일반적인 IP 대역 시도
      const subnets = [0, 1, 50, 68, 100, 192];
      const commonIPs = [1, 2, 10, 20, 27, 50, 68, 74, 100, 101, 200, 254];
      for (const subnet of subnets) {
        for (const ip of commonIPs) {
          const url = `http://192.168.${subnet}.${ip}:3000`;
          if (!ipCandidates.includes(url)) {
            ipCandidates.push(url);
          }
        }
      }
    }
    
    // 병렬로 여러 IP 시도 (첫 번째 성공한 응답 즉시 반환)
    console.log(`🔍 ${ipCandidates.length}개의 IP 후보 시도 시작:`, ipCandidates.slice(0, 5), '...');
    const promises = ipCandidates.map(async (url, index) => {
      try {
        console.log(`  [${index + 1}/${ipCandidates.length}] 시도 중: ${url}`);
        const response = await fetch(`${url}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(2000) // 2초로 증가 (서버 응답이 느릴 수 있음)
        });
        if (response.ok) {
          const data = await response.json();
          const serverUrl = data.server_url || url;
          // 성공한 URL을 localStorage에 저장
          if (typeof window !== 'undefined') {
            localStorage.setItem(SERVER_URL_KEY, serverUrl);
          }
          cachedServerUrl = serverUrl;
          console.log(`✅ 서버 자동 감지 성공: ${serverUrl} (시도 ${index + 1}/${ipCandidates.length})`);
          return serverUrl;
        } else {
          console.log(`  ❌ ${url} 응답 실패: ${response.status}`);
        }
      } catch (error: any) {
        // 실패한 IP는 로그만 남기고 무시 (처음 몇 개만 상세 로그)
        if (error.name !== 'AbortError') {
          if (index < 3) {
            console.log(`  ❌ ${url} 연결 실패: ${error.message || '알 수 없는 오류'}`);
          }
        }
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
    console.log('🔍 모든 IP 시도 완료, 결과 확인 중...');
    const results = await Promise.allSettled(promises);
    const successResult = results.find(r => 
      r.status === 'fulfilled' && r.value !== null && r.value !== ''
    );
    if (successResult && successResult.status === 'fulfilled' && successResult.value) {
      const detectedUrl = successResult.value;
      console.log('✅ 최종 감지된 서버 URL:', detectedUrl);
      return detectedUrl;
    }
    
    // 모든 시도가 실패한 경우
    console.error('❌ 모든 IP 시도 실패 - 서버를 찾을 수 없습니다');
    console.error('   시도한 IP 개수:', ipCandidates.length);
    console.error('   실패한 결과:', results.filter(r => r.status === 'rejected').length, '개');
    console.error('시도한 IP 범위:', {
      subnets: [0, 1, 50, 68, 100, 192],
      commonIPs: [1, 2, 10, 20, 27, 50, 68, 74, 100, 101, 200, 254],
      total: ipCandidates.length
    });
  }
  
  // 4. 기본값 반환 (10.0.2.2는 제외)
  console.warn('⚠️ 자동 감지 실패, 기본값 반환 (10.0.2.2 제외)');
  const defaultUrl = getServerUrl();
  // 10.0.2.2가 기본값이면 빈 문자열 반환하여 사용자가 수동 입력하도록 유도
  if (defaultUrl && defaultUrl !== '' && !defaultUrl.includes('10.0.2.2')) {
    return defaultUrl;
  }
  
  // 기본값도 없거나 10.0.2.2면 에러
  if (defaultUrl.includes('10.0.2.2')) {
    console.error('❌ 기본값이 10.0.2.2입니다. 서버를 찾을 수 없습니다.');
    throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요. (포트 3000)');
  }
  
  throw new Error('서버 URL을 찾을 수 없습니다.');
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

