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
  IonToggle
} from '@ionic/react';
import './Health_ios.css';

interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

const Health_ios: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [healthData, setHealthData] = useState<HealthData>({
    heartRate: null,
    hrv: null,
    oxygenSaturation: null,
  });
  const [backgroundMonitoring, setBackgroundMonitoring] = useState<boolean>(false);
  const [sleepFocus, setSleepFocus] = useState<boolean>(false);
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');

  useEffect(() => {
    // HealthData 플러그인을 비동기로 로드 (UI 렌더링을 막지 않음)
    const loadHealthData = async () => {
      try {
        const { Capacitor } = await import('@capacitor/core');
        const currentPlatform = Capacitor.getPlatform();
        setPlatform(currentPlatform);
        
        const { HealthData } = await import('../plugins/healthdata');
        setHealthDataPlugin(HealthData);
        
        // iOS에서만 HealthKit 권한 요청
        if (currentPlatform === 'ios') {
          try {
            console.log('HealthData 권한 요청 중... (iOS)');
            const result = await HealthData.requestAuthorization();
            console.log('HealthData 권한 요청 결과:', result);
            if (result.success) {
              console.log('HealthData 권한 승인됨');
              // 권한 승인 후 자동으로 데이터 가져오기는 useEffect에서 처리됨
            } else {
              console.log('HealthData 권한 거부됨 또는 미결정');
              const message = result.message || 'HealthKit 권한이 필요합니다.';
              alert(message + '\n\n설정 > Health > 데이터 액세스 및 기기 > poseul에서 권한을 허용해주세요.');
            }
            
            // 저장된 age와 bmi 불러오기 (localStorage 사용)
            try {
              const savedAge = localStorage.getItem('userAge');
              const savedBmi = localStorage.getItem('userBmi');
              if (savedAge) setAge(savedAge);
              if (savedBmi) setBmi(savedBmi);
            } catch (err) {
              console.log('저장된 나이/BMI 불러오기 실패:', err);
            }
          } catch (err: any) {
            console.error('HealthData 권한 요청 실패:', err);
            const errorMsg = err?.message || err?.toString() || String(err);
            alert('HealthKit 권한 요청 중 오류가 발생했습니다:\n' + errorMsg);
          }
        } else if (currentPlatform === 'android') {
          console.log('Android 플랫폼 - HealthData는 아직 구현되지 않았습니다.');
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


  // 백그라운드 모니터링 이벤트 리스너 (HealthKit 데이터 업데이트 감지)
  useEffect(() => {
    if (!healthDataPlugin || platform !== 'ios' || !backgroundMonitoring) return;

    // HealthKit 백그라운드 업데이트 이벤트 리스너
    // 백그라운드에서는 서버 전송만 하고 UI 업데이트는 하지 않음
    const listener = healthDataPlugin.addListener('healthDataUpdated', async () => {
      console.log('🔄 백그라운드에서 HealthKit 데이터 업데이트 감지');
      // 백그라운드에서는 데이터를 가져와서 서버로만 전송 (UI 업데이트 없음)
      // fetchHealthData를 호출하지 않고 백그라운드에서만 서버 전송
    });

    return () => {
      listener.remove();
    };
  }, [healthDataPlugin, platform, backgroundMonitoring]);

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

  const sendToServer = async (data: {
    heartRate: number | null;
    HRV: number | null;
    oxygenSaturation: number | null;
    bmi: number | null;
    age: number | null;
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

  const handleSleepFocusToggle = async (enabled: boolean) => {
    if (platform !== 'ios') {
      console.log('수면 집중모드는 iOS에서만 사용 가능합니다.');
      return;
    }
    try {
      // iOS 설정 앱으로 이동하여 수면 집중모드를 제어
      // 또는 네이티브 플러그인을 통해 제어
      if (healthDataPlugin && typeof healthDataPlugin.setSleepFocus === 'function') {
        const result = await healthDataPlugin.setSleepFocus({ enabled });
        if (result.success) {
          setSleepFocus(enabled);
        }
      } else {
        // 네이티브 플러그인이 없으면 설정 앱으로 이동
        try {
          const { App } = await import('@capacitor/app');
          // iOS 설정 앱 열기
          if (typeof (window as any).webkit?.messageHandlers !== 'undefined') {
            // 네이티브 브릿지를 통해 설정 앱 열기
            window.location.href = 'app-settings:';
          } else {
            alert('설정 > 집중 모드 > 수면에서 수면 집중모드를 설정할 수 있습니다.');
          }
        } catch (err) {
          alert('설정 > 집중 모드 > 수면에서 수면 집중모드를 설정할 수 있습니다.');
        }
      }
    } catch (err: any) {
      console.log('수면 집중모드 설정 실패:', err);
      alert('수면 집중모드 설정에 실패했습니다.');
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ko-KR', {
        year: 'numeric',
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
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>포술 🧃</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">포술 🧃</IonTitle>
          </IonToolbar>
        </IonHeader>

        <IonText color="primary">
          <h2>안녕, 뚱딱앱 세상에 오신 걸 환영합니다 🎉</h2>
        </IonText>

        {/* 사용자 정보 입력 */}
        <IonCard>
          <IonCardHeader>
            <IonCardTitle>사용자 정보</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
                  <IonItem>
                    <IonLabel position="stacked">나이</IonLabel>
                    <IonInput
                      type="number"
                      value={age}
                      placeholder="나이를 입력하세요"
                      onIonInput={async (e) => {
                        const value = e.detail.value!;
                        setAge(value);
                        // localStorage에도 저장 (웹 호환성)
                        try {
                          localStorage.setItem('userAge', value || '');
                          // iOS에서 UserDefaults에 저장
                          if (platform === 'ios' && healthDataPlugin) {
                            try {
                              await healthDataPlugin.saveUserInfo({
                                age: value || '',
                                bmi: bmi || ''
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
                        // localStorage에도 저장 (웹 호환성)
                        try {
                          localStorage.setItem('userBmi', value || '');
                          // iOS에서 UserDefaults에 저장
                          if (platform === 'ios' && healthDataPlugin) {
                            try {
                              await healthDataPlugin.saveUserInfo({
                                age: age || '',
                                bmi: value || ''
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
          </IonCardContent>
        </IonCard>

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
            {platform === 'ios' && !healthDataPlugin && (
              <IonText color="warning">
                <p>HealthData 플러그인을 로드하는 중...</p>
              </IonText>
            )}
          </IonCardContent>
        </IonCard>

        {/* 수면 집중모드 토글 */}
        <IonCard>
          <IonCardHeader>
            <IonCardTitle>수면 집중모드</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel>수면 집중모드 활성화</IonLabel>
              <IonToggle
                checked={sleepFocus}
                onIonChange={(e) => handleSleepFocusToggle(e.detail.checked)}
                disabled={platform !== 'ios'}
              />
            </IonItem>
            {platform === 'android' && (
              <IonText color="warning">
                <p>수면 집중모드는 iOS에서만 사용 가능합니다.</p>
              </IonText>
            )}
            {platform === 'web' && (
              <IonText color="warning">
                <p>수면 집중모드는 iOS에서만 사용 가능합니다.</p>
              </IonText>
            )}
            {platform === 'ios' && (
              <IonText color="medium">
                <p style={{ fontSize: '0.9em', marginTop: '10px' }}>
                  수면 집중모드를 활성화하면 방해 알림이 차단됩니다.
                </p>
              </IonText>
            )}
          </IonCardContent>
        </IonCard>

        {/* HealthData */}
        <IonCard>
          <IonCardHeader>
            <IonCardTitle>
              {platform === 'ios' ? 'HealthKit 데이터' : platform === 'android' ? 'HealthData (Android - 구현 예정)' : 'HealthData (웹 미지원)'}
            </IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            {platform === 'ios' && healthDataPlugin && (
              <IonButton
                expand="block"
                color="primary"
                onClick={async () => {
                  try {
                    console.log('HealthKit 권한 요청 버튼 클릭');
                    const result = await healthDataPlugin.requestAuthorization();
                    console.log('HealthKit 권한 요청 결과:', result);
                    if (result.success) {
                      alert('HealthKit 권한이 허용되었습니다!');
                      // 권한 승인 후 자동으로 데이터 가져오기는 useEffect에서 처리됨
                      // 권한 승인 후 데이터 가져오기 시도
                      setTimeout(() => {
                        fetchHealthData(healthDataPlugin);
                      }, 500);
                    } else {
                      const message = result.message || 'HealthKit 권한이 거부되었습니다.';
                      alert(message + '\n\n설정 > Health > 데이터 액세스 및 기기 > poseul에서 권한을 허용해주세요.');
                    }
                  } catch (err: any) {
                    console.error('HealthKit 권한 요청 실패:', err);
                    const errorMsg = err?.message || err?.toString() || String(err);
                    alert('HealthKit 권한 요청 중 오류가 발생했습니다:\n' + errorMsg);
                  }
                }}
              >
                HealthKit 권한 요청
              </IonButton>
            )}

            {platform === 'android' && (
              <IonText color="warning">
                <p>Android에서는 아직 HealthData가 구현되지 않았습니다. iOS에서만 사용 가능합니다.</p>
              </IonText>
            )}
            {platform === 'web' && (
              <IonText color="warning">
                <p>웹에서는 HealthData를 사용할 수 없습니다.</p>
              </IonText>
            )}
            {platform === 'ios' && !healthDataPlugin && (
              <IonText color="warning">
                <p>HealthData 플러그인을 로드하는 중...</p>
              </IonText>
            )}

            {/* 심박수 */}
            <IonItem>
              <IonLabel>
                <h2>심박수</h2>
                {healthData.heartRate ? (
                  <>
                    <p>{healthData.heartRate.value.toFixed(0)} bpm</p>
                    <p>{formatDate(healthData.heartRate.date)}</p>
                  </>
                ) : (
                  <p>데이터 없음</p>
                )}
              </IonLabel>
            </IonItem>

            {/* 심박변이 */}
            <IonItem>
              <IonLabel>
                <h2>심박변이 (HRV)</h2>
                {healthData.hrv ? (
                  <>
                    <p>{healthData.hrv.value.toFixed(2)} ms</p>
                    <p>{formatDate(healthData.hrv.date)}</p>
                  </>
                ) : (
                  <p>데이터 없음</p>
                )}
              </IonLabel>
            </IonItem>

            {/* 혈중산소포화도 */}
            <IonItem>
              <IonLabel>
                <h2>혈중산소포화도</h2>
                {healthData.oxygenSaturation ? (
                  <>
                    <p>{healthData.oxygenSaturation.value.toFixed(1)}%</p>
                    <p>{formatDate(healthData.oxygenSaturation.date)}</p>
                  </>
                ) : (
                  <p>데이터 없음</p>
                )}
              </IonLabel>
            </IonItem>
          </IonCardContent>
        </IonCard>
      </IonContent>
    </IonPage>
  );
};

export default Health_ios;

