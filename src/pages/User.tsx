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
  IonButton,
  IonSelect,
  IonSelectOption,
  IonModal,
  IonButtons,
  IonButton as IonModalButton
} from '@ionic/react';
import { LocalNotifications } from '@capacitor/local-notifications';
import { Capacitor } from '@capacitor/core';
import SignIn from '../components/SignIn';
import './User.css';

const User: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [gender, setGender] = useState<string>('0'); // 0: 여성, 1: 남성
  const [feedbackTime, setFeedbackTime] = useState<string>('22:00'); // 기본값: 오후 10시
  const [showFeedbackModal, setShowFeedbackModal] = useState<boolean>(false);
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);

  const requestNotificationPermission = async () => {
    try {
      const status = await LocalNotifications.checkPermissions();
      if (status.display !== 'granted') {
        await LocalNotifications.requestPermissions();
      }
    } catch (err) {
      console.log('알림 권한 요청 실패:', err);
    }
  };

  const scheduleDailyNotification = async () => {
    try {
      const savedTime = localStorage.getItem('feedbackTime') || '22:00';
      const [hours, minutes] = savedTime.split(':').map(Number);
      
      // 기존 알림 취소
      await LocalNotifications.cancel({ notifications: [{ id: 1 }] });
      
      // 매일 지정된 시간에 알림 스케줄
      await LocalNotifications.schedule({
        notifications: [
          {
            title: '온도 피드백',
            body: '오늘밤 온도는 어땠나요?',
            id: 1,
            schedule: {
              every: 'day',
              on: {
                hour: hours,
                minute: minutes
              }
            },
            actionTypeId: 'FEEDBACK_ACTION',
            extra: {
              type: 'temperature_feedback'
            }
          }
        ]
      });
      
      console.log(`✅ 매일 ${savedTime}에 알림이 스케줄되었습니다.`);
    } catch (err) {
      console.log('알림 스케줄 실패:', err);
    }
  };

  useEffect(() => {
    // 저장된 나이, BMI, 성별, 피드백 시간 불러오기
    try {
      const savedAge = localStorage.getItem('userAge');
      const savedBmi = localStorage.getItem('userBmi');
      const savedGender = localStorage.getItem('userGender');
      const savedFeedbackTime = localStorage.getItem('feedbackTime');
      if (savedAge) setAge(savedAge);
      if (savedBmi) setBmi(savedBmi);
      if (savedGender) setGender(savedGender);
      if (savedFeedbackTime) setFeedbackTime(savedFeedbackTime);
    } catch (err) {
      console.log('저장된 사용자 정보 불러오기 실패:', err);
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
    
    // 알림 권한 요청 및 기존 알림 스케줄 확인
    if (Capacitor.isNativePlatform()) {
      requestNotificationPermission();
      scheduleDailyNotification();
    }
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
            bmi: bmi || '',
            gender: gender || '0'
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
            bmi: value || '',
            gender: gender || '0'
          });
        } catch (err) {
          console.log('BMI UserDefaults 저장 실패:', err);
        }
      }
    } catch (err) {
      console.log('BMI 저장 실패:', err);
    }
  };

  const handleGenderChange = async (value: string) => {
    setGender(value);
    try {
      localStorage.setItem('userGender', value || '0');
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: age || '',
            bmi: bmi || '',
            gender: value || '0'
          });
        } catch (err) {
          console.log('성별 UserDefaults 저장 실패:', err);
        }
      }
    } catch (err) {
      console.log('성별 저장 실패:', err);
    }
  };

  const handleFeedbackTimeChange = async (value: string) => {
    setFeedbackTime(value);
    try {
      localStorage.setItem('feedbackTime', value || '22:00');
      // 알림 재스케줄
      if (Capacitor.isNativePlatform()) {
        await scheduleDailyNotification();
      }
    } catch (err) {
      console.log('피드백 시간 저장 실패:', err);
    }
  };

  const handleFeedbackSubmit = async (feedback: 'hot' | 'cold' | 'comfortable') => {
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 
        (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios' 
          ? 'http://192.168.68.74:3000' 
          : 'http://localhost:3000');
      
      const response = await fetch(`${apiBaseUrl}/temperature_feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feedback: feedback,
          date: new Date().toISOString()
        }),
      });

      if (response.ok) {
        console.log('✅ 피드백 저장 완료');
        setShowFeedbackModal(false);
      } else {
        console.error('피드백 저장 실패');
      }
    } catch (err) {
      console.error('피드백 저장 중 오류:', err);
    }
  };

  // 알림 클릭 및 수신 이벤트 리스너
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      let actionListener: any = null;
      let receivedListener: any = null;
      
      // 알림 클릭 이벤트
      LocalNotifications.addListener('localNotificationActionPerformed', (action) => {
        if (action.notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener) => {
        actionListener = listener;
      });
      
      // 알림 수신 이벤트 (앱이 포그라운드에 있을 때)
      LocalNotifications.addListener('localNotificationReceived', (notification) => {
        if (notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener) => {
        receivedListener = listener;
      });
      
      // 컴포넌트 언마운트 시 리스너 제거
      return () => {
        if (actionListener) {
          actionListener.remove();
        }
        if (receivedListener) {
          receivedListener.remove();
        }
      };
    }
  }, []);

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
            <IonItem>
              <IonLabel position="stacked">성별</IonLabel>
              <IonSelect
                value={gender}
                placeholder="성별을 선택하세요"
                onIonChange={(e) => handleGenderChange(e.detail.value)}
              >
                <IonSelectOption value="0">여성</IonSelectOption>
                <IonSelectOption value="1">남성</IonSelectOption>
              </IonSelect>
            </IonItem>
          </IonCardContent>
        </IonCard>

        <IonCard>
          <IonCardHeader>
            <IonCardTitle>피드백 알림 설정</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel position="stacked">알림 시간</IonLabel>
              <IonInput
                type="time"
                value={feedbackTime}
                onIonInput={(e) => handleFeedbackTimeChange(e.detail.value!)}
              />
            </IonItem>
            <IonButton expand="block" onClick={() => setShowFeedbackModal(true)} style={{ marginTop: '16px' }}>
              지금 피드백 남기기
            </IonButton>
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

        {/* 피드백 모달 */}
        <IonModal isOpen={showFeedbackModal} onDidDismiss={() => setShowFeedbackModal(false)}>
          <IonHeader>
            <IonToolbar>
              <IonTitle>온도 피드백</IonTitle>
              <IonButtons slot="end">
                <IonModalButton onClick={() => setShowFeedbackModal(false)}>닫기</IonModalButton>
              </IonButtons>
            </IonToolbar>
          </IonHeader>
          <IonContent className="ion-padding">
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <h2 className="feedback-title">오늘밤 온도는 어땠나요?</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '32px' }}>
                <IonButton 
                  expand="block" 
                  color="danger"
                  onClick={() => handleFeedbackSubmit('hot')}
                  style={{ height: '60px', fontSize: '18px' }}
                >
                  더웠어요🔥
                </IonButton>
                <IonButton 
                  expand="block" 
                  onClick={() => handleFeedbackSubmit('comfortable')}
                  className="comfortable-feedback-button"
                  style={{ 
                    height: '60px', 
                    fontSize: '18px',
                    background: 'linear-gradient(135deg, #A0E8A0 0%, #90E890 50%, #88E800 100%)',
                    borderRadius: '12px',
                    boxShadow: '0 4px 16px rgba(136, 232, 0, 0.4)',
                    color: 'white',
                    fontWeight: '600',
                    border: 'none',
                    outline: 'none'
                  }}
                >
                  쾌적했어요🍀
                </IonButton>
                <IonButton 
                  expand="block" 
                  onClick={() => handleFeedbackSubmit('cold')}
                  className="cold-feedback-button"
                  style={{ 
                    height: '60px', 
                    fontSize: '18px',
                    background: 'linear-gradient(135deg, #E0F6FF 0%, #87CEEB 50%, #B0E0E6 100%)',
                    borderRadius: '12px',
                    boxShadow: '0 4px 16px rgba(135, 206, 235, 0.4)',
                    color: 'white',
                    fontWeight: '600',
                    border: 'none',
                    outline: 'none'
                  }}
                >
                  추웠어요❄️
                </IonButton>
              </div>
            </div>
          </IonContent>
        </IonModal>
      </IonContent>
    </IonPage>
  );
};

export default User;

