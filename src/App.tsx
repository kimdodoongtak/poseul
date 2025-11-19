import React, { useEffect, useState } from 'react';
import { Route, useHistory } from 'react-router-dom';
import {
  IonApp,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
  IonModal,
  IonHeader,
  IonToolbar,
  IonTitle,
  IonContent,
  IonButton,
  IonText,
  setupIonicReact
} from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import { Capacitor } from '@capacitor/core';

import { home, person, settings, heart } from 'ionicons/icons';
import Home from './pages/Home';
import Iot from './pages/Iot';
import User from './pages/User';
import Health_ios from './pages/Health_ios';

/* Core CSS required for Ionic components to work properly */
import '@ionic/react/css/core.css';

/* Basic CSS for apps built with Ionic */
import '@ionic/react/css/normalize.css';
import '@ionic/react/css/structure.css';
import '@ionic/react/css/typography.css';

/* Optional CSS utils that can be commented out */
import '@ionic/react/css/padding.css';
import '@ionic/react/css/float-elements.css';
import '@ionic/react/css/text-alignment.css';
import '@ionic/react/css/text-transformation.css';
import '@ionic/react/css/flex-utils.css';
import '@ionic/react/css/display.css';

/**
 * Ionic Dark Mode
 * -----------------------------------------------------
 * For more info, please see:
 * https://ionicframework.com/docs/theming/dark-mode
 */

/* import '@ionic/react/css/palettes/dark.always.css'; */
/* import '@ionic/react/css/palettes/dark.class.css'; */
/* import '@ionic/react/css/palettes/dark.system.css'; */ // 다크 모드 비활성화

/* Theme variables */
import './theme/variables.css';
import './App.css';

setupIonicReact();

const AppContent: React.FC = () => {
  const [showDisclaimer, setShowDisclaimer] = useState<boolean>(false);
  const history = useHistory();
  
  useEffect(() => {
    // 플랫폼에 따라 body에 클래스 추가
    const platform = Capacitor.getPlatform();
    if (platform === 'android') {
      document.body.classList.add('platform-android');
      document.body.classList.remove('platform-ios');
    } else if (platform === 'ios') {
      document.body.classList.add('platform-ios');
      document.body.classList.remove('platform-android');
    } else {
      document.body.classList.add('platform-web');
    }
    
    // Safe area CSS 변수 설정
    const root = document.documentElement;
    if (platform === 'android') {
      // 갤럭시 S24 플러스 펀치홀 높이 대략 84px
      root.style.setProperty('--safe-area-inset-top', '84px');
      // 하단 네비게이션 바 높이 (기본값)
      root.style.setProperty('--safe-area-inset-bottom', '0px');
    } else if (platform === 'ios') {
      // iOS Safe Area는 CSS env() 변수를 사용하므로 여기서는 기본값만 설정
      root.style.setProperty('--safe-area-inset-top', 'env(safe-area-inset-top, 0px)');
      root.style.setProperty('--safe-area-inset-bottom', 'env(safe-area-inset-bottom, 0px)');
      root.style.setProperty('--safe-area-inset-left', 'env(safe-area-inset-left, 0px)');
      root.style.setProperty('--safe-area-inset-right', 'env(safe-area-inset-right, 0px)');
    }
    
    // 앱 처음 실행 시 면책사항 팝업 확인
    // 개발 서버에서는 항상 면책사항 표시
    const isDevelopment = window.location.hostname === 'localhost' || 
                         window.location.hostname === '127.0.0.1' ||
                         window.location.hostname.includes('localhost') ||
                         import.meta.env.DEV;
    
    if (isDevelopment) {
      // 개발 환경에서는 항상 표시
      setShowDisclaimer(true);
    } else {
      // 프로덕션 환경에서는 localStorage 확인
      const disclaimerAccepted = localStorage.getItem('disclaimer_accepted');
      if (!disclaimerAccepted) {
        setShowDisclaimer(true);
      }
    }
  }, []);
  
  const handleDisclaimerAccept = () => {
    localStorage.setItem('disclaimer_accepted', 'true');
    setShowDisclaimer(false);
    // 초기 설정 페이지(Health)로 이동 - 기본정보 입력 화면
    // 모달이 닫힌 후 라우팅이 확실히 적용되도록 약간의 딜레이 추가
    setTimeout(() => {
      history.push('/health_ios');
      // 탭도 활성화
      const healthTab = document.querySelector('ion-tab-button[tab="health_ios"]');
      if (healthTab) {
        (healthTab as HTMLElement).click();
      }
    }, 100);
  };
  
  return (
    <>
      <IonTabs>
        <IonRouterOutlet>
          <Route exact path="/home">
            <Home />
          </Route>
          <Route exact path="/health_ios">
            <Health_ios />
          </Route>
          <Route exact path="/iot">
            <Iot />
          </Route>
          <Route exact path="/user">
            <User />
          </Route>
          <Route exact path="/">
            <Home />
          </Route>
        </IonRouterOutlet>
        <IonTabBar slot="bottom">
          <IonTabButton tab="health_ios" href="/health_ios">
            <IonIcon aria-hidden="true" icon={heart} />
            <IonLabel>Health</IonLabel>
          </IonTabButton>
          <IonTabButton tab="home" href="/home">
            <IonIcon aria-hidden="true" icon={home} />
            <IonLabel>홈</IonLabel>
          </IonTabButton>
          <IonTabButton tab="iot" href="/iot">
            <IonIcon aria-hidden="true" icon={settings} />
            <IonLabel>IoT</IonLabel>
          </IonTabButton>
          <IonTabButton tab="user" href="/user">
            <IonIcon aria-hidden="true" icon={person} />
            <IonLabel>사용자</IonLabel>
          </IonTabButton>
        </IonTabBar>
      </IonTabs>
      
      <IonModal
        isOpen={showDisclaimer}
        backdropDismiss={false}
        className="disclaimer-modal"
      >
        <IonContent className="disclaimer-content-wrapper" scrollY={false}>
          <div className="disclaimer-card">
            <div className="disclaimer-header">
              <h1>면책사항</h1>
            </div>
            <div className="disclaimer-body">
              <IonText className="disclaimer-text">
                <p>
                  이 앱은 수면 보조 도구로,<br />
                  의료적으로 사용이 불가합니다.
                </p>
                <p>
                  모델이 예측한 체온 정보는<br />
                  직접적으로 제공되지 않습니다.
                </p>
              </IonText>
            </div>
            <div className="disclaimer-button-container">
              <IonButton
                expand="block"
                size="large"
                onClick={handleDisclaimerAccept}
                className="disclaimer-button"
              >
                확인했습니다
              </IonButton>
            </div>
          </div>
        </IonContent>
      </IonModal>
    </>
  );
};

const App: React.FC = () => {
  console.log('🎯 App 컴포넌트 렌더링 시작');
  
  return (
    <IonApp className={Capacitor.getPlatform() === 'android' ? 'platform-android' : Capacitor.getPlatform() === 'ios' ? 'platform-ios' : 'platform-web'}>
      <IonReactRouter>
        <AppContent />
      </IonReactRouter>
    </IonApp>
  );
};

export default App;
