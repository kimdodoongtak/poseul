import { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
  IonCard,
  IonCardHeader,
  IonCardTitle,
  IonCardContent,
  IonItem,
  IonLabel,
  IonToggle,
  IonRange,
  IonSelect,
  IonSelectOption,
  IonButton,
  IonSpinner,
  IonText,
} from '@ionic/react';
import { Capacitor } from '@capacitor/core';
import { IotService, AirConditionerMode, FanSpeed } from '../services';
import { ModelService } from '../services';
import './Tab4.css';

interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

const Tab4: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(false); // 초기값을 false로 설정
  const [status, setStatus] = useState<{
    currentTemperature: number;
    airQuality: number;
    power: boolean;
    targetTemperature: number;
    mode: AirConditionerMode;
    fanSpeed: FanSpeed;
  } | null>(null);
  const [healthData, setHealthData] = useState<HealthData>({
    heartRate: null,
    hrv: null,
    oxygenSaturation: null,
  });
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [autoControlEnabled, setAutoControlEnabled] = useState<boolean>(false);
  const [predictedTemperature, setPredictedTemperature] = useState<number | null>(null);

  useEffect(() => {
    // 초기 상태만 로드 (자동 새로고침 제거)
    loadStatus();
  }, []);

  useEffect(() => {
    // HealthData 플러그인 로드 (iOS HealthKit 사용)
    const loadHealthData = async () => {
      try {
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
              setTimeout(async () => {
                await fetchHealthData(HealthData);
              }, 500);
            } else {
              console.log('HealthData 권한 거부됨');
            }
          } catch (err: any) {
            console.error('HealthData 권한 요청 실패:', err);
          }
        } else if (currentPlatform === 'android') {
          // 안드로이드에서는 서버에서 iOS 데이터 가져오기
          console.log('Android 플랫폼 - 서버에서 건강 데이터 가져오기');
          try {
            const { HealthDataService } = await import('../services');
            const result = await HealthDataService.getLatestHealthData();
            if (result.success && result.data) {
              setHealthData({
                heartRate: result.data.heartRate || null,
                hrv: result.data.hrv || null,
                oxygenSaturation: result.data.oxygenSaturation || null,
              });
            } else {
              generateSimulatedHealthData();
            }
          } catch (err) {
            console.error('서버에서 건강 데이터 가져오기 실패:', err);
            generateSimulatedHealthData();
          }
        } else {
          generateSimulatedHealthData();
        }
      } catch (err) {
        console.log('HealthData 플러그인 로드 실패:', err);
        generateSimulatedHealthData();
      }
    };
    
    setTimeout(() => {
      loadHealthData();
    }, 500);
  }, []);

  // 자동 제어: 건강 데이터로 예측하고 IoT 제어
  useEffect(() => {
    if (autoControlEnabled && healthData.heartRate && healthData.hrv && healthData.oxygenSaturation && status) {
      performAutoControl();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoControlEnabled, healthData.heartRate?.value, healthData.hrv?.value, healthData.oxygenSaturation?.value]);

  // 시뮬레이션 건강 데이터 생성
  const generateSimulatedHealthData = () => {
    const heartRate = Math.floor(Math.random() * 41) + 60; // 60-100
    const hrv = Math.random() * 30 + 20; // 20-50
    const oxygenSaturation = Math.random() * 5 + 95; // 95-100
    
    setHealthData({
      heartRate: { value: heartRate, date: new Date().toISOString() },
      hrv: { value: hrv, date: new Date().toISOString() },
      oxygenSaturation: { value: oxygenSaturation, date: new Date().toISOString() },
    });
  };

  const fetchHealthData = async (HealthData: any) => {
    if (!HealthData) {
      console.log('HealthData 플러그인이 없습니다.');
      generateSimulatedHealthData();
      return;
    }
    
    try {
      const [heartRate, hrv, oxygenSaturation] = await Promise.all([
        HealthData.getLatestHeartRate().catch(() => null),
        HealthData.getLatestHeartRateVariability().catch(() => null),
        HealthData.getLatestOxygenSaturation().catch(() => null),
      ]);

      setHealthData({
        heartRate: heartRate || null,
        hrv: hrv || null,
        oxygenSaturation: oxygenSaturation || null,
      });
    } catch (err) {
      console.error('HealthData 가져오기 실패:', err);
      generateSimulatedHealthData();
    }
  };

  // 건강 데이터로 예측하고 자동으로 IoT 제어
  const performAutoControl = async () => {
    if (!healthData.heartRate || !healthData.hrv || !healthData.oxygenSaturation) {
      return;
    }

    try {
      // 모델로 체온 예측 (기본값 사용)
      const predictionRequest = {
        heartRate: healthData.heartRate.value,
        hrv: healthData.hrv.value,
        bmi: 22.0, // 기본값
        oxygenSaturation: healthData.oxygenSaturation.value,
        gender: 'MALE' as const,
        age: 30, // 기본값
      };

      const result = await ModelService.predictTemperature(predictionRequest);
      
      if (result.success) {
        setPredictedTemperature(result.predictedTemperature);
        
        // 예측된 온도에 따라 에어컨 자동 제어
        if (result.temperatureCategory === '추움' || result.predictedTemperature < 34.5) {
          // 추우면 에어컨 끄기 또는 온도 높이기
          if (status && status.power) {
            await IotService.setPower(false);
            await loadStatus();
          }
        } else if (result.temperatureCategory === '더움' || result.predictedTemperature > 35.6) {
          // 더우면 에어컨 켜기
          if (status && !status.power) {
            await IotService.setPower(true);
            await loadStatus();
          }
          // 목표 온도 조절 (예측 온도에 맞춰)
          const targetTemp = Math.max(16, Math.min(30, Math.round(result.predictedTemperature - 2)));
          if (status && status.targetTemperature !== targetTemp) {
            await IotService.setTargetTemperature(targetTemp);
            await loadStatus();
          }
        }
      }
    } catch (error) {
      console.error('자동 제어 실패:', error);
    }
  };

  const loadStatus = async () => {
    setLoading(true);
    setError(null);
    // 조회 시작 시 일단 오프라인으로 설정 (성공하면 온라인으로 변경)
    setIsOnline(false);
    
    try {
      console.log('IoT 상태 조회 중...');
      const result = await IotService.getStatus();
      console.log('IoT 상태 조회 결과:', result);
      
      // 응답이 유효한지 엄격하게 확인
      if (result && result.state && typeof result.state === 'object') {
        // 실제 데이터가 있는지 확인
        const hasValidData = result.currentTemperature != null || 
                             result.state.power != null ||
                             result.state.targetTemperature != null;
        
        if (hasValidData) {
          setStatus({
            currentTemperature: result.currentTemperature ?? 0,
            airQuality: result.airQuality ?? 0,
            power: result.state.power ?? false,
            targetTemperature: result.state.targetTemperature ?? 0,
            mode: result.state.mode ?? 'AUTO',
            fanSpeed: result.state.fanSpeed ?? 'AUTO',
          });
          setIsOnline(true); // 성공 시에만 온라인으로 설정
          setError(null); // 성공 시 에러 메시지 제거
          console.log('✅ IoT 상태 조회 성공 - 온라인으로 설정');
        } else {
          throw new Error('서버 응답에 유효한 데이터가 없습니다.');
        }
      } else {
        throw new Error('유효하지 않은 응답입니다.');
      }
    } catch (error: any) {
      console.error('❌ Failed to load status:', error);
      const errorMessage = error.message || '상태를 불러오는데 실패했습니다. 서버가 실행 중인지 확인해주세요.';
      setError(errorMessage);
      setIsOnline(false); // 에러 시 오프라인으로 설정
      console.log('❌ IoT 상태 조회 실패 - 오프라인으로 설정');
      // 오프라인 상태일 때는 기존 상태 유지 (null로 설정하지 않음)
    } finally {
      setLoading(false);
    }
  };

  const handlePowerToggle = async (power: boolean) => {
    setLoading(true);
    setError(null);
    try {
      console.log(`전원 ${power ? '켜기' : '끄기'} 요청...`);
      const result = await IotService.setPower(power);
      console.log('전원 제어 응답:', result);
      
      if (!result.success) {
        throw new Error(result.message || '전원 제어에 실패했습니다.');
      }
      
      // 상태 업데이트 (status가 없으면 기본값으로 생성)
      if (status) {
        setStatus({ ...status, power });
      } else {
        // 상태가 없으면 기본값으로 생성
        setStatus({
          currentTemperature: 25,
          airQuality: 0,
          power,
          targetTemperature: 24,
          mode: 'AUTO',
          fanSpeed: 'AUTO',
        });
      }
      
      // 서버에서 최신 상태 가져오기 (약간의 지연 후)
      setTimeout(async () => {
        await loadStatus();
      }, 500);
    } catch (error: any) {
      console.error('Failed to toggle power:', error);
      const errorMessage = error.message || '전원 제어에 실패했습니다. 서버가 실행 중인지 확인해주세요.';
      setError(errorMessage);
      // 에러 발생 시 상태 롤백
      if (status) {
        setStatus({ ...status, power: !power });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTemperatureChange = async (temperature: number) => {
    setLoading(true);
    try {
      await IotService.setTargetTemperature(temperature);
      setStatus(status ? { ...status, targetTemperature: temperature } : null);
    } catch (error) {
      console.error('Failed to set temperature:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleModeChange = async (mode: AirConditionerMode) => {
    setLoading(true);
    try {
      await IotService.setMode(mode);
      setStatus(status ? { ...status, mode } : null);
    } catch (error) {
      console.error('Failed to set mode:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFanSpeedChange = async (fanSpeed: FanSpeed) => {
    setLoading(true);
    try {
      await IotService.setFanSpeed(fanSpeed);
      setStatus(status ? { ...status, fanSpeed } : null);
    } catch (error) {
      console.error('Failed to set fan speed:', error);
    } finally {
      setLoading(false);
    }
  };

  const getModeText = (mode: AirConditionerMode) => {
    const modeMap: Record<AirConditionerMode, string> = {
      COOL: '냉방',
      AIR_DRY: '제습',
      AIR_CLEAN: '공기청정',
      AUTO: '자동',
    };
    return modeMap[mode] || mode;
  };

  const getFanSpeedText = (fanSpeed: FanSpeed) => {
    const fanSpeedMap: Record<FanSpeed, string> = {
      HIGH: '강',
      MID: '중',
      LOW: '약',
      AUTO: '자동',
    };
    return fanSpeedMap[fanSpeed] || fanSpeed;
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>IoT 제어</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">에어컨 제어</IonTitle>
          </IonToolbar>
        </IonHeader>

        <div className="container">
          {/* 에어컨 제어 카드 */}
          <IonCard className="air-conditioner-card">
            <IonCardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <IonCardTitle>에어컨</IonCardTitle>
                <IonText color={isOnline ? 'success' : 'danger'}>
                  {isOnline ? '온라인' : '오프라인'}
                </IonText>
              </div>
            </IonCardHeader>
            <IonCardContent>
              {/* 온도 표시 */}
              <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: '20px' }}>
                <div style={{ textAlign: 'center' }}>
                  <IonText color="primary">
                    <h3>현재 온도</h3>
                    <p style={{ fontSize: '24px', fontWeight: 'bold' }}>
                      {status?.currentTemperature != null 
                        ? (typeof status.currentTemperature === 'number' 
                            ? status.currentTemperature.toFixed(1) 
                            : status.currentTemperature)
                        : '21.0'}°C
                    </p>
                  </IonText>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <IonText color="warning">
                    <h3>설정 온도</h3>
                    <p style={{ fontSize: '24px', fontWeight: 'bold' }}>
                      {status?.targetTemperature != null 
                        ? (typeof status.targetTemperature === 'number' 
                            ? status.targetTemperature.toFixed(1) 
                            : status.targetTemperature)
                        : '30.0'}°C
                    </p>
                  </IonText>
                </div>
              </div>

              {/* 전원 켜기 버튼 */}
              <IonButton
                expand="block"
                color={status?.power ? 'success' : 'medium'}
                onClick={async () => {
                  const newPowerState = !status?.power;
                  console.log(`전원 버튼 클릭: ${newPowerState ? '켜기' : '끄기'}`);
                  await handlePowerToggle(newPowerState);
                }}
                disabled={loading}
                style={{ marginBottom: '16px' }}
              >
                {loading ? (
                  <IonSpinner name="crescent" />
                ) : status?.power ? (
                  '끄기'
                ) : (
                  '켜기'
                )}
              </IonButton>

              {/* 온도 조절 버튼 */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <IonButton
                  expand="block"
                  fill="outline"
                  onClick={() => {
                    if (status && status.targetTemperature > 16) {
                      handleTemperatureChange(status.targetTemperature - 1);
                    }
                  }}
                  disabled={loading || !status || !status.power || !isOnline}
                >
                  온도 ↓
                </IonButton>
                <IonButton
                  expand="block"
                  fill="outline"
                  onClick={() => {
                    if (status && status.targetTemperature < 30) {
                      handleTemperatureChange(status.targetTemperature + 1);
                    }
                  }}
                  disabled={loading || !status || !status.power || !isOnline}
                >
                  온도 ↑
                </IonButton>
              </div>

              {/* 모드 선택 */}
              <div style={{ marginBottom: '16px' }}>
                <IonLabel>
                  <h3>모드</h3>
                </IonLabel>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                  {(['COOL', 'AIR_DRY', 'AIR_CLEAN', 'AUTO'] as AirConditionerMode[]).map((mode) => (
                    <IonButton
                      key={mode}
                      size="small"
                      color={status?.mode === mode ? 'primary' : 'medium'}
                      onClick={() => handleModeChange(mode)}
                      disabled={loading || !status || !status.power || !isOnline}
                    >
                      {getModeText(mode)}
                    </IonButton>
                  ))}
                </div>
              </div>

              {/* 풍량 선택 */}
              <div style={{ marginBottom: '16px' }}>
                <IonLabel>
                  <h3>풍량</h3>
                </IonLabel>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                  {(['HIGH', 'MID', 'LOW', 'AUTO'] as FanSpeed[]).map((speed) => (
                    <IonButton
                      key={speed}
                      size="small"
                      color={status?.fanSpeed === speed ? 'primary' : 'medium'}
                      onClick={() => handleFanSpeedChange(speed)}
                      disabled={loading || !status || !status.power || !isOnline}
                    >
                      {getFanSpeedText(speed)}
                    </IonButton>
                  ))}
                </div>
              </div>

              {/* 새로고침 버튼 */}
              <IonButton
                expand="block"
                fill="outline"
                onClick={loadStatus}
                disabled={loading}
              >
                {loading ? <IonSpinner name="crescent" /> : '새로고침'}
              </IonButton>
            </IonCardContent>
          </IonCard>

          {/* IoT 기기 정보 카드 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>IOT 기기 정보</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonText>
                <p>연결된 IOT 기기의 상태와 정보를 확인할 수 있습니다.</p>
              </IonText>
              <ul style={{ marginTop: '16px', paddingLeft: '20px' }}>
                <li>에어컨: 현재 온도와 설정 온도 확인</li>
                <li>기타 기기: 온라인/오프라인 상태 확인</li>
              </ul>
            </IonCardContent>
          </IonCard>

          {/* 에러 메시지 */}
          {error && (
            <IonCard>
              <IonCardContent>
                <IonText color="danger">
                  <p>{error}</p>
                </IonText>
              </IonCardContent>
            </IonCard>
          )}

          {loading && (
            <div className="loading-container">
              <IonSpinner name="crescent" />
              <IonText>처리 중...</IonText>
            </div>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Tab4;
