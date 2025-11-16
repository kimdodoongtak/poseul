import { registerPlugin } from '@capacitor/core';
import type { HttpRequestPlugin } from './definitions';

const HttpRequest = registerPlugin<HttpRequestPlugin>('HttpRequest', {
  web: () => import('./web').then(m => new m.HttpRequestWeb()),
});

export * from './definitions';
export { HttpRequest };

