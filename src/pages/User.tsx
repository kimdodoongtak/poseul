import React, { useState, useEffect } from 'react';
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
  IonButton
} from '@ionic/react';
import SignIn from '../components/SignIn';
import './User.css';

const User: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);

  useEffect(() => {
    // 저장된 나이와 BMI 불러오기
    try {
      const savedAge = localStorage.getItem('userAge');
      const savedBmi = localStorage.getItem('userBmi');
      if (savedAge) setAge(savedAge);
      if (savedBmi) setBmi(savedBmi);
    } catch (err) {
      console.log('저장된 나이/BMI 불러오기 실패:', err);
    }

          // HealthData 플러그인 로드 (iOS에서 UserDefaults 저장용)
    const loadHealthData = async () => {
      try {
        const { Capacitor } = await import('@capacitor/core');
        const currentPlatform = Capacitor.getPlatform();
        setPlatform(currentPlatform);
        
        if (currentPlatform === 'ios') {
          const { HealthData } = await import('../plugins/healthdata');
          setHealthDataPlugin(HealthData);
        }
      } catch (err) {
        console.log('HealthData 플러그인 로드 실패:', err);
      }
    };
    
    setTimeout(() => {
      loadHealthData();
    }, 500);
  }, []);

  const handleAgeChange = async (value: string) => {
    setAge(value);
    try {
      localStorage.setItem('userAge', value || '');
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: value || '',
            bmi: bmi || ''
          });
        } catch (err) {
          console.log('나이 UserDefaults 저장 실패:', err);
        }
      }
    } catch (err) {
      console.log('나이 저장 실패:', err);
    }
  };

  const handleBmiChange = async (value: string) => {
    setBmi(value);
    try {
      localStorage.setItem('userBmi', value || '');
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: age || '',
            bmi: value || ''
          });
        } catch (err) {
          console.log('BMI UserDefaults 저장 실패:', err);
        }
      }
    } catch (err) {
      console.log('BMI 저장 실패:', err);
    }
  };

  useEffect(() => {
    // 다크모드 상태 불러오기
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    setIsDarkMode(savedDarkMode);
    if (savedDarkMode) {
      document.body.classList.add('dark');
    }
  }, []);

  const handleDarkModeToggle = (enabled: boolean) => {
    setIsDarkMode(enabled);
    localStorage.setItem('darkMode', enabled.toString());
    if (enabled) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>사용자</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader>
          <IonToolbar>
            <IonTitle size="large">사용자</IonTitle>
          </IonToolbar>
        </IonHeader>
        
        {/* 로그인 모달 */}
        {showSignIn && (
          <div style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)'
          }}>
            <SignIn onClose={() => setShowSignIn(false)} />
          </div>
        )}

        <IonCard>
          <IonCardHeader>
            <IonCardTitle>사용자 정보</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel position="stacked">나이</IonLabel>
              <IonInput
                type="number"
                value={age}
                placeholder="나이를 입력하세요"
                onIonInput={(e) => handleAgeChange(e.detail.value!)}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">BMI</IonLabel>
              <IonInput
                type="number"
                value={bmi}
                placeholder="BMI를 입력하세요"
                onIonInput={(e) => handleBmiChange(e.detail.value!)}
              />
            </IonItem>
          </IonCardContent>
        </IonCard>

        <IonCard>
          <IonCardHeader>
            <IonCardTitle>설정</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonButton expand="block" onClick={() => setShowSignIn(true)}>
              로그인
            </IonButton>
          </IonCardContent>
        </IonCard>
      </IonContent>
    </IonPage>
  );
};

export default User;

