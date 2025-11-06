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
import { IotService, AirConditionerMode, FanSpeed } from '../services';
import './Iot.css';

const Iot: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{
    currentTemperature: number;
    airQuality: number;
    power: boolean;
    targetTemperature: number;
    mode: AirConditionerMode;
    fanSpeed: FanSpeed;
  } | null>(null);

  useEffect(() => {
    loadStatus();
    // 주기적으로 상태 업데이트 (5초마다)
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
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
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const handlePowerToggle = async (power: boolean) => {
    setLoading(true);
    try {
      await IotService.setPower(power);
      setStatus(status ? { ...status, power } : null);
      await loadStatus();
    } catch (error) {
      console.error('Failed to toggle power:', error);
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
          {/* 현재 상태 */}
          {status && (
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
          )}

          {/* 전원 제어 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>전원</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonItem>
                <IonLabel>전원 {status?.power ? 'ON' : 'OFF'}</IonLabel>
                <IonToggle
                  checked={status?.power || false}
                  onIonChange={(e) => handlePowerToggle(e.detail.checked)}
                  disabled={loading}
                />
              </IonItem>
            </IonCardContent>
          </IonCard>

          {/* 목표 온도 */}
          {status && status.power && (
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
                <IonRange
                  min={16}
                  max={30}
                  step={1}
                  value={status.targetTemperature}
                  onIonChange={(e) =>
                    handleTemperatureChange(Number(e.detail.value))
                  }
                  disabled={loading}
                >
                  <IonLabel slot="start">16°C</IonLabel>
                  <IonLabel slot="end">30°C</IonLabel>
                </IonRange>
              </IonCardContent>
            </IonCard>
          )}

          {/* 작동 모드 */}
          {status && status.power && (
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>작동 모드</IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <IonItem>
                  <IonLabel position="stacked">모드 선택</IonLabel>
                  <IonSelect
                    value={status.mode}
                    onIonChange={(e) =>
                      handleModeChange(e.detail.value as AirConditionerMode)
                    }
                    disabled={loading}
                  >
                    <IonSelectOption value="COOL">냉방</IonSelectOption>
                    <IonSelectOption value="AIR_DRY">제습</IonSelectOption>
                    <IonSelectOption value="AIR_CLEAN">공기청정</IonSelectOption>
                    <IonSelectOption value="AUTO">자동</IonSelectOption>
                  </IonSelect>
                </IonItem>
              </IonCardContent>
            </IonCard>
          )}

          {/* 풍량 조절 */}
          {status && status.power && (
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>풍량</IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <IonItem>
                  <IonLabel position="stacked">풍량 선택</IonLabel>
                  <IonSelect
                    value={status.fanSpeed}
                    onIonChange={(e) =>
                      handleFanSpeedChange(e.detail.value as FanSpeed)
                    }
                    disabled={loading}
                  >
                    <IonSelectOption value="HIGH">강</IonSelectOption>
                    <IonSelectOption value="MID">중</IonSelectOption>
                    <IonSelectOption value="LOW">약</IonSelectOption>
                    <IonSelectOption value="AUTO">자동</IonSelectOption>
                  </IonSelect>
                </IonItem>
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

