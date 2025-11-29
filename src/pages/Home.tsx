import { useState, useEffect, useRef } from 'react';
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
  IonInput,
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
  const [sleepDuration, setSleepDuration] = useState<string>('08:00'); // 기본 8시간 (시:분 형식)

  // 다크모드 관련 상태
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const animationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAnimatingRef = useRef<boolean>(false);
  const animationElementRef = useRef<HTMLElement | null>(null);

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
    const duration = timeToHours(sleepDuration);
    if (isNaN(duration) || duration <= 0 || duration > 24) {
      alert('올바른 시간을 선택해주세요. (0.5 ~ 24시간)');
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
        
        // 백그라운드 모니터링 비활성화 (워치 배터리 절약)
        // 앱을 키고 자게 할 거라 백그라운드 배달 불필요
        
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

  // 시:분 형식을 시간으로 변환 (예: "08:30" -> 8.5)
  const timeToHours = (timeStr: string): number => {
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours + (minutes / 60);
  };

  // 시간을 시:분 형식으로 변환 (예: 8.5 -> "08:30")
  const hoursToTime = (hours: number): string => {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  };

  // 시간 증가/감소 핸들러
  const handleDurationChange = (delta: number) => {
    const currentHours = timeToHours(sleepDuration);
    const newHours = Math.max(0.5, Math.min(24, currentHours + delta));
    setSleepDuration(hoursToTime(newHours));
  };

  // 시간 입력 핸들러
  const handleDurationInput = (timeStr: string) => {
    const hours = timeToHours(timeStr);
    if (hours >= 0.5 && hours <= 24) {
      setSleepDuration(timeStr);
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


  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      // 타임아웃 정리
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
      
      // 애니메이션 요소 정리
      const animationElement = animationElementRef.current;
      if (animationElement) {
        const existingHandler = (animationElement as any).__animationEndHandler;
        if (existingHandler) {
          animationElement.removeEventListener('animationend', existingHandler);
          animationElement.removeEventListener('animationiteration', existingHandler);
        }
        if ((animationElement as any).__animationTimeout) {
          clearTimeout((animationElement as any).__animationTimeout);
        }
      }
    };
  }, []);

  // 다크모드 토글 핸들러
  const handleDarkModeToggle = (enabled: boolean) => {
    // 이미 애니메이션이 진행 중이면 무시
    if (isAnimatingRef.current) {
      console.log('애니메이션 진행 중, 무시');
      return;
    }

    // 기존 타임아웃 정리
    if (animationTimeoutRef.current) {
      clearTimeout(animationTimeoutRef.current);
      animationTimeoutRef.current = null;
    }

    setIsDarkMode(enabled);
    localStorage.setItem('darkMode', enabled.toString());
    
    if (enabled) {
      // 다크모드 클래스는 먼저 제거 (애니메이션 중에는 다크모드가 아님)
      document.body.classList.remove('dark');
      
      // 애니메이션 재생 시작
      const animationElement = animationElementRef.current || 
        (document.querySelector('.dark-mode-animation') as HTMLElement);
      
      if (animationElement) {
        animationElementRef.current = animationElement;
        isAnimatingRef.current = true;
        console.log('애니메이션 시작');
        
        // 기존 이벤트 리스너 제거
        const existingHandler = (animationElement as any).__animationEndHandler;
        if (existingHandler) {
          animationElement.removeEventListener('animationend', existingHandler);
          animationElement.removeEventListener('animationiteration', existingHandler);
        }
        
        // 기존 타임아웃 정리
        if ((animationElement as any).__animationTimeout) {
          clearTimeout((animationElement as any).__animationTimeout);
        }
        
        // 클래스 제거 및 리플로우
        animationElement.classList.remove('playing');
        void animationElement.offsetWidth;
        
        // 다음 프레임에서 클래스 추가
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (!isAnimatingRef.current) return; // 취소되었는지 확인
            
            animationElement.classList.add('playing');
            console.log('playing 클래스 추가됨', animationElement.classList.contains('playing'));
          });
        });
        
        // 애니메이션 종료 후 다크모드 활성화
        const handleAnimationEnd = () => {
          console.log('애니메이션 종료');
          isAnimatingRef.current = false;
          animationElement.classList.remove('playing');
          document.body.classList.add('dark');
          
          // 이벤트 리스너 정리
          if ((animationElement as any).__animationEndHandler === handleAnimationEnd) {
            (animationElement as any).__animationEndHandler = null;
          }
          if ((animationElement as any).__animationTimeout) {
            clearTimeout((animationElement as any).__animationTimeout);
            (animationElement as any).__animationTimeout = null;
          }
        };
        
        // animationend와 animationiteration 모두 처리
        animationElement.addEventListener('animationend', handleAnimationEnd, { once: true });
        animationElement.addEventListener('animationiteration', (e) => {
          // iOS에서 animationiteration이 발생할 수 있으므로 무시
          console.log('animationiteration 이벤트 무시');
        }, { once: true });
        
        (animationElement as any).__animationEndHandler = handleAnimationEnd;
        
        // 타임아웃으로도 처리 (안전장치)
        const timeoutId = setTimeout(() => {
          if (animationElement.classList.contains('playing')) {
            console.log('타임아웃으로 애니메이션 종료 처리');
            handleAnimationEnd();
          }
        }, 1600);
        
        (animationElement as any).__animationTimeout = timeoutId;
        animationTimeoutRef.current = timeoutId;
      }
    } else {
      isAnimatingRef.current = false;
      document.body.classList.remove('dark');
      // 애니메이션 재생 중지하고 첫 프레임으로 복귀
      const animationElement = animationElementRef.current || 
        (document.querySelector('.dark-mode-animation') as HTMLElement);
      
      if (animationElement) {
        animationElement.classList.remove('playing');
        // 기존 이벤트 리스너 제거
        const existingHandler = (animationElement as any).__animationEndHandler;
        if (existingHandler) {
          animationElement.removeEventListener('animationend', existingHandler);
          animationElement.removeEventListener('animationiteration', existingHandler);
        }
        // 기존 타임아웃 정리
        if ((animationElement as any).__animationTimeout) {
          clearTimeout((animationElement as any).__animationTimeout);
          (animationElement as any).__animationTimeout = null;
        }
        (animationElement as any).__animationEndHandler = null;
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
                <div style={{ textAlign: 'center' }}>
                  <IonText>
                    <p style={{ 
                      fontSize: '18px', 
                      fontWeight: '600', 
                      marginTop: '20px',
                      marginBottom: '12px',
                      color: '#B895B6',
                      letterSpacing: '0.3px'
                    }}>
                      🌙 수면 모드 활성화 중 💤
                    </p>
                  </IonText>
                  <IonText>
                    <p style={{ 
                      fontSize: '15px', 
                      marginBottom: '20px',
                      color: '#66748D',
                      fontWeight: '500'
                    }}>
                      남은 시간: <span style={{ fontWeight: '600', color: '#C4A1C2' }}>{remainingTime.hours}시간 {remainingTime.minutes}분</span>
                    </p>
                  </IonText>
                  <IonButton expand="block" color="danger" onClick={handleStopSleepMode} disabled={loading}>
                    {loading ? <IonSpinner name="crescent" /> : '수면 모드 중지'}
                  </IonButton>
                </div>
              ) : (
                <div>
                  <div style={{ marginBottom: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                    <IonLabel style={{ fontSize: '16px', fontWeight: '500', marginTop: '8px' }} className="duration-label">
                      동작 시간 선택
                    </IonLabel>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: '300px' }}>
                      <button
                        onClick={() => handleDurationChange(-0.5)}
                        disabled={timeToHours(sleepDuration) <= 0.5}
                        className="duration-control-button"
                        style={{
                          width: '56px',
                          height: '56px',
                          borderRadius: '50%',
                          border: 'none',
                          background: 'linear-gradient(135deg, #C4A1C2 0%, #B895B6 100%)',
                          color: 'white',
                          fontSize: '28px',
                          fontWeight: 'bold',
                          cursor: timeToHours(sleepDuration) <= 0.5 ? 'not-allowed' : 'pointer',
                          opacity: timeToHours(sleepDuration) <= 0.5 ? 0.5 : 1,
                          boxShadow: '0 4px 12px rgba(196, 161, 194, 0.4)',
                          transition: 'all 0.2s ease',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          outline: 'none',
                          flexShrink: 0,
                        }}
                        onMouseDown={(e) => e.preventDefault()}
                      >
                        −
                      </button>
                      <IonInput
                        type="text"
                        inputMode="numeric"
                        value={sleepDuration}
                        onIonInput={(e) => {
                          const value = e.detail.value || '';
                          // HH:mm 형식으로만 입력 허용
                          const formatted = value.replace(/[^0-9:]/g, '');
                          if (formatted.length <= 5) {
                            setSleepDuration(formatted);
                          }
                        }}
                        onIonBlur={(e: any) => {
                          const value = e.detail?.value || sleepDuration;
                          // HH:mm 형식 검증 및 자동 포맷팅
                          const parts = value.split(':');
                          if (parts.length === 2) {
                            const hours = Math.min(23, Math.max(0, parseInt(parts[0]) || 0));
                            const minutes = Math.min(59, Math.max(0, parseInt(parts[1]) || 0));
                            // 30분 단위로 반올림
                            const roundedMinutes = Math.round(minutes / 30) * 30;
                            const finalMinutes = roundedMinutes === 60 ? 0 : roundedMinutes;
                            const finalHours = roundedMinutes === 60 ? Math.min(23, hours + 1) : hours;
                            const timeStr = `${String(finalHours).padStart(2, '0')}:${String(finalMinutes).padStart(2, '0')}`;
                            setSleepDuration(timeStr);
                          } else if (value.length === 4 && !value.includes(':')) {
                            // HHmm 형식으로 입력된 경우
                            const hours = Math.min(23, Math.max(0, parseInt(value.substring(0, 2)) || 0));
                            const minutes = Math.min(59, Math.max(0, parseInt(value.substring(2, 4)) || 0));
                            const roundedMinutes = Math.round(minutes / 30) * 30;
                            const finalMinutes = roundedMinutes === 60 ? 0 : roundedMinutes;
                            const finalHours = roundedMinutes === 60 ? Math.min(23, hours + 1) : hours;
                            const timeStr = `${String(finalHours).padStart(2, '0')}:${String(finalMinutes).padStart(2, '0')}`;
                            setSleepDuration(timeStr);
                          } else if (value.length === 0 || !value.includes(':')) {
                            // 형식이 맞지 않으면 기본값으로
                            setSleepDuration('08:00');
                          }
                        }}
                        placeholder="08:00"
                        className="sleep-duration-input"
                        style={{
                          width: 'auto',
                          textAlign: 'center',
                          margin: '0 auto',
                          fontSize: '32px',
                          fontWeight: '700',
                          color: '#66748D',
                          '--padding-start': '0',
                          '--padding-end': '0',
                          '--highlight-color': 'transparent',
                          '--highlight-color-focused': 'transparent',
                          outline: 'none',
                          border: 'none',
                        } as React.CSSProperties}
                      />
                      <button
                        onClick={() => handleDurationChange(0.5)}
                        disabled={timeToHours(sleepDuration) >= 24}
                        className="duration-control-button"
                        style={{
                          width: '56px',
                          height: '56px',
                          borderRadius: '50%',
                          border: 'none',
                          background: 'linear-gradient(135deg, #C4A1C2 0%, #B895B6 100%)',
                          color: 'white',
                          fontSize: '28px',
                          fontWeight: 'bold',
                          cursor: timeToHours(sleepDuration) >= 24 ? 'not-allowed' : 'pointer',
                          opacity: timeToHours(sleepDuration) >= 24 ? 0.5 : 1,
                          boxShadow: '0 4px 12px rgba(196, 161, 194, 0.4)',
                          transition: 'all 0.2s ease',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          outline: 'none',
                          flexShrink: 0,
                        }}
                        onMouseDown={(e) => e.preventDefault()}
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <IonButton 
                    expand="block" 
                    color="primary" 
                    onClick={handleStartSleepMode} 
                    disabled={loading}
                    className="sleep-start-button"
                  >
                    {loading ? <IonSpinner name="crescent" /> : '수면 시작'}
                  </IonButton>
                  <IonText>
                    <p style={{ fontSize: '14px', marginTop: '16px', marginBottom: '0', lineHeight: '1.6', textAlign: 'center', color: '#7C88A9' }}>
                      수면 모드를 시작하면 설정한 시간 동안만<br />
                      자동 온도 조절이 동작합니다.
                    </p>
                  </IonText>
                </div>
              )}
            </IonCardContent>
          </IonCard>

          {/* 다크모드 토글 */}
          <IonCard className="dark-mode-card">
            <IonCardContent>
              <div className="dark-mode-animation-wrapper">
                <div 
                  className="dark-mode-animation"
                  ref={(el) => {
                    if (el) {
                      animationElementRef.current = el;
                    }
                  }}
                ></div>
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

