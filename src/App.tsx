import React, { useEffect } from 'react';
import { Route } from 'react-router-dom';
import {
  IonApp,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
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

setupIonicReact();

const App: React.FC = () => {
  console.log('🎯 App 컴포넌트 렌더링 시작');
  
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
    
    // Safe area CSS 변수 설정 (Android)
    if (platform === 'android') {
      const root = document.documentElement;
      // 갤럭시 S24 플러스 펀치홀 높이 대략 84px
      root.style.setProperty('--safe-area-inset-top', '84px');
      // 하단 네비게이션 바 높이 (기본값)
      root.style.setProperty('--safe-area-inset-bottom', '0px');
    }
  }, []);
  
  return (
    <IonApp className={Capacitor.getPlatform() === 'android' ? 'platform-android' : Capacitor.getPlatform() === 'ios' ? 'platform-ios' : 'platform-web'}>
    <IonReactRouter>
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
    </IonReactRouter>
  </IonApp>
);
};

export default App;
