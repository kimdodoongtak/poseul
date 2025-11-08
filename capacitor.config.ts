import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig & {
  ios?: {
    packageClassList?: string[];
  };
  packageClassList?: string[];
} = {
  appId: 'com.poseul.app',
  appName: 'poseul',
  webDir: 'dist',
  ios: {
    packageClassList: [
      'AppPlugin',
      'HapticsPlugin',
      'KeyboardPlugin',
      'StatusBarPlugin',
      'HealthData'
    ]
  },
  packageClassList: [
    'AppPlugin',
    'HapticsPlugin',
    'KeyboardPlugin',
    'StatusBarPlugin',
    'HealthData'
  ]
};

export default config;
