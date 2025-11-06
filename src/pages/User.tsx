import { IonContent, IonHeader, IonPage, IonTitle, IonToolbar } from '@ionic/react';
import './User.css';

const User: React.FC = () => {
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>사용자</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <IonHeader collapse="condense">
          <IonToolbar>
            <IonTitle size="large">사용자</IonTitle>
          </IonToolbar>
        </IonHeader>
        <div className="container">
          <h2>사용자 정보</h2>
          <p>사용자 정보 및 설정이 여기에 구현됩니다.</p>
        </div>
      </IonContent>
    </IonPage>
  );
};

export default User;

