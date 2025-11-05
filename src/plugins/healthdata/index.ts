import { registerPlugin } from '@capacitor/core';
import type { HealthDataPlugin } from './definitions';

const HealthData = registerPlugin<HealthDataPlugin>('HealthData', {
  web: () => import('./web').then(m => new m.HealthDataWeb()),
});

export * from './definitions';
export { HealthData };

