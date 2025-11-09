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
  IonButton,
  IonText,
  IonSpinner,
} from '@ionic/react';
import { ModelService } from '../services';
import './Home.css';

const Home: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<{
    temperature: number;
    status: 'COMFORTABLE' | 'COLD' | 'HOT';
  } | null>(null);

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
        <IonHeader>
          <IonToolbar>
            <IonTitle size="large">온도 예측</IonTitle>
          </IonToolbar>
        </IonHeader>

        <div className="container">
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

