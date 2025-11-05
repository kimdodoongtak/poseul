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
  IonSpinner
} from '@ionic/react';
import './Tab1.css';

interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

const Tab1: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [healthData, setHealthData] = useState<HealthData>({
    heartRate: null,
    hrv: null,
    oxygenSaturation: null,
  });
  const [backgroundMonitoring, setBackgroundMonitoring] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
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
              console.log('HealthData 권한 승인됨, 데이터 가져오기 시작...');
              // 권한 승인 후 약간의 지연을 두고 데이터 가져오기
              setTimeout(async () => {
                await fetchHealthData(HealthData);
              }, 500);
            } else {
              console.log('HealthData 권한 거부됨');
              alert('HealthKit 권한이 필요합니다.\n\n설정 > Health > 데이터 액세스 및 기기 > poseul에서 권한을 허용해주세요.');
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

  // 백그라운드 모니터링이 활성화된 경우 주기적으로 데이터 업데이트 (iOS만)
  useEffect(() => {
    if (!healthDataPlugin || !backgroundMonitoring || platform !== 'ios') return;
    
    const interval = setInterval(() => {
      fetchHealthData(healthDataPlugin);
    }, 30000); // 30초마다 업데이트

    return () => {
      clearInterval(interval);
    };
  }, [backgroundMonitoring, healthDataPlugin, platform]);

  const fetchHealthData = async (HealthData: any) => {
    if (!HealthData) {
      console.log('HealthData 플러그인이 없습니다.');
      alert('HealthData 플러그인이 로드되지 않았습니다.');
      return;
    }
    setLoading(true);
    
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

      console.log('HealthData 가져오기 결과:', { 
        heartRate: heartRate ? `${heartRate.value} bpm` : '없음',
        hrv: hrv ? `${hrv.value} ms` : '없음',
        oxygenSaturation: oxygenSaturation ? `${oxygenSaturation.value}%` : '없음'
      });

      const normalizedHeartRate = normalizeData(heartRate);
      const normalizedHrv = normalizeData(hrv);
      const normalizedOxygen = normalizeData(oxygenSaturation);

      // 모든 데이터가 없으면 메시지 표시
      if (!normalizedHeartRate && !normalizedHrv && !normalizedOxygen) {
        alert('Health 앱에 데이터가 없습니다. Health 앱에서 심박수, HRV, 혈중산소포화도 데이터를 확인해주세요.');
      }

      setHealthData({
        heartRate: normalizedHeartRate,
        hrv: normalizedHrv,
        oxygenSaturation: normalizedOxygen,
      });
    } catch (err: any) {
      console.error('HealthData 데이터 가져오기 실패:', err);
      const errorMsg = err?.message || err?.toString() || String(err);
      alert('데이터를 가져오는 중 오류가 발생했습니다:\n' + errorMsg);
    } finally {
      setLoading(false);
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
                onIonInput={(e) => setAge(e.detail.value!)}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">BMI</IonLabel>
              <IonInput
                type="number"
                value={bmi}
                placeholder="BMI를 입력하세요"
                onIonInput={(e) => setBmi(e.detail.value!)}
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

        {/* HealthData */}
        <IonCard>
          <IonCardHeader>
            <IonCardTitle>
              {platform === 'ios' ? 'HealthKit 데이터' : platform === 'android' ? 'HealthData (Android - 구현 예정)' : 'HealthData (웹 미지원)'}
            </IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonButton
              expand="block"
              onClick={async () => {
                if (!healthDataPlugin) {
                  alert('HealthData 플러그인이 로드되지 않았습니다.');
                  return;
                }
                if (platform !== 'ios') {
                  alert('iOS에서만 HealthData를 사용할 수 있습니다.');
                  return;
                }
                console.log('데이터 새로고침 버튼 클릭');
                await fetchHealthData(healthDataPlugin);
              }}
              disabled={loading || !healthDataPlugin || platform !== 'ios'}
            >
              {loading ? <IonSpinner /> : '데이터 새로고침'}
            </IonButton>

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

export default Tab1;
