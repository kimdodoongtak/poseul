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
import DeviceRegistration from './components/DeviceRegistration';
import SplashScreen from './components/SplashScreen';
import { isAuthenticated, getUserNo } from './services/AuthService';

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
import '@ionic/react/css/palettes/dark.class.css'; // 다크 모드 활성화 (body.dark 클래스 사용)
/* import '@ionic/react/css/palettes/dark.system.css'; */

/* Theme variables */
import './theme/variables.css';
import './App.css';

setupIonicReact();

const AppContent: React.FC = () => {
  const [showSplash, setShowSplash] = useState<boolean>(true);
  const [showDisclaimer, setShowDisclaimer] = useState<boolean>(false);
  const [splashCompleted, setSplashCompleted] = useState<boolean>(false);
  const history = useHistory();
  const logoutInProgressRef = React.useRef<boolean>(false); // 로그아웃 진행 중 플래그
  
  // 플랫폼 설정 (앱 시작 시 즉시 실행)
  useEffect(() => {
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
  }, []);

  // 로그아웃 이벤트 리스너 (앱 시작 시 즉시 등록)
  useEffect(() => {
    const handleAuthStateChanged = (event: CustomEvent) => {
      const authenticated = event.detail?.authenticated ?? isAuthenticated();
      if (!authenticated) {
        // 로그아웃 감지
        logoutInProgressRef.current = true;
        console.log('🔍 App - 로그아웃 감지, 플래그 설정');
        // 5초 후 플래그 해제 (User.tsx와 동일하게)
        setTimeout(() => {
          logoutInProgressRef.current = false;
          console.log('✅ App - 로그아웃 완료 플래그 해제');
        }, 5000);
      }
    };
    
    window.addEventListener('authStateChanged', handleAuthStateChanged as EventListener);
    
    return () => {
      window.removeEventListener('authStateChanged', handleAuthStateChanged as EventListener);
    };
  }, []);

  // 스플래시 스크린 완료 후 면책사항 체크
  useEffect(() => {
    if (!splashCompleted) {
      return; // 스플래시가 완료되기 전에는 면책사항 체크하지 않음
    }
    
    // 앱 처음 실행 시 면책사항 팝업 확인
    // 개발 서버에서는 항상 면책사항 표시
    const isDevelopment = window.location.hostname === 'localhost' || 
                         window.location.hostname === '127.0.0.1' ||
                         window.location.hostname.includes('localhost') ||
                         import.meta.env.DEV;
    
    const checkAuthAndShowLogin = () => {
      // 로그아웃 진행 중이면 무시
      if (logoutInProgressRef.current) {
        console.log('🔍 App - 로그아웃 진행 중, 로그인 체크 무시');
        return;
      }
      
      const authenticated = isAuthenticated();
      const userNo = getUserNo();
      
      // 로그인 안 되어 있거나 user_no가 null이면 User 페이지로 이동하여 로그인 모달 표시
      if (!authenticated || userNo === null) {
        console.log('⚠️ 앱 시작 - 로그인 필요 또는 user_no가 null, User 페이지로 이동');
        setTimeout(() => {
          history.push('/user');
          // User 페이지에 로그인 모달 표시하라는 이벤트 전달
          window.dispatchEvent(new CustomEvent('showLoginModal'));
        }, 100);
      } else {
        console.log('✅ 앱 시작 - 로그인 확인됨, user_no:', userNo);
      }
    };
    
    if (isDevelopment) {
      // 개발 환경에서는 항상 표시
      setShowDisclaimer(true);
    } else {
      // 프로덕션 환경에서는 사용자별 localStorage 확인
      const authenticated = isAuthenticated();
      const userNo = getUserNo();
      
      if (authenticated && userNo !== null) {
        // 로그인되어 있으면 사용자별 면책사항 동의 확인
        const disclaimerAccepted = localStorage.getItem(`disclaimer_accepted_${userNo}`);
        if (!disclaimerAccepted) {
          setShowDisclaimer(true);
        } else {
          // 면책사항이 이미 수락되었으면 로그인 체크
          checkAuthAndShowLogin();
        }
      } else {
        // 로그인 안 되어 있으면 면책사항 표시 (나중에 로그인하면 사용자별로 저장됨)
        // 기존 공통 면책사항도 확인 (하위 호환성)
        const oldDisclaimerAccepted = localStorage.getItem('disclaimer_accepted');
        if (!oldDisclaimerAccepted) {
          setShowDisclaimer(true);
        } else {
          // 기존 공통 면책사항이 있으면 로그인 체크
          checkAuthAndShowLogin();
        }
      }
    }
  }, [history, splashCompleted]);
  
  const handleDisclaimerAccept = () => {
    // 면책사항 수락 후 로그인 체크
    const authenticated = isAuthenticated();
    const userNo = getUserNo();
    
    if (authenticated && userNo !== null) {
      // 로그인되어 있으면 사용자별로 저장
      localStorage.setItem(`disclaimer_accepted_${userNo}`, 'true');
      console.log(`✅ 면책사항 동의 저장 (user_no: ${userNo})`);
    } else {
      // 로그인 안 되어 있으면 임시로 공통 저장 (나중에 로그인하면 사용자별로 저장됨)
      localStorage.setItem('disclaimer_accepted', 'true');
      console.log('✅ 면책사항 동의 저장 (임시, 로그인 후 사용자별로 저장됨)');
    }
    
    setShowDisclaimer(false);
    
    if (!authenticated || userNo === null) {
      // 로그인 안 되어 있으면 User 페이지로 이동하여 로그인 모달 표시
      setTimeout(() => {
        history.push('/user');
        // User 페이지에 로그인 모달 표시하라는 이벤트 전달
        window.dispatchEvent(new CustomEvent('showLoginModal'));
      }, 100);
    } else {
      // 로그인되어 있으면 Health 페이지로 이동
      setTimeout(() => {
        history.push('/health_ios');
        // 탭도 활성화
        const healthTab = document.querySelector('ion-tab-button[tab="health_ios"]');
        if (healthTab) {
          (healthTab as HTMLElement).click();
        }
      }, 100);
    }
  };
  
  const handleSplashComplete = () => {
    setShowSplash(false);
    setSplashCompleted(true);
  };

  return (
    <>
      {showSplash && (
        <SplashScreen onComplete={handleSplashComplete} />
      )}
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
          <Route exact path="/iot/register">
            <DeviceRegistration />
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
