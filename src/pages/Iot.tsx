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
  IonIcon,
  IonButtons,
} from '@ionic/react';
import { refreshOutline } from 'ionicons/icons';
import { useHistory } from 'react-router-dom';
import { IotService, AirConditionerMode, FanSpeed, getIotServiceBaseUrl } from '../services';
import { autoDetectServerUrl } from '../services/ServerConfig';
import { isAuthenticated, getIotDeviceStatus, getAuthHeaders } from '../services/AuthService';
import './Iot.css';

const Iot: React.FC = () => {
  const history = useHistory();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 기본 상태 설정 - 서버 연결 실패 시에도 UI가 보이도록
  const [status, setStatus] = useState<{
    currentTemperature: number;
    power: boolean;
    targetTemperature: number;
    mode: AirConditionerMode;
    fanSpeed: FanSpeed;
  }>({
    currentTemperature: 0,
    power: false,
    targetTemperature: 24,
    mode: 'AUTO',
    fanSpeed: 'AUTO',
  });
  
  // 온도 범위 상태 (현재 사용 중인 값)
  const [temperatureRange, setTemperatureRange] = useState<{ min: number | null; max: number | null }>({
    min: null,
    max: null,
  });
  
  // 캐시 여부 상태
  const [isCachedRange, setIsCachedRange] = useState<boolean>(false);
  
  // 자동 조절 범위 여부 상태
  const [isAutoRange, setIsAutoRange] = useState<boolean>(false);
  
  // 원래 설정된 온도 범위 상태
  const [originalTemperatureRange, setOriginalTemperatureRange] = useState<{ min: number | null; max: number | null }>({
    min: null,
    max: null,
  });
  
  // 온도 임계값 설정 팝업 관련 상태
  const [showThresholdAlert, setShowThresholdAlert] = useState(false);
  const [pendingTemperature, setPendingTemperature] = useState<number | null>(null);
  
  // 로그인 관련 상태
  const [showLoginAlert, setShowLoginAlert] = useState(false);

  const loadStatus = useCallback(async () => {
    setError(null);
    try {
      // 먼저 로그인 상태 확인
      const authenticated = isAuthenticated();
      console.log(`🔍 IoT 페이지 - 로그인 상태 확인: ${authenticated}`);
      
      if (!authenticated) {
        console.log('❌ IoT 페이지 - 로그인되지 않음');
        setError('로그인이 필요합니다. 먼저 로그인해주세요.');
        return;
      }

      // 사용자 정보 확인 (디버깅용)
      try {
        const { getCurrentUser } = await import('../services/AuthService');
        const user = await getCurrentUser();
        console.log(`✅ IoT 페이지 - 사용자 정보 확인: user_id=${user.id}, user_no=${user.user_no}`);
      } catch (userError: any) {
        console.error('❌ IoT 페이지 - 사용자 정보 가져오기 실패:', userError);
        console.error('❌ 에러 상세:', userError.message, userError.stack);
        setError('로그인 정보를 확인할 수 없습니다. 다시 로그인해주세요.');
        return;
      }

      const result = await IotService.getStatus();
      setStatus({
        currentTemperature: result.currentTemperature,
        power: result.state.power,
        targetTemperature: result.state.targetTemperature,
        mode: result.state.mode,
        fanSpeed: result.state.fanSpeed,
      });
      
      // 온도 범위도 함께 조회
      try {
        // IotService의 baseUrl 가져오기
        const baseUrl = getIotServiceBaseUrl();
        console.log('🌡️ 온도 범위 조회 시작:', `${baseUrl}/temperature-range`);
        const rangeResponse = await fetch(`${baseUrl}/temperature-range`, {
          headers: getAuthHeaders()
        });
        console.log('🌡️ 온도 범위 응답 상태:', rangeResponse.status);
        
        if (rangeResponse.ok) {
          const rangeData = await rangeResponse.json();
          console.log('🌡️ 온도 범위 데이터:', rangeData);
          
          if (rangeData.success && rangeData.min_temp != null && rangeData.max_temp != null) {
            console.log('✅ 온도 범위 설정:', rangeData.min_temp, '~', rangeData.max_temp);
            setTemperatureRange({
              min: rangeData.min_temp,
              max: rangeData.max_temp,
            });
            
            // 캐시 여부 저장 (수동 조절 캐시)
            setIsCachedRange(rangeData.is_cached === true);
            
            // 자동 조절 범위 여부 저장 (수동 조절 캐시가 없고 DB에도 없을 때)
            setIsAutoRange(rangeData.is_auto === true);
            
            // 원래 설정된 온도 범위도 저장
            if (rangeData.original_min_temp != null && rangeData.original_max_temp != null) {
              setOriginalTemperatureRange({
                min: rangeData.original_min_temp,
                max: rangeData.original_max_temp,
              });
            }
          } else {
            console.warn('⚠️ 온도 범위 데이터가 없거나 유효하지 않음:', rangeData);
          }
        } else {
          const errorText = await rangeResponse.text();
          console.error('❌ 온도 범위 조회 실패:', rangeResponse.status, errorText);
        }
      } catch (e) {
        console.error('❌ 온도 범위 조회 중 오류:', e);
      }
    } catch (error: any) {
      console.error('Failed to load status:', error);
      const errorMessage = error.message || '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.';
      setError(errorMessage);
      
      // 등록되지 않았거나 404 에러인 경우 에러 메시지만 표시
      if (errorMessage.includes('등록된 디바이스가 없습니다') || errorMessage.includes('404')) {
        console.log('⚠️ 등록된 디바이스가 없습니다. User 페이지에서 IoT 재등록을 진행해주세요.');
        setError('등록된 디바이스가 없습니다. User 페이지에서 IoT 재등록을 진행해주세요.');
        return;
      }
      
      // 연결 실패 시 자동 감지 재시도
      if (errorMessage.includes('서버') || errorMessage.includes('timeout') || errorMessage.includes('연결')) {
        console.log('🔄 연결 실패 - 서버 URL 자동 감지 재시도...');
        try {
          const serverUrl = await autoDetectServerUrl();
          if (!serverUrl || serverUrl === '') {
            throw new Error('서버 URL 자동 감지 실패: 빈 URL 반환');
          }
          console.log('✅ 자동 감지된 서버 URL:', serverUrl);
          IotService.updateBaseUrl(serverUrl);
          // 재시도
          setTimeout(() => {
            loadStatus();
          }, 1000);
        } catch (detectError: any) {
          console.error('❌ 서버 URL 자동 감지 실패:', detectError);
          setError(detectError.message || '서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
      }
    }
  }, []);

  useEffect(() => {
    // 로그인 상태 확인 함수
    const checkLoginAndRegistration = async () => {
      console.log('🔍 IoT 페이지 - 로그인 상태 확인 시작');
      
      if (!isAuthenticated()) {
        console.log('❌ IoT 페이지 - 로그인되지 않음');
        // 로그인하지 않았으면 안내창 표시
        setShowLoginAlert(true);
        return;
      }

      console.log('✅ IoT 페이지 - 로그인됨, 사용자 정보 확인 중...');
      
      // 사용자 정보 확인
      try {
        const { getCurrentUser } = await import('../services/AuthService');
        const user = await getCurrentUser();
        console.log(`✅ IoT 페이지 - 사용자 정보 확인: user_id=${user.id}, user_no=${user.user_no}`);
      } catch (userError) {
        console.error('❌ IoT 페이지 - 사용자 정보 가져오기 실패:', userError);
        setShowLoginAlert(true);
        return;
      }

      // 로그인했으면 IoT 등록 정보 확인
      try {
        console.log('🔍 IoT 페이지 - IoT 등록 정보 확인 중...');
        const iotStatus = await getIotDeviceStatus();
        console.log('📋 IoT 페이지 - IoT 등록 정보:', iotStatus);
        
        if (iotStatus.success && iotStatus.registered) {
          // IoT 등록 정보가 있으면 localStorage에 저장
          localStorage.setItem('thinq_device_id', iotStatus.deviceId || '');
          localStorage.setItem('thinq_device_name', iotStatus.deviceName || '');
          localStorage.setItem('iot_device_registered', 'true');
          console.log('✅ IoT 페이지 - IoT 등록 정보 저장 완료');
        } else {
          // 등록되지 않았으면 등록 페이지로 리다이렉트하지 않고 그냥 진행
          // (등록 화면은 User 페이지에서 IoT 재등록 버튼으로 접근)
          localStorage.removeItem('iot_device_registered');
          console.log('⚠️ IoT 페이지 - IoT 등록 정보 없음');
        }
      } catch (error) {
        console.error('❌ IoT 페이지 - IoT 등록 정보 확인 실패:', error);
      }
    };

    // Alert가 닫혔을 때만 체크 (Alert가 열려있으면 체크하지 않음)
    if (!showLoginAlert) {
      checkLoginAndRegistration();
    }

    // 로그인 상태 변경 이벤트 리스너 (다른 페이지에서 로그인/로그아웃 시 동기화)
    const handleAuthStateChanged = (event: CustomEvent) => {
      const authenticated = event.detail?.authenticated ?? isAuthenticated();
      console.log(`🔍 IoT 페이지 - 로그인 상태 변경 이벤트: ${authenticated}`);
      if (authenticated) {
        setShowLoginAlert(false);
        // 로그인되었으면 다시 확인
        checkLoginAndRegistration();
        setTimeout(() => {
          if (isAuthenticated()) {
            loadStatus();
          }
        }, 500);
      } else {
        setShowLoginAlert(true);
      }
    };
    
    // localStorage storage 이벤트 리스너 (다른 탭에서 로그인/로그아웃 시 동기화)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth_token') {
        const authenticated = isAuthenticated();
        console.log(`🔍 IoT 페이지 - localStorage 변경 감지, 로그인 상태: ${authenticated}`);
        if (authenticated) {
          setShowLoginAlert(false);
          checkLoginAndRegistration();
          setTimeout(() => {
            if (isAuthenticated()) {
              loadStatus();
            }
          }, 500);
        } else {
          setShowLoginAlert(true);
        }
      }
    };
    
    window.addEventListener('authStateChanged', handleAuthStateChanged as EventListener);
    window.addEventListener('storage', handleStorageChange);

    // UI를 먼저 렌더링하고, 그 다음에 상태 조회
    // 자동 감지는 연결 실패 시에만 실행
    setTimeout(() => {
      if (isAuthenticated()) {
        loadStatus();
      }
    }, 500);
    
    // cleanup 함수
    return () => {
      window.removeEventListener('authStateChanged', handleAuthStateChanged as EventListener);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [loadStatus, history, showLoginAlert]);

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
      <IonContent fullscreen className="ion-padding iot-page">
        {/* 별 배경 효과 (다크모드) */}
        <div className="stars-background"></div>

        <div className="container" style={{ display: 'block', visibility: 'visible', opacity: 1 }}>
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

          {/* 현재 상태 - 큰 온도 숫자 중심, 정보 카드 분리 */}
          <div className="status-section">
            <div className="status-main-card">
              <div className="status-temperature-display">
                <div className="status-label">현재 온도</div>
                <div className="status-temperature-value-wrapper">
                  <div className="status-temperature-value">{status.currentTemperature}</div>
                  <div className="status-temperature-unit">°C</div>
                </div>
                {status.power && status.targetTemperature > 0 && (
                  <div className="status-target-info">
                    <span className="status-target-label">목표</span>
                    <span className="status-target-value">{status.targetTemperature}°C</span>
                    {Math.abs(status.currentTemperature - status.targetTemperature) > 0.5 && (
                      <span className="status-temperature-diff">
                        {status.currentTemperature > status.targetTemperature ? '↑' : '↓'} {Math.abs(status.currentTemperature - status.targetTemperature).toFixed(1)}°C
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
            {/* 온도범위 표시 */}
            {temperatureRange.min !== null && temperatureRange.max !== null && (
              <div className="temperature-range-section">
                <div className="temperature-range-card">
                  <div className="temperature-range-label">
                    {isCachedRange ? '수동 온도 범위' : isAutoRange ? '자동 온도 범위' : '온도 범위'}
                  </div>
                  <div className="temperature-range-values">
                    <span className="temperature-range-number">{temperatureRange.min?.toFixed(1)}</span>
                    <span className="temperature-range-unit">°C</span>
                    <span className="temperature-range-separator">~</span>
                    <span className="temperature-range-number">{temperatureRange.max?.toFixed(1)}</span>
                    <span className="temperature-range-unit">°C</span>
                  </div>
                  {originalTemperatureRange.min !== null && originalTemperatureRange.max !== null && 
                   (originalTemperatureRange.min !== temperatureRange.min || originalTemperatureRange.max !== temperatureRange.max) && (
                    <div className="temperature-range-original">
                      원래 설정: {originalTemperatureRange.min.toFixed(1)}°C ~ {originalTemperatureRange.max.toFixed(1)}°C
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 전원 제어 - 헤더 없이 버튼 중심 */}
          <div className="power-section">
            <IonButton
              expand="block"
              color={status.power ? 'danger' : 'success'}
              onClick={() => handlePowerToggle(!status.power)}
              disabled={loading}
              className="power-main-button"
            >
              {status.power ? '전원 끄기' : '전원 켜기'}
            </IonButton>
            <IonButton
              expand="block"
              fill="outline"
              onClick={loadStatus}
              disabled={loading}
              className="power-refresh-button"
            >
              상태 새로고침
            </IonButton>
          </div>

          {/* 목표 온도 - 큰 온도 숫자, 버튼 그리드 */}
          {status.power && (
          <IonCard className="temperature-card">
            <IonCardHeader>
              <IonCardTitle>목표 온도</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <div className="temperature-display-section">
                <div className="temperature-value-large">
                  {pendingTemperature !== null ? pendingTemperature : status.targetTemperature}°C
                </div>
                {pendingTemperature !== null && pendingTemperature !== status.targetTemperature && (
                  <div className="temperature-pending">선택된 온도: {pendingTemperature}°C</div>
                )}
              </div>
              <div className="temperature-controls">
                <div className="temperature-adjust-buttons">
                  <IonButton
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
                <div className="temperature-preset-buttons">
                  <IonButton
                    fill="outline"
                    onClick={() => handleTemperatureChange(18)}
                    disabled={loading}
                  >
                    18°C
                  </IonButton>
                  <IonButton
                    fill="outline"
                    onClick={() => handleTemperatureChange(22)}
                    disabled={loading}
                  >
                    22°C
                  </IonButton>
                  <IonButton
                    fill="outline"
                    onClick={() => handleTemperatureChange(26)}
                    disabled={loading}
                  >
                    26°C
                  </IonButton>
                </div>
                <IonButton
                  expand="block"
                  color="primary"
                  className="temperature-confirm-button"
                  onClick={handleConfirmTemperature}
                  disabled={loading}
                >
                  확인 ({(pendingTemperature !== null ? pendingTemperature : status.targetTemperature)}°C)
                </IonButton>
              </div>
            </IonCardContent>
          </IonCard>
          )}

          {/* 작동 모드 - 2x2 그리드 */}
          {status.power && (
          <IonCard className="mode-card">
            <IonCardHeader>
              <IonCardTitle>작동 모드</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <div className="mode-grid">
                <IonButton
                  color={status.mode === 'COOL' ? 'primary' : 'medium'}
                  onClick={() => handleModeChange('COOL')}
                  disabled={loading}
                  className="mode-button"
                >
                  냉방
                </IonButton>
                <IonButton
                  color={status.mode === 'AIR_DRY' ? 'primary' : 'medium'}
                  onClick={() => handleModeChange('AIR_DRY')}
                  disabled={loading}
                  className="mode-button"
                >
                  제습
                </IonButton>
                <IonButton
                  color={status.mode === 'AIR_CLEAN' ? 'primary' : 'medium'}
                  onClick={() => handleModeChange('AIR_CLEAN')}
                  disabled={loading}
                  className="mode-button"
                >
                  공기청정
                </IonButton>
                <IonButton
                  color={status.mode === 'AUTO' ? 'primary' : 'medium'}
                  onClick={() => handleModeChange('AUTO')}
                  disabled={loading}
                  className="mode-button"
                >
                  자동
                </IonButton>
              </div>
            </IonCardContent>
          </IonCard>
          )}

          {/* 풍량 조절 - 가로 배치 */}
          {status.power && (
          <IonCard className="fan-card">
            <IonCardHeader>
              <IonCardTitle>풍량</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <div className="fan-row">
                <IonButton
                  color={status.fanSpeed === 'HIGH' ? 'primary' : 'medium'}
                  onClick={() => handleFanSpeedChange('HIGH')}
                  disabled={loading}
                  className="fan-button"
                >
                  강
                </IonButton>
                <IonButton
                  color={status.fanSpeed === 'MID' ? 'primary' : 'medium'}
                  onClick={() => handleFanSpeedChange('MID')}
                  disabled={loading}
                  className="fan-button"
                >
                  중
                </IonButton>
                <IonButton
                  color={status.fanSpeed === 'LOW' ? 'primary' : 'medium'}
                  onClick={() => handleFanSpeedChange('LOW')}
                  disabled={loading}
                  className="fan-button"
                >
                  약
                </IonButton>
                <IonButton
                  color={status.fanSpeed === 'AUTO' ? 'primary' : 'medium'}
                  onClick={() => handleFanSpeedChange('AUTO')}
                  disabled={loading}
                  className="fan-button"
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
          subHeader={
            pendingTemperature !== null
              ? `오늘밤 온도 범위: ${pendingTemperature - 1}도 ~ ${pendingTemperature + 1}도`
              : `오늘밤 온도 범위: ${status.targetTemperature - 1}도 ~ ${status.targetTemperature + 1}도`
          }
          message="오늘 하루는 현재 설정하신 온도로 진행할까요?"
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
        {/* 로그인 안내 Alert */}
        <IonAlert
          isOpen={showLoginAlert}
          backdropDismiss={false}
          header="로그인 필요"
          message="IoT 기기를 사용하려면 로그인이 필요합니다. Health 페이지에서 로그인해주세요."
          buttons={[
            {
              text: '확인',
              handler: () => {
                setShowLoginAlert(false);
                // Health 페이지로 이동하고 로그인 모달을 열기 위해 state 전달
                history.push('/health_ios?showLogin=true');
              }
            }
          ]}
        />
    </IonPage>
  );
};

export default Iot;


