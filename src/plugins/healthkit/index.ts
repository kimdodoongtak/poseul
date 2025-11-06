import { registerPlugin } from '@capacitor/core';
import type { HealthKitPlugin } from './definitions';

const HealthKit = registerPlugin<HealthKitPlugin>('HealthKit', {
  web: () => import('./web').then(m => new m.HealthKitWeb()),
});

export * from './definitions';
export { HealthKit };

