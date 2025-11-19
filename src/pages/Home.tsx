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
  IonSelect,
  IonSelectOption,
} from '@ionic/react';
import { ModelService, HealthDataService, IotService } from '../services';
import { getServerUrl } from '../services/ServerConfig';
import ChartDataService, {
  NightChartData,
  TemperatureDataPoint,
  HeartRateDataPoint,
} from '../services/ChartDataService';
import TemperatureChart from '../components/TemperatureChart';
import HeartRateChart from '../components/HeartRateChart';
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

  // 차트 데이터 상태
  const [chartData, setChartData] = useState<NightChartData | null>(null);
  const [lastCollectionTime, setLastCollectionTime] = useState<number>(0);
  const collectionIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // 차트 데이터 로드
  const loadChartData = () => {
    const data = ChartDataService.getTodayData();
    setChartData(data);
  };

  // DB에서 차트 데이터 로드
  const loadChartDataFromDB = async () => {
    try {
      console.log('📊 DB에서 차트 데이터 로드 시작...');
      const baseUrl = getServerUrl();
      
      // 오늘 날짜의 빈 데이터 구조 생성
      const today = new Date().toISOString().split('T')[0];
      const dbChartData: NightChartData = {
        date: today,
        temperatureData: [],
        heartRateData: [],
        lastUpdated: new Date().toISOString(),
      };
      
      // 1. 심박수 데이터 가져오기 (predicted_results)
      try {
        const heartRateResponse = await fetch(`${baseUrl}/chart/heartrate?hours=12`);
        if (heartRateResponse.ok) {
          const heartRateData = await heartRateResponse.json();
          if (heartRateData.success && heartRateData.data) {
            // DB 데이터를 차트 형식으로 변환
            heartRateData.data.forEach((point: any) => {
              const timestamp = new Date(point.timestamp);
              dbChartData.heartRateData.push({
                timestamp: point.timestamp,
                hour: point.hour,
                minute: point.minute,
                heartRate: point.heartRate,
              });
            });
            console.log(`✅ 심박수 데이터 ${heartRateData.count}개 로드 완료`);
          }
        }
      } catch (error) {
        console.error('심박수 데이터 로드 실패:', error);
      }
      
      // 2. 온도 데이터 가져오기 (test_script_logs)
      try {
        const tempResponse = await fetch(`${baseUrl}/chart/temperature?hours=12`);
        if (tempResponse.ok) {
          const tempData = await tempResponse.json();
          if (tempData.success && tempData.data) {
            // DB 데이터를 차트 형식으로 변환
            tempData.data.forEach((point: any) => {
              dbChartData.temperatureData.push({
                timestamp: point.timestamp,
                hour: point.hour,
                minute: point.minute,
                predictedTemperature: point.predictedTemperature,
                temperatureCategory: point.temperatureCategory,
                currentTemperature: point.currentTemperature,
                targetTemperature: point.targetTemperature,
              });
            });
            console.log(`✅ 온도 데이터 ${tempData.count}개 로드 완료`);
          }
        }
      } catch (error) {
        console.error('온도 데이터 로드 실패:', error);
      }
      
      // 3. DB 데이터가 있으면 localStorage에 저장하고 차트에 표시
      if (dbChartData.temperatureData.length > 0 || dbChartData.heartRateData.length > 0) {
        try {
          localStorage.setItem('night_chart_data', JSON.stringify(dbChartData));
          setChartData(dbChartData);
          console.log('✅ DB 데이터를 차트에 반영 완료');
        } catch (error) {
          console.error('차트 데이터 저장 실패:', error);
        }
      } else {
        // DB 데이터가 없으면 기존 데이터 로드
        loadChartData();
      }
    } catch (error) {
      console.error('DB 차트 데이터 로드 실패:', error);
      // 실패 시 기존 데이터 로드
      loadChartData();
    }
  };

  // 1시간마다 데이터 수집 (로컬 저장용 - 필요시 사용)
  const collectChartData = async () => {
    try {
      console.log('📊 차트 데이터 수집 시작...');
      
      // 1. 건강 데이터 가져오기 (심박수, HRV, 산소포화도)
      const healthData = await HealthDataService.getLatestHealthData();
      
      if (!healthData.success || !healthData.data) {
        console.warn('건강 데이터를 가져올 수 없습니다.');
        return;
      }

      const heartRate = healthData.data.heartRate?.value;
      const hrv = healthData.data.hrv?.value;
      const oxygenSaturation = healthData.data.oxygenSaturation?.value;

      if (!heartRate || !hrv || !oxygenSaturation) {
        console.warn('건강 데이터가 불완전합니다.');
        return;
      }

      // 2. 예측 수행 (기본값 사용 - 실제로는 사용자 정보 필요)
      let predictedTemp = 0;
      let temperatureCategory: '더움' | '추움' | '적정' = '적정';
      
      try {
        // 기본값으로 예측 시도 (실제로는 사용자 정보 필요)
        const prediction = await ModelService.predictTemperature({
          heartRate,
          hrv,
          bmi: 22.0, // 기본값
          oxygenSaturation,
          gender: 'MALE', // 기본값
          age: 30, // 기본값
        });

        if (prediction.success) {
          predictedTemp = prediction.predictedTemperature;
          // 서버 응답 형식 변환
          // 서버는 '적정', '추움', '더움'을 반환하고 ModelService는 그대로 전달
          const serverCategory = prediction.temperatureCategory;
          if (serverCategory === '더움' || serverCategory === 'HOT') {
            temperatureCategory = '더움';
          } else if (serverCategory === '추움' || serverCategory === 'COLD') {
            temperatureCategory = '추움';
          } else {
            temperatureCategory = '적정';
          }
        }
      } catch (error) {
        console.error('예측 실패:', error);
      }

      // 3. 현재 온도와 목표 온도 가져오기
      let currentTemp: number | null = null;
      let targetTemp: number | null = null;

      try {
        const iotStatus = await IotService.getStatus();
        currentTemp = iotStatus.currentTemperature;
        targetTemp = iotStatus.state.targetTemperature;
      } catch (error) {
        console.error('IoT 상태 조회 실패:', error);
      }

      // 4. 데이터 저장
      ChartDataService.addTemperatureDataPoint(
        predictedTemp,
        temperatureCategory,
        currentTemp,
        targetTemp
      );

      if (heartRate) {
        ChartDataService.addHeartRateDataPoint(heartRate);
      }

      // 5. 차트 데이터 다시 로드
      loadChartData();
      setLastCollectionTime(Date.now());

      console.log('✅ 차트 데이터 수집 완료');
    } catch (error) {
      console.error('차트 데이터 수집 실패:', error);
    }
  };

  // 수면 모드 상태 주기적 업데이트
  useEffect(() => {
    fetchSleepModeStatus();
    const interval = setInterval(() => {
      fetchSleepModeStatus();
    }, 60000); // 1분마다 업데이트

    return () => clearInterval(interval);
  }, []);

  // 테스트 데이터 생성 함수
  const generateTestData = () => {
    const now = new Date();
    const testData: NightChartData = {
      date: now.toISOString().split('T')[0],
      temperatureData: [],
      heartRateData: [],
      lastUpdated: now.toISOString(),
    };

    // 12시간치 테스트 데이터 생성 (1시간 간격) - 최근 12시간
    const currentHour = now.getHours();
    const startHour = currentHour >= 12 ? currentHour - 11 : (currentHour + 24) - 11;
    
    for (let i = 0; i < 12; i++) {
      const hour = (startHour + i) % 24;
      const minute = hour === 0 ? 30 : 0; // 첫 번째는 30분, 나머지는 0분
      const timestamp = new Date(now);
      timestamp.setHours(hour, minute, 0, 0);

      // 온도 데이터 (다양한 패턴)
      let predictedTemp = 34.5 + Math.sin((hour - 6) * Math.PI / 12) * 1.5; // 34.5~36.5 범위
      let category: '더움' | '추움' | '적정' = '적정';
      if (predictedTemp < 34.5) {
        category = '추움';
        predictedTemp = 33.5 + Math.random() * 0.8; // 33.5~34.3
      } else if (predictedTemp > 35.6) {
        category = '더움';
        predictedTemp = 35.7 + Math.random() * 0.8; // 35.7~36.5
      } else {
        predictedTemp = 34.5 + Math.random() * 1.1; // 34.5~35.6
      }

      testData.temperatureData.push({
        timestamp: timestamp.toISOString(),
        hour,
        minute,
        predictedTemperature: Number(predictedTemp.toFixed(1)),
        temperatureCategory: category,
        currentTemperature: 24.0 + Math.random() * 3, // 24~27도
        targetTemperature: 25.0 + Math.random() * 2, // 25~27도
      });

      // 심박수 데이터 (60~80 bpm 범위)
      const heartRate = 60 + Math.sin((hour - 6) * Math.PI / 12) * 10 + Math.random() * 5;
      testData.heartRateData.push({
        timestamp: timestamp.toISOString(),
        hour,
        minute,
        heartRate: Math.round(heartRate),
      });
    }

    // localStorage에 저장
    try {
      localStorage.setItem('night_chart_data', JSON.stringify(testData));
      setChartData(testData);
      console.log('✅ 테스트 데이터 생성 완료:', testData);
    } catch (error) {
      console.error('테스트 데이터 저장 실패:', error);
    }
  };

  // 차트 데이터 초기 로드 및 DB에서 데이터 가져오기
  useEffect(() => {
    // 초기 데이터 로드
    loadChartData();

    // DB에서 차트 데이터 로드 (predicted_results, test_script_logs)
    loadChartDataFromDB();

    // 테스트 데이터가 없으면 생성 (DB 데이터가 없을 때만)
    setTimeout(() => {
      const existingData = ChartDataService.getTodayData();
      if (!existingData || existingData.temperatureData.length === 0) {
        console.log('📊 테스트 데이터 생성 중...');
        generateTestData();
      }
    }, 2000); // DB 로드 후 확인

    // 주기적으로 DB에서 데이터 갱신 (5분마다)
    collectionIntervalRef.current = setInterval(() => {
      loadChartDataFromDB();
    }, 300000); // 5분

    return () => {
      if (collectionIntervalRef.current) {
        clearInterval(collectionIntervalRef.current);
      }
    };
  }, []);

  return (
    <IonPage className="home-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>홈</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>

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

          {/* 온도 차트 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>하룻밤 온도 변화</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              {chartData && chartData.temperatureData.length > 0 ? (
                <>
                  <TemperatureChart data={chartData.temperatureData} />
                  <IonText color="medium">
                    <p style={{ fontSize: '12px', marginTop: '10px', textAlign: 'center' }}>
                      마지막 업데이트: {new Date(chartData.lastUpdated).toLocaleTimeString()}
                    </p>
                  </IonText>
                </>
              ) : (
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <IonText color="medium">
                    <p>데이터가 없습니다. 1시간마다 자동으로 데이터가 수집됩니다.</p>
                  </IonText>
                </div>
              )}
            </IonCardContent>
          </IonCard>

          {/* 심박수 차트 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>하룻밤 심박수 변화</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              {chartData && chartData.heartRateData.length > 0 ? (
                <>
                  <HeartRateChart data={chartData.heartRateData} />
                  <IonText color="medium">
                    <p style={{ fontSize: '12px', marginTop: '10px', textAlign: 'center' }}>
                      마지막 업데이트: {new Date(chartData.lastUpdated).toLocaleTimeString()}
                    </p>
                  </IonText>
                </>
              ) : (
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <IonText color="medium">
                    <p>데이터가 없습니다. 1시간마다 자동으로 데이터가 수집됩니다.</p>
                  </IonText>
                </div>
              )}
            </IonCardContent>
          </IonCard>

          {/* 모델 테스트 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>모델 테스트</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonButton expand="block" onClick={handleTestModel} disabled={loading} className="model-test-button">
                {loading ? <IonSpinner name="crescent" /> : '모델 테스트'}
              </IonButton>
            </IonCardContent>
          </IonCard>
        </div>

      </IonContent>
    </IonPage>
  );
};

export default Home;

