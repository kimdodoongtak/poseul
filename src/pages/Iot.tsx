import { useState, useEffect, useCallback } from 'react';
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
  IonButton,
  IonSpinner,
  IonText,
  IonAlert,
} from '@ionic/react';
import { IotService, AirConditionerMode, FanSpeed } from '../services';
import './Iot.css';

const Iot: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 기본 상태 설정 - 서버 연결 실패 시에도 UI가 보이도록
  const [status, setStatus] = useState<{
    currentTemperature: number;
    airQuality: number;
    power: boolean;
    targetTemperature: number;
    mode: AirConditionerMode;
    fanSpeed: FanSpeed;
  }>({
    currentTemperature: 0,
    airQuality: 0,
    power: false,
    targetTemperature: 24,
    mode: 'AUTO',
    fanSpeed: 'AUTO',
  });
  
  // 온도 임계값 설정 팝업 관련 상태
  const [showThresholdAlert, setShowThresholdAlert] = useState(false);
  const [pendingTemperature, setPendingTemperature] = useState<number | null>(null);

  const loadStatus = useCallback(async () => {
    setError(null);
    try {
      const result = await IotService.getStatus();
      setStatus({
        currentTemperature: result.currentTemperature,
        airQuality: result.airQuality,
        power: result.state.power,
        targetTemperature: result.state.targetTemperature,
        mode: result.state.mode,
        fanSpeed: result.state.fanSpeed,
      });
    } catch (error: any) {
      console.error('Failed to load status:', error);
      setError(error.message || '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
    }
  }, []);

  useEffect(() => {
    // UI가 먼저 렌더링되도록 지연 후 상태 조회
    const timeoutId = setTimeout(() => {
      loadStatus();
    }, 500); // 500ms 지연
    
    return () => {
      clearTimeout(timeoutId);
    };
  }, [loadStatus]);

  const handlePowerToggle = async (power: boolean) => {
    setLoading(true);
    setError(null);
    try {
      await IotService.setPower(power);
      setStatus({ ...status, power });
      await loadStatus();
    } catch (error: any) {
      console.error('Failed to toggle power:', error);
      setError(error.message || '전원 제어에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleTemperatureChange = (temperature: number) => {
    // 전원이 켜져있으면 임시로 온도만 선택 (확인 버튼을 눌러야 적용)
    if (status.power) {
      console.log('온도 선택:', temperature, '현재 온도:', status.targetTemperature);
      setPendingTemperature(temperature);
    } else {
      // 전원이 꺼져있으면 바로 설정
      applyTemperatureChange(temperature);
    }
  };

  const handleConfirmTemperature = () => {
    // 확인 버튼을 누르면 팝업 표시
    // pendingTemperature가 null이면 현재 온도를 사용
    const targetTemp = pendingTemperature !== null ? pendingTemperature : status.targetTemperature;
    if (status.power) {
      // pendingTemperature를 설정하고 팝업 표시
      setPendingTemperature(targetTemp);
      setShowThresholdAlert(true);
    }
  };

  const applyTemperatureChange = async (temperature: number) => {
    setLoading(true);
    setError(null);
    try {
      await IotService.setTargetTemperature(temperature);
      setStatus({ ...status, targetTemperature: temperature });
    } catch (error: any) {
      console.error('Failed to set temperature:', error);
      setError(error.message || '온도 설정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleThresholdConfirm = async () => {
    // pendingTemperature가 null이면 현재 온도를 사용
    const targetTemp = pendingTemperature !== null ? pendingTemperature : status.targetTemperature;
    
    setLoading(true);
    setError(null);
    try {
      // 먼저 온도 설정
      await IotService.setTargetTemperature(targetTemp);
      setStatus({ ...status, targetTemperature: targetTemp });
      
      // 임계값 저장
      const result = await IotService.saveTemperatureThreshold(targetTemp);
      if (result.success) {
        console.log('✅ 온도 임계값 저장 성공');
      } else {
        console.warn('⚠️ 온도 임계값 저장 실패:', result.message);
        // 임계값 저장 실패해도 온도는 설정되었으므로 에러는 표시하지 않음
      }
    } catch (error: any) {
      console.error('Failed to set temperature and save threshold:', error);
      setError(error.message || '온도 설정에 실패했습니다.');
    } finally {
      setLoading(false);
      setShowThresholdAlert(false);
      setPendingTemperature(null);
    }
  };

  const handleThresholdCancel = () => {
    // 팝업 취소 시 온도는 설정하지 않음
    setShowThresholdAlert(false);
    setPendingTemperature(null);
  };

  const handleModeChange = async (mode: AirConditionerMode) => {
    setLoading(true);
    setError(null);
    try {
      await IotService.setMode(mode);
      setStatus({ ...status, mode });
    } catch (error: any) {
      console.error('Failed to set mode:', error);
      setError(error.message || '모드 설정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleFanSpeedChange = async (fanSpeed: FanSpeed) => {
    setLoading(true);
    setError(null);
    try {
      await IotService.setFanSpeed(fanSpeed);
      setStatus({ ...status, fanSpeed });
    } catch (error: any) {
      console.error('Failed to set fan speed:', error);
      setError(error.message || '풍량 설정에 실패했습니다.');
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
    <IonPage className="iot-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>IoT 제어</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>

        <div className="container" style={{ padding: '16px', display: 'block', visibility: 'visible', opacity: 1 }}>
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

          {/* 현재 상태 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>현재 상태</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonItem>
                <IonLabel>
                  <h2>현재 온도</h2>
                  <p>{status.currentTemperature}°C</p>
                </IonLabel>
              </IonItem>
              <IonItem>
                <IonLabel>
                  <h2>공기질</h2>
                  <p>{status.airQuality}</p>
                </IonLabel>
              </IonItem>
            </IonCardContent>
          </IonCard>

          {/* 전원 제어 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>전원</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonButton
                expand="block"
                color={status.power ? 'danger' : 'success'}
                onClick={() => handlePowerToggle(!status.power)}
                disabled={loading}
              >
                {status.power ? '전원 끄기' : '전원 켜기'}
              </IonButton>
              <IonButton
                expand="block"
                fill="outline"
                onClick={loadStatus}
                disabled={loading}
                style={{ marginTop: '10px' }}
              >
                상태 새로고침
              </IonButton>
            </IonCardContent>
          </IonCard>

          {/* 목표 온도 */}
          {status.power && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>목표 온도</IonCardTitle>
            </IonCardHeader>
              <IonCardContent>
                <IonItem>
                  <IonLabel>
                    <h2>{pendingTemperature !== null ? pendingTemperature : status.targetTemperature}°C</h2>
                    {pendingTemperature !== null && pendingTemperature !== status.targetTemperature && (
                      <p style={{ color: '#666', fontSize: '14px' }}>선택된 온도: {pendingTemperature}°C</p>
                    )}
                  </IonLabel>
                </IonItem>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => {
                      const currentTemp = pendingTemperature !== null ? pendingTemperature : status.targetTemperature;
                      if (currentTemp > 16) {
                        handleTemperatureChange(currentTemp - 1);
                      }
                    }}
                    disabled={loading || (pendingTemperature !== null ? pendingTemperature : status.targetTemperature) <= 16}
                  >
                    -1°C
                  </IonButton>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => {
                      const currentTemp = pendingTemperature !== null ? pendingTemperature : status.targetTemperature;
                      if (currentTemp < 30) {
                        handleTemperatureChange(currentTemp + 1);
                      }
                    }}
                    disabled={loading || (pendingTemperature !== null ? pendingTemperature : status.targetTemperature) >= 30}
                  >
                    +1°C
                  </IonButton>
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => handleTemperatureChange(18)}
                    disabled={loading}
                  >
                    18°C
                  </IonButton>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => handleTemperatureChange(22)}
                    disabled={loading}
                  >
                    22°C
                  </IonButton>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => handleTemperatureChange(26)}
                    disabled={loading}
                  >
                    26°C
                  </IonButton>
                </div>
                
                {/* 확인 버튼 - 온도 조절 버튼들 바로 아래 */}
                <IonButton
                  expand="block"
                  color="primary"
                  onClick={handleConfirmTemperature}
                  disabled={loading}
                  style={{ 
                    marginTop: '20px', 
                    width: '100%',
                    height: '48px',
                    fontSize: '16px',
                    fontWeight: 'bold'
                  }}
                >
                  확인 ({(pendingTemperature !== null ? pendingTemperature : status.targetTemperature)}°C)
                </IonButton>
              </IonCardContent>
            </IonCard>
          )}

          {/* 작동 모드 */}
          {status.power && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>작동 모드</IonCardTitle>
            </IonCardHeader>
              <IonCardContent>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <IonButton
                    expand="block"
                    color={status.mode === 'COOL' ? 'primary' : 'medium'}
                    onClick={() => handleModeChange('COOL')}
                    disabled={loading}
                  >
                    냉방
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.mode === 'AIR_DRY' ? 'primary' : 'medium'}
                    onClick={() => handleModeChange('AIR_DRY')}
                    disabled={loading}
                  >
                    제습
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.mode === 'AIR_CLEAN' ? 'primary' : 'medium'}
                    onClick={() => handleModeChange('AIR_CLEAN')}
                    disabled={loading}
                  >
                    공기청정
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.mode === 'AUTO' ? 'primary' : 'medium'}
                    onClick={() => handleModeChange('AUTO')}
                    disabled={loading}
                  >
                    자동
                  </IonButton>
                </div>
              </IonCardContent>
            </IonCard>
          )}

          {/* 풍량 조절 */}
          {status.power && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>풍량</IonCardTitle>
            </IonCardHeader>
              <IonCardContent>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <IonButton
                    expand="block"
                    color={status.fanSpeed === 'HIGH' ? 'primary' : 'medium'}
                    onClick={() => handleFanSpeedChange('HIGH')}
                    disabled={loading}
                  >
                    강
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.fanSpeed === 'MID' ? 'primary' : 'medium'}
                    onClick={() => handleFanSpeedChange('MID')}
                    disabled={loading}
                  >
                    중
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.fanSpeed === 'LOW' ? 'primary' : 'medium'}
                    onClick={() => handleFanSpeedChange('LOW')}
                    disabled={loading}
                  >
                    약
                  </IonButton>
                  <IonButton
                    expand="block"
                    color={status.fanSpeed === 'AUTO' ? 'primary' : 'medium'}
                    onClick={() => handleFanSpeedChange('AUTO')}
                    disabled={loading}
                  >
                    자동
                  </IonButton>
                </div>
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

        {/* 온도 임계값 설정 팝업 */}
        <IonAlert
          isOpen={showThresholdAlert}
          onDidDismiss={handleThresholdCancel}
          header="온도 범위 설정"
          message={
            pendingTemperature !== null
              ? `오늘 하루는 현재 설정하신 온도로 진행할까요?\n\n오늘 임계값: ${pendingTemperature - 1}도 ~ ${pendingTemperature + 1}도`
              : `오늘 하루는 현재 설정하신 온도로 진행할까요?\n\n오늘 임계값: ${status.targetTemperature - 1}도 ~ ${status.targetTemperature + 1}도`
          }
          buttons={[
            {
              text: '취소',
              role: 'cancel',
              handler: handleThresholdCancel,
            },
            {
              text: '예',
              handler: handleThresholdConfirm,
            },
          ]}
        />
      </IonContent>
    </IonPage>
  );
};

export default Iot;

