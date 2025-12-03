import React, { useEffect, useState } from 'react';
import './SplashScreen.css';

interface SplashScreenProps {
  onComplete: () => void;
}

const SplashScreen: React.FC<SplashScreenProps> = ({ onComplete }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    // 상태 초기화 (매번 새로고침 시 깨끗한 상태로 시작)
    setIsVisible(true);
    setIsAnimating(false);
    
    // 약간의 지연 후 애니메이션 시작 (렌더링 완료 보장)
    const startTimer = setTimeout(() => {
      setIsAnimating(true);
    }, 50);

    // 2초 후 페이드 아웃 시작
    const fadeOutTimer = setTimeout(() => {
      setIsVisible(false);
    }, 2000);

    // 2.5초 후 완전히 제거
    const removeTimer = setTimeout(() => {
      onComplete();
    }, 2500);

    return () => {
      clearTimeout(startTimer);
      clearTimeout(fadeOutTimer);
      clearTimeout(removeTimer);
    };
  }, [onComplete]);

  if (!isVisible && !isAnimating) {
    return null;
  }

  return (
    <div className={`splash-screen ${isVisible ? 'visible' : 'fade-out'}`}>
      <div className="splash-content">
        <img 
          src="/open.png" 
          alt="Splash" 
          className={`splash-image ${isAnimating ? 'animate' : ''}`}
        />
      </div>
    </div>
  );
};

export default SplashScreen;

