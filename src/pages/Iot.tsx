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

  const handleTemperatureChange = async (temperature: number) => {
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
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>IoT 제어</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader>
          <IonToolbar>
            <IonTitle size="large">에어컨 제어</IonTitle>
          </IonToolbar>
        </IonHeader>

        <div className="container">
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
                    <h2>{status.targetTemperature}°C</h2>
                  </IonLabel>
                </IonItem>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => {
                      if (status.targetTemperature > 16) {
                        handleTemperatureChange(status.targetTemperature - 1);
                      }
                    }}
                    disabled={loading || status.targetTemperature <= 16}
                  >
                    -1°C
                  </IonButton>
                  <IonButton
                    expand="block"
                    fill="outline"
                    onClick={() => {
                      if (status.targetTemperature < 30) {
                        handleTemperatureChange(status.targetTemperature + 1);
                      }
                    }}
                    disabled={loading || status.targetTemperature >= 30}
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
      </IonContent>
    </IonPage>
  );
};

export default Iot;

