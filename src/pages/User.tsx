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
  IonButton as IonModalButton,
  IonText,
  IonAlert,
  IonIcon,
} from '@ionic/react';
import { refreshOutline, closeOutline } from 'ionicons/icons';
import { LocalNotifications, ActionPerformed, LocalNotificationSchema } from '@capacitor/local-notifications';
import { Capacitor } from '@capacitor/core';
import SignIn from '../components/SignIn';
import './User.css';
import { autoDetectServerUrl, getServerUrl } from '../services/ServerConfig';
import IotService from '../services/IotService';
import ModelService from '../services/ModelService';
import HealthDataService from '../services/HealthDataService';

const User: React.FC = () => {
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [gender, setGender] = useState<string>('0'); // 0: 여성, 1: 남성
  const [feedbackTime, setFeedbackTime] = useState<string>('22:00'); // 기본값: 오후 10시
  const [showFeedbackModal, setShowFeedbackModal] = useState<boolean>(false);
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [showResetAlert, setShowResetAlert] = useState<boolean>(false);
  const [feedbackCount, setFeedbackCount] = useState<number>(0);
  const [isFeedbackDisabled, setIsFeedbackDisabled] = useState<boolean>(false);

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
    
    // 서버 URL 자동 감지 (앱이 완전히 로드된 후 백그라운드에서 실행)
    // 앱 시작 시 실행하지 않고, 나중에 필요할 때만 실행
    setTimeout(() => {
      const detectServerUrl = async () => {
        try {
          const serverUrl = await autoDetectServerUrl();
          console.log('✅ 서버 URL 자동 감지 완료:', serverUrl);
          // 모든 서비스의 baseUrl 업데이트
          IotService.updateBaseUrl(serverUrl);
          ModelService.updateBaseUrl(serverUrl);
          HealthDataService.updateBaseUrl(serverUrl);
        } catch (err) {
          console.error('서버 URL 자동 감지 실패:', err);
          // 오류가 발생해도 앱은 계속 작동하도록
        }
      };
      detectServerUrl();
    }, 3000); // 3초 후에 실행하여 앱이 먼저 완전히 로드되도록
    
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

  const fetchFeedbackCount = async () => {
    try {
      const apiBaseUrl = getServerUrl();
      const response = await fetch(`${apiBaseUrl}/feedback/count`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        const count = result.count || 0;
        setFeedbackCount(count);
        setIsFeedbackDisabled(count >= 7);
      } else {
        console.error('피드백 카운트 조회 실패:', response.status);
      }
    } catch (err) {
      console.error('피드백 카운트 조회 중 오류:', err);
    }
  };

  const handleFeedbackSubmit = async (feedback: 'hot' | 'cold' | 'comfortable') => {
    try {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      const apiBaseUrl = getServerUrl();
      
      console.log('📤 피드백 전송 시작:', { feedback, apiBaseUrl });
      
      // 타임아웃 추가 (10초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const response = await fetch(`${apiBaseUrl}/temperature_feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            feedback: feedback,
            date: new Date().toISOString()
          }),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 피드백 저장 완료:', result);
          setShowFeedbackModal(false);
          alert('✅ 피드백이 저장되었습니다.');
          // 피드백 카운트 업데이트
          await fetchFeedbackCount();
        } else {
          const errorText = await response.text();
          console.error('❌ 피드백 저장 실패:', response.status, response.statusText, errorText);
          alert(`피드백 저장 실패: ${response.status} - ${errorText}`);
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        
        if (fetchError.name === 'AbortError') {
          console.error('❌ 요청 타임아웃 (10초 초과)');
          alert('요청 시간이 초과되었습니다. 서버가 실행 중인지 확인해주세요.');
        } else {
          console.error('❌ 피드백 저장 중 오류:', fetchError);
          // Mixed Content 경고는 무시하고 실제로 요청이 성공했는지 확인
          console.log('💡 Mixed Content 경고가 발생했지만, MIXED_CONTENT_ALWAYS_ALLOW 설정으로 요청이 성공했을 수 있습니다.');
          alert(`피드백 저장 중 오류 발생: ${fetchError.message || fetchError}\n\n서버 로그를 확인해주세요.`);
        }
      }
    } catch (err: any) {
      console.error('❌ 피드백 저장 중 예외:', err);
      alert(`피드백 저장 중 예외 발생: ${err.message || err}`);
    }
  };

  // 알림 클릭 및 수신 이벤트 리스너
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      let actionListener: any = null;
      let receivedListener: any = null;
      
      // 알림 클릭 이벤트
      LocalNotifications.addListener('localNotificationActionPerformed', (action: ActionPerformed) => {
        if (action.notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener: any) => {
        actionListener = listener;
      });
      
      // 알림 수신 이벤트 (앱이 포그라운드에 있을 때)
      LocalNotifications.addListener('localNotificationReceived', (notification: LocalNotificationSchema) => {
        if (notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener: any) => {
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

  // 다크모드 상태 불러오기 (Home 탭에서 관리하므로 여기서는 불러오기만)
  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    if (savedDarkMode) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, []);

  // 피드백 카운트 조회
  useEffect(() => {
    fetchFeedbackCount();
    // 30초마다 피드백 카운트 업데이트
    const interval = setInterval(() => {
      fetchFeedbackCount();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleResetFeedbackPeriod = async () => {
    try {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      const apiBaseUrl = getServerUrl();
      
      console.log('📤 피드백 기간 재갱신 요청:', apiBaseUrl);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const response = await fetch(`${apiBaseUrl}/feedback/reset`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 피드백 기간 재갱신 완료:', result);
          alert(result.message || '✅ 피드백 기간이 재갱신되었습니다.');
          
          // 재갱신 후 알림 다시 스케줄
          await scheduleDailyNotification();
          // 피드백 카운트 업데이트
          await fetchFeedbackCount();
        } else {
          const errorText = await response.text();
          console.error('❌ 피드백 기간 재갱신 실패:', response.status, response.statusText, errorText);
          alert(`피드백 기간 재갱신 실패: ${response.status} - ${errorText}`);
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        
        if (fetchError.name === 'AbortError') {
          console.error('❌ 요청 타임아웃 (10초 초과)');
          alert('요청 시간이 초과되었습니다. 서버가 실행 중인지 확인해주세요.');
        } else {
          console.error('❌ 피드백 기간 재갱신 중 오류:', fetchError);
          alert(`피드백 기간 재갱신 중 오류 발생: ${fetchError.message || fetchError}`);
        }
      }
    } catch (err: any) {
      console.error('❌ 피드백 기간 재갱신 중 예외:', err);
      alert(`피드백 기간 재갱신 중 예외 발생: ${err.message || err}`);
    }
  };

  return (
    <IonPage className="user-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>사용자</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        {/* 별 배경 효과 (다크모드) */}
        <div className="stars-background"></div>
        
        {/* 로그인 모달 */}
        {showSignIn && (
          <div className="login-modal-backdrop" style={{ 
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

        <IonCard className="user-info-card">
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

        <IonCard className="feedback-settings-card">
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
            <IonButton 
              expand="block" 
              className="feedback-submit-button"
              onClick={() => {
                fetchFeedbackCount(); // 모달 열 때 카운트 다시 확인
                setShowFeedbackModal(true);
              }} 
              disabled={isFeedbackDisabled}
              style={{ marginTop: '16px' }}
            >
              지금 피드백 남기기 {!isFeedbackDisabled && `(${feedbackCount}/7)`}
            </IonButton>
            {isFeedbackDisabled ? (
              <IonText color="medium" style={{ display: 'block', textAlign: 'center', marginTop: '8px', fontSize: '14px' }}>
                피드백을 7번 완료했습니다. 재갱신 버튼을 눌러 다시 시작하세요.
              </IonText>
            ) : (
              <IonText color="medium" style={{ display: 'block', textAlign: 'center', marginTop: '8px', fontSize: '14px' }}>
                남은 피드백: {7 - feedbackCount}번
              </IonText>
            )}
          </IonCardContent>
        </IonCard>

        {/* 온도 범위 관리 - 헤더 없이 버튼만 */}
        <div className="temperature-range-management-section">
          <IonButton 
            expand="block" 
            className="reset-feedback-button"
            onClick={() => setShowResetAlert(true)}
          >
            <IonIcon icon={refreshOutline} slot="start" />
            온도 범위 재갱신
          </IonButton>
        </div>

        <IonCard className="settings-card">
          <IonCardHeader>
            <IonCardTitle>설정</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonButton expand="block" onClick={() => setShowSignIn(true)} style={{ marginTop: '16px' }}>
              로그인
            </IonButton>
          </IonCardContent>
        </IonCard>

        {/* 하단 여백 추가 (스크롤 끝까지 내려가도록) */}
        <div style={{ height: '80px', width: '100%' }}></div>

        {/* 피드백 모달 */}
        <IonModal 
          isOpen={showFeedbackModal} 
          onDidDismiss={() => setShowFeedbackModal(false)}
          backdropDismiss={true}
          className="feedback-modal"
        >
          <IonContent className="feedback-content-wrapper" scrollY={false}>
            <div className="feedback-card">
              <div className="feedback-header">
                <h1>온도 피드백</h1>
                <button 
                  className="feedback-close-button"
                  onClick={() => setShowFeedbackModal(false)}
                  aria-label="닫기"
                >
                  <IonIcon icon={closeOutline} />
                </button>
              </div>
              <div className="feedback-body">
                <h2 className="feedback-title">오늘밤 온도는 어땠나요?</h2>
                <div className="feedback-emoji-container">
                  <div 
                    className="feedback-emoji-item hot-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('hot')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">🔥</div>
                    <div className="feedback-text">더웠어요</div>
                  </div>
                  <div 
                    className="feedback-emoji-item comfortable-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('comfortable')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">🍀</div>
                    <div className="feedback-text">쾌적했어요</div>
                  </div>
                  <div 
                    className="feedback-emoji-item cold-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('cold')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">❄️</div>
                    <div className="feedback-text">추웠어요</div>
                  </div>
                </div>
              </div>
            </div>
          </IonContent>
        </IonModal>

        {/* 재갱신 확인 알림 */}
        <IonAlert
          isOpen={showResetAlert}
          onDidDismiss={() => setShowResetAlert(false)}
          header="온도 범위 재갱신"
          message="재갱신을 하게되면 다시 7번의 피드백을 해주셔야 합니다. 현재 저장된 임계값부터 다시 7번의 피드백을 받아 조정합니다. 계속하시겠습니까?"
          buttons={[
            {
              text: '취소',
              role: 'cancel',
              handler: () => {
                setShowResetAlert(false);
              }
            },
            {
              text: '확인',
              handler: () => {
                handleResetFeedbackPeriod();
                setShowResetAlert(false);
              }
            }
          ]}
        />
      </IonContent>
    </IonPage>
  );
};

export default User;

