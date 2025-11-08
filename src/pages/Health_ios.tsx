import React, { useState, useEffect } from 'react';
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
import { personOutline } from 'ionicons/icons';
import SignIn from '../components/SignIn';
import './Health_ios.css';

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
  
  // 초기 설정 단계 관리
  const [setupStep, setSetupStep] = useState<'info' | 'permission' | 'monitoring' | 'complete'>('info');
  const [isSetupComplete, setIsSetupComplete] = useState<boolean>(false);
  const [hasHealthKitPermission, setHasHealthKitPermission] = useState<boolean>(false);
  
  // UI 템플릿 관련 상태
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);

  useEffect(() => {
    // 초기 설정 완료 여부 확인
    const checkSetupComplete = () => {
      try {
        const savedAge = localStorage.getItem('userAge');
        const savedBmi = localStorage.getItem('userBmi');
        const savedGender = localStorage.getItem('userGender');
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
            localStorage.setItem('userGender', '0');
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
  }, []);

  // 10분마다 자동으로 최신 데이터 가져오기 (iOS만)
  useEffect(() => {
    if (!healthDataPlugin || platform !== 'ios') return;
    
    // 초기 로드 후 첫 데이터 가져오기
    const initialTimeout = setTimeout(() => {
      fetchHealthData(healthDataPlugin);
    }, 1000); // 1초 후 첫 데이터 가져오기
    
    // 10분마다 자동으로 데이터 가져오기
    const interval = setInterval(() => {
      fetchHealthData(healthDataPlugin);
    }, 10 * 60 * 1000); // 10분 = 600000ms

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [healthDataPlugin, platform]);


  // 백그라운드 모니터링 이벤트 리스너는 제거 (10분마다만 가져오기)
  // 실시간 업데이트 대신 10분마다만 데이터를 가져오도록 함
  // useEffect(() => {
  //   if (!healthDataPlugin || platform !== 'ios' || !backgroundMonitoring) return;
  //   const listener = healthDataPlugin.addListener('healthDataUpdated', async () => {
  //     await fetchHealthDataInBackground(healthDataPlugin);
  //   });
  //   return () => {
  //     listener.remove();
  //   };
  // }, [healthDataPlugin, platform, backgroundMonitoring]);

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
        // Promise를 반환하지 않도록 void로 처리하여 완전히 백그라운드로 실행
        void sendToServer({
          heartRate: normalizedHeartRate?.value || null,
          HRV: normalizedHrv?.value || null,
          oxygenSaturation: normalizedOxygen?.value || null,
          bmi: bmi ? parseFloat(bmi) : null,
          age: age ? parseFloat(age) : null,
          gender: gender && gender !== '' ? parseFloat(gender) : 0.0,
        }).catch((err) => {
          console.error('서버 전송 실패 (백그라운드):', err);
        });
      }
    } catch (err: any) {
      console.error('HealthData 데이터 가져오기 실패:', err);
      const errorMsg = err?.message || err?.toString() || String(err);
      alert('데이터를 가져오는 중 오류가 발생했습니다:\n' + errorMsg);
    }
  };

  // 백그라운드에서 데이터 가져오기 (UI 업데이트 및 서버 전송)
  const fetchHealthDataInBackground = async (HealthData: any) => {
    if (!HealthData) {
      console.log('HealthData 플러그인이 없습니다.');
      return;
    }
    
    console.log('🔄 백그라운드에서 HealthData 가져오기 시작...');
    
    try {
      const [heartRate, hrv, oxygenSaturation] = await Promise.all([
        HealthData.getLatestHeartRate().catch(() => null),
        HealthData.getLatestHeartRateVariability().catch(() => null),
        HealthData.getLatestOxygenSaturation().catch(() => null),
      ]);

      // 빈 딕셔너리를 null로 변환
      const normalizeData = (data: any) => {
        if (!data || Object.keys(data).length === 0) return null;
        return data;
      };

      const normalizedHeartRate = normalizeData(heartRate);
      const normalizedHrv = normalizeData(hrv);
      const normalizedOxygen = normalizeData(oxygenSaturation);

      console.log('🔄 백그라운드 HealthData 가져오기 결과:', { 
        heartRate: normalizedHeartRate ? `${normalizedHeartRate.value} bpm` : '없음',
        hrv: normalizedHrv ? `${normalizedHrv.value} ms` : '없음',
        oxygenSaturation: normalizedOxygen ? `${normalizedOxygen.value}%` : '없음'
      });

      // UI 업데이트 (백그라운드에서도 최신 데이터 표시)
      setHealthData({
        heartRate: normalizedHeartRate,
        hrv: normalizedHrv,
        oxygenSaturation: normalizedOxygen,
      });

      // 서버로 전송
      if (normalizedHeartRate || normalizedHrv || normalizedOxygen) {
        void sendToServer({
          heartRate: normalizedHeartRate?.value || null,
          HRV: normalizedHrv?.value || null,
          oxygenSaturation: normalizedOxygen?.value || null,
          bmi: bmi ? parseFloat(bmi) : null,
          age: age ? parseFloat(age) : null,
          gender: gender && gender !== '' ? parseFloat(gender) : 0.0,
        }).catch((err) => {
          console.error('🔄 백그라운드 서버 전송 실패:', err);
        });
      }
    } catch (err: any) {
      console.error('🔄 백그라운드 HealthData 가져오기 실패:', err);
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
    // 서버 URL 설정 (환경 변수나 설정에서 가져올 수 있음)
    const serverURL = 'http://192.168.68.74:3000/healthdata'; // 현재 컴퓨터 IP 주소
    // 또는 UserDefaults에서 가져오기 (iOS)
    // const serverURL = localStorage.getItem('serverURL') || 'http://192.168.68.74:3000/healthdata';

    try {
      console.log('📤 서버로 데이터 전송 시작:', data);

      // 타임아웃 추가 (10초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초 타임아웃

      try {
        console.log('📡 서버 연결 시도:', serverURL);
        const response = await fetch(serverURL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 서버 응답:', result);
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
        
        // 네트워크 에러인 경우 더 명확한 메시지
        if (fetchError.message?.includes('Failed to fetch') || 
            fetchError.message?.includes('NetworkError') ||
            fetchError.name === 'TypeError') {
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

  return (
    <IonPage className="health-ios-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>포슬💭</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">포슬💭</IonTitle>
          </IonToolbar>
        </IonHeader>

        {/* 로그인 버튼 */}
        {isSetupComplete && (
          <div 
            className="on-boarding-btn" 
            onClick={() => setShowSignIn(true)}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '18px',
              background: 'white',
              position: 'fixed',
              top: 'calc(var(--safe-area-inset-top) + 20px)',
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
            <SignIn onClose={() => setShowSignIn(false)} />
          </div>
        )}

        {/* 초기 설정 화면 */}
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
                          localStorage.setItem('userAge', value || '');
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
                          localStorage.setItem('userBmi', value || '');
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
                          localStorage.setItem('userGender', value || '0');
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

        {/* 메인 화면 (설정 완료 후) */}
        {isSetupComplete && (
          <>

            {/* 백그라운드 모니터링 토글 */}
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>백그라운드 모니터링</IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <IonItem>
                  <IonLabel>백그라운드 모니터링 활성화</IonLabel>
                  <IonToggle
                    checked={backgroundMonitoring}
                    onIonChange={(e) => handleBackgroundMonitoringToggle(e.detail.checked)}
                    disabled={!healthDataPlugin || platform !== 'ios'}
                  />
                </IonItem>
                {platform === 'android' && (
                  <IonText color="warning">
                    <p>Android에서는 아직 HealthData가 구현되지 않았습니다.</p>
                  </IonText>
                )}
                {platform === 'web' && (
                  <IonText color="warning">
                    <p>웹에서는 HealthData를 사용할 수 없습니다. (iOS/Android에서만 사용 가능)</p>
                  </IonText>
                )}
              </IonCardContent>
            </IonCard>

            {/* HealthKit 데이터 표시 */}
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>
                  {platform === 'ios' ? 'HealthKit 데이터' : platform === 'android' ? 'HealthData (Android - 구현 예정)' : 'HealthData (웹 미지원)'}
                </IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <IonGrid>
                  <IonRow>
                    {/* 심박수 */}
                    <IonCol size="4">
                      <div className="health-data-box heart-rate-box">
                        <div className="health-data-label">심박수</div>
                        {healthData.heartRate ? (
                          <>
                            <div className="health-data-value-container">
                              <div className="health-data-value">{healthData.heartRate.value.toFixed(0)}</div>
                              <div className="health-data-unit">bpm</div>
                            </div>
                            <div className="health-data-date">{formatDate(healthData.heartRate.date)}</div>
                          </>
                        ) : (
                          <div className="health-data-empty">데이터 없음</div>
                        )}
                      </div>
                    </IonCol>

                    {/* 심박변이 */}
                    <IonCol size="4">
                      <div className="health-data-box hrv-box">
                        <div className="health-data-label">심박변이</div>
                        {healthData.hrv ? (
                          <>
                            <div className="health-data-value-container">
                              <div className="health-data-value">{healthData.hrv.value.toFixed(2)}</div>
                              <div className="health-data-unit">ms</div>
                            </div>
                            <div className="health-data-date">{formatDate(healthData.hrv.date)}</div>
                          </>
                        ) : (
                          <div className="health-data-empty">데이터 없음</div>
                        )}
                      </div>
                    </IonCol>

                    {/* 혈중산소포화도 */}
                    <IonCol size="4">
                      <div className="health-data-box oxygen-box">
                        <div className="health-data-label">산소포화도</div>
                        {healthData.oxygenSaturation ? (
                          <>
                            <div className="health-data-value-container">
                              <div className="health-data-value">{healthData.oxygenSaturation.value.toFixed(1)}</div>
                              <div className="health-data-unit">%</div>
                            </div>
                            <div className="health-data-date">{formatDate(healthData.oxygenSaturation.date)}</div>
                          </>
                        ) : (
                          <div className="health-data-empty">데이터 없음</div>
                        )}
                      </div>
                    </IonCol>
                  </IonRow>
                </IonGrid>
              </IonCardContent>
        </IonCard>
          </>
        )}
      </IonContent>
    </IonPage>
  );
};

export default Health_ios;

