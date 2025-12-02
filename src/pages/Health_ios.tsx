import React, { useState, useEffect, useRef } from 'react';
import { App } from '@capacitor/app';
import { useLocation } from 'react-router-dom';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
  IonText,
  IonItem,
  IonLabel,
  IonInput,
  IonButton,
  IonCard,
  IonCardHeader,
  IonCardTitle,
  IonCardContent,
  IonToggle,
  IonIcon,
  IonGrid,
  IonRow,
  IonCol,
  IonSelect,
  IonSelectOption
} from '@ionic/react';
import { personOutline, closeOutline, cameraOutline } from 'ionicons/icons';
import SignIn from '../components/SignIn';
import SignUp from '../components/SignUp';
import './Health_ios.css';
import { isAuthenticated, logout } from '../services/AuthService';
import { getServerUrl, autoDetectServerUrl } from '../services/ServerConfig';
import ChartDataService, {
  NightChartData,
} from '../services/ChartDataService';
import TemperatureChart from '../components/TemperatureChart';
import HeartRateChart from '../components/HeartRateChart';
import { ModelService, IotService, HealthDataService } from '../services';

interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

const Health_ios: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [gender, setGender] = useState<string>('0'); // 0: 여성, 1: 남성
  const [healthData, setHealthData] = useState<HealthData>({
    heartRate: null,
    hrv: null,
    oxygenSaturation: null,
  });
  const [backgroundMonitoring, setBackgroundMonitoring] = useState<boolean>(false);
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  
  // 차트 데이터 상태
  const [chartData, setChartData] = useState<NightChartData | null>(null);
  const [lastCollectionTime, setLastCollectionTime] = useState<number>(0);
  const lastCollectionTimeRef = useRef<number>(0); // useRef로 변경하여 의존성 문제 해결
  const collectionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // 초기 설정 단계 관리
  const [setupStep, setSetupStep] = useState<'info' | 'permission' | 'monitoring' | 'complete'>('info');
  const [isSetupComplete, setIsSetupComplete] = useState<boolean>(false);
  const [hasHealthKitPermission, setHasHealthKitPermission] = useState<boolean>(false);
  
  // UI 템플릿 관련 상태
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [showSignUp, setShowSignUp] = useState<boolean>(false);
  const [showUserInfo, setShowUserInfo] = useState<boolean>(false);
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [profileImage, setProfileImage] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>('');
  const location = useLocation();
  const loginSuccessRef = useRef<boolean>(false); // 로그인 성공 플래그

  // URL 파라미터 변경 감지 (IoT 페이지에서 로그인 요청 시)
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    if (searchParams.get('showLogin') === 'true') {
      setShowSignIn(true);
      // URL에서 파라미터 제거 (뒤로가기 시 다시 열리지 않도록)
      window.history.replaceState({}, '', '/health_ios');
    }
  }, [location.search]);

  // 사용자 정보 로드 (서버에서 가져오기)
  const loadUserInfo = async () => {
    if (!isAuthenticated()) return;
    
    try {
      const { getAuthHeaders, getUserNo } = await import('../services/AuthService');
      const userNo = getUserNo();
      if (!userNo) return;
      
      const baseUrl = getServerUrl();
      
      // 1. 사용자 기본 정보 (아이디, 프로필 이미지)
      const meResponse = await fetch(`${baseUrl}/auth/me`, {
        headers: getAuthHeaders()
      });
      
      if (meResponse.ok) {
        const meResult = await meResponse.json();
        setUserId(meResult.id || '');
        
        // 프로필 이미지 로드 (사용자별로 구분)
        if (meResult.profile_image_url) {
          const imageUrl = meResult.profile_image_url.startsWith('http') 
            ? meResult.profile_image_url 
            : `${baseUrl}${meResult.profile_image_url}`;
          setProfileImage(imageUrl);
          localStorage.setItem(`profile_image_${userNo}`, imageUrl);
        } else {
          const savedImage = localStorage.getItem(`profile_image_${userNo}`);
          if (savedImage) {
            setProfileImage(savedImage);
          } else {
            // 기본 프로필 이미지 사용 (null로 설정하면 기본 이미지가 표시됨)
            setProfileImage(null);
          }
        }
      }
      
      // 2. 사용자 건강 정보 (나이, BMI, 성별) - predicted_results에서 최신 데이터 가져오기
      const healthResponse = await fetch(`${baseUrl}/healthdata/latest`, {
        headers: getAuthHeaders()
      });
      
      if (healthResponse.ok) {
        const healthResult = await healthResponse.json();
        if (healthResult.success && healthResult.data) {
          // 서버에서 가져온 데이터로 업데이트
          if (healthResult.data.age) {
            const ageValue = String(healthResult.data.age);
            setAge(ageValue);
            localStorage.setItem(`userAge_${userNo}`, ageValue);
          } else {
            // 서버에 없으면 localStorage에서 가져오기
            const savedAge = localStorage.getItem(`userAge_${userNo}`);
            if (savedAge) {
              setAge(savedAge);
            }
          }
          
          if (healthResult.data.bmi) {
            const bmiValue = String(healthResult.data.bmi);
            setBmi(bmiValue);
            localStorage.setItem(`userBmi_${userNo}`, bmiValue);
          } else {
            const savedBmi = localStorage.getItem(`userBmi_${userNo}`);
            if (savedBmi) {
              setBmi(savedBmi);
            }
          }
          
          if (healthResult.data.gender !== undefined && healthResult.data.gender !== null) {
            // gender가 숫자면 문자열로 변환 (0 -> '0', 1 -> '1')
            const genderValue = String(healthResult.data.gender);
            setGender(genderValue);
            localStorage.setItem(`userGender_${userNo}`, genderValue);
          } else {
            const savedGender = localStorage.getItem(`userGender_${userNo}`);
            if (savedGender) {
              setGender(savedGender);
            }
          }
        }
      } else {
        // 서버에서 가져오기 실패 시 localStorage에서 가져오기
        const savedAge = localStorage.getItem(`userAge_${userNo}`);
        const savedBmi = localStorage.getItem(`userBmi_${userNo}`);
        const savedGender = localStorage.getItem(`userGender_${userNo}`);
        
        if (savedAge) setAge(savedAge);
        if (savedBmi) setBmi(savedBmi);
        if (savedGender) setGender(savedGender);
      }
    } catch (error) {
      console.error('사용자 정보 로드 실패:', error);
      // 에러 발생 시에도 localStorage에서 가져오기 시도
      try {
        const { getUserNo } = await import('../services/AuthService');
        const userNo = getUserNo();
        if (userNo) {
          const savedAge = localStorage.getItem(`userAge_${userNo}`);
          const savedBmi = localStorage.getItem(`userBmi_${userNo}`);
          const savedGender = localStorage.getItem(`userGender_${userNo}`);
          
          if (savedAge) setAge(savedAge);
          if (savedBmi) setBmi(savedBmi);
          if (savedGender) setGender(savedGender);
        }
      } catch (e) {
        console.error('localStorage에서 사용자 정보 로드 실패:', e);
      }
    }
  };

  useEffect(() => {
    // 초기 로그인 상태 확인
    const authenticated = isAuthenticated();
    setIsLoggedIn(authenticated);
    
    // 로그인되어 있으면 사용자 정보 로드
    if (authenticated) {
      loadUserInfo();
    } else {
      // 로그아웃 상태면 모든 사용자 데이터 초기화
      setProfileImage(null);
      setUserId('');
      setAge('');
      setBmi('');
      setGender('0');
    }
    
    // 로그인 상태 변경 이벤트 리스너 (다른 페이지에서 로그인/로그아웃 시 동기화)
    const handleAuthStateChanged = (event: CustomEvent) => {
      // 로그인 성공 직후에는 상태를 변경하지 않음
      if (loginSuccessRef.current) {
        console.log('🔍 Health 페이지 - 로그인 성공 직후, 이벤트 무시');
        return;
      }
      const authenticated = event.detail?.authenticated ?? isAuthenticated();
      setIsLoggedIn(authenticated);
      console.log(`🔍 Health 페이지 - 로그인 상태 변경 이벤트: ${authenticated}`);
      
      // 로그인 시 사용자 정보 로드, 로그아웃 시 초기화
      if (authenticated) {
        loadUserInfo();
      } else {
        setProfileImage(null);
        setUserId('');
        setAge('');
        setBmi('');
        setGender('0');
      }
    };
    
    // localStorage storage 이벤트 리스너 (다른 탭에서 로그인/로그아웃 시 동기화)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth_token' || e.key === 'user_no') {
        // 로그인 성공 직후에는 상태를 변경하지 않음
        if (loginSuccessRef.current) {
          console.log('🔍 Health 페이지 - 로그인 성공 직후, storage 이벤트 무시');
          return;
        }
        const authenticated = isAuthenticated();
        setIsLoggedIn(authenticated);
        console.log(`🔍 Health 페이지 - localStorage 변경 감지, 로그인 상태: ${authenticated}`);
        
        // 로그인 시 사용자 정보 로드, 로그아웃 시 초기화
        if (authenticated) {
          loadUserInfo();
        } else {
          setProfileImage(null);
          setUserId('');
          setAge('');
          setBmi('');
          setGender('0');
        }
      }
    };
    
    // 페이지 포커스 시 상태 확인
    const handleFocus = () => {
      // 로그인 성공 직후에는 상태를 변경하지 않음
      if (loginSuccessRef.current) {
        console.log('🔍 Health 페이지 - 로그인 성공 직후, 포커스 이벤트 무시');
        return;
      }
      const authenticated = isAuthenticated();
      setIsLoggedIn(authenticated);
      console.log(`🔍 Health 페이지 - 포커스 이벤트, 로그인 상태: ${authenticated}`);
      
      // 로그인 시 사용자 정보 로드
      if (authenticated) {
        loadUserInfo();
      }
    };
    
    window.addEventListener('authStateChanged', handleAuthStateChanged as EventListener);
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('focus', handleFocus);
    
    // cleanup 함수
    return () => {
      window.removeEventListener('authStateChanged', handleAuthStateChanged as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  useEffect(() => {
    // 초기 설정 완료 여부 확인
    const checkSetupComplete = async () => {
      try {
        const { getUserNo } = await import('../services/AuthService');
        const userNo = getUserNo();
        
        // 사용자별로 localStorage에서 가져오기
        const savedAge = userNo ? localStorage.getItem(`userAge_${userNo}`) : localStorage.getItem('userAge');
        const savedBmi = userNo ? localStorage.getItem(`userBmi_${userNo}`) : localStorage.getItem('userBmi');
        const savedGender = userNo ? localStorage.getItem(`userGender_${userNo}`) : localStorage.getItem('userGender');
        const setupComplete = localStorage.getItem('healthSetupComplete');
        const hasPermission = localStorage.getItem('healthKitPermission') === 'true';
        
        // 성별은 '0' 또는 '1'이면 유효 (빈 문자열이나 null이 아니면)
        const hasValidGender = savedGender !== null && savedGender !== '';
        const hasValidAge = savedAge !== null && savedAge !== '';
        const hasValidBmi = savedBmi !== null && savedBmi !== '';
        
        if (setupComplete === 'true' && hasValidAge && hasValidBmi && hasValidGender && hasPermission) {
          setIsSetupComplete(true);
          setSetupStep('complete');
          if (savedAge) setAge(savedAge);
          if (savedBmi) setBmi(savedBmi);
          if (savedGender) setGender(savedGender);
          setHasHealthKitPermission(hasPermission);
        } else {
          // 저장된 정보가 있으면 불러오기
          if (savedAge) setAge(savedAge);
          if (savedBmi) setBmi(savedBmi);
          // 성별이 없으면 기본값 '0' 설정 및 저장
          if (savedGender) {
            setGender(savedGender);
          } else {
            setGender('0');
            const userNo = await import('../services/AuthService').then(m => m.getUserNo());
            if (userNo) {
              localStorage.setItem(`userGender_${userNo}`, '0');
            } else {
              localStorage.setItem('userGender', '0');
            }
          }
          if (hasPermission) setHasHealthKitPermission(true);
          
          // 설정 단계 결정 (성별은 기본값 '0'이 있으므로 항상 유효)
          const finalGender = savedGender || '0';
          if (hasValidAge && hasValidBmi) {
            if (hasPermission) {
              // 나이, BMI, 성별, 권한 모두 있으면 설정 완료
              localStorage.setItem('healthSetupComplete', 'true');
              setIsSetupComplete(true);
              setSetupStep('complete');
            } else {
              setSetupStep('permission');
            }
          } else {
            setSetupStep('info');
          }
        }
      } catch (err) {
        console.log('초기 설정 확인 실패:', err);
      }
    };
    
    checkSetupComplete();
    
    // HealthData 플러그인을 비동기로 로드 (UI 렌더링을 막지 않음)
    const loadHealthData = async () => {
      try {
        const { Capacitor } = await import('@capacitor/core');
        const currentPlatform = Capacitor.getPlatform();
        setPlatform(currentPlatform);
        
        const { HealthData } = await import('../plugins/healthdata');
        setHealthDataPlugin(HealthData);
        
        // iOS가 아니면 설정 완료로 표시
        if (currentPlatform !== 'ios') {
          setIsSetupComplete(true);
          setSetupStep('complete');
        }
      } catch (err) {
        console.log('HealthData 플러그인 로드 실패:', err);
      }
    };
    
    // UI가 먼저 렌더링되도록 지연
    setTimeout(() => {
      loadHealthData();
    }, 500);
    
    // 서버 URL 자동 감지 (앱 시작 시 백그라운드에서 실행)
    setTimeout(() => {
      const detectServerUrl = async () => {
        try {
          // iOS에서 localhost인 경우 제거하고 자동 감지
          const currentUrl = getServerUrl();
          if (!currentUrl || currentUrl.includes('localhost')) {
            console.log('🔄 서버 URL 자동 감지 시작...');
            const serverUrl = await autoDetectServerUrl();
            console.log('✅ 서버 URL 자동 감지 완료:', serverUrl);
          }
        } catch (err) {
          console.error('서버 URL 자동 감지 실패:', err);
        }
      };
      detectServerUrl();
    }, 1000); // 1초 후에 실행
  }, []);

  // 10분마다 자동으로 최신 데이터 가져오기 (iOS는 HealthKit, 안드로이드는 서버에서)
  useEffect(() => {
    // iOS는 HealthKit 플러그인 사용
    if (platform === 'ios' && healthDataPlugin) {
      // 초기 로드 후 첫 데이터 가져오기
      const initialTimeout = setTimeout(() => {
        fetchHealthData(healthDataPlugin);
        const now = Date.now();
        setLastCollectionTime(now);
        lastCollectionTimeRef.current = now;
      }, 1000); // 1초 후 첫 데이터 가져오기
      
      // 10분마다 자동으로 데이터 가져오기
      const interval = setInterval(() => {
        console.log('⏰ 10분 주기 - HealthData 가져오기 시작...');
        fetchHealthData(healthDataPlugin);
        const now = Date.now();
        setLastCollectionTime(now);
        lastCollectionTimeRef.current = now;
      }, 10 * 60 * 1000); // 10분 = 600000ms
      
      console.log('✅ 10분마다 HealthData 자동 수집 시작');

      // 앱이 포그라운드로 돌아올 때 데이터 수집 확인
      const handleAppStateChange = async (state: { isActive: boolean }) => {
        if (state.isActive) {
          const now = Date.now();
          const timeSinceLastCollection = now - lastCollectionTimeRef.current;
          const tenMinutes = 10 * 60 * 1000; // 10분
          
          // 마지막 수집 후 10분 이상 지났으면 데이터 수집
          if (timeSinceLastCollection >= tenMinutes) {
            const minutesPassed = Math.floor(timeSinceLastCollection / 60000);
            console.log(`⏰ 앱 포그라운드 복귀 - 마지막 수집 후 ${minutesPassed}분 경과, 데이터 수집 시작...`);
            fetchHealthData(healthDataPlugin);
            setLastCollectionTime(now);
            lastCollectionTimeRef.current = now;
          } else {
            const minutesPassed = Math.floor(timeSinceLastCollection / 60000);
            const minutesRemaining = Math.floor((tenMinutes - timeSinceLastCollection) / 60000);
            console.log(`⏰ 앱 포그라운드 복귀 - 마지막 수집 후 ${minutesPassed}분 경과, 다음 수집까지 ${minutesRemaining}분 남음`);
          }
        }
      };

      // 앱 상태 변경 리스너 등록
      let listener: any = null;
      App.addListener('appStateChange', handleAppStateChange).then((l) => {
        listener = l;
      });

      return () => {
        clearTimeout(initialTimeout);
        clearInterval(interval);
        if (listener) {
          listener.remove();
        }
      };
    }
    
    // 안드로이드는 서버에서 데이터 가져오기
    if (platform === 'android') {
      // UI가 먼저 렌더링되도록 지연 후 데이터 가져오기 (ANR 방지)
      const initialTimeout = setTimeout(() => {
        fetchHealthDataFromServer();
        const now = Date.now();
        setLastCollectionTime(now);
        lastCollectionTimeRef.current = now;
      }, 500); // 500ms 지연으로 UI 먼저 렌더링
      
      // 10분마다 자동으로 데이터 가져오기
      const interval = setInterval(() => {
        console.log('⏰ 10분 주기 - 서버에서 HealthData 가져오기 시작...');
        fetchHealthDataFromServer();
        const now = Date.now();
        setLastCollectionTime(now);
        lastCollectionTimeRef.current = now;
      }, 10 * 60 * 1000); // 10분 = 600000ms
      
      console.log('✅ 10분마다 HealthData 자동 수집 시작 (Android)');

      // 앱이 포그라운드로 돌아올 때 데이터 수집 확인
      const handleAppStateChange = async (state: { isActive: boolean }) => {
        if (state.isActive) {
          const now = Date.now();
          const timeSinceLastCollection = now - lastCollectionTimeRef.current;
          const tenMinutes = 10 * 60 * 1000; // 10분
          
          // 마지막 수집 후 10분 이상 지났으면 데이터 수집
          if (timeSinceLastCollection >= tenMinutes) {
            const minutesPassed = Math.floor(timeSinceLastCollection / 60000);
            console.log(`⏰ 앱 포그라운드 복귀 - 마지막 수집 후 ${minutesPassed}분 경과, 데이터 수집 시작...`);
            fetchHealthDataFromServer();
            setLastCollectionTime(now);
            lastCollectionTimeRef.current = now;
          } else {
            const minutesPassed = Math.floor(timeSinceLastCollection / 60000);
            const minutesRemaining = Math.floor((tenMinutes - timeSinceLastCollection) / 60000);
            console.log(`⏰ 앱 포그라운드 복귀 - 마지막 수집 후 ${minutesPassed}분 경과, 다음 수집까지 ${minutesRemaining}분 남음`);
          }
        }
      };

      // 앱 상태 변경 리스너 등록
      let listener: any = null;
      App.addListener('appStateChange', handleAppStateChange).then((l) => {
        listener = l;
      });

      return () => {
        clearTimeout(initialTimeout);
        clearInterval(interval);
        if (listener) {
          listener.remove();
        }
      };
    }
  }, [healthDataPlugin, platform]); // lastCollectionTime 제거 - useRef로 관리


  // 백그라운드 모니터링은 네이티브 코드에서만 처리합니다
  // JavaScript 리스너는 제거되었습니다 (네이티브에서 직접 데이터 수집 및 서버 전송)

  const fetchHealthData = async (HealthData: any) => {
    if (!HealthData) {
      console.log('HealthData 플러그인이 없습니다.');
      alert('HealthData 플러그인이 로드되지 않았습니다.');
      return;
    }
    
    console.log('HealthData 가져오기 시작...');
    
    try {
      const [heartRate, hrv, oxygenSaturation] = await Promise.all([
        HealthData.getLatestHeartRate()
          .catch((err: any) => {
            console.error('심박수 가져오기 실패:', err);
            const errorMsg = err?.message || err?.toString() || String(err);
            if (errorMsg.includes('authorization') || errorMsg.includes('권한')) {
              alert('HealthKit 권한이 필요합니다. 설정 > Health > 데이터 액세스 및 기기에서 권한을 허용해주세요.');
            } else if (errorMsg.includes('not found') || errorMsg.includes('No') || errorMsg.includes('없음')) {
              console.log('심박수 데이터가 없습니다.');
            } else {
              console.error('심박수 가져오기 오류:', errorMsg);
            }
            return null;
          }),
        HealthData.getLatestHeartRateVariability()
          .catch((err: any) => {
            console.error('HRV 가져오기 실패:', err);
            const errorMsg = err?.message || err?.toString() || String(err);
            if (errorMsg.includes('authorization') || errorMsg.includes('권한')) {
              // 권한 에러는 한 번만 표시
            } else if (errorMsg.includes('not found') || errorMsg.includes('No') || errorMsg.includes('없음')) {
              console.log('HRV 데이터가 없습니다.');
            } else {
              console.error('HRV 가져오기 오류:', errorMsg);
            }
            return null;
          }),
        HealthData.getLatestOxygenSaturation()
          .catch((err: any) => {
            console.error('혈중산소포화도 가져오기 실패:', err);
            const errorMsg = err?.message || err?.toString() || String(err);
            if (errorMsg.includes('authorization') || errorMsg.includes('권한')) {
              // 권한 에러는 한 번만 표시
            } else if (errorMsg.includes('not found') || errorMsg.includes('No') || errorMsg.includes('없음')) {
              console.log('혈중산소포화도 데이터가 없습니다.');
            } else {
              console.error('혈중산소포화도 가져오기 오류:', errorMsg);
            }
            return null;
          }),
      ]);

      // 빈 딕셔너리를 null로 변환
      const normalizeData = (data: any) => {
        if (!data || Object.keys(data).length === 0) return null;
        return data;
      };

      const normalizedHeartRate = normalizeData(heartRate);
      const normalizedHrv = normalizeData(hrv);
      const normalizedOxygen = normalizeData(oxygenSaturation);

      console.log('HealthData 가져오기 결과:', { 
        heartRate: normalizedHeartRate ? `${normalizedHeartRate.value} bpm` : '없음',
        hrv: normalizedHrv ? `${normalizedHrv.value} ms` : '없음',
        oxygenSaturation: normalizedOxygen ? `${normalizedOxygen.value}%` : '없음'
      });

      // 모든 데이터가 없으면 콘솔에만 표시 (알림은 표시하지 않음)
      if (!normalizedHeartRate && !normalizedHrv && !normalizedOxygen) {
        console.log('Health 앱에 데이터가 없습니다. Health 앱에서 심박수, HRV, 혈중산소포화도 데이터를 확인해주세요.');
      }

      // Health data 가져오기 결과를 먼저 표시
      setHealthData({
        heartRate: normalizedHeartRate,
        hrv: normalizedHrv,
        oxygenSaturation: normalizedOxygen,
      });

      // 서버로 데이터 전송은 완전히 백그라운드로 처리 (로딩 상태와 무관)
      if (normalizedHeartRate || normalizedHrv || normalizedOxygen) {
        console.log('📤 서버로 데이터 전송 시작 (10분 주기)...');
        // Promise를 반환하지 않도록 void로 처리하여 완전히 백그라운드로 실행
        void sendToServer({
          heartRate: normalizedHeartRate?.value || null,
          HRV: normalizedHrv?.value || null,
          oxygenSaturation: normalizedOxygen?.value || null,
          bmi: bmi ? parseFloat(bmi) : null,
          age: age ? parseFloat(age) : null,
          gender: gender && gender !== '' ? parseFloat(gender) : 0.0,
        }).then(() => {
          console.log('✅ 서버 전송 성공 (10분 주기)');
        }).catch((err) => {
          console.error('❌ 서버 전송 실패 (백그라운드):', err);
        });
      } else {
        console.log('⚠️ 전송할 데이터가 없습니다 (모든 값이 null)');
      }
    } catch (err: any) {
      console.error('HealthData 데이터 가져오기 실패:', err);
      const errorMsg = err?.message || err?.toString() || String(err);
      alert('데이터를 가져오는 중 오류가 발생했습니다:\n' + errorMsg);
    }
  };

  // 백그라운드 데이터 수집은 네이티브 코드에서만 처리합니다

  // 안드로이드에서 서버에서 건강 데이터 가져오기
  const fetchHealthDataFromServer = async () => {
    try {
      // 서버 URL 설정 (플랫폼별로 자동 설정)
      const { Capacitor } = await import('@capacitor/core');
      const currentPlatform = Capacitor.getPlatform();
      // 서버 URL 자동 감지
      let serverURL: string;
      try {
        const baseUrl = getServerUrl();
        // iOS에서 localhost이거나 빈 문자열인 경우 자동 감지
        if (!baseUrl || baseUrl === '' || baseUrl.includes('localhost')) {
          console.log('⚠️ localhost 감지 또는 URL 없음, 자동 감지 시도');
          const detectedUrl = await autoDetectServerUrl();
          if (!detectedUrl || detectedUrl === '') {
            throw new Error('서버 URL 자동 감지 실패');
          }
          serverURL = `${detectedUrl}/healthdata/latest`;
        } else {
          serverURL = `${baseUrl}/healthdata/latest`;
        }
      } catch (error) {
        console.log('⚠️ 서버 URL 가져오기 실패, 자동 감지 시도:', error);
        try {
          const detectedUrl = await autoDetectServerUrl();
          if (!detectedUrl || detectedUrl === '') {
            throw new Error('서버 URL 자동 감지 실패');
          }
          serverURL = `${detectedUrl}/healthdata/latest`;
        } catch (detectError) {
          console.error('❌ 서버 자동 감지 실패:', detectError);
          // iOS에서는 localhost를 사용하지 않음
          throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
      }
      
      console.log('📱 서버에서 건강 데이터 가져오기 시작:', serverURL);
      
      // 인증 헤더 가져오기
      const { getAuthHeaders } = await import('../services/AuthService');
      const authHeaders = getAuthHeaders();
      
      // 타임아웃 설정 (3초로 단축하여 ANR 방지)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      
      const response = await fetch(serverURL, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,  // 인증 헤더 추가 (JWT 토큰)
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.success && result.data) {
        // 서버에서 받은 데이터를 UI 형식으로 변환
        setHealthData({
          heartRate: result.data.heartRate || null,
          hrv: result.data.hrv || null,
          oxygenSaturation: result.data.oxygenSaturation || null,
        });
        
        console.log('✅ 서버에서 건강 데이터 가져오기 성공:', result.data);
      } else {
        console.log('📊 서버에 저장된 건강 데이터가 없습니다.');
        setHealthData({
          heartRate: null,
          hrv: null,
          oxygenSaturation: null,
        });
      }
    } catch (error: any) {
      // 타임아웃 에러는 조용히 처리
      if (error.name === 'AbortError') {
        console.log('⏱️ 서버 응답 시간 초과 (3초)');
      } else {
        console.error('서버에서 건강 데이터 가져오기 실패:', error);
      }
      // 에러 발생 시 조용히 실패 (이전 동작 유지)
      setHealthData({
        heartRate: null,
        hrv: null,
        oxygenSaturation: null,
      });
    }
  };

  // 차트 데이터 로드 (빈 데이터만 반환)
  const loadChartData = () => {
    const today = new Date().toISOString().split('T')[0];
    const emptyData: NightChartData = {
      date: today,
      temperatureData: [],
      heartRateData: [],
      lastUpdated: new Date().toISOString(),
    };
    setChartData(emptyData);
  };

  // DB에서 차트 데이터 로드
  const loadChartDataFromDB = async () => {
    try {
      console.log('📊 DB에서 차트 데이터 로드 시작...');
      const baseUrl = getServerUrl();
      
      // 오늘 날짜의 빈 데이터 구조 생성
      const today = new Date().toISOString().split('T')[0];
      const dbChartData: NightChartData = {
        date: today,
        temperatureData: [],
        heartRateData: [],
        lastUpdated: new Date().toISOString(),
      };
      
      // 1. 심박수 데이터 가져오기 (predicted_results)
      try {
        const { getAuthHeaders } = await import('../services/AuthService');
        const heartRateResponse = await fetch(`${baseUrl}/chart/heartrate?hours=12`, {
          headers: getAuthHeaders()
        });
        if (heartRateResponse.ok) {
          const heartRateData = await heartRateResponse.json();
          if (heartRateData.success && heartRateData.data) {
            // DB 데이터를 차트 형식으로 변환
            heartRateData.data.forEach((point: any) => {
              // 서버에서 받은 timestamp를 사용하여 실제 시간 확인
              const timestamp = new Date(point.timestamp);
              const serverHour = timestamp.getHours();
              const serverMinute = timestamp.getMinutes();
              
              // 서버에서 받은 hour, minute과 timestamp에서 파싱한 시간이 일치하는지 확인
              if (point.hour !== serverHour || point.minute !== serverMinute) {
                console.warn(`⚠️ 시간 불일치: 서버 hour=${point.hour}, minute=${point.minute}, timestamp 파싱=${serverHour}:${serverMinute}`);
              }
              
              dbChartData.heartRateData.push({
                timestamp: point.timestamp,
                hour: serverHour,  // timestamp에서 파싱한 실제 시간 사용
                minute: serverMinute,  // timestamp에서 파싱한 실제 시간 사용
                heartRate: point.heartRate,
              });
              
              console.log(`📊 심박수 데이터: ${serverHour}:${serverMinute.toString().padStart(2, '0')}, HR=${point.heartRate}, timestamp=${point.timestamp}`);
            });
            console.log(`✅ 심박수 데이터 ${heartRateData.count}개 로드 완료`);
          }
        }
      } catch (error) {
        console.error('심박수 데이터 로드 실패:', error);
      }
      
      // 2. 온도 데이터 가져오기 (test_script_logs)
      try {
        const { getAuthHeaders } = await import('../services/AuthService');
        const tempResponse = await fetch(`${baseUrl}/chart/temperature?hours=12`, {
          headers: getAuthHeaders()
        });
        if (tempResponse.ok) {
          const tempData = await tempResponse.json();
          if (tempData.success && tempData.data) {
            // DB 데이터를 차트 형식으로 변환
            tempData.data.forEach((point: any) => {
              dbChartData.temperatureData.push({
                timestamp: point.timestamp,
                hour: point.hour,
                minute: point.minute,
                predictedTemperature: point.predictedTemperature,
                temperatureCategory: point.temperatureCategory,
                currentTemperature: point.currentTemperature,
                targetTemperature: point.targetTemperature,
              });
            });
            console.log(`✅ 온도 데이터 ${tempData.count}개 로드 완료`);
          }
        }
      } catch (error) {
        console.error('온도 데이터 로드 실패:', error);
      }
      
      // 3. DB 데이터가 있으면 DB 데이터 사용, 없으면 빈 데이터 표시
      if (dbChartData.temperatureData.length > 0 || dbChartData.heartRateData.length > 0) {
        console.log(`✅ DB 데이터 ${dbChartData.temperatureData.length}개(온도), ${dbChartData.heartRateData.length}개(심박수) 로드 완료`);
        // DB 데이터를 차트에 표시
        try {
          localStorage.setItem('night_chart_data', JSON.stringify(dbChartData));
          setChartData(dbChartData);
          console.log('✅ DB 데이터를 차트에 표시했습니다.');
        } catch (error) {
          console.error('DB 데이터 저장 실패:', error);
        }
        return true; // DB 데이터가 있음을 반환
      } else {
        console.log('⚠️ DB에 데이터가 없습니다.');
        // 빈 데이터로 설정
        try {
          localStorage.setItem('night_chart_data', JSON.stringify(dbChartData));
          setChartData(dbChartData);
          console.log('✅ 빈 데이터로 설정했습니다.');
        } catch (error) {
          console.error('빈 데이터 저장 실패:', error);
        }
        return false; // DB 데이터가 없음을 반환
      }
    } catch (error) {
      console.error('DB 차트 데이터 로드 실패:', error);
      // 실패 시 빈 데이터로 설정
      const today = new Date().toISOString().split('T')[0];
      const emptyData: NightChartData = {
        date: today,
        temperatureData: [],
        heartRateData: [],
        lastUpdated: new Date().toISOString(),
      };
      try {
        localStorage.setItem('night_chart_data', JSON.stringify(emptyData));
        setChartData(emptyData);
        console.log('✅ 빈 데이터로 설정했습니다.');
      } catch (err) {
        console.error('빈 데이터 저장 실패:', err);
      }
      return false;
    }
  };

  // 테스트 데이터 생성 함수
  const generateTestData = () => {
    const now = new Date();
    const testData: NightChartData = {
      date: now.toISOString().split('T')[0],
      temperatureData: [],
      heartRateData: [],
      lastUpdated: now.toISOString(),
    };

    // 12시간치 테스트 데이터 생성 (1시간 간격) - 최근 12시간
    const currentHour = now.getHours();
    const startHour = currentHour >= 12 ? currentHour - 11 : (currentHour + 24) - 11;
    
    for (let i = 0; i < 12; i++) {
      const hour = (startHour + i) % 24;
      const minute = hour === 0 ? 30 : 0; // 첫 번째는 30분, 나머지는 0분
      const timestamp = new Date(now);
      timestamp.setHours(hour, minute, 0, 0);

      // 온도 데이터 (다양한 패턴)
      let predictedTemp = 34.5 + Math.sin((hour - 6) * Math.PI / 12) * 1.5; // 34.5~36.5 범위
      let category: '더움' | '추움' | '적정' = '적정';
      if (predictedTemp < 34.5) {
        category = '추움';
        predictedTemp = 33.5 + Math.random() * 0.8; // 33.5~34.3
      } else if (predictedTemp > 35.6) {
        category = '더움';
        predictedTemp = 35.7 + Math.random() * 0.8; // 35.7~36.5
      } else {
        predictedTemp = 34.5 + Math.random() * 1.1; // 34.5~35.6
      }

      testData.temperatureData.push({
        timestamp: timestamp.toISOString(),
        hour,
        minute,
        predictedTemperature: Number(predictedTemp.toFixed(1)),
        temperatureCategory: category,
        currentTemperature: 24.0 + Math.random() * 3, // 24~27도
        targetTemperature: 25.0 + Math.random() * 2, // 25~27도
      });

      // 심박수 데이터 (60~80 bpm 범위)
      const heartRate = 60 + Math.sin((hour - 6) * Math.PI / 12) * 10 + Math.random() * 5;
      testData.heartRateData.push({
        timestamp: timestamp.toISOString(),
        hour,
        minute,
        heartRate: Math.round(heartRate),
      });
    }

    // localStorage에 저장
    try {
      localStorage.setItem('night_chart_data', JSON.stringify(testData));
      setChartData(testData);
      console.log('✅ 테스트 데이터 생성 완료:', testData);
    } catch (error) {
      console.error('테스트 데이터 저장 실패:', error);
    }
  };

  const sendToServer = async (data: {
    heartRate: number | null;
    HRV: number | null;
    oxygenSaturation: number | null;
    bmi: number | null;
    age: number | null;
    gender: number | null;
  }) => {
    // 서버 URL 자동 감지 (실패 시 자동으로 다른 IP 시도)
    let serverURL: string;
    try {
      // 먼저 저장된 URL 시도
      const baseUrl = getServerUrl();
      // iOS에서 localhost이거나 빈 문자열인 경우 자동 감지
      if (!baseUrl || baseUrl === '' || baseUrl.includes('localhost')) {
        console.log('⚠️ localhost 감지 또는 URL 없음, 자동 감지 시도');
        try {
          const detectedUrl = await autoDetectServerUrl();
          if (!detectedUrl || detectedUrl === '') {
            throw new Error('서버 URL 자동 감지 실패');
          }
          serverURL = `${detectedUrl}/healthdata`;
          console.log('✅ 서버 자동 감지 성공:', serverURL);
        } catch (detectError) {
          console.error('❌ 서버 자동 감지 실패:', detectError);
          throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
      } else {
        // /healthdata 엔드포인트 추가
        if (!baseUrl.endsWith('/healthdata')) {
          serverURL = `${baseUrl}/healthdata`;
        } else {
          serverURL = baseUrl;
        }
      }
    } catch (error) {
      console.log('⚠️ 서버 URL 가져오기 실패, 자동 감지 시도:', error);
      // 자동 감지 시도
      try {
        const detectedUrl = await autoDetectServerUrl();
        serverURL = `${detectedUrl}/healthdata`;
        console.log('✅ 서버 자동 감지 성공:', serverURL);
      } catch (detectError) {
        console.error('❌ 서버 자동 감지 실패:', detectError);
        // iOS에서는 localhost를 사용하지 않음
        serverURL = ''; // 빈 문자열로 설정하여 에러 발생
      }
    }

    // 서버 URL이 없으면 에러
    if (!serverURL || serverURL === '') {
      console.error('❌ 서버 URL이 없습니다. 자동 감지를 다시 시도합니다.');
      try {
        const detectedUrl = await autoDetectServerUrl();
        serverURL = `${detectedUrl}/healthdata`;
        console.log('✅ 서버 자동 감지 성공:', serverURL);
      } catch (detectError) {
        console.error('❌ 서버 자동 감지 최종 실패:', detectError);
        throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
      }
    }

    try {
      console.log('📤 서버로 데이터 전송 시작:', data);

      // 타임아웃 추가 (10초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초 타임아웃

      try {
        console.log('📡 서버 연결 시도:', serverURL);
        // 인증 헤더 추가
        const { getAuthHeaders } = await import('../services/AuthService');
        const headers = getAuthHeaders();
        
        const response = await fetch(serverURL, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(data),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 서버 응답:', result);
          
          // iOS에서 서버 URL을 UserDefaults에도 저장 (백그라운드 작업용)
          if (platform === 'ios' && healthDataPlugin) {
            try {
              // baseUrl에서 /healthdata 제거
              const baseUrl = serverURL.replace('/healthdata', '');
              await healthDataPlugin.saveUserInfo({
                age: age || '',
                bmi: bmi || '',
                gender: gender || '0',
                serverURL: baseUrl // 서버 URL도 함께 저장
              });
              console.log('✅ 서버 URL을 UserDefaults에 저장 완료:', baseUrl);
            } catch (err) {
              console.log('⚠️ UserDefaults에 서버 URL 저장 실패 (무시):', err);
            }
          }
          
          return result;
        } else {
          const errorText = await response.text();
          console.error('❌ 서버 응답 오류:', response.status, response.statusText, errorText);
          throw new Error(`Server error: ${response.status} - ${errorText}`);
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          console.error('❌ 서버 전송 타임아웃 (10초) - 서버가 응답하지 않습니다');
          // 타임아웃 시 자동 감지 재시도
          try {
            console.log('🔄 서버 자동 감지 재시도...');
            const detectedUrl = await autoDetectServerUrl();
            const newServerURL = `${detectedUrl}/healthdata`;
            console.log('✅ 새로운 서버 URL 감지:', newServerURL);
            // 새로운 URL로 재시도
            const retryController = new AbortController();
            const retryTimeoutId = setTimeout(() => retryController.abort(), 10000);
            try {
              const retryResponse = await fetch(newServerURL, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                signal: retryController.signal,
              });
              clearTimeout(retryTimeoutId);
              if (retryResponse.ok) {
                const result = await retryResponse.json();
                console.log('✅ 재시도 성공:', result);
                return result;
              }
            } catch (retryError) {
              clearTimeout(retryTimeoutId);
              throw retryError;
            }
          } catch (detectError) {
            console.error('❌ 자동 감지 재시도 실패:', detectError);
          }
          throw new Error('서버 전송 타임아웃: 서버가 응답하지 않습니다. 서버가 실행 중인지 확인해주세요.');
        }
        // 더 자세한 에러 정보 로깅
        const errorDetails = {
          name: fetchError.name,
          message: fetchError.message,
          stack: fetchError.stack,
          error: fetchError,
          url: serverURL
        };
        console.error('❌ fetch 에러 상세:', errorDetails);
        
        // 네트워크 에러인 경우 자동 감지 재시도
        if (fetchError.message?.includes('Failed to fetch') || 
            fetchError.message?.includes('NetworkError') ||
            fetchError.name === 'TypeError') {
          try {
            console.log('🔄 네트워크 에러 - 서버 자동 감지 재시도...');
            const detectedUrl = await autoDetectServerUrl();
            const newServerURL = `${detectedUrl}/healthdata`;
            console.log('✅ 새로운 서버 URL 감지:', newServerURL);
            // 새로운 URL로 재시도
            const retryController = new AbortController();
            const retryTimeoutId = setTimeout(() => retryController.abort(), 10000);
            try {
              const retryResponse = await fetch(newServerURL, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                signal: retryController.signal,
              });
              clearTimeout(retryTimeoutId);
              if (retryResponse.ok) {
                const result = await retryResponse.json();
                console.log('✅ 재시도 성공:', result);
                return result;
              }
            } catch (retryError) {
              clearTimeout(retryTimeoutId);
            }
          } catch (detectError) {
            console.error('❌ 자동 감지 재시도 실패:', detectError);
          }
          throw new Error(`네트워크 연결 실패: ${serverURL}에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.`);
        }
        throw fetchError;
      }
    } catch (err: any) {
      // 더 자세한 에러 정보 로깅
      const errorInfo = {
        message: err?.message,
        name: err?.name,
        stack: err?.stack,
        toString: err?.toString(),
        error: err,
        url: serverURL,
        timestamp: new Date().toISOString()
      };
      console.error('❌ 서버 전송 실패:', errorInfo);
      
      // 네트워크 에러인 경우 서버 연결 테스트
      if (err?.message?.includes('네트워크') || 
          err?.message?.includes('연결') ||
          err?.message?.includes('Failed to fetch')) {
        console.log('🔍 서버 연결 테스트 시작...');
        testServerConnection(serverURL).catch((testErr) => {
          console.error('🔍 서버 연결 테스트 실패:', testErr);
        });
      }
      
      // 사용자에게 알리지 않고 조용히 실패 (백그라운드 전송이므로)
      return null;
    }
  };

  // 서버 연결 테스트 함수
  const testServerConnection = async (url: string) => {
    try {
      const healthURL = url.replace('/healthdata', '/health');
      console.log('🔍 서버 헬스 체크:', healthURL);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5초 타임아웃
      
      try {
        const response = await fetch(healthURL, {
          method: 'GET',
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        
        if (response.ok) {
          const result = await response.json();
          console.log('✅ 서버 연결 성공:', result);
          return true;
        } else {
          console.error('❌ 서버 응답 오류:', response.status);
          return false;
        }
      } catch (fetchErr: any) {
        clearTimeout(timeoutId);
        console.error('❌ 서버 연결 실패:', fetchErr.message);
        return false;
      }
    } catch (err) {
      console.error('❌ 서버 연결 테스트 실패:', err);
      return false;
    }
  };

  // 차트 데이터 초기 로드 및 DB에서 데이터 가져오기
  useEffect(() => {
    // 초기 빈 데이터 설정 (가상 데이터 로드하지 않음)
    const today = new Date().toISOString().split('T')[0];
    const emptyData: NightChartData = {
      date: today,
      temperatureData: [],
      heartRateData: [],
      lastUpdated: new Date().toISOString(),
    };
    setChartData(emptyData);

    // DB에서 차트 데이터 로드 (predicted_results, test_script_logs)
    loadChartDataFromDB().then((hasDbData) => {
      if (hasDbData) {
        console.log('✅ DB 데이터를 사용하여 차트를 표시합니다.');
      } else {
        console.log('⚠️ DB 데이터가 없습니다.');
      }
    }).catch((error) => {
      console.error('DB 데이터 로드 실패:', error);
      // 에러 발생 시 빈 데이터로 설정
      const today = new Date().toISOString().split('T')[0];
      const emptyData: NightChartData = {
        date: today,
        temperatureData: [],
        heartRateData: [],
        lastUpdated: new Date().toISOString(),
      };
      try {
        localStorage.setItem('night_chart_data', JSON.stringify(emptyData));
        setChartData(emptyData);
        console.log('✅ 빈 데이터로 설정했습니다.');
      } catch (err) {
        console.error('빈 데이터 저장 실패:', err);
      }
    });

    // 주기적으로 DB에서 데이터 갱신 (5분마다)
    collectionIntervalRef.current = setInterval(() => {
      loadChartDataFromDB();
    }, 300000); // 5분

    return () => {
      if (collectionIntervalRef.current) {
        clearInterval(collectionIntervalRef.current);
      }
    };
  }, []);

  const handleBackgroundMonitoringToggle = async (enabled: boolean) => {
    if (!healthDataPlugin || platform !== 'ios') {
      console.log('HealthData 플러그인이 사용 불가능합니다. (iOS에서만 사용 가능)');
      return;
    }
    try {
      const result = await healthDataPlugin.startBackgroundMonitoring({ enabled });
      if (result.success) {
        setBackgroundMonitoring(enabled);
      }
    } catch (err: any) {
      console.log('백그라운드 모니터링 설정 실패:', err);
    }
  };

  // 나이/BMI/성별 입력 완료 후 다음 단계로
  const handleInfoStepComplete = () => {
    if (age && bmi && gender) {
      setSetupStep('permission');
    } else {
      alert('나이, BMI, 성별을 모두 입력해주세요.');
    }
  };

  // HealthKit 권한 요청 완료 후 다음 단계로
  const handlePermissionRequest = async () => {
    if (!healthDataPlugin || platform !== 'ios') {
      alert('iOS에서만 HealthKit을 사용할 수 있습니다.');
      return false;
    }
    try {
      const result = await healthDataPlugin.requestAuthorization();
      if (result.success) {
        setHasHealthKitPermission(true);
        localStorage.setItem('healthKitPermission', 'true');
        return true;
      } else {
        const message = result.message || 'HealthKit 권한이 필요합니다.';
        alert(message + '\n\n설정 > Health > 데이터 액세스 및 기기 > poseul에서 권한을 허용해주세요.');
        return false;
      }
    } catch (err: any) {
      console.error('HealthKit 권한 요청 실패:', err);
      const errorMsg = err?.message || err?.toString() || String(err);
      alert('HealthKit 권한 요청 중 오류가 발생했습니다:\n' + errorMsg);
      return false;
    }
  };

  useEffect(() => {
    // 다크모드 상태 불러오기
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    setIsDarkMode(savedDarkMode);
    if (savedDarkMode) {
      document.body.classList.add('dark');
    }
  }, []);

  const handleDarkModeToggle = (enabled: boolean) => {
    setIsDarkMode(enabled);
    localStorage.setItem('darkMode', enabled.toString());
    if (enabled) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ko-KR', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };




  // 웹에서 예시 데이터 사용
  const displayHealthData = platform === 'web' ? {
    heartRate: { value: 72, date: new Date().toISOString() },
    hrv: { value: 45.5, date: new Date().toISOString() },
    oxygenSaturation: { value: 98.5, date: new Date().toISOString() }
  } : healthData;

  const isExampleData = platform === 'web';

  return (
    <IonPage className="health-ios-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>포슬💭</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        {/* 별 배경 효과 (다크모드) */}
        <div className="stars-background"></div>

        {/* 사용자 아이콘 버튼 */}
        {isSetupComplete && (
          <div 
            className="on-boarding-btn" 
            onClick={() => {
              // 클릭 시마다 최신 로그인 상태 확인 (state가 아닌 직접 확인)
              const authenticated = isAuthenticated();
              console.log(`🔍 Health 페이지 - 아이콘 클릭, 로그인 상태: ${authenticated}`);
              
              if (authenticated) {
                loadUserInfo();
                setShowUserInfo(true);
              } else {
                setShowSignIn(true);
              }
            }}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '18px',
              background: 'white',
              position: 'fixed',
              top: 'calc(var(--safe-area-inset-top, 0px) + 44px + 12px)',
              right: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 5px 5px rgba(0, 0, 0, 0.2)',
              zIndex: 1000
            }}
          >
            <IonIcon icon={personOutline} style={{ fontSize: '20px' }} />
          </div>
        )}

        {/* 로그인 모달 */}
        {showSignIn && (
          <div style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)'
          }}>
            <SignIn 
              onClose={() => {
                // 모달만 닫기 (상태는 onSuccess에서만 관리)
                setShowSignIn(false);
              }}
              onSuccess={() => {
                console.log('✅ Health 페이지 - onSuccess 호출됨');
                
                // 로그인 성공 플래그 설정 (이벤트 리스너가 상태를 덮어쓰지 않도록)
                loginSuccessRef.current = true;
                
                // 모달 닫기
                setShowSignIn(false);
                
                // 약간의 지연 후 사용자 정보 모달 표시 (토큰이 완전히 저장된 후)
                setTimeout(() => {
                  // localStorage에서 직접 토큰 확인
                  const token = localStorage.getItem('auth_token');
                  console.log(`🔍 Health 페이지 - localStorage 직접 확인: ${token ? `있음 (길이: ${token.length})` : '없음'}`);
                  
                  // 토큰 재확인 (안전장치)
                  const authenticated = isAuthenticated();
                  console.log(`🔍 Health 페이지 - isAuthenticated() 결과: ${authenticated}`);
                  
                  if (authenticated && token) {
                    // 함수형 업데이트로 확실하게 true 유지
                    setIsLoggedIn(() => true);
                    loadUserInfo();
                    setShowUserInfo(true);
                    console.log('✅ Health 페이지 - 사용자 정보 모달 표시');
                    
                    // 2초 후 플래그 해제 (이제 다른 이벤트가 상태를 업데이트해도 됨)
                    setTimeout(() => {
                      loginSuccessRef.current = false;
                      console.log('✅ Health 페이지 - 로그인 성공 플래그 해제');
                    }, 2000);
                  } else {
                    console.warn('⚠️ Health 페이지 - 토큰이 없음, 상태 재설정');
                    console.warn(`⚠️ Health 페이지 - token: ${token ? '있음' : '없음'}, authenticated: ${authenticated}`);
                    setIsLoggedIn(false);
                    loginSuccessRef.current = false;
                  }
                }, 100); // 100ms로 단축 (localStorage는 동기적이므로)
              }}
            />
          </div>
        )}

        {/* 회원가입 모달 */}
        {showSignUp && (
          <div style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)'
          }}>
            <SignUp 
              onClose={() => {
                setShowSignUp(false);
                // 로그인 상태 강제 업데이트
                setIsLoggedIn(isAuthenticated());
              }}
              onSuccess={() => {
                // User 페이지와 동일: 즉시 true로 설정 (토큰은 이미 저장됨)
                setIsLoggedIn(true);
                setShowSignUp(false);
                console.log('✅ Health 페이지 - 회원가입 성공, 상태 업데이트 완료');
                
                // 실제 토큰 확인 (안전장치)
                setTimeout(() => {
                  const authenticated = isAuthenticated();
                  if (!authenticated) {
                    console.warn('⚠️ Health 페이지 - 토큰이 없음, 상태 재설정');
                    setIsLoggedIn(false);
                  } else {
                    setIsLoggedIn(true);
                    console.log('✅ Health 페이지 - 토큰 확인 완료');
                  }
                }, 100);
              }}
            />
          </div>
        )}

        {/* 사용자 정보 모달 */}
        {showUserInfo && isAuthenticated() && (
          <div className="user-info-modal-backdrop" style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(4px)'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowUserInfo(false);
            }
          }}
          >
            <div className="user-info-modal" style={{
              background: 'linear-gradient(135deg, #ffffff 0%, #f5f7fa 100%)',
              borderRadius: '24px',
              padding: '0',
              width: '85%',
              maxWidth: '340px',
              boxShadow: '0 24px 80px rgba(0, 0, 0, 0.25)',
              position: 'relative',
              overflow: 'hidden'
            }}
            onClick={(e) => e.stopPropagation()}
            >
              {/* 상단 민트색 헤더 */}
              <div style={{
                background: 'linear-gradient(135deg, #b8d8e0 0%, #a0c8d4 100%)',
                backgroundColor: '#b8d8e0',
                padding: '14px 18px 32px 18px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                {/* 배경 장식 원 */}
                <div style={{
                  position: 'absolute',
                  top: '-40px',
                  right: '-40px',
                  width: '120px',
                  height: '120px',
                  background: 'rgba(255, 255, 255, 0.15)',
                  borderRadius: '50%'
                }} />
                <div style={{
                  position: 'absolute',
                  bottom: '-25px',
                  left: '-25px',
                  width: '100px',
                  height: '100px',
                  background: 'rgba(255, 255, 255, 0.12)',
                  borderRadius: '50%'
                }} />
                
                {/* 헤더 내용 */}
                <div style={{
                  position: 'relative',
                  zIndex: 1,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: '10px'
                }}>
                  <div 
                    style={{ 
                      fontSize: '1.1rem', 
                      fontWeight: '600', 
                      color: '#ffffff', 
                      letterSpacing: '-0.2px',
                      textShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                      WebkitTextFillColor: '#ffffff',
                      WebkitTextStrokeColor: 'transparent'
                    }}
                  >
                    내 프로필
                  </div>
                  <button
                    onClick={() => {
                      setShowUserInfo(false);
                      if (!isAuthenticated()) {
                        setIsLoggedIn(false);
                      }
                    }}
                    style={{
                      background: 'rgba(255, 255, 255, 0.2)',
                      border: 'none',
                      padding: '6px',
                      cursor: 'pointer',
                      borderRadius: '10px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                      width: '32px',
                      height: '32px',
                      backdropFilter: 'blur(10px)'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)';
                    }}
                  >
                    <IonIcon icon={closeOutline} style={{ fontSize: '18px', color: '#ffffff' }} />
                  </button>
                </div>
                
                {/* 프로필 이미지 (헤더 내부) */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  position: 'relative',
                  zIndex: 1
                }}>
                  <div style={{
                    position: 'relative',
                    width: '120px',
                    height: '120px',
                    overflow: 'visible'
                  }}>
                    <div style={{
                      width: '120px',
                      height: '120px',
                      overflow: 'hidden',
                      borderRadius: '50%',
                      border: '4px solid white',
                      boxShadow: '0 6px 24px rgba(0, 0, 0, 0.2)',
                      backgroundColor: '#ffffff',
                      position: 'relative',
                      zIndex: 1
                    }}>
                      <img
                        key={profileImage || 'default'}
                        src={profileImage || '/default-profile.png'}
                        alt="프로필"
                        style={{
                          width: '150px',
                          height: '150px',
                          objectFit: 'cover',
                          display: 'block',
                          marginLeft: '5px',
                          marginTop: '-20px'
                        }}
                        onError={(e) => {
                          // 이미지 로드 실패 시 기본 이미지로 대체
                          console.error('이미지 로드 실패:', profileImage);
                          (e.target as HTMLImageElement).src = '/default-profile.png';
                        }}
                        onLoad={() => {
                          console.log('✅ 이미지 로드 성공:', profileImage);
                        }}
                      />
                    </div>
                    <button
                      className="profile-camera-button"
                      onClick={() => {
                        document.getElementById('profile-image-input')?.click();
                      }}
                      style={{
                        position: 'absolute',
                        bottom: '0px',
                        right: '0px',
                        width: '26px',
                        height: '26px',
                        borderRadius: '50%',
                        WebkitBorderRadius: '50%',
                        MozBorderRadius: '50%',
                        background: 'linear-gradient(135deg, #d0e8ec 0%, #c0d8dc 100%)',
                        backgroundColor: '#d0e8ec',
                        border: '2.5px solid white',
                        WebkitBoxShadow: '0 3px 10px rgba(0, 0, 0, 0.25)',
                        boxShadow: '0 3px 10px rgba(0, 0, 0, 0.25)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        transition: 'transform 0.2s',
                        zIndex: 100,
                        overflow: 'hidden'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'scale(1.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'scale(1)';
                      }}
                    >
                      <IonIcon icon={cameraOutline} style={{ fontSize: '14px', color: 'white' }} />
                    </button>
                  </div>
                </div>
              </div>
              
              {/* 본문 영역 */}
              <div style={{
                padding: '18px 20px 20px 20px',
                marginTop: '-25px',
                position: 'relative',
                zIndex: 2
              }}>
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: 'none' }}
                      id="profile-image-input"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        const input = e.target as HTMLInputElement;
                        
                        if (file) {
                          // 이미지 미리보기
                          const reader = new FileReader();
                          reader.onload = async (event) => {
                            const result = event.target?.result as string;
                            setProfileImage(result);
                            
                            // 서버에 업로드
                            try {
                              const { getAuthHeaders, getUserNo } = await import('../services/AuthService');
                              const userNo = getUserNo();
                              if (!userNo) {
                                console.error('사용자 번호를 가져올 수 없습니다.');
                                return;
                              }
                              
                              const baseUrl = getServerUrl();
                              const formData = new FormData();
                              formData.append('image', file, file.name);
                              
                              const authHeaders = getAuthHeaders();
                              // FormData를 사용할 때는 Content-Type을 설정하지 않음 (브라우저가 자동 설정)
                              // Authorization 헤더만 유지
                              const headers: HeadersInit = {};
                              const authHeaderValue = (authHeaders as any)['Authorization'];
                              if (authHeaderValue) {
                                (headers as any)['Authorization'] = authHeaderValue;
                              }
                              
                              console.log('📤 업로드 요청:', {
                                url: `${baseUrl}/auth/profile-image`,
                                fileName: file.name,
                                fileSize: file.size,
                                fileType: file.type
                              });
                              
                              const response = await fetch(`${baseUrl}/auth/profile-image`, {
                                method: 'POST',
                                headers: headers,
                                body: formData
                              });
                              
                              if (response.ok) {
                                const uploadResult = await response.json();
                                console.log('📤 업로드 응답:', uploadResult);
                                
                                if (uploadResult.profile_image_url) {
                                  // 상대 경로인 경우 서버 URL 추가
                                  let imageUrl = uploadResult.profile_image_url.startsWith('http') 
                                    ? uploadResult.profile_image_url 
                                    : `${baseUrl}${uploadResult.profile_image_url}`;
                                  
                                  // 캐시 버스터 추가 (이미지 갱신을 위해)
                                  const separator = imageUrl.includes('?') ? '&' : '?';
                                  imageUrl = `${imageUrl}${separator}t=${Date.now()}`;
                                  
                                  console.log('🖼️ 설정할 이미지 URL:', imageUrl);
                                  
                                  // 상태 업데이트
                                  setProfileImage(imageUrl);
                                  
                                  // 사용자별로 localStorage에 저장
                                  localStorage.setItem(`profile_image_${userNo}`, imageUrl);
                                  
                                  // 서버에서 최신 정보 다시 불러오기
                                  await loadUserInfo();
                                  
                                  console.log(`✅ 프로필 이미지 업로드 성공 (user_no: ${userNo})`);
                                } else {
                                  console.warn('⚠️ profile_image_url이 응답에 없습니다.');
                                }
                              } else {
                                const errorData = await response.json().catch(() => ({}));
                                console.error('프로필 이미지 업로드 실패:', errorData);
                                // 업로드 실패 시 미리보기 제거
                                setProfileImage(null);
                              }
                            } catch (error) {
                              console.error('프로필 이미지 업로드 실패:', error);
                              // 업로드 실패 시 미리보기 제거
                              setProfileImage(null);
                            }
                            
                            // input 초기화하여 같은 파일을 다시 선택해도 onChange가 트리거되도록 함
                            if (input) {
                              input.value = '';
                            }
                          };
                          reader.readAsDataURL(file);
                        } else {
                          // 파일이 선택되지 않았을 때도 input 초기화
                          if (input) {
                            input.value = '';
                          }
                        }
                      }}
                    />
                
                {/* 사용자 ID */}
                {userId && (
                  <div style={{
                    textAlign: 'center',
                    marginBottom: '20px',
                    marginTop: '45px'
                  }}>
                    <IonText style={{ 
                      fontSize: '1rem', 
                      fontWeight: '600', 
                      color: '#2d3748',
                      letterSpacing: '-0.2px'
                    }}>
                      {userId}
                    </IonText>
                  </div>
                )}
                
                {/* 정보 카드 */}
                <div style={{
                  background: 'white',
                  borderRadius: '16px',
                  padding: '16px',
                  marginBottom: '20px',
                  boxShadow: '0 2px 12px rgba(0, 0, 0, 0.06)',
                  border: '1px solid rgba(0, 0, 0, 0.05)'
                }}>
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: '1fr 1fr',
                    gap: '12px',
                    marginBottom: '12px'
                  }}>
                    <div style={{
                      padding: '12px',
                      background: 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
                      borderRadius: '10px',
                      border: '1px solid rgba(0, 0, 0, 0.05)'
                    }}>
                      <IonLabel style={{ 
                        color: '#718096', 
                        fontWeight: '600', 
                        fontSize: '0.7rem',
                        marginBottom: '6px', 
                        display: 'block',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        나이
                      </IonLabel>
                      <IonText style={{ 
                        color: '#2d3748', 
                        fontSize: '1.2rem', 
                        fontWeight: '700', 
                        display: 'block' 
                      }}>
                        {age || '-'}
                      </IonText>
                    </div>
                    
                    <div style={{
                      padding: '12px',
                      background: 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
                      borderRadius: '10px',
                      border: '1px solid rgba(0, 0, 0, 0.05)'
                    }}>
                      <IonLabel style={{ 
                        color: '#718096', 
                        fontWeight: '600', 
                        fontSize: '0.7rem',
                        marginBottom: '6px', 
                        display: 'block',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        BMI
                      </IonLabel>
                      <IonText style={{ 
                        color: '#2d3748', 
                        fontSize: '1.2rem', 
                        fontWeight: '700', 
                        display: 'block' 
                      }}>
                        {bmi || '-'}
                      </IonText>
                    </div>
                  </div>
                  
                  <div style={{
                    padding: '12px',
                    background: 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
                    borderRadius: '10px',
                    border: '1px solid rgba(0, 0, 0, 0.05)'
                  }}>
                    <IonLabel style={{ 
                      color: '#718096', 
                      fontWeight: '600', 
                      fontSize: '0.7rem',
                      marginBottom: '6px', 
                      display: 'block',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      성별
                    </IonLabel>
                    <IonText style={{ 
                      color: '#2d3748', 
                      fontSize: '1.2rem', 
                      fontWeight: '700', 
                      display: 'block' 
                    }}>
                      {gender === '1' ? '남성' : gender === '0' ? '여성' : '-'}
                    </IonText>
                  </div>
                </div>
                
                {/* 로그아웃 버튼 */}
                <IonButton 
                  expand="block" 
                  onClick={async () => {
                    const { getUserNo } = await import('../services/AuthService');
                    const userNo = getUserNo();
                    
                    logout();
                    setIsLoggedIn(false);
                    setShowUserInfo(false);
                    setProfileImage(null);
                    setUserId('');
                    setAge('');
                    setBmi('');
                    setGender('0');
                    
                    // 현재 사용자의 데이터만 삭제
                    if (userNo) {
                      localStorage.removeItem(`profile_image_${userNo}`);
                      localStorage.removeItem(`userAge_${userNo}`);
                      localStorage.removeItem(`userBmi_${userNo}`);
                      localStorage.removeItem(`userGender_${userNo}`);
                    }
                  }}
                  style={{ 
                    marginTop: '8px',
                    '--background': 'linear-gradient(135deg, #b8d8e0 0%, #a0c8d4 100%)',
                    '--background-hover': 'linear-gradient(135deg, #a8d0d8 0%, #98c0cc 100%)',
                    '--border-radius': '16px',
                    height: '52px',
                    fontWeight: '700',
                    fontSize: '1rem',
                    boxShadow: '0 6px 20px rgba(184, 216, 224, 0.4)',
                    letterSpacing: '0.3px'
                  }}
                >
                  로그아웃
                </IonButton>
              </div>
            </div>
          </div>
        )}

        {/* 초기 설정 화면 - iOS만 */}
        {!isSetupComplete && platform === 'ios' && (
          <>
            <IonText className="setup-title">
              <h2>초기 설정</h2>
            </IonText>

            {/* 단계 1: 나이, BMI 입력 */}
            {setupStep === 'info' && (
              <IonCard>
                <IonCardHeader>
                  <IonCardTitle>1단계: 기본 정보 입력</IonCardTitle>
                </IonCardHeader>
                <IonCardContent>
                  <IonText color="medium">
                    <p>나이, BMI, 성별을 입력해주세요.</p>
                  </IonText>
                  <IonItem>
                    <IonLabel position="stacked">나이</IonLabel>
                    <IonInput
                      type="number"
                      value={age}
                      placeholder="나이를 입력하세요"
                      onIonInput={async (e) => {
                        const value = e.detail.value!;
                        setAge(value);
                        try {
                          const { getUserNo } = await import('../services/AuthService');
                          const userNo = getUserNo();
                          if (userNo) {
                            localStorage.setItem(`userAge_${userNo}`, value || '');
                          } else {
                            localStorage.setItem('userAge', value || '');
                          }
                          if (platform === 'ios' && healthDataPlugin) {
                            try {
                              await healthDataPlugin.saveUserInfo({
                                age: value || '',
                                bmi: bmi || '',
                                gender: gender || '0'
                              });
                            } catch (err) {
                              console.log('나이 UserDefaults 저장 실패:', err);
                            }
                          }
                        } catch (err) {
                          console.log('나이 저장 실패:', err);
                        }
                      }}
                    />
                  </IonItem>
                  <IonItem>
                    <IonLabel position="stacked">BMI</IonLabel>
                    <IonInput
                      type="number"
                      value={bmi}
                      placeholder="BMI를 입력하세요"
                      onIonInput={async (e) => {
                        const value = e.detail.value!;
                        setBmi(value);
                        try {
                          const { getUserNo } = await import('../services/AuthService');
                          const userNo = getUserNo();
                          if (userNo) {
                            localStorage.setItem(`userBmi_${userNo}`, value || '');
                          } else {
                            localStorage.setItem('userBmi', value || '');
                          }
                          if (platform === 'ios' && healthDataPlugin) {
                            try {
                              await healthDataPlugin.saveUserInfo({
                                age: age || '',
                                bmi: value || '',
                                gender: gender || '0'
                              });
                            } catch (err) {
                              console.log('BMI UserDefaults 저장 실패:', err);
                            }
                          }
                        } catch (err) {
                          console.log('BMI 저장 실패:', err);
                        }
                      }}
                    />
                  </IonItem>
                  <IonItem>
                    <IonLabel position="stacked">성별</IonLabel>
                    <IonSelect
                      value={gender}
                      placeholder="성별을 선택하세요"
                      onIonChange={async (e) => {
                        const value = e.detail.value;
                        setGender(value);
                        try {
                          const { getUserNo } = await import('../services/AuthService');
                          const userNo = getUserNo();
                          if (userNo) {
                            localStorage.setItem(`userGender_${userNo}`, value || '0');
                          } else {
                            localStorage.setItem('userGender', value || '0');
                          }
                          if (platform === 'ios' && healthDataPlugin) {
                            try {
                              await healthDataPlugin.saveUserInfo({
                                age: age || '',
                                bmi: bmi || '',
                                gender: value || '0'
                              });
                            } catch (err) {
                              console.log('성별 UserDefaults 저장 실패:', err);
                            }
                          }
                        } catch (err) {
                          console.log('성별 저장 실패:', err);
                        }
                      }}
                    >
                      <IonSelectOption value="0">여성</IonSelectOption>
                      <IonSelectOption value="1">남성</IonSelectOption>
                    </IonSelect>
                  </IonItem>
                  <IonButton
                    expand="block"
                    color="primary"
                    onClick={handleInfoStepComplete}
                    style={{ marginTop: '20px' }}
                  >
                    다음 단계
                  </IonButton>
                </IonCardContent>
              </IonCard>
            )}

            {/* 단계 2: HealthKit 권한 요청 */}
            {setupStep === 'permission' && (
              <IonCard>
                <IonCardHeader>
                  <IonCardTitle>2단계: HealthKit 권한 요청</IonCardTitle>
                </IonCardHeader>
                <IonCardContent>
                  <IonText color="medium">
                    <p>HealthKit 데이터를 사용하기 위해 권한이 필요합니다.</p>
                  </IonText>
                  {healthDataPlugin ? (
                    <IonButton
                      expand="block"
                      color="primary"
                      onClick={async () => {
                        const success = await handlePermissionRequest();
                        // 권한 요청 완료 후 설정 완료 처리 및 데이터 가져오기
                        if (success) {
                          localStorage.setItem('healthSetupComplete', 'true');
                          setIsSetupComplete(true);
                          setSetupStep('complete');
                          // 권한 승인 후 바로 데이터 가져오기
                          setTimeout(() => {
                            fetchHealthData(healthDataPlugin);
                          }, 500);
                        }
                      }}
                      style={{ marginTop: '20px' }}
                    >
                      HealthKit 권한 요청
                    </IonButton>
                  ) : null}
                </IonCardContent>
              </IonCard>
            )}
          </>
        )}

        {/* 메인 화면 (설정 완료 후 또는 Android/Web) */}
        {(isSetupComplete || platform !== 'ios') && (
          <div className="container">
            
            {/* HealthKit 데이터 표시 - 다양한 레이아웃 */}
            <div className="health-data-section">
              {isExampleData && (
                <div style={{ textAlign: 'center', marginBottom: '12px' }}>
                  <IonText color="medium" style={{ fontSize: '13px', fontStyle: 'italic' }}>
                    ※ 웹에서는 예시 데이터가 표시됩니다
                  </IonText>
                </div>
              )}
              {/* HRV와 산소포화도 - 가로 배치 */}
              <div className="health-data-secondary-row">
                {/* 심박변이 */}
                <IonCard className="hrv-card">
                  <IonCardContent>
                    <div className="health-data-label-small">심박변이</div>
                    {displayHealthData.hrv ? (
                      <>
                        <div className="health-data-value-small">{displayHealthData.hrv.value.toFixed(2)}<span className="health-data-unit-small">ms</span></div>
                        <div className="health-data-date-small">{formatDate(displayHealthData.hrv.date)}</div>
                      </>
                    ) : (
                      <div className="health-data-empty-small">데이터 없음</div>
                    )}
                  </IonCardContent>
                </IonCard>

                {/* 혈중산소포화도 */}
                <IonCard className="oxygen-card">
                  <IonCardContent>
                    <div className="health-data-label-small">산소포화도</div>
                    {displayHealthData.oxygenSaturation ? (
                      <>
                        <div className="health-data-value-small">{displayHealthData.oxygenSaturation.value.toFixed(1)}<span className="health-data-unit-small">%</span></div>
                        <div className="health-data-date-small">{formatDate(displayHealthData.oxygenSaturation.date)}</div>
                      </>
                    ) : (
                      <div className="health-data-empty-small">데이터 없음</div>
                    )}
                  </IonCardContent>
                </IonCard>
              </div>

              {/* 심박수 - 큰 숫자 중심, 헤더 없음 */}
              <IonCard className="health-data-main-card heart-rate-main">
                <IonCardContent>
                  <div className="health-data-label-large">심박수</div>
                  {displayHealthData.heartRate ? (
                    <>
                      <div className="health-data-value-wrapper-large">
                        <div className="health-data-value-large">{displayHealthData.heartRate.value.toFixed(0)}</div>
                        <div className="health-data-unit-large">bpm</div>
                      </div>
                      <div className="health-data-date-large" style={{ fontSize: '13px', marginTop: '8px' }}>
                        마지막 업데이트: {new Date(displayHealthData.heartRate.date).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </>
                  ) : (
                    <div className="health-data-empty-large">데이터 없음</div>
                  )}
                  
                  {/* 심박수 차트 */}
                  {chartData ? (
                    <div style={{ marginTop: '12px' }}>
                      <HeartRateChart data={chartData.heartRateData} />
                    </div>
                  ) : (
                    <div style={{ padding: '20px', textAlign: 'center', marginTop: '12px' }}>
                      <IonText color="medium">
                        <p>데이터가 없습니다. 10분마다 자동으로 데이터가 수집됩니다.</p>
                      </IonText>
                    </div>
                  )}
                </IonCardContent>
              </IonCard>
            </div>
          </div>
        )}

        {/* 온도 차트 */}
        <div className="container">
        <IonCard className="temperature-chart-card">
          <IonCardContent>
            <div className="temperature-chart-title">하룻밤 온도 변화</div>
            {chartData ? (
              <TemperatureChart data={chartData.temperatureData} />
            ) : (
              <div style={{ padding: '20px', textAlign: 'center' }}>
                <IonText color="medium">
                  <p>데이터가 없습니다. 10분마다 자동으로 데이터가 수집됩니다.</p>
                </IonText>
              </div>
            )}
          </IonCardContent>
        </IonCard>
        </div>

      </IonContent>
    </IonPage>
  );
};

export default Health_ios;

