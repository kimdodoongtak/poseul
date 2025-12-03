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
} from '@ionic/react';
import { arrowForwardOutline, closeOutline } from 'ionicons/icons';
import { login, getIotDeviceStatus, isAuthenticated, getToken, getUserNo } from '../services/AuthService';
import SignUp from './SignUp';
import './SignIn.css';

interface SignInProps {
  onClose: () => void;
  onSuccess?: () => void;
}

const SignIn: React.FC<SignInProps> = ({ onClose, onSuccess }) => {
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSignUp, setShowSignUp] = useState(false);

  const handleSignIn = async () => {
    // 입력 검증
    if (!id.trim() || !password.trim()) {
      setError('아이디와 비밀번호를 입력해주세요.');
      return;
    }

    setError('');
    setIsLoading(true);

    try {
      console.log('🔵 SignIn - 로그인 시작:', id.trim());
      
      // 1. 로그인 API 호출
      const loginResult = await login({ id: id.trim(), password });
      console.log('✅ SignIn - login() 함수 완료, 응답:', loginResult ? '있음' : '없음');
      
      // 2. 토큰 저장 확인 (즉시 확인)
      const token = getToken();
      console.log('🔵 SignIn - 토큰 확인:', token ? `있음 (길이: ${token.length})` : '없음');
      
      if (!token) {
        console.error('❌ SignIn - 토큰이 저장되지 않음');
        // localStorage 직접 확인
        const directToken = localStorage.getItem('auth_token');
        console.error('❌ SignIn - localStorage 직접 확인:', directToken ? `있음 (길이: ${directToken.length})` : '없음');
        throw new Error('로그인 토큰 저장에 실패했습니다.');
      }
      
      console.log('✅ SignIn - 토큰 저장 확인 완료');
      
      // 3. 면책사항 동의 사용자별로 저장 (기존 공통 면책사항이 있으면 마이그레이션)
      const userNo = getUserNo();
      if (userNo !== null) {
        const oldDisclaimerAccepted = localStorage.getItem('disclaimer_accepted');
        const userDisclaimerAccepted = localStorage.getItem(`disclaimer_accepted_${userNo}`);
        
        if (oldDisclaimerAccepted && !userDisclaimerAccepted) {
          // 기존 공통 면책사항이 있고 사용자별 면책사항이 없으면 마이그레이션
          localStorage.setItem(`disclaimer_accepted_${userNo}`, 'true');
          console.log(`✅ 면책사항 동의 사용자별로 저장 (user_no: ${userNo}, 기존 공통 동의 마이그레이션)`);
        } else if (!userDisclaimerAccepted) {
          // 사용자별 면책사항이 없으면 새로 저장 (로그인 전에 동의한 경우)
          localStorage.setItem(`disclaimer_accepted_${userNo}`, 'true');
          console.log(`✅ 면책사항 동의 사용자별로 저장 (user_no: ${userNo})`);
        }
      }
      
      // 4. 로그인 성공 콜백 호출 (토큰 저장 확인 후)
      if (onSuccess) {
        console.log('✅ SignIn - onSuccess 호출');
        onSuccess();
      }
      
      // 5. IoT 등록 정보 불러오기 (비동기, 실패해도 무시)
      setTimeout(async () => {
        try {
          console.log('🔵 SignIn - IoT 등록 정보 불러오기 시작');
          
          // 토큰 확인 (재시도 로직)
          let token = getToken();
          let retryCount = 0;
          while (!token && retryCount < 5) {
            console.log(`🔵 SignIn - 토큰 확인 중... (재시도 ${retryCount + 1}/5)`);
            await new Promise(resolve => setTimeout(resolve, 100));
            token = getToken();
            retryCount++;
          }
          
          if (!token) {
            console.warn('⚠️ SignIn - 토큰을 찾을 수 없음, IoT 등록 정보 불러오기 건너뜀');
            return;
          }
          
          console.log(`✅ SignIn - 토큰 확인 완료 (길이: ${token.length})`);
          const iotStatus = await getIotDeviceStatus();
          if (iotStatus.success && iotStatus.registered) {
            // IoT 등록 정보가 있으면 localStorage에 저장
            if (iotStatus.deviceId) {
              localStorage.setItem('thinq_device_id', iotStatus.deviceId);
            }
            if (iotStatus.deviceName) {
              localStorage.setItem('thinq_device_name', iotStatus.deviceName);
            }
            if (iotStatus.patToken) {
              localStorage.setItem('thinq_pat_token', iotStatus.patToken);
            }
            localStorage.setItem('iot_device_registered', 'true');
            
            // 서버 URL 자동 감지 및 IotService 초기화
            try {
              const { autoDetectServerUrl } = await import('../services/ServerConfig');
              const serverUrl = await autoDetectServerUrl();
              if (serverUrl) {
                const IotService = (await import('../services/IotService')).default;
                IotService.updateBaseUrl(serverUrl);
                console.log('✅ 로그인 후 IoT 서비스 초기화 완료:', serverUrl);
              }
            } catch (serverError) {
              console.log('서버 URL 자동 감지 실패 (무시):', serverError);
            }
          }
        } catch (iotError) {
          // IoT 등록 정보 불러오기 실패해도 로그인은 성공
          console.log('IoT 등록 정보 불러오기 실패 (무시):', iotError);
        }
      }, 100);
      
      // 6. 모달 닫기 (onSuccess가 완전히 처리되도록 충분한 지연)
      setTimeout(() => {
        onClose();
        setId('');
        setPassword('');
      }, 500);
    } catch (err: any) {
      setError(err.message || '로그인에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="sign-in-modal">
      <div className="sign-in-container">
        <div className="sign-in-header">
          <IonText className="sign-in-title">로그인</IonText>
          <IonButton fill="clear" onClick={onClose} className="close-button">
            <IonIcon icon={closeOutline} />
          </IonButton>
        </div>

        <IonText className="sign-in-subtitle">
          포슬 앱에 오신 것을 환영합니다. 건강 데이터를 관리하고 IoT 기기를 제어할 수 있습니다.
        </IonText>

        {error && (
          <IonText color="danger" className="error-message">
            {error}
          </IonText>
        )}

        <IonItem className="sign-in-input-item">
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

        <IonItem className="sign-in-input-item">
          <IonLabel position="stacked">비밀번호</IonLabel>
          <IonInput
            type="password"
            autocomplete="current-password"
            enterkeyhint="done"
            value={password}
            onIonInput={(e) => setPassword(e.detail.value!)}
            placeholder="비밀번호를 입력하세요"
            disabled={isLoading}
            clearOnEdit={false}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSignIn();
              }
            }}
          />
        </IonItem>

        <IonButton
          className="sign-in-button"
          expand="block"
          type="submit"
          onClick={handleSignIn}
          disabled={isLoading}
        >
          {isLoading ? <IonSpinner name="crescent" /> : (
            <>
              <IonIcon icon={arrowForwardOutline} slot="end" />
              로그인
            </>
          )}
        </IonButton>

        <IonRow className="or-divider">
          <div className="divider"></div>
          <IonText className="or-text">OR</IonText>
          <div className="divider"></div>
        </IonRow>

        <div style={{ textAlign: 'center', marginTop: '12px' }}>
          <button 
            className="sign-up-link-text"
            onClick={() => setShowSignUp(true)}
            disabled={isLoading}
          >
            회원가입
          </button>
        </div>
      </div>

      {/* 회원가입 모달 */}
      {showSignUp && (
        <SignUp
          onClose={() => setShowSignUp(false)}
          onSuccess={() => {
            // 회원가입 성공 시 회원가입 모달 닫고 로그인 모달도 닫기
            setShowSignUp(false);
            if (onSuccess) {
              onSuccess();
            }
            setTimeout(() => {
              onClose();
            }, 500);
          }}
        />
      )}
    </div>
  );
};

export default SignIn;

