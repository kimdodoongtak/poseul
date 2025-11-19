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
      
      // 10.0.2.2는 에뮬레이터용이므로 실제 기기에서는 작동하지 않음
      // 무조건 자동 감지 실행 (저장된 URL이 있더라도)
      if (currentUrl.includes('10.0.2.2') || currentUrl.includes('localhost')) {
        console.log('🔄 서버 URL 자동 감지 시작 (에뮬레이터용 IP 감지됨)...');
        setDetectingServer(true);
        
        // localStorage에서 10.0.2.2 제거
        if (typeof window !== 'undefined') {
          const savedUrl = localStorage.getItem('server_url');
          if (savedUrl && savedUrl.includes('10.0.2.2')) {
            console.log('🗑️ 에뮬레이터용 URL 제거:', savedUrl);
            localStorage.removeItem('server_url');
          }
        }
        
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
          }
        } catch (err) {
          console.error('❌ 서버 URL 자동 감지 실패:', err);
          setConnectionStatus('❌ 서버 자동 감지 중 오류가 발생했습니다.');
          // 실패해도 현재 URL 유지
          setServerUrl(currentUrl);
        } finally {
          setDetectingServer(false);
        }
      } else {
        // 이미 올바른 URL이 있으면 그대로 사용하되, 연결 테스트는 나중에
        console.log('✅ 저장된 서버 URL 사용:', currentUrl);
        setServerUrl(currentUrl);
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
    // PAT 토큰 형식 검증 (thinqpat_로 시작)
    setIsValid(value.trim().startsWith('thinqpat_') && value.trim().length > 20);
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
    if (!isValid) {
      setError('올바른 PAT 토큰 형식이 아닙니다.');
      return;
    }

    setLoading(true);
    setError(null);
    setLoadingMessage('디바이스 목록 조회 중...');

    try {
      const baseUrl = serverUrl || getServerUrl();
      const requestStartTime = Date.now();
      console.log('🔍 PAT 토큰 등록 시도:', {
        baseUrl,
        patToken: patToken.trim().substring(0, 20) + '...',
        fullUrl: `${baseUrl}/iot/auto-register`,
        timestamp: new Date().toISOString()
      });
      
      // 타임아웃 설정 (15초로 증가 - LG ThinQ API 응답이 느릴 수 있음)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(2);
        console.error(`⏱️ 요청 타임아웃 (${elapsed}초 경과)`);
        controller.abort();
      }, 15000);
      
      setLoadingMessage('서버 연결 중...');
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
        } else if (fetchError.message?.includes('Failed to fetch') || fetchError.message?.includes('NetworkError')) {
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
        <div className="container" style={{ padding: '24px', maxWidth: '600px', margin: '0 auto' }}>
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>LG ThinQ 에어컨 등록</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonText color="dark">
                <p style={{ fontSize: '14px', marginBottom: '24px', color: '#333', fontWeight: '500' }}>
                  PAT 토큰을 입력하면 자동으로 등록된 에어컨을 찾아 연결합니다.
                </p>
              </IonText>

              {/* PAT 토큰 만들기 버튼 */}
              <IonButton
                expand="block"
                fill="outline"
                onClick={handleOpenPatSite}
                style={{ marginBottom: '24px' }}
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
                  style={{
                    '--background': '#ffffff',
                    '--color': '#000000',
                    'background': '#ffffff',
                    'color': '#000000',
                    'border': '2px solid #333',
                    'border-radius': '8px',
                  } as React.CSSProperties}
                />
              </IonItem>

              {patToken && !isValid && (
                <IonText color="danger" style={{ fontSize: '12px', marginTop: '8px', display: 'block' }}>
                  PAT 토큰은 'thinqpat_'로 시작해야 합니다.
                </IonText>
              )}

              {/* 연결 테스트 버튼 */}
              {isValid && !loading && (
                <IonButton
                  expand="block"
                  fill="outline"
                  color="medium"
                  onClick={handleTestConnection}
                  disabled={testingConnection}
                  style={{ marginTop: '16px' }}
                >
                  {testingConnection ? (
                    <>
                      <IonSpinner name="crescent" style={{ marginRight: '8px' }} />
                      연결 테스트 중...
                    </>
                  ) : (
                    '연결 테스트'
                  )}
                </IonButton>
              )}

              {connectionStatus && (
                <IonText 
                  color={connectionStatus.startsWith('✅') ? 'success' : 'danger'} 
                  style={{ fontSize: '14px', marginTop: '12px', display: 'block' }}
                >
                  {connectionStatus}
                </IonText>
              )}

              {error && (
                <IonText color="danger" style={{ fontSize: '14px', marginTop: '16px', display: 'block' }}>
                  {error}
                </IonText>
              )}

              {/* 확인 버튼 */}
              <IonButton
                expand="block"
                color="primary"
                onClick={handleRegister}
                disabled={!isValid || loading}
                style={{ 
                  marginTop: '24px',
                  borderRadius: '8px',
                  '--border-radius': '8px'
                } as React.CSSProperties}
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

              <IonText style={{ fontSize: '12px', marginTop: '16px', display: 'block', color: '#666' }}>
                💡 PAT 토큰은 https://connect-pat.lgthinq.com 에서 발급받을 수 있습니다.
              </IonText>
              
              {/* 서버 URL 표시 및 수동 입력 */}
              <div style={{ marginTop: '12px' }}>
                {detectingServer ? (
                  <IonText style={{ fontSize: '11px', display: 'block', color: '#999' }}>
                    🔄 서버 자동 감지 중...
                  </IonText>
                ) : (
                  <>
                    <IonText style={{ fontSize: '11px', display: 'block', color: '#999' }}>
                      🔗 서버: {serverUrl}
                      {serverUrl.includes('10.0.2.2') && (
                        <span style={{ color: '#ff6b6b', marginLeft: '8px' }}>
                          (에뮬레이터용 - 실제 기기에서는 작동하지 않을 수 있음)
                        </span>
                      )}
                    </IonText>
                    
                    {!showManualInput ? (
                      <IonButton
                        fill="clear"
                        size="small"
                        onClick={() => setShowManualInput(true)}
                        style={{ 
                          marginTop: '8px',
                          fontSize: '12px',
                          '--padding-start': '0',
                          '--padding-end': '0'
                        } as React.CSSProperties}
                      >
                        서버 URL 수동 입력
                      </IonButton>
                    ) : (
                      <div style={{ marginTop: '12px' }}>
                        <IonItem>
                          <IonLabel position="stacked">서버 URL</IonLabel>
                          <IonInput
                            type="text"
                            value={manualServerUrl}
                            placeholder="http://192.168.x.x:3000"
                            onIonInput={(e) => setManualServerUrl(e.detail.value!)}
                            style={{
                              '--background': '#ffffff',
                              '--color': '#000000',
                              'background': '#ffffff',
                              'color': '#000000',
                              'border': '1px solid #ccc',
                              'border-radius': '4px',
                            } as React.CSSProperties}
                          />
                        </IonItem>
                        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                          <IonButton
                            size="small"
                            onClick={() => {
                              if (manualServerUrl.trim()) {
                                let url = manualServerUrl.trim();
                                if (!url.startsWith('http://') && !url.startsWith('https://')) {
                                  url = `http://${url}`;
                                }
                                console.log('📝 수동으로 서버 URL 설정:', url);
                                setServerUrl(url);
                                localStorage.setItem('server_url', url);
                                setShowManualInput(false);
                                setManualServerUrl('');
                                setConnectionStatus('✅ 서버 URL이 업데이트되었습니다.');
                              }
                            }}
                          >
                            적용
                          </IonButton>
                          <IonButton
                            fill="outline"
                            size="small"
                            onClick={() => {
                              setShowManualInput(false);
                              setManualServerUrl('');
                            }}
                          >
                            취소
                          </IonButton>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </IonCardContent>
          </IonCard>
        </div>
      </IonContent>
    </IonPage>
  );
};

export default DeviceRegistration;

