/**
 * 서버 URL 설정 관리
 * 자동으로 서버 IP를 감지하여 사용
 */

const SERVER_URL_KEY = 'server_url';

// Railway 배포 URL (환경 변수에서 가져오거나 하드코딩)
// 배포 후 Railway에서 제공하는 URL로 변경하세요 (예: 'your-app.railway.app')
const RAILWAY_URL = typeof import.meta !== 'undefined' && import.meta.env?.VITE_RAILWAY_URL 
  ? import.meta.env.VITE_RAILWAY_URL 
  : 'poseul-production.up.railway.app'; // Railway URL (기본값)

// 하드코딩된 서버 IP 목록 (우선 사용)
// 현재 네트워크: 192.168.68.x 대역 (현재 컴퓨터 IP: 192.168.68.66)
const HARDCODED_SERVER_IPS = ['192.168.68.66', '172.29.88.134', '172.15.5.58', '192.168.0.143', '172.30.1.68', '192.168.68.75', '192.168.68.76', '192.168.68.77', '192.168.68.72', '172.15.5.72', '192.168.219.125'];
const HARDCODED_SERVER_URL = `http://${HARDCODED_SERVER_IPS[0]}:3000`; // 첫 번째를 기본값으로 사용

// 동기 버전 (기본값 반환용)
let cachedServerUrl: string | null = null;

/**
 * 서버 URL 가져오기 (동기 버전 - 빠른 접근용)
 * 우선순위: Railway URL > 웹 환경에서는 localhost > 하드코딩된 IP > 캐시 > localStorage > 환경 변수 > 기본값
 */
export function getServerUrl(): string {
  // Railway URL이 설정되어 있으면 최우선 사용 (HTTPS)
  if (RAILWAY_URL) {
    const railwayUrl = RAILWAY_URL.startsWith('http') ? RAILWAY_URL : `https://${RAILWAY_URL}`;
    cachedServerUrl = railwayUrl;
    console.log(`🚂 [getServerUrl] Railway URL 사용: ${railwayUrl}`);
    return railwayUrl;
  } else {
    console.log('⚠️ [getServerUrl] Railway URL이 설정되지 않았습니다.');
  }
  
  // 웹 환경에서는 localhost 우선 사용
  if (typeof window !== 'undefined') {
    try {
      if (!(window as any).Capacitor || !(window as any).Capacitor.isNativePlatform()) {
        // 웹 브라우저 환경
        const webUrl = 'http://localhost:3000';
        cachedServerUrl = webUrl;
        return webUrl;
      }
    } catch (e) {
      // Capacitor 접근 실패 시 웹으로 간주
      const webUrl = 'http://localhost:3000';
      cachedServerUrl = webUrl;
      return webUrl;
    }
  }
  
  // 네이티브 앱에서는 하드코딩된 서버 URL 우선 사용
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
      // Railway URL이 설정되어 있는데 localStorage에 다른 URL이 저장되어 있으면 제거
      if (RAILWAY_URL && !savedUrl.includes('railway.app')) {
        console.log('🗑️ [iOS] Railway URL이 설정되어 있는데 다른 URL이 저장됨, 제거:', savedUrl);
        localStorage.removeItem(SERVER_URL_KEY);
        cachedServerUrl = null;
        // Railway URL 반환
        const railwayUrl = RAILWAY_URL.startsWith('http') ? RAILWAY_URL : `https://${RAILWAY_URL}`;
        return railwayUrl;
      }
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
  // Railway URL이 설정되어 있으면 최우선 시도 (HTTPS)
  console.log(`🔍 [autoDetectServerUrl] Railway URL 확인: ${RAILWAY_URL || 'null'}`);
  if (RAILWAY_URL) {
    const railwayUrl = RAILWAY_URL.startsWith('http') ? RAILWAY_URL : `https://${RAILWAY_URL}`;
    console.log(`🚂 [autoDetectServerUrl] Railway 서버 우선 시도: ${railwayUrl}`);
    try {
      const response = await fetch(`${railwayUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(10000)
      });
      if (response.ok) {
        const data = await response.json();
        const serverUrl = data.server_url || railwayUrl;
        if (typeof window !== 'undefined') {
          localStorage.setItem(SERVER_URL_KEY, serverUrl);
        }
        cachedServerUrl = serverUrl;
        console.log('✅ [autoDetectServerUrl] Railway 서버 연결 성공:', serverUrl);
        return serverUrl;
      } else {
        console.log(`⚠️ [autoDetectServerUrl] Railway 서버 응답 실패 (${response.status}), 다른 IP 시도...`);
      }
    } catch (error: any) {
      console.log('⚠️ [autoDetectServerUrl] Railway 서버 연결 실패, 다른 IP 시도...', error?.message || error);
    }
  } else {
    console.log('⚠️ [autoDetectServerUrl] Railway URL이 설정되지 않았습니다.');
  }
  
  // 웹 환경에서는 localhost 우선 시도
  if (typeof window !== 'undefined') {
    try {
      if (!(window as any).Capacitor || !(window as any).Capacitor.isNativePlatform()) {
        // 웹 브라우저 환경 - localhost 먼저 시도
        try {
          const response = await fetch('http://localhost:3000/health', {
            method: 'GET',
            signal: AbortSignal.timeout(10000) // 10초로 증가
          });
          if (response.ok) {
            const data = await response.json();
            const serverUrl = data.server_url || 'http://localhost:3000';
            if (typeof window !== 'undefined') {
              localStorage.setItem(SERVER_URL_KEY, serverUrl);
            }
            cachedServerUrl = serverUrl;
            console.log('✅ 웹 환경에서 localhost 연결 성공:', serverUrl);
            return serverUrl;
          }
        } catch (e) {
          console.log('⚠️ localhost 연결 실패, 다른 IP 시도...');
        }
      }
    } catch (e) {
      // Capacitor 접근 실패 시 웹으로 간주하고 localhost 시도
      try {
        const response = await fetch('http://localhost:3000/health', {
          method: 'GET',
          signal: AbortSignal.timeout(10000) // 10초로 증가
        });
        if (response.ok) {
          const serverUrl = 'http://localhost:3000';
          if (typeof window !== 'undefined') {
            localStorage.setItem(SERVER_URL_KEY, serverUrl);
          }
          cachedServerUrl = serverUrl;
          console.log('✅ 웹 환경에서 localhost 연결 성공:', serverUrl);
          return serverUrl;
        }
      } catch (err) {
        console.log('⚠️ localhost 연결 실패, 다른 IP 시도...');
      }
    }
  }
  
  // 0. 하드코딩된 서버 URL 목록 확인 (병렬로 시도, 첫 번째 IP 우선)
  // 주의: Railway URL이 있으면 이미 위에서 처리되었으므로 여기서는 하드코딩된 IP만 시도
  console.log(`⚠️ [autoDetectServerUrl] Railway URL 시도 실패 또는 없음, 하드코딩된 IP 목록 시도 시작`);
  const hardcodedUrls = HARDCODED_SERVER_IPS.map(ip => `http://${ip}:3000`);
  console.log(`🔍 하드코딩된 서버 IP 목록 확인 중: ${HARDCODED_SERVER_IPS.join(', ')}`);
  
  // 첫 번째 IP를 먼저 시도 (현재 네트워크 IP)
  const firstUrl = hardcodedUrls[0];
  try {
    console.log(`🎯 우선 시도: ${firstUrl}`);
    const response = await fetch(`${firstUrl}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(10000) // 10초로 증가 (iOS 네트워크 지연 대응)
    });
    if (response.ok) {
      const data = await response.json();
      const serverUrl = data.server_url || firstUrl;
      if (typeof window !== 'undefined') {
        localStorage.setItem(SERVER_URL_KEY, serverUrl);
      }
      cachedServerUrl = serverUrl;
      console.log('✅ 우선 IP 연결 성공:', serverUrl);
      return serverUrl;
    }
  } catch (error) {
    console.log(`⚠️ 우선 IP 실패, 다른 IP 시도...`);
  }
  
  // 나머지 IP들을 병렬로 시도
  const hardcodedPromises = hardcodedUrls.slice(1).map(async (url) => {
    try {
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000) // 5초로 증가
      });
      if (response.ok) {
        const data = await response.json();
        const serverUrl = data.server_url || url;
        if (typeof window !== 'undefined') {
          localStorage.setItem(SERVER_URL_KEY, serverUrl);
        }
        cachedServerUrl = serverUrl;
        console.log('✅ 하드코딩된 서버 URL 연결 성공:', serverUrl);
        return serverUrl;
      }
    } catch (error) {
      // 조용히 실패 처리
    }
    return null;
  });
  
  // 첫 번째 성공한 URL 반환
  const results = await Promise.allSettled(hardcodedPromises);
  const successResult = results.find(r => 
    r.status === 'fulfilled' && r.value !== null && r.value !== ''
  );
  if (successResult && successResult.status === 'fulfilled' && successResult.value) {
    return successResult.value;
  }
  
  console.log(`⚠️ 하드코딩된 서버 URL 목록 모두 연결 실패, 다른 IP 시도...`);
  
  // 1. 저장된 URL이 있으면 먼저 확인 (빠른 확인)
  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem(SERVER_URL_KEY);
    if (savedUrl) {
      // Railway URL이 설정되어 있는데 localStorage에 다른 URL이 저장되어 있으면 제거
      if (RAILWAY_URL && !savedUrl.includes('railway.app')) {
        console.log('🗑️ [iOS] Railway URL이 설정되어 있는데 다른 URL이 저장됨, 제거:', savedUrl);
        localStorage.removeItem(SERVER_URL_KEY);
        cachedServerUrl = null;
        // Railway URL로 계속 진행하지 않고 자동 감지 계속
      } else if (!savedUrl.includes('railway.app')) {
        // 현재 하드코딩된 첫 번째 IP와 다르면 제거 (IP가 변경되었을 수 있음)
        const currentFirstIp = HARDCODED_SERVER_IPS[0];
        if (savedUrl.includes(currentFirstIp) === false && savedUrl.match(/192\.168\.68\.\d+/)) {
          console.log(`⚠️ 저장된 URL이 현재 IP(${currentFirstIp})와 다름, 자동 감지 시작:`, savedUrl);
          localStorage.removeItem(SERVER_URL_KEY);
          cachedServerUrl = null;
        }
        // 잘못된 IP 대역이면 즉시 제거하고 자동 감지 시작
        // 10.0.2.2는 에뮬레이터용이므로 실제 기기에서는 작동하지 않음
        else if (savedUrl.includes('192.168.68.74') || savedUrl.includes('192.168.68.76') || savedUrl.includes('192.168.68.77') || savedUrl.includes('192.168.0.57') || savedUrl.includes('10.0.2.2')) {
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
      // 현재 네트워크 IP 최우선 시도 (현재 컴퓨터 IP - 첫 번째)
      ipCandidates.push(`http://${HARDCODED_SERVER_IPS[0]}:3000`);
      // 하드코딩된 서버 IP 목록 나머지 시도
      HARDCODED_SERVER_IPS.slice(1).forEach(ip => {
        ipCandidates.push(`http://${ip}:3000`);
      });
      // 192.168.0.x 대역 시도 (현재 네트워크)
      for (const ip of [1, 100, 143, 200, 254]) {
        const url = `http://192.168.0.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 네트워크 IP 시도 (172.15.5.72 - 이전 네트워크)
      ipCandidates.push('http://172.15.5.72:3000');
      // 172.15.5.x 대역 시도
      for (const ip of [1, 2, 10, 20, 50, 72, 100, 200, 254]) {
        const url = `http://172.15.5.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 서버 IP 시도 (172.30.1.1 - 이전 네트워크)
      ipCandidates.push('http://172.30.1.1:3000');
      ipCandidates.push('http://192.168.50.27:3000');
      
      // 192.168.219.x 대역도 시도
      for (const ip of [1, 100, 125, 200, 254]) {
        const url = `http://192.168.219.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 172.30.x.x 대역도 시도
      const commonIPs172 = [1, 2, 10, 20, 100, 200, 254];
      for (const ip of commonIPs172) {
        const url = `http://172.30.1.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 일반적인 로컬 네트워크 IP 대역 (더 넓은 범위)
      const subnets = [0, 1, 50, 68, 100, 192, 219];
      const commonIPs = [1, 2, 10, 20, 27, 50, 57, 68, 72, 74, 75, 77, 100, 101, 125, 143, 200, 254];
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
      // 현재 네트워크 IP 최우선 시도 (현재 컴퓨터 IP - 첫 번째)
      ipCandidates.push(`http://${HARDCODED_SERVER_IPS[0]}:3000`);
      // 하드코딩된 서버 IP 목록 나머지 시도
      HARDCODED_SERVER_IPS.slice(1).forEach(ip => {
        ipCandidates.push(`http://${ip}:3000`);
      });
      // 192.168.0.x 대역 시도 (현재 네트워크)
      for (const ip of [1, 100, 143, 200, 254]) {
        const url = `http://192.168.0.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 네트워크 IP 시도 (172.15.5.72 - 이전 네트워크)
      ipCandidates.push('http://172.15.5.72:3000');
      // 172.15.5.x 대역 시도
      for (const ip of [1, 2, 10, 20, 50, 72, 100, 200, 254]) {
        const url = `http://172.15.5.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 서버 IP 시도 (172.30.1.1 - 이전 네트워크)
      ipCandidates.push('http://172.30.1.1:3000');
      ipCandidates.push('http://192.168.50.27:3000');
      
      // 192.168.219.x 대역도 시도
      for (const ip of [1, 100, 125, 200, 254]) {
        const url = `http://192.168.219.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 일반적인 서브넷 대역을 먼저 시도 (더 넓은 범위)
      const subnets = [0, 1, 50, 68, 100, 192, 219];
      const commonIPs = [1, 2, 10, 20, 27, 50, 57, 68, 72, 74, 75, 77, 100, 101, 125, 143, 200, 254];
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
      // 웹에서도 현재 네트워크 IP 최우선 시도 (현재 컴퓨터 IP - 첫 번째)
      ipCandidates.push(`http://${HARDCODED_SERVER_IPS[0]}:3000`);
      // 하드코딩된 서버 IP 목록 나머지 시도
      HARDCODED_SERVER_IPS.slice(1).forEach(ip => {
        ipCandidates.push(`http://${ip}:3000`);
      });
      // 192.168.0.x 대역 시도 (현재 네트워크)
      for (const ip of [1, 100, 143, 200, 254]) {
        const url = `http://192.168.0.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 네트워크 IP 시도 (172.15.5.72 - 이전 네트워크)
      ipCandidates.push('http://172.15.5.72:3000');
      // 172.15.5.x 대역 시도
      for (const ip of [1, 2, 10, 20, 50, 72, 100, 200, 254]) {
        const url = `http://172.15.5.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 현재 서버 IP 시도 (172.30.1.1 - 이전 네트워크)
      ipCandidates.push('http://172.30.1.1:3000');
      // 이전 서버 IP도 시도
      ipCandidates.push('http://192.168.0.57:3000');
      ipCandidates.push('http://192.168.50.27:3000');
      
      // 192.168.219.x 대역도 시도
      for (const ip of [1, 100, 125, 200, 254]) {
        const url = `http://192.168.219.${ip}:3000`;
        if (!ipCandidates.includes(url)) {
          ipCandidates.push(url);
        }
      }
      
      // 웹에서도 일반적인 IP 대역 시도
      const subnets = [0, 1, 50, 68, 100, 192, 219];
      const commonIPs = [1, 2, 10, 20, 27, 50, 57, 68, 72, 74, 75, 77, 100, 101, 125, 143, 200, 254];
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
    console.log(`🔍 ${ipCandidates.length}개의 IP 후보 자동 감지 시작...`);
    const promises = ipCandidates.map(async (url, index) => {
      try {
        // 처음 3개만 상세 로그
        if (index < 3) {
        console.log(`  [${index + 1}/${ipCandidates.length}] 시도 중: ${url}`);
        }
        const response = await fetch(`${url}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(10000) // 10초로 증가 (iOS 네트워크 지연 대응)
        });
        if (response.ok) {
          const data = await response.json();
          const serverUrl = data.server_url || url;
          // 성공한 URL을 localStorage에 저장
          if (typeof window !== 'undefined') {
            localStorage.setItem(SERVER_URL_KEY, serverUrl);
          }
          cachedServerUrl = serverUrl;
          console.log(`✅ 서버 자동 감지 성공: ${serverUrl} (${index + 1}/${ipCandidates.length}번째 시도)`);
          return serverUrl;
        }
      } catch (error: any) {
        // 실패한 IP는 로그 없이 무시 (처음 3개만 상세 로그)
        if (error.name !== 'AbortError' && index < 3) {
          // 조용히 실패 처리
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
    const results = await Promise.allSettled(promises);
    const successResult = results.find(r => 
      r.status === 'fulfilled' && r.value !== null && r.value !== ''
    );
    if (successResult && successResult.status === 'fulfilled' && successResult.value) {
      const detectedUrl = successResult.value;
      console.log('✅ 최종 감지된 서버 URL:', detectedUrl);
      return detectedUrl;
    }
    
    // 모든 시도가 실패한 경우 (로그 최소화)
    console.error('❌ 모든 IP 시도 실패 - 서버를 찾을 수 없습니다');
    console.error(`   시도한 IP 개수: ${ipCandidates.length}개`);
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

