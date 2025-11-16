import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

console.log('🚀 main.tsx 로드됨');

const container = document.getElementById('root');
if (!container) {
  console.error('❌ root 요소를 찾을 수 없습니다!');
  // root 요소가 없으면 body에 직접 추가
  const newRoot = document.createElement('div');
  newRoot.id = 'root';
  newRoot.style.cssText = 'background-color: #ffffff; color: #000000; width: 100%; height: 100%; min-height: 100vh;';
  document.body.appendChild(newRoot);
  const root = createRoot(newRoot);
  try {
    console.log('✅ React 앱 렌더링 시작');
    root.render(<App />);
    console.log('✅ React 앱 렌더링 완료');
  } catch (error) {
    console.error('❌ React 앱 렌더링 실패:', error);
  }
} else {
  console.log('✅ root 요소 찾음');
  const root = createRoot(container);
  try {
    console.log('✅ React 앱 렌더링 시작');
    root.render(<App />);
    console.log('✅ React 앱 렌더링 완료');
  } catch (error) {
    console.error('❌ React 앱 렌더링 실패:', error);
  }
}