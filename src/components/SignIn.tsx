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
import './SignIn.css';

interface SignInProps {
  onClose: () => void;
}

const SignIn: React.FC<SignInProps> = ({ onClose }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSignIn = () => {
    setIsLoading(true);
    const isValid = email.trim() !== '' && password.trim() !== '';

    // 로그인 처리 (나중에 실제 로그인 로직으로 교체)
    setTimeout(() => {
      setIsLoading(false);
      if (isValid) {
        // 로그인 성공
        setTimeout(() => {
          onClose();
          setEmail('');
          setPassword('');
        }, 1000);
      }
    }, 2000);
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
          포술 앱에 오신 것을 환영합니다. 건강 데이터를 관리하고 IoT 기기를 제어할 수 있습니다.
        </IonText>

        <IonItem className="sign-in-input-item">
          <IonLabel position="stacked">이메일</IonLabel>
          <IonInput
            type="email"
            autocomplete="email"
            inputmode="email"
            enterkeyhint="next"
            value={email}
            onIonInput={(e) => setEmail(e.detail.value!)}
            placeholder="이메일을 입력하세요"
          />
        </IonItem>

        <IonItem className="sign-in-input-item">
          <IonLabel position="stacked">비밀번호</IonLabel>
          <IonInput
            type="password"
            value={password}
            onIonInput={(e) => setPassword(e.detail.value!)}
            placeholder="비밀번호를 입력하세요"
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

        <IonText className="footer-text">
          이메일, Apple 또는 Google로 가입하기
        </IonText>
      </div>
    </div>
  );
};

export default SignIn;

