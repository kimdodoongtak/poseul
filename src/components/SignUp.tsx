import React, { useState } from 'react';
import {
  IonButton,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonRow,
  IonText,
  IonSpinner,
  IonSelect,
  IonSelectOption,
} from '@ionic/react';
import { arrowForwardOutline, closeOutline, openOutline, checkmarkCircleOutline, arrowBackOutline } from 'ionicons/icons';
import { register } from '../services/AuthService';
import { getServerUrl, autoDetectServerUrl } from '../services/ServerConfig';
import IotService from '../services/IotService';
import './SignUp.css';

interface SignUpProps {
  onClose: () => void;
  onSuccess?: () => void;
}

const SignUp: React.FC<SignUpProps> = ({ onClose, onSuccess }) => {
  const [step, setStep] = useState<1 | 2>(1); // 1: 회원가입 정보, 2: IoT 등록
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [age, setAge] = useState('');
  const [bmi, setBmi] = useState('');
  const [gender, setGender] = useState('0'); // 0: 여성, 1: 남성
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [patToken, setPatToken] = useState('');
  const [isValidPatToken, setIsValidPatToken] = useState(false);
  const [iotError, setIotError] = useState('');
  const [iotLoading, setIotLoading] = useState(false);
  const [iotLoadingMessage, setIotLoadingMessage] = useState('등록 중...');

  const handlePatTokenChange = (value: string) => {
    setPatToken(value);
    setIotError('');
    const trimmed = value.trim();
    const valid = trimmed.startsWith('thinqpat_') && trimmed.length > 20;
    setIsValidPatToken(valid);
  };

  const handleOpenPatSite = () => {
    window.open('https://connect-pat.lgthinq.com', '_blank');
  };

  const handleRegisterIot = async (): Promise<string | null> => {
    if (!isValidPatToken) {
      setIotError('올바른 PAT 토큰 형식이 아닙니다. (thinqpat_로 시작하고 20자 이상이어야 합니다)');
      return null;
    }

    setIotLoading(true);
    setIotError('');
    setIotLoadingMessage('서버 연결 확인 중...');

    try {
      let baseUrl = getServerUrl();
      
      if (!baseUrl || baseUrl === '' || baseUrl.includes('localhost')) {
        setIotLoadingMessage('서버 자동 감지 중...');
        try {
          const detectedUrl = await autoDetectServerUrl();
          if (!detectedUrl || detectedUrl === '') {
            throw new Error('서버 URL 자동 감지 실패. 서버가 실행 중인지 확인해주세요.');
          }
          baseUrl = detectedUrl;
          IotService.updateBaseUrl(detectedUrl);
        } catch (detectError) {
          throw new Error('서버를 찾을 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        }
      }

      setIotLoadingMessage('PAT 토큰 검증 중...');
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60초로 증가
      
      let response: Response;
      try {
        response = await fetch(`${baseUrl}/iot/auto-register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pat_token: patToken.trim(),
            user_id: id.trim(),
          }),
          signal: controller.signal,
        });
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          throw new Error('요청 시간이 초과되었습니다. 서버가 응답하지 않거나 네트워크 연결이 느립니다.');
        } else if (fetchError.message?.includes('Failed to fetch') || fetchError.message?.includes('NetworkError')) {
          throw new Error(`서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. (${baseUrl})`);
        } else {
          throw new Error(`요청 실패: ${fetchError.message || '알 수 없는 오류'}`);
        }
      }

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'IoT 등록에 실패했습니다.' }));
        throw new Error(errorData.detail || errorData.message || 'IoT 등록에 실패했습니다.');
      }

      setIotLoadingMessage('에어컨 찾는 중...');
      const data = await response.json();

      if (data.success) {
        // device_id를 반환
        return data.deviceId || patToken.trim();
      } else if (data.needsSelection && data.devices && data.devices.length > 0) {
        // 여러 개의 에어컨이 있는 경우 첫 번째 것 선택
        const selectedDevice = data.devices[0];
        const registerResponse = await fetch(`${baseUrl}/iot/register-device`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            patToken: patToken.trim(),
            deviceId: selectedDevice.deviceId,
            userId: id.trim(),
          }),
        });

        if (!registerResponse.ok) {
          throw new Error('디바이스 등록에 실패했습니다.');
        }

        const registerData = await registerResponse.json();
        return registerData.deviceId || patToken.trim();
      } else {
        throw new Error(data.message || 'IoT 등록에 실패했습니다.');
      }
    } catch (err: any) {
      setIotError(err.message || 'IoT 등록에 실패했습니다.');
      return null;
    } finally {
      setIotLoading(false);
      setIotLoadingMessage('등록 중...');
    }
  };

  const handleNext = () => {
    // 입력 검증
    if (!id.trim()) {
      setError('아이디를 입력해주세요.');
      return;
    }

    if (!password.trim()) {
      setError('비밀번호를 입력해주세요.');
      return;
    }

    if (password.length < 4) {
      setError('비밀번호는 최소 4자 이상이어야 합니다.');
      return;
    }

    if (password !== confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }

    setError('');
    setStep(2);
  };

  const handleBack = () => {
    setStep(1);
    setIotError('');
    setPatToken('');
    setIsValidPatToken(false);
  };

  const handleSignUp = async () => {
    setError('');
    setIotError('');
    setIsLoading(true);

    try {
      // 먼저 회원가입 완료
      const registerData: any = { 
        id: id.trim(), 
        password
      };
      
      // 나이/BMI/성별이 입력되어 있으면 포함
      if (age.trim()) {
        registerData.age = parseInt(age.trim(), 10);
      }
      if (bmi.trim()) {
        registerData.bmi = parseFloat(bmi.trim());
      }
      if (gender.trim()) {
        registerData.gender = gender.trim() === '1' ? 'M' : 'F';
      }
      
      const registerResult = await register(registerData);
      
      console.log('✅ 회원가입 성공:', registerResult);
      
      // 회원가입 성공 후 IoT 등록 시도 (PAT 토큰이 입력되어 있으면)
      if (patToken.trim() && isValidPatToken) {
        try {
          console.log('🔍 회원가입 후 IoT 등록 시작...');
          const deviceInfo = await handleRegisterIot();
          if (!deviceInfo) {
            // IoT 등록 실패해도 회원가입은 성공
            setIotError('IoT 등록에 실패했지만 회원가입은 완료되었습니다.');
          } else {
            console.log('✅ IoT 등록 성공:', deviceInfo);
          }
        } catch (iotError: any) {
          // IoT 등록 실패해도 회원가입은 성공
          console.error('IoT 등록 실패:', iotError);
          setIotError('IoT 등록에 실패했지만 회원가입은 완료되었습니다.');
        }
      }
      
      // 회원가입 성공
      if (onSuccess) {
        onSuccess();
      }
      
      setTimeout(() => {
        onClose();
        setStep(1);
        setId('');
        setPassword('');
        setConfirmPassword('');
        setAge('');
        setBmi('');
        setGender('0');
        setPatToken('');
      }, 1000);
    } catch (err: any) {
      console.error('회원가입 실패:', err);
      setError(err.message || '회원가입에 실패했습니다.');
    } finally {
      setIsLoading(false);
      setIotLoading(false); // IoT 로딩 상태도 초기화
    }
  };

  return (
    <div className="sign-up-modal">
      <div className="sign-up-container">
        <div className="sign-up-header">
          <IonText className="sign-up-title">
            {step === 1 ? '회원가입' : 'IoT 기기 등록'}
          </IonText>
          <IonButton fill="clear" onClick={onClose} className="close-button">
            <IonIcon icon={closeOutline} />
          </IonButton>
        </div>

        {step === 1 ? (
          <>
            <IonText className="sign-up-subtitle">
              포술 앱에 가입하여 건강 데이터를 관리하고<br />
              IoT 기기를 제어하세요.
            </IonText>

            {error && (
              <IonText color="danger" className="error-message">
                {error}
              </IonText>
            )}

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">아이디</IonLabel>
              <IonInput
                type="text"
                autocomplete="username"
                inputmode="text"
                enterkeyhint="next"
                value={id}
                onIonInput={(e) => setId(e.detail.value!)}
                placeholder="아이디를 입력하세요"
                disabled={isLoading}
              />
            </IonItem>

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">비밀번호</IonLabel>
              <IonInput
                type="password"
                autocomplete="new-password"
                enterkeyhint="next"
                value={password}
                onIonInput={(e) => setPassword(e.detail.value!)}
                placeholder="비밀번호를 입력하세요 (최소 4자)"
                disabled={isLoading}
                clearOnEdit={false}
              />
            </IonItem>

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">비밀번호 확인</IonLabel>
              <IonInput
                type="password"
                autocomplete="new-password"
                enterkeyhint="next"
                value={confirmPassword}
                onIonInput={(e) => setConfirmPassword(e.detail.value!)}
                placeholder="비밀번호를 다시 입력하세요"
                disabled={isLoading}
                clearOnEdit={false}
              />
            </IonItem>

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">나이</IonLabel>
              <IonInput
                type="number"
                inputmode="numeric"
                enterkeyhint="next"
                value={age}
                onIonInput={(e) => setAge(e.detail.value!)}
                placeholder="나이를 입력하세요"
                disabled={isLoading}
              />
            </IonItem>

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">BMI</IonLabel>
              <IonInput
                type="number"
                inputmode="decimal"
                enterkeyhint="next"
                value={bmi}
                onIonInput={(e) => setBmi(e.detail.value!)}
                placeholder="BMI를 입력하세요"
                disabled={isLoading}
              />
            </IonItem>

            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">성별</IonLabel>
              <IonSelect
                value={gender}
                placeholder="성별을 선택하세요"
                onIonChange={(e) => setGender(e.detail.value)}
                disabled={isLoading}
              >
                <IonSelectOption value="0">여성</IonSelectOption>
                <IonSelectOption value="1">남성</IonSelectOption>
              </IonSelect>
            </IonItem>

            <IonButton
              className="sign-up-button"
              expand="block"
              onClick={handleNext}
              disabled={isLoading}
            >
              <IonIcon icon={arrowForwardOutline} slot="end" />
              다음
            </IonButton>
          </>
        ) : (
          <>
            <IonText className="sign-up-subtitle">
              PAT 토큰을 입력하면 자동으로 등록된<br />
              에어컨을 찾아 연결합니다.
            </IonText>

            {error && (
              <IonText color="danger" className="error-message">
                {error}
              </IonText>
            )}

            {iotError && (
              <IonText color="danger" className="error-message">
                {iotError}
              </IonText>
            )}

            {/* PAT 토큰 만들기 버튼 */}
            <IonButton
              expand="block"
              fill="outline"
              onClick={handleOpenPatSite}
              disabled={isLoading || iotLoading}
              className="pat-token-button"
              style={{ 
                marginBottom: '16px'
              }}
            >
              <IonIcon icon={openOutline} slot="start" />
              PAT 토큰 만들러 가기
            </IonButton>

            {/* PAT 토큰 입력 */}
            <IonItem className="sign-up-input-item">
              <IonLabel position="stacked">PAT 토큰</IonLabel>
              <IonInput
                type="text"
                value={patToken}
                placeholder="thinqpat_..."
                onIonInput={(e) => handlePatTokenChange(e.detail.value!)}
                disabled={isLoading || iotLoading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && patToken.trim() && isValidPatToken) {
                    handleSignUp();
                  }
                }}
              />
            </IonItem>

            {patToken && !isValidPatToken && (
              <IonText color="danger" style={{ fontSize: '12px', display: 'block', marginTop: '8px' }}>
                PAT 토큰은 'thinqpat_'로 시작해야 합니다.
              </IonText>
            )}

            <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
              <IonButton
                fill="clear"
                expand="block"
                onClick={handleBack}
                disabled={isLoading || iotLoading}
                className="sign-up-back-button"
                style={{ flex: 1 }}
              >
                <IonIcon icon={arrowBackOutline} slot="start" />
                이전
              </IonButton>
              <IonButton
                className="sign-up-button"
                expand="block"
                onClick={handleSignUp}
                disabled={isLoading || iotLoading}
                style={{ flex: 2 }}
              >
                {isLoading || iotLoading ? (
                  <>
                    <IonSpinner name="crescent" style={{ marginRight: '8px' }} />
                    {iotLoading ? iotLoadingMessage : '회원가입 중...'}
                  </>
                ) : (
                  <>
                    <IonIcon icon={checkmarkCircleOutline} slot="end" />
                    회원가입 완료
                  </>
                )}
              </IonButton>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SignUp;

