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
  IonInput,
  IonButton,
  IonText,
  IonSpinner,
  IonIcon,
} from '@ionic/react';
import { openOutline, checkmarkCircleOutline } from 'ionicons/icons';
import { useHistory } from 'react-router-dom';
import { getServerUrl, autoDetectServerUrl } from '../services/ServerConfig';
import './DeviceRegistration.css';

const DeviceRegistration: React.FC = () => {
  const [patToken, setPatToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('등록 중...');
  const [error, setError] = useState<string | null>(null);
  const [isValid, setIsValid] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string>(getServerUrl());
  const [detectingServer, setDetectingServer] = useState(false);
  const [showManualInput, setShowManualInput] = useState(false);
  const [manualServerUrl, setManualServerUrl] = useState('');
  const history = useHistory();

  // 컴포넌트 마운트 시 서버 URL 자동 감지
  useEffect(() => {
    const detectServer = async () => {
      const currentUrl = getServerUrl();
      console.log('🔍 현재 서버 URL:', currentUrl);
      
      // 항상 자동 감지 실행 (IP가 바뀔 수 있으므로)
      console.log('🔄 서버 URL 자동 감지 시작...');
      setDetectingServer(true);
      
      try {
        const detectedUrl = await autoDetectServerUrl();
        console.log('✅ 자동 감지된 서버 URL:', detectedUrl);
        
        // 빈 문자열이 반환되면 서버를 찾지 못한 것
        if (!detectedUrl || detectedUrl === '') {
          console.error('❌ 서버를 찾을 수 없습니다. 수동 입력이 필요합니다.');
          setConnectionStatus('❌ 서버를 자동으로 찾을 수 없습니다. 서버 IP를 확인해주세요.');
          // 기본값 유지
          setServerUrl(currentUrl);
        } else {
          setServerUrl(detectedUrl);
          setConnectionStatus(null); // 성공 시 상태 초기화
          console.log('✅ 서버 URL 업데이트 완료:', detectedUrl);
        }
      } catch (err) {
        console.error('❌ 서버 URL 자동 감지 실패:', err);
        setConnectionStatus('❌ 서버 자동 감지 중 오류가 발생했습니다.');
        // 실패해도 현재 URL 유지
        setServerUrl(currentUrl);
      } finally {
        setDetectingServer(false);
      }
    };

    // 약간의 지연 후 실행 (컴포넌트가 완전히 마운트된 후)
    const timer = setTimeout(() => {
      detectServer();
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  const handlePatTokenChange = (value: string) => {
    setPatToken(value);
    setError(null);
    // PAT 토큰 형식 검증 (thinqpat_로 시작하고 최소 길이 체크)
    const trimmed = value.trim();
    const valid = trimmed.startsWith('thinqpat_') && trimmed.length > 20;
    setIsValid(valid);
    console.log('PAT 토큰 검증:', { 
      trimmed: trimmed.substring(0, 20) + '...', 
      length: trimmed.length, 
      startsWith: trimmed.startsWith('thinqpat_'),
      isValid: valid 
    });
  };

  const handleOpenPatSite = () => {
    window.open('https://connect-pat.lgthinq.com', '_blank');
  };

  const handleTestConnection = async () => {
    if (!isValid) {
      setError('올바른 PAT 토큰 형식이 아닙니다.');
      return;
    }

    setTestingConnection(true);
    setError(null);
    setConnectionStatus(null);

    try {
      const baseUrl = serverUrl || getServerUrl();
      const requestStartTime = Date.now();
      console.log('🧪 PAT 토큰 연결 테스트 시작:', {
        baseUrl,
        patToken: patToken.trim().substring(0, 20) + '...',
        fullUrl: `${baseUrl}/iot/test-pat-token`,
        timestamp: new Date().toISOString()
      });

      // 먼저 서버 연결 확인
      console.log('🔍 서버 연결 확인 중...');
      try {
        const healthResponse = await fetch(`${baseUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(3000) // 3초
        });
        if (healthResponse.ok) {
          console.log('✅ 서버 연결 확인 성공');
        } else {
          console.warn('⚠️ 서버 응답 이상:', healthResponse.status);
        }
      } catch (healthError: any) {
        console.error('❌ 서버 연결 실패:', healthError);
        setConnectionStatus(`❌ 서버에 연결할 수 없습니다. 서버 URL: ${baseUrl}`);
        setTestingConnection(false);
        return;
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
        console.error(`⏱️ PAT 토큰 테스트 타임아웃 (${elapsed}초 경과)`);
        controller.abort();
      }, 10000); // 테스트는 10초

      console.log('📤 PAT 토큰 테스트 요청 전송:', `${baseUrl}/iot/test-pat-token`);
      const response = await fetch(`${baseUrl}/iot/test-pat-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          pat_token: patToken.trim(),
          user_id: 'default',
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
      console.log('📥 PAT 토큰 테스트 응답 수신:', {
        status: response.status,
        elapsed: `${elapsed}초`
      });

      const data = await response.json();
      console.log('🧪 연결 테스트 결과:', data);

      if (data.success && data.connected) {
        setConnectionStatus(`✅ 연결 성공! 등록된 디바이스: ${data.deviceCount}개`);
      } else {
        setConnectionStatus(`❌ ${data.message || '연결 실패'}`);
      }
    } catch (err: any) {
      console.error('❌ 연결 테스트 실패:', err);
      console.error('   에러 타입:', err.name);
      console.error('   에러 메시지:', err.message);
      
      if (err.name === 'AbortError') {
        setConnectionStatus('❌ 연결 테스트 시간 초과 (10초). 서버가 응답하지 않습니다.');
      } else if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        setConnectionStatus(`❌ 서버에 연결할 수 없습니다. 서버 URL: ${serverUrl || getServerUrl()}`);
      } else {
        setConnectionStatus(`❌ 연결 테스트 실패: ${err.message || '알 수 없는 오류'}`);
      }
    } finally {
      setTestingConnection(false);
    }
  };

  const handleRegister = async () => {
    console.log('🔘 확인 버튼 클릭:', { isValid, patToken: patToken.substring(0, 20) + '...', loading });
    
    if (!isValid) {
      const errorMsg = '올바른 PAT 토큰 형식이 아닙니다. (thinqpat_로 시작하고 20자 이상이어야 합니다)';
      console.error('❌ PAT 토큰 형식 오류:', errorMsg);
      setError(errorMsg);
      return;
    }

    setLoading(true);
    setError(null);
    setLoadingMessage('서버 연결 확인 중...');

    try {
      let baseUrl = serverUrl || getServerUrl();
      
      // 서버 URL이 없거나 localhost인 경우 자동 감지
      if (!baseUrl || baseUrl === '' || baseUrl.includes('localhost')) {
        console.log('⚠️ 서버 URL 없음 또는 localhost 감지, 자동 감지 시도');
        setLoadingMessage('서버 자동 감지 중...');
        try {
          const detectedUrl = await autoDetectServerUrl();
          if (!detectedUrl || detectedUrl === '') {
            throw new Error('서버 URL 자동 감지 실패');
          }
          baseUrl = detectedUrl;
          setServerUrl(detectedUrl);
          console.log('✅ 서버 자동 감지 성공:', baseUrl);
        } catch (detectError) {
          console.error('❌ 서버 자동 감지 실패:', detectError);
          throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
      }

      const requestStartTime = Date.now();
      console.log('🔍 PAT 토큰 등록 시도:', {
        baseUrl,
        patToken: patToken.trim().substring(0, 20) + '...',
        fullUrl: `${baseUrl}/iot/auto-register`,
        timestamp: new Date().toISOString()
      });
      
      // 먼저 서버 연결 확인
      setLoadingMessage('서버 연결 확인 중...');
      try {
        const healthResponse = await fetch(`${baseUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000) // 5초
        });
        if (!healthResponse.ok) {
          throw new Error(`서버 응답 오류: ${healthResponse.status}`);
        }
        console.log('✅ 서버 연결 확인 성공');
      } catch (healthError: any) {
        console.error('❌ 서버 연결 실패:', healthError);
        
        // 서버 URL 자동 감지 재시도
        if (!healthError.message?.includes('자동 감지')) {
          console.log('🔄 서버 연결 실패 - 서버 URL 자동 감지 재시도...');
          setLoadingMessage('서버 자동 감지 중...');
          try {
            const detectedUrl = await autoDetectServerUrl();
            if (detectedUrl && detectedUrl !== '' && detectedUrl !== baseUrl) {
              console.log('✅ 새로운 서버 URL 감지:', detectedUrl);
              setServerUrl(detectedUrl);
              baseUrl = detectedUrl;
              // 재연결 시도
              const retryHealthResponse = await fetch(`${baseUrl}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(5000)
              });
              if (retryHealthResponse.ok) {
                console.log('✅ 재연결 성공');
              } else {
                throw new Error(`서버 응답 오류: ${retryHealthResponse.status}`);
              }
            } else {
              throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (${baseUrl})`);
            }
          } catch (detectError: any) {
            console.error('❌ 서버 URL 자동 감지 실패:', detectError);
            throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (${baseUrl})`);
          }
        } else {
          throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (${baseUrl})`);
        }
      }
      
      // 타임아웃 설정 (30초로 증가 - LG ThinQ API 응답이 매우 느릴 수 있음)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
        console.error(`⏱️ 요청 타임아웃 (${elapsed}초 경과)`);
        controller.abort();
      }, 30000); // 30초로 증가
      
      setLoadingMessage('PAT 토큰 검증 중...');
      console.log('📤 서버로 요청 전송:', `${baseUrl}/iot/auto-register`);
      
      let response: Response;
      try {
        response = await fetch(`${baseUrl}/iot/auto-register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pat_token: patToken.trim(),
            user_id: 'default', // 나중에 실제 사용자 ID로 확장
          }),
          signal: controller.signal,
        });
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
        
        if (fetchError.name === 'AbortError') {
          console.error(`❌ 요청 타임아웃 (${elapsed}초)`);
          throw new Error(`요청 시간이 초과되었습니다 (${elapsed}초). 서버가 응답하지 않거나 네트워크 연결이 느립니다.`);
        } else if (fetchError.message?.includes('Failed to fetch') || fetchError.message?.includes('NetworkError') || fetchError.message?.includes('서버에 연결할 수 없습니다')) {
          console.error(`❌ 네트워크 오류: ${fetchError.message}`);
          throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (${baseUrl})`);
        } else {
          console.error(`❌ 요청 실패: ${fetchError.message}`);
          throw new Error(`요청 실패: ${fetchError.message}`);
        }
      }
      
      clearTimeout(timeoutId);
      const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
      
      console.log('📥 서버 응답 수신:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        elapsed: `${elapsed}초`
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: '서버 오류가 발생했습니다.' }));
        const errorMessage = errorData.detail || errorData.error || errorData.message || `서버 오류 (${response.status})`;
        console.error('❌ 서버 오류 응답:', errorMessage);
        throw new Error(errorMessage);
      }

      setLoadingMessage('에어컨 찾는 중...');
      const data = await response.json();

      if (data.success) {
        setLoadingMessage('등록 완료 중...');
        
        // localStorage에 PAT 토큰 저장
        localStorage.setItem('thinq_pat_token', patToken.trim());
        localStorage.setItem('thinq_device_id', data.deviceId);
        localStorage.setItem('thinq_device_name', data.deviceName);
        localStorage.setItem('iot_device_registered', 'true');

        // 잠시 후 IoT 페이지로 이동 (사용자가 성공 메시지를 볼 수 있도록)
        setTimeout(() => {
          history.push('/iot');
        }, 500);
      } else if (data.needsSelection) {
        // 여러 개의 에어컨이 있는 경우 선택 화면 표시
        // 일단 첫 번째 것을 자동 선택하거나, 선택 화면을 만들어야 함
        // 여기서는 첫 번째 것을 자동 선택
        if (data.devices && data.devices.length > 0) {
          const selectedDevice = data.devices[0];
          const registerResponse = await fetch(`${baseUrl}/iot/register-device`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              patToken: patToken.trim(),
              deviceId: selectedDevice.deviceId,
              userId: 'default',
            }),
          });

          const registerData = await registerResponse.json();
          if (registerData.success) {
            localStorage.setItem('thinq_pat_token', patToken.trim());
            localStorage.setItem('thinq_device_id', registerData.deviceId);
            localStorage.setItem('thinq_device_name', registerData.deviceName);
            localStorage.setItem('iot_device_registered', 'true');
            history.push('/iot');
          } else {
            setError(registerData.message || '디바이스 등록에 실패했습니다.');
          }
        } else {
          setError('등록할 디바이스를 찾을 수 없습니다.');
        }
      } else {
        setError(data.message || '디바이스 등록에 실패했습니다.');
      }
    } catch (err: any) {
      console.error('❌ 등록 실패:', err);
      console.error('   에러 타입:', err.name);
      console.error('   에러 메시지:', err.message);
      
      if (err.name === 'AbortError' || err.message?.includes('시간이 초과')) {
        setError(err.message || '요청 시간이 초과되었습니다. 네트워크 연결을 확인하고 다시 시도해주세요.');
      } else if (err.message?.includes('서버에 연결할 수 없습니다')) {
        setError(err.message);
      } else {
        setError(err.message || '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
      }
    } finally {
      setLoading(false);
      setLoadingMessage('등록 중...');
    }
  };

  return (
    <IonPage className="device-registration-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>IoT 디바이스 등록</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <div className="container">
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>LG ThinQ 에어컨 등록</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonText color="dark">
                <p className="description-text">
                  PAT 토큰을 입력하면 자동으로 등록된 에어컨을 찾아 연결합니다.
                </p>
              </IonText>

              {/* PAT 토큰 만들기 버튼 */}
              <IonButton
                expand="block"
                fill="outline"
                onClick={handleOpenPatSite}
                className="pat-token-button"
              >
                <IonIcon icon={openOutline} slot="start" />
                PAT 토큰 만들러 가기
              </IonButton>

              {/* PAT 토큰 입력 */}
              <IonItem>
                <IonLabel position="stacked">PAT 토큰</IonLabel>
                <IonInput
                  type="text"
                  value={patToken}
                  placeholder="thinqpat_..."
                  onIonInput={(e) => handlePatTokenChange(e.detail.value!)}
                  disabled={loading}
                />
              </IonItem>

              {patToken && !isValid && (
                <IonText color="danger" className="error-text">
                  PAT 토큰은 'thinqpat_'로 시작해야 합니다.
                </IonText>
              )}

              {error && (
                <IonText color="danger" className="error-text">
                  {error}
                </IonText>
              )}

              {/* 확인 버튼 */}
              <IonButton
                expand="block"
                color="primary"
                onClick={handleRegister}
                disabled={!isValid || loading}
                className="confirm-button"
              >
                {loading ? (
                  <>
                    <IonSpinner name="crescent" style={{ marginRight: '8px' }} />
                    {loadingMessage}
                  </>
                ) : (
                  <>
                    <IonIcon icon={checkmarkCircleOutline} slot="start" />
                    확인
                  </>
                )}
              </IonButton>
            </IonCardContent>
          </IonCard>
        </div>
      </IonContent>
    </IonPage>
  );
};

export default DeviceRegistration;

