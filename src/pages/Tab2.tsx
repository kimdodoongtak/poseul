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
  IonSelect,
  IonSelectOption,
  IonButton,
  IonText,
  IonSpinner,
} from '@ionic/react';
import { Capacitor } from '@capacitor/core';
import { ModelService, TemperaturePredictionRequest } from '../services';
import './Tab2.css';

interface HealthData {
  heartRate: { value: number; date: string } | null;
  hrv: { value: number; date: string } | null;
  oxygenSaturation: { value: number; date: string } | null;
}

const Tab2: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<{
    temperature: number;
    status: 'COMFORTABLE' | 'COLD' | 'HOT';
  } | null>(null);
  const [healthData, setHealthData] = useState<HealthData>({
    heartRate: null,
    hrv: null,
    oxygenSaturation: null,
  });
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [autoPredictEnabled, setAutoPredictEnabled] = useState<boolean>(false);

  const [formData, setFormData] = useState<TemperaturePredictionRequest>({
    heartRate: 0,
    hrv: 0,
    bmi: 0,
    oxygenSaturation: 0,
    gender: 'MALE',
    age: 0,
  });

  useEffect(() => {
    // HealthData 플러그인 로드 (iOS HealthKit 사용)
    const loadHealthData = async () => {
      try {
        const currentPlatform = Capacitor.getPlatform();
        setPlatform(currentPlatform);
        
        const { HealthData } = await import('../plugins/healthdata');
        setHealthDataPlugin(HealthData);
        
        // iOS에서만 HealthKit 권한 요청
        if (currentPlatform === 'ios') {
          try {
            console.log('HealthData 권한 요청 중... (iOS)');
            const result = await HealthData.requestAuthorization();
            console.log('HealthData 권한 요청 결과:', result);
            if (result.success) {
              console.log('HealthData 권한 승인됨, 데이터 가져오기 시작...');
              setTimeout(async () => {
                await fetchHealthData(HealthData);
              }, 500);
            } else {
              console.log('HealthData 권한 거부됨');
            }
          } catch (err: any) {
            console.error('HealthData 권한 요청 실패:', err);
          }
        } else if (currentPlatform === 'android') {
          // 안드로이드에서는 서버에서 iOS 데이터 가져오기
          console.log('Android 플랫폼 - 서버에서 건강 데이터 가져오기');
          try {
            const { HealthDataService } = await import('../services');
            const result = await HealthDataService.getLatestHealthData();
            if (result.success && result.data) {
              setHealthData({
                heartRate: result.data.heartRate || null,
                hrv: result.data.hrv || null,
                oxygenSaturation: result.data.oxygenSaturation || null,
              });
              
              // 폼 데이터에 자동으로 채우기
              if (result.data.heartRate) {
                setFormData(prev => ({ ...prev, heartRate: result.data!.heartRate!.value }));
              }
              if (result.data.hrv) {
                setFormData(prev => ({ ...prev, hrv: result.data!.hrv!.value }));
              }
              if (result.data.oxygenSaturation) {
                setFormData(prev => ({ ...prev, oxygenSaturation: result.data!.oxygenSaturation!.value }));
              }
            } else {
              generateSimulatedHealthData();
            }
          } catch (err) {
            console.error('서버에서 건강 데이터 가져오기 실패:', err);
            generateSimulatedHealthData();
          }
        } else {
          // 웹에서는 시뮬레이션 데이터 사용
          generateSimulatedHealthData();
        }
      } catch (err) {
        console.log('HealthData 플러그인 로드 실패:', err);
        generateSimulatedHealthData();
      }
    };
    
    setTimeout(() => {
      loadHealthData();
    }, 500);
  }, []);

  // 시뮬레이션 건강 데이터 생성 (안드로이드 앱과 동일한 방식)
  const generateSimulatedHealthData = () => {
    const heartRate = Math.floor(Math.random() * 41) + 60; // 60-100
    const hrv = Math.random() * 30 + 20; // 20-50
    const oxygenSaturation = Math.random() * 5 + 95; // 95-100
    
    setHealthData({
      heartRate: { value: heartRate, date: new Date().toISOString() },
      hrv: { value: hrv, date: new Date().toISOString() },
      oxygenSaturation: { value: oxygenSaturation, date: new Date().toISOString() },
    });

    // 폼 데이터에 자동으로 채우기
    setFormData(prev => ({
      ...prev,
      heartRate: heartRate,
      hrv: hrv,
      oxygenSaturation: oxygenSaturation,
    }));
  };

  const fetchHealthData = async (HealthData: any) => {
    if (!HealthData) {
      console.log('HealthData 플러그인이 없습니다.');
      generateSimulatedHealthData();
      return;
    }
    
    try {
      const [heartRate, hrv, oxygenSaturation] = await Promise.all([
        HealthData.getLatestHeartRate().catch(() => null),
        HealthData.getLatestHeartRateVariability().catch(() => null),
        HealthData.getLatestOxygenSaturation().catch(() => null),
      ]);

      setHealthData({
        heartRate: heartRate || null,
        hrv: hrv || null,
        oxygenSaturation: oxygenSaturation || null,
      });

      // 폼 데이터에 자동으로 채우기
      if (heartRate) {
        setFormData(prev => ({ ...prev, heartRate: heartRate.value }));
      }
      if (hrv) {
        setFormData(prev => ({ ...prev, hrv: hrv.value }));
      }
      if (oxygenSaturation) {
        setFormData(prev => ({ ...prev, oxygenSaturation: oxygenSaturation.value }));
      }
    } catch (err) {
      console.error('HealthData 가져오기 실패:', err);
      generateSimulatedHealthData();
    }
  };

  // 건강 데이터로 자동 예측
  useEffect(() => {
    if (autoPredictEnabled && healthData.heartRate && healthData.hrv && healthData.oxygenSaturation && formData.bmi > 0 && formData.age > 0) {
      const performAutoPredict = async () => {
        setLoading(true);
        try {
          const result = await ModelService.predictTemperature(formData);
          if (result.success) {
            const statusMap: { [key: string]: 'COMFORTABLE' | 'COLD' | 'HOT' } = {
              '적정': 'COMFORTABLE',
              '추움': 'COLD',
              '더움': 'HOT',
            };
            
            setPrediction({
              temperature: result.predictedTemperature,
              status: statusMap[result.temperatureCategory] || 'COMFORTABLE',
            });
          }
        } catch (error: any) {
          console.error('Auto prediction failed:', error);
        } finally {
          setLoading(false);
        }
      };
      performAutoPredict();
    }
  }, [autoPredictEnabled, healthData, formData.bmi, formData.age, formData.gender, formData.heartRate, formData.hrv, formData.oxygenSaturation]);

  const handlePredict = async () => {
    setLoading(true);
    try {
      const result = await ModelService.predictTemperature(formData);
      if (result.success) {
        // 서버 응답 형식 변환
        const statusMap: { [key: string]: 'COMFORTABLE' | 'COLD' | 'HOT' } = {
          '적정': 'COMFORTABLE',
          '추움': 'COLD',
          '더움': 'HOT',
        };
        
        setPrediction({
          temperature: result.predictedTemperature,
          status: statusMap[result.temperatureCategory] || 'COMFORTABLE',
        });
      } else {
        alert(result.error || '예측 실패');
      }
    } catch (error: any) {
      console.error('Prediction failed:', error);
      alert(error.message || '예측 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshHealthData = async () => {
    if (healthDataPlugin && platform === 'ios') {
      await fetchHealthData(healthDataPlugin);
    } else if (platform === 'android') {
      // 안드로이드에서는 서버에서 iOS 데이터 가져오기
      try {
        const { HealthDataService } = await import('../services');
        const result = await HealthDataService.getLatestHealthData();
        if (result.success && result.data) {
          setHealthData({
            heartRate: result.data.heartRate || null,
            hrv: result.data.hrv || null,
            oxygenSaturation: result.data.oxygenSaturation || null,
          });
          
          // 폼 데이터에 자동으로 채우기
          if (result.data.heartRate) {
            setFormData(prev => ({ ...prev, heartRate: result.data!.heartRate!.value }));
          }
          if (result.data.hrv) {
            setFormData(prev => ({ ...prev, hrv: result.data!.hrv!.value }));
          }
          if (result.data.oxygenSaturation) {
            setFormData(prev => ({ ...prev, oxygenSaturation: result.data!.oxygenSaturation!.value }));
          }
        } else {
          generateSimulatedHealthData();
        }
      } catch (err) {
        console.error('서버에서 건강 데이터 가져오기 실패:', err);
        generateSimulatedHealthData();
      }
    } else {
      generateSimulatedHealthData();
    }
  };

  const handleTestModel = async () => {
    setLoading(true);
    try {
      const result = await ModelService.testModel();
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

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>홈</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">온도 예측</IonTitle>
          </IonToolbar>
        </IonHeader>

        <div className="container">
          {/* iOS HealthKit 건강 데이터 */}
          {(platform === 'ios' || platform === 'android') && (
            <IonCard>
              <IonCardHeader>
                <IonCardTitle>
                  {platform === 'ios' ? 'HealthKit 데이터' : 'iOS HealthKit 데이터 (서버에서 가져옴)'}
                </IonCardTitle>
              </IonCardHeader>
              <IonCardContent>
                <IonButton expand="block" onClick={handleRefreshHealthData} disabled={loading || (platform === 'ios' && !healthDataPlugin)}>
                  {loading ? <IonSpinner name="crescent" /> : '건강 데이터 새로고침'}
                </IonButton>
                
                {platform === 'ios' && !healthDataPlugin && (
                  <IonText color="warning">
                    <p>HealthData 플러그인을 로드하는 중...</p>
                  </IonText>
                )}
                
                {platform === 'android' && (
                  <IonText color="primary">
                    <p>iOS에서 받은 HealthKit 데이터를 서버에서 가져옵니다.</p>
                  </IonText>
                )}
                
                {healthData.heartRate && (
                  <IonItem>
                    <IonLabel>
                      <h2>심박수</h2>
                      <p>{healthData.heartRate.value.toFixed(0)} bpm</p>
                    </IonLabel>
                  </IonItem>
                )}
                
                {healthData.hrv && (
                  <IonItem>
                    <IonLabel>
                      <h2>HRV</h2>
                      <p>{healthData.hrv.value.toFixed(2)} ms</p>
                    </IonLabel>
                  </IonItem>
                )}
                
                {healthData.oxygenSaturation && (
                  <IonItem>
                    <IonLabel>
                      <h2>산소포화도</h2>
                      <p>{healthData.oxygenSaturation.value.toFixed(1)}%</p>
                    </IonLabel>
                  </IonItem>
                )}

                <IonItem>
                  <IonLabel>자동 예측 활성화</IonLabel>
                  <input
                    type="checkbox"
                    checked={autoPredictEnabled}
                    onChange={(e) => setAutoPredictEnabled(e.target.checked)}
                  />
                </IonItem>
              </IonCardContent>
            </IonCard>
          )}

          {/* 입력 폼 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>체온 예측 입력</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonItem>
                <IonLabel position="stacked">심박수 (bpm)</IonLabel>
                <IonInput
                  type="number"
                  value={formData.heartRate}
                  onIonInput={(e) =>
                    setFormData({ ...formData, heartRate: Number(e.detail.value) })
                  }
                />
              </IonItem>

              <IonItem>
                <IonLabel position="stacked">HRV</IonLabel>
                <IonInput
                  type="number"
                  value={formData.hrv}
                  onIonInput={(e) =>
                    setFormData({ ...formData, hrv: Number(e.detail.value) })
                  }
                />
              </IonItem>

              <IonItem>
                <IonLabel position="stacked">BMI</IonLabel>
                <IonInput
                  type="number"
                  value={formData.bmi}
                  onIonInput={(e) =>
                    setFormData({ ...formData, bmi: Number(e.detail.value) })
                  }
                />
              </IonItem>

              <IonItem>
                <IonLabel position="stacked">산소포화도 (%)</IonLabel>
                <IonInput
                  type="number"
                  value={formData.oxygenSaturation}
                  onIonInput={(e) =>
                    setFormData({
                      ...formData,
                      oxygenSaturation: Number(e.detail.value),
                    })
                  }
                />
              </IonItem>

              <IonItem>
                <IonLabel position="stacked">성별</IonLabel>
                <IonSelect
                  value={formData.gender}
                  onIonChange={(e) =>
                    setFormData({ ...formData, gender: e.detail.value as 'MALE' | 'FEMALE' })
                  }
                >
                  <IonSelectOption value="MALE">남성</IonSelectOption>
                  <IonSelectOption value="FEMALE">여성</IonSelectOption>
                </IonSelect>
              </IonItem>

              <IonItem>
                <IonLabel position="stacked">나이</IonLabel>
                <IonInput
                  type="number"
                  value={formData.age}
                  onIonInput={(e) =>
                    setFormData({ ...formData, age: Number(e.detail.value) })
                  }
                />
              </IonItem>

              <IonButton expand="block" onClick={handlePredict} disabled={loading}>
                {loading ? <IonSpinner name="crescent" /> : '예측하기'}
              </IonButton>
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

          {/* 심박수 차트 영역 (추후 구현) */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>심박수 차트</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <p>차트 기능은 추후 구현 예정입니다.</p>
            </IonCardContent>
          </IonCard>

          {/* 모델 테스트 */}
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>모델 테스트</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <IonButton expand="block" onClick={handleTestModel} disabled={loading}>
                {loading ? <IonSpinner name="crescent" /> : '모델 테스트'}
              </IonButton>
            </IonCardContent>
          </IonCard>
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Tab2;
