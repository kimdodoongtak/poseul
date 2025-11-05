import { useState } from 'react';
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
import { ModelService, TemperaturePredictionRequest } from '../services';
import './Home.css';

const Home: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<{
    temperature: number;
    status: 'COMFORTABLE' | 'COLD' | 'HOT';
  } | null>(null);

  const [formData, setFormData] = useState<TemperaturePredictionRequest>({
    heartRate: 0,
    hrv: 0,
    bmi: 0,
    oxygenSaturation: 0,
    gender: 'MALE',
    age: 0,
  });

  const handlePredict = async () => {
    setLoading(true);
    try {
      const result = await ModelService.predictTemperature(formData);
      setPrediction({
        temperature: result.predictedTemperature,
        status: result.status,
      });
    } catch (error) {
      console.error('Prediction failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTestModel = async () => {
    setLoading(true);
    try {
      const result = await ModelService.testModel();
      alert(result.message);
    } catch (error) {
      console.error('Model test failed:', error);
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

export default Home;

