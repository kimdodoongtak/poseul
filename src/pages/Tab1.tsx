import { IonContent, IonHeader, IonPage, IonTitle, IonToolbar, IonText } from '@ionic/react';
import ExploreContainer from '../components/ExploreContainer';
import './Tab1.css';

const Tab1: React.FC = () => {
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>Tab 1</IonTitle>
        </IonToolbar>
      </IonHeader>
        <IonContent>
          <IonHeader collapse="condense">
            <IonToolbar>
              <IonTitle size="large">포술 🧃</IonTitle>
            </IonToolbar>
          </IonHeader>

          <IonText color="primary">
            <h2>안녕, 뚱딱앱 세상에 오신 걸 환영합니다 🎉</h2>
          </IonText>
        </IonContent>
    </IonPage>
  );
};

export default Tab1;
