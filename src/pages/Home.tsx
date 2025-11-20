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
  IonButton,
  IonText,
  IonSpinner,
  IonItem,
  IonLabel,
  IonSelect,
  IonSelectOption,
  IonToggle,
} from '@ionic/react';
import { ModelService, HealthDataService, IotService } from '../services';
import { getServerUrl } from '../services/ServerConfig';
import './Home.css';

const Home: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<{
    temperature: number;
    status: 'COMFORTABLE' | 'COLD' | 'HOT';
  } | null>(null);
  
  // 수면 모드 관련 상태
  const [sleepModeActive, setSleepModeActive] = useState(false);
  const [remainingTime, setRemainingTime] = useState<{ hours: number; minutes: number }>({ hours: 0, minutes: 0 });
  const [sleepDuration, setSleepDuration] = useState<string>('8'); // 기본 8시간

  // 다크모드 관련 상태
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);

  const handleTestModel = async () => {
    setLoading(true);
    try {
      console.log('모델 테스트 시작...');
      const result = await ModelService.testModel();
      console.log('모델 테스트 결과:', result);
      alert(result.message);
    } catch (error: any) {
      console.error('Model test failed:', error);
      alert(error.message || '서버 연결 실패');
    } finally {
      setLoading(false);
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'COMFORTABLE':
        return '쾌적함';
      case 'COLD':
        return '추움';
      case 'HOT':
        return '더움';
      default:
        return status;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMFORTABLE':
        return 'success';
      case 'COLD':
        return 'primary';
      case 'HOT':
        return 'danger';
      default:
        return 'medium';
    }
  };

  // 수면 모드 상태 조회
  const fetchSleepModeStatus = async () => {
    try {
      const baseUrl = getServerUrl();
      const response = await fetch(`${baseUrl}/sleep-mode/status`);
      if (response.ok) {
        const data = await response.json();
        setSleepModeActive(data.active);
        if (data.active) {
          setRemainingTime({
            hours: Math.floor(data.remaining_hours),
            minutes: data.remaining_minutes % 60
          });
        }
      }
    } catch (error) {
      console.error('수면 모드 상태 조회 실패:', error);
    }
  };

  // 수면 모드 시작
  const handleStartSleepMode = async () => {
    const duration = parseFloat(sleepDuration);
    if (isNaN(duration) || duration <= 0) {
      alert('올바른 시간을 선택해주세요.');
      return;
    }

    setLoading(true);
    try {
      const baseUrl = getServerUrl();
      const response = await fetch(`${baseUrl}/sleep-mode/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ duration_hours: duration }),
      });

      if (response.ok) {
        const data = await response.json();
        setSleepModeActive(true);
        setRemainingTime({
          hours: Math.floor(data.duration_hours),
          minutes: Math.round((data.duration_hours % 1) * 60)
        });
        alert(data.message);
      } else {
        const errorData = await response.json();
        alert(errorData.detail || '수면 모드 시작에 실패했습니다.');
      }
    } catch (error: any) {
      console.error('수면 모드 시작 실패:', error);
      alert('수면 모드 시작에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 수면 모드 중지
  const handleStopSleepMode = async () => {
    setLoading(true);
    try {
      const baseUrl = getServerUrl();
      const response = await fetch(`${baseUrl}/sleep-mode/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSleepModeActive(false);
        setRemainingTime({ hours: 0, minutes: 0 });
        alert(data.message);
      } else {
        const errorData = await response.json();
        alert(errorData.detail || '수면 모드 중지에 실패했습니다.');
      }
    } catch (error: any) {
      console.error('수면 모드 중지 실패:', error);
      alert('수면 모드 중지에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 차트 관련 함수들 제거됨 (Health 탭으로 이동)

  // 수면 모드 상태 주기적 업데이트
  useEffect(() => {
    fetchSleepModeStatus();
    const interval = setInterval(() => {
      fetchSleepModeStatus();
    }, 60000); // 1분마다 업데이트

    return () => clearInterval(interval);
  }, []);

  // 다크모드 상태 불러오기
  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    setIsDarkMode(savedDarkMode);
    if (savedDarkMode) {
      document.body.classList.add('dark');
    }
  }, []);

  // 다크모드 토글 핸들러
  const handleDarkModeToggle = (enabled: boolean) => {
    setIsDarkMode(enabled);
    localStorage.setItem('darkMode', enabled.toString());
    if (enabled) {
      // 다크모드 클래스는 먼저 제거 (애니메이션 중에는 다크모드가 아님)
      document.body.classList.remove('dark');
      
      // 애니메이션 재생 시작
      const animationElement = document.querySelector('.dark-mode-animation') as HTMLElement;
      if (animationElement) {
        console.log('애니메이션 시작');
        
        // 기존 이벤트 리스너 제거
        const existingHandler = (animationElement as any).__animationEndHandler;
        if (existingHandler) {
          animationElement.removeEventListener('animationend', existingHandler);
        }
        
        // 클래스 제거 및 리플로우
        animationElement.classList.remove('playing');
        void animationElement.offsetWidth;
        
        // 다음 프레임에서 클래스 추가
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            animationElement.classList.add('playing');
            console.log('playing 클래스 추가됨', animationElement.classList.contains('playing'));
            
            // 스타일 확인
            const computedStyle = window.getComputedStyle(animationElement);
            console.log('애니메이션:', computedStyle.animation);
            console.log('배경 이미지:', computedStyle.backgroundImage);
          });
        });
        
        // 애니메이션 종료 후 다크모드 활성화
        const handleAnimationEnd = () => {
          console.log('애니메이션 종료');
          animationElement.classList.remove('playing');
          document.body.classList.add('dark');
        };
        animationElement.addEventListener('animationend', handleAnimationEnd, { once: true });
        (animationElement as any).__animationEndHandler = handleAnimationEnd;
        
        // 타임아웃으로도 처리 (안전장치)
        setTimeout(() => {
          if (animationElement.classList.contains('playing')) {
            console.log('타임아웃으로 애니메이션 종료 처리');
            animationElement.classList.remove('playing');
            document.body.classList.add('dark');
          }
        }, 1600);
      }
    } else {
      document.body.classList.remove('dark');
      // 애니메이션 재생 중지하고 첫 프레임으로 복귀
      const animationElement = document.querySelector('.dark-mode-animation') as HTMLElement;
      if (animationElement) {
        animationElement.classList.remove('playing');
        // 기존 이벤트 리스너 제거
        const existingHandler = (animationElement as any).__animationEndHandler;
        if (existingHandler) {
          animationElement.removeEventListener('animationend', existingHandler);
        }
      }
    }
  };

  // 차트 관련 함수들 제거됨 (Health 탭으로 이동)

  return (
    <IonPage className="home-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>홈</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        {/* 별 배경 효과 (다크모드) */}
        <div className="stars-background"></div>

        <div className="container">
          {/* 수면 모드 카드 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>수면 모드</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              {sleepModeActive ? (
                <div>
                  <IonText color="success">
                    <p style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '8px' }}>
                      😴 수면 모드 활성화 중
                    </p>
                  </IonText>
                  <IonText color="medium">
                    <p style={{ fontSize: '14px', marginBottom: '16px' }}>
                      남은 시간: {remainingTime.hours}시간 {remainingTime.minutes}분
                    </p>
                  </IonText>
                  <IonButton expand="block" color="danger" onClick={handleStopSleepMode} disabled={loading}>
                    {loading ? <IonSpinner name="crescent" /> : '수면 모드 중지'}
                  </IonButton>
                </div>
              ) : (
                <div>
                  <IonText color="medium">
                    <p style={{ fontSize: '14px', marginBottom: '16px' }}>
                      수면 모드를 시작하면 설정한 시간 동안만 자동 온도 조절이 동작합니다.
                    </p>
                  </IonText>
                  <IonItem style={{ marginBottom: '16px', borderRadius: '12px' }}>
                    <IonLabel position="stacked">동작 시간 선택</IonLabel>
                    <IonSelect
                      value={sleepDuration}
                      placeholder="시간 선택"
                      onIonChange={(e) => setSleepDuration(e.detail.value)}
                      interface="popover"
                    >
                      <IonSelectOption value="0.5">0.5시간</IonSelectOption>
                      <IonSelectOption value="1">1시간</IonSelectOption>
                      <IonSelectOption value="2">2시간</IonSelectOption>
                      <IonSelectOption value="3">3시간</IonSelectOption>
                      <IonSelectOption value="4">4시간</IonSelectOption>
                      <IonSelectOption value="5">5시간</IonSelectOption>
                      <IonSelectOption value="6">6시간</IonSelectOption>
                      <IonSelectOption value="7">7시간</IonSelectOption>
                      <IonSelectOption value="8">8시간</IonSelectOption>
                      <IonSelectOption value="9">9시간</IonSelectOption>
                      <IonSelectOption value="10">10시간</IonSelectOption>
                      <IonSelectOption value="11">11시간</IonSelectOption>
                      <IonSelectOption value="12">12시간</IonSelectOption>
                      <IonSelectOption value="13">13시간</IonSelectOption>
                      <IonSelectOption value="14">14시간</IonSelectOption>
                      <IonSelectOption value="15">15시간</IonSelectOption>
                      <IonSelectOption value="16">16시간</IonSelectOption>
                      <IonSelectOption value="17">17시간</IonSelectOption>
                      <IonSelectOption value="18">18시간</IonSelectOption>
                      <IonSelectOption value="19">19시간</IonSelectOption>
                      <IonSelectOption value="20">20시간</IonSelectOption>
                      <IonSelectOption value="21">21시간</IonSelectOption>
                      <IonSelectOption value="22">22시간</IonSelectOption>
                      <IonSelectOption value="23">23시간</IonSelectOption>
                      <IonSelectOption value="24">24시간</IonSelectOption>
                    </IonSelect>
                  </IonItem>
                  <IonButton 
                    expand="block" 
                    color="primary" 
                    onClick={handleStartSleepMode} 
                    disabled={loading}
                    className="sleep-start-button"
                  >
                    {loading ? <IonSpinner name="crescent" /> : '수면 시작'}
                  </IonButton>
                </div>
              )}
            </IonCardContent>
          </IonCard>

          {/* 다크모드 토글 */}
          <IonCard className="dark-mode-card">
            <IonCardContent>
              <div className="dark-mode-animation-wrapper">
                <div className={`dark-mode-animation ${isDarkMode ? 'playing' : ''}`}></div>
              </div>
              <IonItem style={{ borderRadius: '12px', marginTop: '16px' }}>
                <IonLabel>다크 모드</IonLabel>
                <IonToggle
                  checked={isDarkMode}
                  onIonChange={(e) => handleDarkModeToggle(e.detail.checked)}
                />
              </IonItem>
            </IonCardContent>
          </IonCard>

          {/* 예측 결과 */}
          {prediction && (
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>예측 결과</IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <div className="prediction-result">
                  <IonText color={getStatusColor(prediction.status)}>
                    <h1>{prediction.temperature.toFixed(1)}°C</h1>
                  </IonText>
                  <IonText color={getStatusColor(prediction.status)}>
                    <p className="status-text">{getStatusText(prediction.status)}</p>
                  </IonText>
                </div>
              </IonCardContent>
            </IonCard>
          )}

          {/* 차트는 Health 탭으로 이동됨 */}

        </div>

      </IonContent>
    </IonPage>
  );
};

export default Home;

