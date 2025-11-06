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
import '@ionic/react/css/palettes/dark.system.css';

/* Theme variables */
import './theme/variables.css';

setupIonicReact();

const App: React.FC = () => (
  <IonApp>
    <IonReactRouter>
      <IonTabs>
        <IonRouterOutlet>
          <Route exact path="/">
            <Health_ios />
          </Route>
          <Route exact path="/health_ios">
            <Health_ios />
          </Route>
          <Route exact path="/home">
            <Home />
          </Route>
          <Route exact path="/iot">
            <Iot />
          </Route>
          <Route exact path="/user">
            <User />
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

export default App;
