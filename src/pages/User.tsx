import React, { useState, useEffect, useRef } from 'react';
import { useHistory } from 'react-router-dom';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
  IonCard,
  IonCardHeader,
  IonCardTitle,
  IonCardContent,
  IonItem,
  IonLabel,
  IonInput,
  IonButton,
  IonSelect,
  IonSelectOption,
  IonModal,
  IonButtons,
  IonButton as IonModalButton,
  IonText,
  IonAlert,
  IonIcon,
} from '@ionic/react';
import { refreshOutline, closeOutline } from 'ionicons/icons';
import { LocalNotifications, ActionPerformed, LocalNotificationSchema } from '@capacitor/local-notifications';
import { Capacitor } from '@capacitor/core';
import SignIn from '../components/SignIn';
import SignUp from '../components/SignUp';
import DeviceRegistration from '../components/DeviceRegistration';
import './User.css';
import { autoDetectServerUrl, getServerUrl } from '../services/ServerConfig';
import IotService from '../services/IotService';
import ModelService from '../services/ModelService';
import HealthDataService from '../services/HealthDataService';
import { isAuthenticated, logout, getCurrentUser, getAuthHeaders, getUserNo } from '../services/AuthService';

const User: React.FC = () => {
  const history = useHistory();
  // 초기 상태: 항상 빈 값으로 시작 (로그인 후에만 저장소에서 불러옴)
  const [age, setAge] = useState<string>('');
  const [bmi, setBmi] = useState<string>('');
  const [gender, setGender] = useState<string>('0');
  const [feedbackTime, setFeedbackTime] = useState<string>('22:00'); // 기본값: 오후 10시
  const [showFeedbackModal, setShowFeedbackModal] = useState<boolean>(false);
  const [healthDataPlugin, setHealthDataPlugin] = useState<any>(null);
  const [platform, setPlatform] = useState<string>('web');
  const [showSignIn, setShowSignIn] = useState<boolean>(false);
  const [showSignUp, setShowSignUp] = useState<boolean>(false);
  const [showResetAlert, setShowResetAlert] = useState<boolean>(false);
  const [feedbackCount, setFeedbackCount] = useState<number>(0);
  const [isFeedbackDisabled, setIsFeedbackDisabled] = useState<boolean>(false);
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [showIotRegistration, setShowIotRegistration] = useState<boolean>(false);
  const [currentUserId, setCurrentUserId] = useState<string | undefined>(undefined);
  const loginSuccessRef = useRef<boolean>(false); // 로그인 성공 플래그
  const loadUserInfoRef = useRef<(() => Promise<void>) | null>(null); // 사용자 정보 로드 함수 참조
  const logoutInProgressRef = useRef<boolean>(false); // 로그아웃 진행 중 플래그

  const requestNotificationPermission = async () => {
    try {
      const status = await LocalNotifications.checkPermissions();
      if (status.display !== 'granted') {
        await LocalNotifications.requestPermissions();
      }
    } catch (err) {
      console.log('알림 권한 요청 실패:', err);
    }
  };

  const scheduleDailyNotification = async () => {
    try {
      // 사용자별 피드백 시간 가져오기
      const userNo = getUserNo();
      const savedTime = userNo 
        ? (localStorage.getItem(`feedbackTime_${userNo}`) || '22:00')
        : (localStorage.getItem('feedbackTime') || '22:00'); // 하위 호환성
      const [hours, minutes] = savedTime.split(':').map(Number);
      
      // 기존 알림 취소
      await LocalNotifications.cancel({ notifications: [{ id: 1 }] });
      
      // 매일 지정된 시간에 알림 스케줄
      await LocalNotifications.schedule({
        notifications: [
          {
            title: '온도 피드백',
            body: '오늘밤 온도는 어땠나요?',
            id: 1,
            schedule: {
              every: 'day',
              on: {
                hour: hours,
                minute: minutes
              }
            },
            actionTypeId: 'FEEDBACK_ACTION',
            extra: {
              type: 'temperature_feedback'
            }
          }
        ]
      });
      
      console.log(`✅ 매일 ${savedTime}에 알림이 스케줄되었습니다.`);
    } catch (err) {
      console.log('알림 스케줄 실패:', err);
    }
  };

  // 사용자 정보를 저장소에서 불러오는 함수 (로그인된 경우에만 호출)
  const loadUserInfoFromStorage = async () => {
    // 로그인 상태가 아니면 절대 실행하지 않음
    if (!isAuthenticated()) {
      setAge('');
      setBmi('');
      setGender('0');
      return;
    }
    
    const currentUserNo = getUserNo();
    if (!currentUserNo) {
      setAge('');
      setBmi('');
      setGender('0');
      return;
    }
    
    // 서버에서 최신 사용자 정보 로드
    try {
      const { getAuthHeaders } = await import('../services/AuthService');
      const baseUrl = getServerUrl();
      
      // 로그인 상태 재확인
      if (!isAuthenticated() || getUserNo() !== currentUserNo) {
        setAge('');
        setBmi('');
        setGender('0');
        return;
      }
      
      // 서버에서 최신 건강 정보 가져오기
      const healthResponse = await fetch(`${baseUrl}/healthdata/latest`, {
        headers: getAuthHeaders()
      });
      
      // 로그인 상태 재확인
      if (!isAuthenticated() || getUserNo() !== currentUserNo) {
        setAge('');
        setBmi('');
        setGender('0');
        return;
      }
      
      if (healthResponse.ok) {
        const healthResult = await healthResponse.json();
        
        // 로그인 상태 재확인
        if (!isAuthenticated() || getUserNo() !== currentUserNo) {
          setAge('');
          setBmi('');
          setGender('0');
          return;
        }
        
        if (healthResult.success && healthResult.data) {
          // 서버에서 가져온 데이터로 업데이트
          if (healthResult.data.age !== undefined && healthResult.data.age !== null) {
            const ageValue = String(healthResult.data.age);
            setAge(ageValue);
            localStorage.setItem(`userAge_${currentUserNo}`, ageValue);
          } else {
            // 서버에 없으면 localStorage에서 가져오기
            const savedAge = localStorage.getItem(`userAge_${currentUserNo}`);
            if (savedAge) {
              setAge(savedAge);
            }
          }
          
          if (healthResult.data.bmi !== undefined && healthResult.data.bmi !== null) {
            const bmiValue = String(healthResult.data.bmi);
            setBmi(bmiValue);
            localStorage.setItem(`userBmi_${currentUserNo}`, bmiValue);
          } else {
            const savedBmi = localStorage.getItem(`userBmi_${currentUserNo}`);
            if (savedBmi) {
              setBmi(savedBmi);
            }
          }
          
          if (healthResult.data.gender !== undefined && healthResult.data.gender !== null) {
            // gender 정규화: 'M'/'F' 또는 'MALE'/'FEMALE' -> '1'/'0'
            let genderValue = healthResult.data.gender;
            if (typeof genderValue === 'string') {
              genderValue = genderValue.toUpperCase();
              genderValue = (genderValue === 'M' || genderValue === 'MALE' || genderValue === '1') ? '1' : '0';
            } else if (typeof genderValue === 'number') {
              genderValue = genderValue === 1 ? '1' : '0';
            } else {
              genderValue = '0';
            }
            setGender(genderValue);
            localStorage.setItem(`userGender_${currentUserNo}`, genderValue);
          } else {
            const savedGender = localStorage.getItem(`userGender_${currentUserNo}`);
            if (savedGender) {
              setGender(savedGender);
            }
          }
        }
      } else {
        // 서버에서 가져오기 실패 시 localStorage에서 가져오기
        if (!isAuthenticated() || getUserNo() !== currentUserNo) {
          setAge('');
          setBmi('');
          setGender('0');
          return;
        }
        
        const savedAge = localStorage.getItem(`userAge_${currentUserNo}`);
        const savedBmi = localStorage.getItem(`userBmi_${currentUserNo}`);
        const savedGender = localStorage.getItem(`userGender_${currentUserNo}`);
        
        if (savedAge) setAge(savedAge);
        if (savedBmi) setBmi(savedBmi);
        if (savedGender) setGender(savedGender);
      }
    } catch (error) {
      console.error('사용자 정보 로드 실패:', error);
      // 에러 발생 시 localStorage에서 가져오기
      if (!isAuthenticated() || getUserNo() !== currentUserNo) {
        setAge('');
        setBmi('');
        setGender('0');
        return;
      }
      
      try {
        const savedAge = localStorage.getItem(`userAge_${currentUserNo}`);
        const savedBmi = localStorage.getItem(`userBmi_${currentUserNo}`);
        const savedGender = localStorage.getItem(`userGender_${currentUserNo}`);
        
        if (savedAge) setAge(savedAge);
        if (savedBmi) setBmi(savedBmi);
        if (savedGender) setGender(savedGender);
      } catch (e) {
        console.error('localStorage에서 사용자 정보 로드 실패:', e);
      }
    }
  };
  
  // 함수 참조 저장
  loadUserInfoRef.current = loadUserInfoFromStorage;

  useEffect(() => {
    // 초기 로그인 상태 확인
    const authenticated = isAuthenticated();
    setIsLoggedIn(authenticated);
    
    // 로그인 안 되어 있으면 빈 값 유지 (localStorage 읽지 않음)
    if (!authenticated) {
      setAge('');
      setBmi('');
      setGender('0');
    } else {
      // 로그인되어 있으면 저장소에서 불러오기
      loadUserInfoFromStorage();
    }
    
    // 앱 시작 시 로그인 모달 표시 이벤트 리스너
    const handleShowLoginModal = () => {
      console.log('🔍 User 페이지 - 로그인 모달 표시 이벤트 수신');
      // 로그아웃 진행 중이면 무시
      if (logoutInProgressRef.current) {
        console.log('🔍 User 페이지 - 로그아웃 진행 중, 로그인 모달 표시 무시');
        setShowSignIn(false); // 모달 강제로 닫기
        return;
      }
      // 이미 모달이 열려있으면 무시 (중복 방지)
      if (showSignIn) {
        console.log('🔍 User 페이지 - 이미 로그인 모달이 열려있음, 무시');
        return;
      }
      if (!isAuthenticated() || getUserNo() === null) {
        setShowSignIn(true);
      }
    };
    
    // 로그인 상태 변경 이벤트 리스너 (다른 페이지에서 로그인/로그아웃 시 동기화)
    const handleAuthStateChanged = (event: CustomEvent) => {
      // 로그인 성공 직후에는 상태를 변경하지 않음
      if (loginSuccessRef.current) {
        console.log('🔍 User 페이지 - 로그인 성공 직후, 이벤트 무시');
        return;
      }
      // 로그아웃 진행 중이면 상태만 업데이트하고 모달은 표시하지 않음
      if (logoutInProgressRef.current) {
        const authenticated = event.detail?.authenticated ?? isAuthenticated();
        setIsLoggedIn(authenticated);
        setShowSignIn(false); // 로그아웃 중에는 모달 강제로 닫기
        console.log(`🔍 User 페이지 - 로그아웃 진행 중, 상태만 업데이트: ${authenticated}`);
        return;
      }
      
      // 로그아웃 상태로 변경되었고 모달이 열려있으면 닫기
      const authenticated = event.detail?.authenticated ?? isAuthenticated();
      if (!authenticated && showSignIn) {
        setShowSignIn(false);
        console.log('🔍 User 페이지 - 로그아웃 상태로 변경, 모달 닫기');
      }
      setIsLoggedIn(authenticated);
      console.log(`🔍 User 페이지 - 로그인 상태 변경 이벤트: ${authenticated}`);
      
      // 로그인 시 사용자 정보 로드, 로그아웃 시 초기화
      if (authenticated) {
        loadUserInfoFromStorage();
      } else {
        setAge('');
        setBmi('');
        setGender('0');
      }
    };
    
    // localStorage storage 이벤트 리스너 (다른 탭에서 로그인/로그아웃 시 동기화)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth_token' || e.key === 'user_no') {
        // 로그인 성공 직후에는 상태를 변경하지 않음
        if (loginSuccessRef.current) {
          console.log('🔍 User 페이지 - 로그인 성공 직후, storage 이벤트 무시');
          return;
        }
        // 로그아웃 진행 중이면 상태만 업데이트하고 모달은 표시하지 않음
        if (logoutInProgressRef.current) {
          const authenticated = isAuthenticated();
          setIsLoggedIn(authenticated);
          setShowSignIn(false); // 로그아웃 중에는 모달 강제로 닫기
          console.log(`🔍 User 페이지 - 로그아웃 진행 중, storage 이벤트 무시`);
          return;
        }
        
        // 로그아웃 상태로 변경되었고 모달이 열려있으면 닫기
        const authenticated = isAuthenticated();
        if (!authenticated && showSignIn) {
          setShowSignIn(false);
          console.log('🔍 User 페이지 - 로그아웃 상태로 변경 (storage), 모달 닫기');
        }
        setIsLoggedIn(authenticated);
        console.log(`🔍 User 페이지 - localStorage 변경 감지, 로그인 상태: ${authenticated}`);
        
        // 로그인 시 사용자 정보 로드, 로그아웃 시 초기화
        if (authenticated) {
          loadUserInfoFromStorage();
        } else {
          setAge('');
          setBmi('');
          setGender('0');
        }
      }
    };
    
    // 페이지 포커스 시 상태 확인 및 사용자 정보 새로고침
    const handleFocus = () => {
      // 로그인 성공 직후에는 상태를 변경하지 않음
      if (loginSuccessRef.current) {
        console.log('🔍 User 페이지 - 로그인 성공 직후, 포커스 이벤트 무시');
        return;
      }
      // 로그아웃 진행 중이면 무시
      if (logoutInProgressRef.current) {
        console.log('🔍 User 페이지 - 로그아웃 진행 중, 포커스 이벤트 무시');
        setShowSignIn(false); // 모달 강제로 닫기
        return;
      }
      const authenticated = isAuthenticated();
      setIsLoggedIn(authenticated);
      console.log(`🔍 User 페이지 - 포커스 이벤트, 로그인 상태: ${authenticated}`);
      
      // 로그아웃 상태이고 모달이 열려있으면 닫기
      if (!authenticated && showSignIn) {
        setShowSignIn(false);
        console.log('🔍 User 페이지 - 로그아웃 상태 (포커스), 모달 닫기');
        return;
      }
      
      // 로그인되어 있으면 사용자 정보 다시 로드 (다른 페이지에서 변경했을 수 있음)
      if (authenticated) {
        console.log('🔄 User 페이지 - 포커스 시 사용자 정보 새로고침');
        loadUserInfoFromStorage();
      } else {
        // 로그인 안 되어 있으면 모든 사용자 정보 초기화
        setAge('');
        setBmi('');
        setGender('0');
      }
    };
    
    window.addEventListener('showLoginModal', handleShowLoginModal);
    window.addEventListener('authStateChanged', handleAuthStateChanged as EventListener);
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('focus', handleFocus);
    
    // cleanup 함수
    const cleanup = () => {
      window.removeEventListener('showLoginModal', handleShowLoginModal);
      window.removeEventListener('authStateChanged', handleAuthStateChanged as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('focus', handleFocus);
    };
    
    
    // 피드백 시간은 사용자별로 localStorage에서 가져오기
    try {
      const currentUserNo = getUserNo();
      if (currentUserNo) {
        // 사용자별 피드백 시간 가져오기
        const savedFeedbackTime = localStorage.getItem(`feedbackTime_${currentUserNo}`);
        if (savedFeedbackTime) {
          setFeedbackTime(savedFeedbackTime);
        } else {
          // 하위 호환성: 기존 공통 feedbackTime이 있으면 사용하고 사용자별로 저장
          const oldFeedbackTime = localStorage.getItem('feedbackTime');
          if (oldFeedbackTime) {
            setFeedbackTime(oldFeedbackTime);
            localStorage.setItem(`feedbackTime_${currentUserNo}`, oldFeedbackTime);
          }
        }
      } else {
        // 로그인하지 않은 경우 기본값 사용
        const savedFeedbackTime = localStorage.getItem('feedbackTime');
        if (savedFeedbackTime) setFeedbackTime(savedFeedbackTime);
      }
    } catch (err) {
      console.log('피드백 시간 불러오기 실패:', err);
    }
    
    // HealthData 플러그인 로드 (iOS에서 UserDefaults 저장용)
    const loadHealthData = async () => {
      try {
        const { Capacitor } = await import('@capacitor/core');
        const currentPlatform = Capacitor.getPlatform();
        setPlatform(currentPlatform);
        
        if (currentPlatform === 'ios') {
          const { HealthData } = await import('../plugins/healthdata');
          setHealthDataPlugin(HealthData);
        }
      } catch (err) {
        console.log('HealthData 플러그인 로드 실패:', err);
      }
    };
    
    // 서버 URL 자동 감지 (앱이 완전히 로드된 후 백그라운드에서 실행)
    // 앱 시작 시 실행하지 않고, 나중에 필요할 때만 실행
    setTimeout(() => {
      const detectServerUrl = async () => {
        try {
          const serverUrl = await autoDetectServerUrl();
          console.log('✅ 서버 URL 자동 감지 완료:', serverUrl);
          // 모든 서비스의 baseUrl 업데이트
          IotService.updateBaseUrl(serverUrl);
          ModelService.updateBaseUrl(serverUrl);
          HealthDataService.updateBaseUrl(serverUrl);
        } catch (err) {
          console.error('서버 URL 자동 감지 실패:', err);
          // 오류가 발생해도 앱은 계속 작동하도록
        }
      };
      detectServerUrl();
    }, 3000); // 3초 후에 실행하여 앱이 먼저 완전히 로드되도록
    
    setTimeout(() => {
      loadHealthData();
    }, 500);
    
    // 알림 권한 요청 및 기존 알림 스케줄 확인
    if (Capacitor.isNativePlatform()) {
      requestNotificationPermission();
      scheduleDailyNotification();
    }
    
    // cleanup 함수 반환
    return cleanup;
  }, []);

  const handleAgeChange = async (value: string) => {
    setAge(value);
    try {
      const userNo = getUserNo();
      
      // 로그인 안 되어 있으면 저장하지 않음
      if (!isAuthenticated() || !userNo) {
        return;
      }
      
      // userNo가 있으면 userNo 포함 키로만 저장 (하위 호환성 제거)
      localStorage.setItem(`userAge_${userNo}`, value || '');
      
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: value || '',
            bmi: bmi || '',
            gender: gender || '0'
          });
        } catch (err) {
          console.log('나이 UserDefaults 저장 실패:', err);
        }
      }
      
      // 서버에 사용자 정보 업데이트 (user_no가 null이면 API 호출 안 함)
      if (isAuthenticated() && userNo !== null && value.trim()) {
        try {
          const apiBaseUrl = getServerUrl();
          const response = await fetch(`${apiBaseUrl}/user/profile`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({
              age: parseInt(value.trim(), 10),
              bmi: bmi ? parseFloat(bmi) : undefined,
              gender: gender === '1' ? 'M' : 'F'
            })
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log('✅ 사용자 정보 업데이트 완료:', result);
          } else {
            console.error('❌ 사용자 정보 업데이트 실패:', response.status);
          }
        } catch (err) {
          console.error('❌ 사용자 정보 업데이트 중 오류:', err);
        }
      } else if (isAuthenticated() && userNo === null) {
        console.warn('⚠️ handleAgeChange - user_no가 null, 서버 업데이트 건너뜀');
      }
    } catch (err) {
      console.log('나이 저장 실패:', err);
    }
  };

  const handleBmiChange = async (value: string) => {
    setBmi(value);
    try {
      const userNo = getUserNo();
      
      // 로그인 안 되어 있으면 저장하지 않음
      if (!isAuthenticated() || !userNo) {
        return;
      }
      
      // userNo가 있으면 userNo 포함 키로만 저장 (하위 호환성 제거)
      localStorage.setItem(`userBmi_${userNo}`, value || '');
      
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: age || '',
            bmi: value || '',
            gender: gender || '0'
          });
        } catch (err) {
          console.log('BMI UserDefaults 저장 실패:', err);
        }
      }
      
      // 서버에 사용자 정보 업데이트 (user_no가 null이면 API 호출 안 함)
      if (isAuthenticated() && userNo !== null && value.trim()) {
        try {
          const apiBaseUrl = getServerUrl();
          const response = await fetch(`${apiBaseUrl}/user/profile`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({
              age: age ? parseInt(age.trim(), 10) : undefined,
              bmi: parseFloat(value.trim()),
              gender: gender === '1' ? 'M' : 'F'
            })
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log('✅ 사용자 정보 업데이트 완료:', result);
          } else {
            console.error('❌ 사용자 정보 업데이트 실패:', response.status);
          }
        } catch (err) {
          console.error('❌ 사용자 정보 업데이트 중 오류:', err);
        }
      } else if (isAuthenticated() && userNo === null) {
        console.warn('⚠️ handleBmiChange - user_no가 null, 서버 업데이트 건너뜀');
      }
    } catch (err) {
      console.log('BMI 저장 실패:', err);
    }
  };

  const handleGenderChange = async (value: string) => {
    setGender(value);
    try {
      const userNo = getUserNo();
      
      // 로그인 안 되어 있으면 저장하지 않음
      if (!isAuthenticated() || !userNo) {
        return;
      }
      
      // userNo가 있으면 userNo 포함 키로만 저장 (하위 호환성 제거)
      localStorage.setItem(`userGender_${userNo}`, value || '0');
      
      // iOS에서 UserDefaults에 저장
      if (platform === 'ios' && healthDataPlugin) {
        try {
          await healthDataPlugin.saveUserInfo({
            age: age || '',
            bmi: bmi || '',
            gender: value || '0'
          });
        } catch (err) {
          console.log('성별 UserDefaults 저장 실패:', err);
        }
      }
      
      // 서버에 사용자 정보 업데이트 (성별 변경 시 room_threshold 재계산됨, user_no가 null이면 API 호출 안 함)
      if (isAuthenticated() && userNo !== null && value.trim()) {
        try {
          const apiBaseUrl = getServerUrl();
          const response = await fetch(`${apiBaseUrl}/user/profile`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({
              age: age ? parseInt(age.trim(), 10) : undefined,
              bmi: bmi ? parseFloat(bmi) : undefined,
              gender: value === '1' ? 'M' : 'F'
            })
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log('✅ 사용자 정보 업데이트 완료 (성별 변경으로 room_threshold 재계산됨):', result);
            if (result.gender_changed) {
              alert('성별이 변경되어 쾌적 온도 범위가 재계산되었습니다.');
              // IoT 페이지에 온도 범위 갱신 이벤트 발생
              window.dispatchEvent(new CustomEvent('temperatureRangeUpdated', {
                detail: { 
                  gender_changed: true,
                  min_temp: result.min_temp,
                  max_temp: result.max_temp
                }
              }));
            }
          } else {
            console.error('❌ 사용자 정보 업데이트 실패:', response.status);
          }
        } catch (err) {
          console.error('❌ 사용자 정보 업데이트 중 오류:', err);
        }
      } else if (isAuthenticated() && userNo === null) {
        console.warn('⚠️ handleGenderChange - user_no가 null, 서버 업데이트 건너뜀');
      }
    } catch (err) {
      console.log('성별 저장 실패:', err);
    }
  };

  const handleFeedbackTimeChange = async (value: string) => {
    setFeedbackTime(value);
    try {
      const userNo = getUserNo();
      if (userNo) {
        // 사용자별로 피드백 시간 저장
        localStorage.setItem(`feedbackTime_${userNo}`, value || '22:00');
      } else {
        // 로그인하지 않은 경우 공통 저장 (하위 호환성)
        localStorage.setItem('feedbackTime', value || '22:00');
      }
      // 알림 재스케줄
      if (Capacitor.isNativePlatform()) {
        await scheduleDailyNotification();
      }
    } catch (err) {
      console.log('피드백 시간 저장 실패:', err);
    }
  };

  const fetchFeedbackCount = async () => {
    // 로그인 체크
    if (!isAuthenticated()) {
      return; // 로그인하지 않았으면 조용히 무시
    }
    
    try {
      const apiBaseUrl = getServerUrl();
      const response = await fetch(`${apiBaseUrl}/feedback/count`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });

      if (response.ok) {
        const result = await response.json();
        const count = result.count || 0;
        setFeedbackCount(count);
        setIsFeedbackDisabled(count >= 7);
      } else if (response.status === 401) {
        // 인증 실패 시 조용히 무시
        console.log('피드백 카운트 조회 - 인증 필요');
      } else {
        console.log('피드백 카운트 조회 실패:', response.status);
      }
    } catch (err) {
      // 네트워크 오류 등은 조용히 무시
      console.log('피드백 카운트 조회 중 오류:', err);
    }
  };

  const handleFeedbackSubmit = async (feedback: 'hot' | 'cold' | 'comfortable') => {
    try {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      const apiBaseUrl = getServerUrl();
      
      console.log('📤 피드백 전송 시작:', { feedback, apiBaseUrl });
      
      // 인증 헤더 가져오기
      const { getAuthHeaders } = await import('../services/AuthService');
      const headers = getAuthHeaders();
      
      // 타임아웃 추가 (10초)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const response = await fetch(`${apiBaseUrl}/temperature_feedback`, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            feedback: feedback,
            date: new Date().toISOString()
          }),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 피드백 저장 완료:', result);
          setShowFeedbackModal(false);
          alert('✅ 피드백이 저장되었습니다.');
          // 피드백 카운트 업데이트
          await fetchFeedbackCount();
        } else {
          const errorText = await response.text();
          console.error('❌ 피드백 저장 실패:', response.status, response.statusText, errorText);
          alert(`피드백 저장 실패: ${response.status} - ${errorText}`);
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        
        if (fetchError.name === 'AbortError') {
          console.error('❌ 요청 타임아웃 (10초 초과)');
          alert('요청 시간이 초과되었습니다. 서버가 실행 중인지 확인해주세요.');
        } else {
          console.error('❌ 피드백 저장 중 오류:', fetchError);
          // Mixed Content 경고는 무시하고 실제로 요청이 성공했는지 확인
          console.log('💡 Mixed Content 경고가 발생했지만, MIXED_CONTENT_ALWAYS_ALLOW 설정으로 요청이 성공했을 수 있습니다.');
          alert(`피드백 저장 중 오류 발생: ${fetchError.message || fetchError}\n\n서버 로그를 확인해주세요.`);
        }
      }
    } catch (err: any) {
      console.error('❌ 피드백 저장 중 예외:', err);
      alert(`피드백 저장 중 예외 발생: ${err.message || err}`);
    }
  };

  // 알림 클릭 및 수신 이벤트 리스너
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      let actionListener: any = null;
      let receivedListener: any = null;
      
      // 알림 클릭 이벤트
      LocalNotifications.addListener('localNotificationActionPerformed', (action: ActionPerformed) => {
        if (action.notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener: any) => {
        actionListener = listener;
      });
      
      // 알림 수신 이벤트 (앱이 포그라운드에 있을 때)
      LocalNotifications.addListener('localNotificationReceived', (notification: LocalNotificationSchema) => {
        if (notification.extra?.type === 'temperature_feedback') {
          setShowFeedbackModal(true);
        }
      }).then((listener: any) => {
        receivedListener = listener;
      });
      
      // 컴포넌트 언마운트 시 리스너 제거
      return () => {
        if (actionListener) {
          actionListener.remove();
        }
        if (receivedListener) {
          receivedListener.remove();
        }
      };
    }
  }, []);

  // 로그인 상태가 변경될 때마다 사용자 정보 확인 및 초기화
  // 이 useEffect는 다른 useEffect보다 먼저 실행되어야 함 (의존성 배열이 비어있으므로 마운트 시 한 번만 실행)
  useEffect(() => {
    // 마운트 시 즉시 로그인 상태 확인 및 초기화 (동기적으로 실행)
    const authenticated = isAuthenticated();
    const currentUserNo = getUserNo();
    
    setIsLoggedIn(authenticated);
    
    if (!authenticated || !currentUserNo) {
      // 로그인 상태가 아니면 모든 사용자 정보 즉시 초기화
      console.log('🔍 User 페이지 - 마운트 시 로그인 상태 확인: 로그아웃 상태, 사용자 정보 즉시 초기화');
      setAge('');
      setBmi('');
      setGender('0');
    }
    
    const checkAuthAndClearData = () => {
      const auth = isAuthenticated();
      const userNo = getUserNo();
      
      setIsLoggedIn(auth);
      
      if (!auth || !userNo) {
        // 로그인 상태가 아니면 모든 사용자 정보 초기화
        console.log('🔍 User 페이지 - 로그인 상태 확인: 로그아웃 상태, 사용자 정보 초기화');
        setAge('');
        setBmi('');
        setGender('0');
        
        // 로그인 상태가 아닐 때는 localStorage에서 사용자 정보를 읽지 않도록 함
        // (이전 사용자의 데이터가 남아있을 수 있음)
        return;
      }
    };
    
    // 로그인 상태 변경 이벤트 리스너
    const handleAuthCheck = () => {
      // 이벤트 발생 후 약간의 지연을 두어 localStorage 변경이 완료된 후 확인
      setTimeout(() => {
        checkAuthAndClearData();
      }, 100);
    };
    
    window.addEventListener('authStateChanged', handleAuthCheck);
    window.addEventListener('storage', handleAuthCheck);
    window.addEventListener('focus', handleAuthCheck);
    
    return () => {
      window.removeEventListener('authStateChanged', handleAuthCheck);
      window.removeEventListener('storage', handleAuthCheck);
      window.removeEventListener('focus', handleAuthCheck);
    };
  }, []);

  // 다크모드 상태 불러오기 (Home 탭에서 관리하므로 여기서는 불러오기만)
  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    if (savedDarkMode) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, []);

  // 피드백 카운트 조회
  useEffect(() => {
    fetchFeedbackCount();
    // 30초마다 피드백 카운트 업데이트
    const interval = setInterval(() => {
      fetchFeedbackCount();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLoginSuccess = () => {
    // 로그인 성공 플래그 설정 (이벤트 리스너가 상태를 덮어쓰지 않도록)
    loginSuccessRef.current = true;
    
    setIsLoggedIn(true);
    setShowSignIn(false);
    
    // 먼저 사용자 정보 초기화 (이전 사용자 정보가 표시되지 않도록)
    setAge('');
    setBmi('');
    setGender('0');
    
    // 로그인 성공 후 사용자 정보 로드 (user_no가 업데이트될 시간을 줌)
    setTimeout(() => {
      if (loadUserInfoRef.current) {
        console.log('🔄 User 페이지 - 로그인 성공 후 사용자 정보 로드');
        loadUserInfoRef.current();
      }
    }, 200);
    
    // 2초 후 플래그 해제 (이제 다른 이벤트가 상태를 업데이트해도 됨)
    setTimeout(() => {
      loginSuccessRef.current = false;
      console.log('✅ User 페이지 - 로그인 성공 플래그 해제');
    }, 2000);
  };

  const handleLogout = async () => {
    // 로그아웃 진행 중 플래그 설정 (가장 먼저 설정)
    logoutInProgressRef.current = true;
    setShowSignIn(false); // 로그인 모달 닫기
    console.log('🔍 User 페이지 - 로그아웃 시작, 플래그 설정');
    
    // 로그아웃 전에 현재 사용자의 localStorage 데이터 삭제
    const currentUserNo = getUserNo();
    if (currentUserNo) {
      localStorage.removeItem(`userAge_${currentUserNo}`);
      localStorage.removeItem(`userBmi_${currentUserNo}`);
      localStorage.removeItem(`userGender_${currentUserNo}`);
      localStorage.removeItem(`feedbackTime_${currentUserNo}`);
    }
    
    // 로그아웃 전에 수면 모드 종료 시도
    try {
      const { getServerUrl } = await import('../services/ServerConfig');
      const { getAuthHeaders } = await import('../services/AuthService');
      const baseUrl = getServerUrl();
      const authHeaders = getAuthHeaders();
      const headers = {
        ...authHeaders,
        'Content-Type': 'application/json',
      };
      const response = await fetch(`${baseUrl}/sleep-mode/stop`, {
        method: 'POST',
        headers: headers,
      });
      if (response.ok) {
        console.log('✅ 로그아웃 시 수면 모드 종료 완료');
      } else {
        console.warn('⚠️ 로그아웃 시 수면 모드 종료 실패 (무시)');
      }
    } catch (error) {
      // 수면 모드 종료 실패해도 로그아웃은 진행
      console.warn('⚠️ 로그아웃 시 수면 모드 종료 중 오류 (무시):', error);
    }
    
    // 로그아웃 실행 (이벤트 발생)
    logout();
    setIsLoggedIn(false);
    
    // 로그아웃 시 모든 사용자 정보 초기화
    setAge('');
    setBmi('');
    setGender('0');
    
    // 5초 후 플래그 해제 (이제 다른 이벤트가 상태를 업데이트해도 됨)
    setTimeout(() => {
      logoutInProgressRef.current = false;
      console.log('✅ User 페이지 - 로그아웃 완료 플래그 해제');
    }, 5000);
  };

  const handleSignUpSuccess = () => {
    // 로그인 성공 플래그 설정 (이벤트 리스너가 상태를 덮어쓰지 않도록)
    loginSuccessRef.current = true;
    
    setIsLoggedIn(true);
    setShowSignUp(false);
    
    // 먼저 사용자 정보 초기화 (이전 사용자 정보가 표시되지 않도록)
    setAge('');
    setBmi('');
    setGender('0');
    
    // 회원가입 성공 후 사용자 정보 로드 (user_no가 업데이트될 시간을 줌)
    setTimeout(() => {
      if (loadUserInfoRef.current) {
        console.log('🔄 User 페이지 - 회원가입 성공 후 사용자 정보 로드');
        loadUserInfoRef.current();
      }
    }, 200);
    
    // 2초 후 플래그 해제 (이제 다른 이벤트가 상태를 업데이트해도 됨)
    setTimeout(() => {
      loginSuccessRef.current = false;
      console.log('✅ User 페이지 - 회원가입 성공 플래그 해제');
    }, 2000);
  };

  const handleResetFeedbackPeriod = async () => {
    try {
      // ServerConfig에서 URL 가져오기 (localStorage > 환경 변수 > 기본값)
      const apiBaseUrl = getServerUrl();
      
      console.log('📤 피드백 기간 재갱신 요청:', apiBaseUrl);
      
      // 인증 헤더 가져오기
      const { getAuthHeaders } = await import('../services/AuthService');
      const headers = getAuthHeaders();
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const response = await fetch(`${apiBaseUrl}/feedback/reset`, {
          method: 'POST',
          headers: headers,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        console.log('📡 서버 응답 상태:', response.status, response.statusText);

        if (response.ok) {
          const result = await response.json();
          console.log('✅ 피드백 기간 재갱신 완료:', result);
          alert(result.message || '✅ 피드백 기간이 재갱신되었습니다.');
          
          // 재갱신 후 알림 다시 스케줄
          await scheduleDailyNotification();
          // 피드백 카운트 업데이트
          await fetchFeedbackCount();
        } else {
          const errorText = await response.text();
          console.error('❌ 피드백 기간 재갱신 실패:', response.status, response.statusText, errorText);
          alert(`피드백 기간 재갱신 실패: ${response.status} - ${errorText}`);
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        
        if (fetchError.name === 'AbortError') {
          console.error('❌ 요청 타임아웃 (10초 초과)');
          alert('요청 시간이 초과되었습니다. 서버가 실행 중인지 확인해주세요.');
        } else {
          console.error('❌ 피드백 기간 재갱신 중 오류:', fetchError);
          alert(`피드백 기간 재갱신 중 오류 발생: ${fetchError.message || fetchError}`);
        }
      }
    } catch (err: any) {
      console.error('❌ 피드백 기간 재갱신 중 예외:', err);
      alert(`피드백 기간 재갱신 중 예외 발생: ${err.message || err}`);
    }
  };

  // IoT 재등록 화면이 열려있으면 DeviceRegistration만 표시
  if (showIotRegistration && currentUserId) {
    return (
      <DeviceRegistration 
        userId={currentUserId}
        hideHeader={false}
        onSuccess={async () => {
          setShowIotRegistration(false);
          setCurrentUserId(undefined);
          
          // 재등록 후 IoT 서비스 초기화 및 연결 확인
          try {
            // 서버 URL 자동 감지
            const serverUrl = await autoDetectServerUrl();
            if (serverUrl) {
              IotService.updateBaseUrl(serverUrl);
            }
            
            // 잠시 대기 후 IoT 상태 확인 (서버에 반영 시간 필요)
            setTimeout(async () => {
              try {
                const status = await IotService.getStatus();
                console.log('✅ IoT 재등록 후 연결 확인:', status);
              } catch (error) {
                console.error('IoT 연결 확인 실패:', error);
              }
            }, 1000);
            
            alert('IoT 디바이스가 재등록되었습니다. 기기가 자동으로 연결되었습니다.');
            // 성공 후 User 페이지로 돌아가기
            history.push('/user');
          } catch (error) {
            console.error('IoT 연결 확인 실패:', error);
            alert('IoT 디바이스가 재등록되었습니다. IoT 페이지에서 연결 상태를 확인해주세요.');
            // 실패해도 User 페이지로 돌아가기
            history.push('/user');
          }
        }}
        onSkip={() => {
          setShowIotRegistration(false);
          setCurrentUserId(undefined);
          history.push('/user');
        }}
        required={false}
      />
    );
  }

  return (
    <IonPage className="user-page">
      <IonHeader>
        <IonToolbar>
          <IonTitle>사용자</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        {/* 별 배경 효과 (다크모드) */}
        <div className="stars-background"></div>
        
        {/* 로그인 모달 */}
        {showSignIn && (
          <div className="login-modal-backdrop" style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)'
          }}>
            <SignIn 
              onClose={() => {
                // 로그아웃 진행 중이면 모달을 닫지 않음 (이미 닫혀있어야 함)
                if (!logoutInProgressRef.current) {
                  setShowSignIn(false);
                }
              }} 
              onSuccess={handleLoginSuccess} 
            />
          </div>
        )}

        {/* 회원가입 모달 */}
        {showSignUp && (
          <div className="login-modal-backdrop" style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)'
          }}>
            <SignUp onClose={() => setShowSignUp(false)} onSuccess={handleSignUpSuccess} />
          </div>
        )}

        <div className="container">
        <IonCard className="user-info-card">
          <IonCardHeader>
            <IonCardTitle>사용자 정보</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel position="stacked">나이</IonLabel>
              <IonInput
                type="number"
                value={age}
                placeholder="나이를 입력하세요"
                onIonInput={(e) => handleAgeChange(e.detail.value!)}
                disabled={!isLoggedIn}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">BMI</IonLabel>
              <IonInput
                type="number"
                value={bmi}
                placeholder="BMI를 입력하세요"
                onIonInput={(e) => handleBmiChange(e.detail.value!)}
                disabled={!isLoggedIn}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">성별</IonLabel>
              <IonSelect
                value={gender}
                placeholder="성별을 선택하세요"
                onIonChange={(e) => handleGenderChange(e.detail.value)}
                disabled={!isLoggedIn}
              >
                <IonSelectOption value="0">여성</IonSelectOption>
                <IonSelectOption value="1">남성</IonSelectOption>
              </IonSelect>
            </IonItem>
            {!isLoggedIn && (
              <IonText color="medium" style={{ display: 'block', textAlign: 'center', marginTop: '16px', fontSize: '14px' }}>
                로그인 후 사용자 정보를 입력하세요.
              </IonText>
            )}
          </IonCardContent>
        </IonCard>

        <IonCard className="feedback-settings-card">
          <IonCardHeader>
            <IonCardTitle>피드백 알림 설정</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel position="stacked">알림 시간</IonLabel>
              <IonInput
                type="time"
                value={feedbackTime}
                onIonInput={(e) => handleFeedbackTimeChange(e.detail.value!)}
              />
            </IonItem>
            <IonButton 
              expand="block" 
              className="feedback-submit-button"
              onClick={() => {
                fetchFeedbackCount(); // 모달 열 때 카운트 다시 확인
                setShowFeedbackModal(true);
              }} 
              disabled={isFeedbackDisabled}
              style={{ marginTop: '16px' }}
            >
              지금 피드백 남기기 {!isFeedbackDisabled && `(${feedbackCount}/7)`}
            </IonButton>
            {isFeedbackDisabled && (
              <IonText color="medium" style={{ display: 'block', textAlign: 'center', marginTop: '8px', fontSize: '14px' }}>
                피드백을 7번 완료했습니다. 재갱신 버튼을 눌러 다시 시작하세요.
              </IonText>
            )}
          </IonCardContent>
        </IonCard>

        <IonCard className="settings-card">
          <IonCardHeader>
            <IonCardTitle>설정</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonText color="medium" style={{ display: 'block', textAlign: 'center', marginBottom: '16px', fontSize: '13px' }}>
              재갱신 시 다시 7번의 피드백이 필요합니다
            </IonText>
            <IonButton 
              expand="block" 
              className="reset-feedback-button"
              onClick={() => setShowResetAlert(true)}
              style={{ marginTop: '0' }}
            >
              <IonIcon icon={refreshOutline} slot="start" />
              온도 범위 재갱신
            </IonButton>
            {isAuthenticated() ? (
              <>
                <IonButton 
                  expand="block" 
                  onClick={async () => {
                    try {
                      const user = await getCurrentUser();
                      setCurrentUserId(user.id);
                      setShowIotRegistration(true);
                    } catch (error) {
                      console.error('사용자 정보 가져오기 실패:', error);
                      alert('사용자 정보를 가져올 수 없습니다. 다시 로그인해주세요.');
                    }
                  }} 
                  style={{ marginTop: '16px' }}
                >
                  IoT 재등록
                </IonButton>
                <IonButton expand="block" onClick={handleLogout} style={{ marginTop: '16px' }}>
                  로그아웃
                </IonButton>
              </>
            ) : (
              <>
                <IonButton expand="block" onClick={() => setShowSignIn(true)} style={{ marginTop: '16px' }}>
                  로그인
                </IonButton>
                <div style={{ textAlign: 'center', marginTop: '12px' }}>
                  <button 
                    className="sign-up-link-text"
                    onClick={() => setShowSignUp(true)}
                  >
                    회원가입
                  </button>
                </div>
              </>
            )}
          </IonCardContent>
        </IonCard>

        </div>

        {/* 하단 여백 추가 (스크롤 끝까지 내려가도록) */}
        <div style={{ height: '80px', width: '100%' }}></div>

        {/* 피드백 모달 */}
        <IonModal 
          isOpen={showFeedbackModal} 
          onDidDismiss={() => setShowFeedbackModal(false)}
          backdropDismiss={true}
          className="feedback-modal"
        >
          <IonContent className="feedback-content-wrapper" scrollY={false}>
            <div className="feedback-card">
              <div className="feedback-header">
                <h1>온도 피드백</h1>
                <button 
                  className="feedback-close-button"
                  onClick={() => setShowFeedbackModal(false)}
                  aria-label="닫기"
                >
                  <IonIcon icon={closeOutline} />
                </button>
              </div>
              <div className="feedback-body">
                <h2 className="feedback-title">오늘밤 온도는 어땠나요?</h2>
                <div className="feedback-emoji-container">
                  <div 
                    className="feedback-emoji-item hot-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('hot')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">🔥</div>
                    <div className="feedback-text">더웠어요</div>
                  </div>
                  <div 
                    className="feedback-emoji-item comfortable-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('comfortable')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">🍀</div>
                    <div className="feedback-text">쾌적했어요</div>
                  </div>
                  <div 
                    className="feedback-emoji-item cold-feedback"
                    onClick={() => !isFeedbackDisabled && handleFeedbackSubmit('cold')}
                    style={{ 
                      cursor: isFeedbackDisabled ? 'not-allowed' : 'pointer',
                      opacity: isFeedbackDisabled ? 0.5 : 1
                    }}
                  >
                    <div className="feedback-emoji">❄️</div>
                    <div className="feedback-text">추웠어요</div>
                  </div>
                </div>
              </div>
            </div>
          </IonContent>
        </IonModal>

        {/* 재갱신 확인 알림 */}
        <IonAlert
          isOpen={showResetAlert}
          onDidDismiss={() => setShowResetAlert(false)}
          header="온도 범위 재갱신"
          subHeader="재갱신을 하게되면 다시 7번의 피드백을 해주셔야 합니다. 현재 저장된 범위부터 다시 7번의 피드백을 받아 조정합니다."
          message="계속하시겠습니까?"
          buttons={[
            {
              text: '취소',
              role: 'cancel',
              handler: () => {
                setShowResetAlert(false);
              }
            },
            {
              text: '확인',
              handler: () => {
                handleResetFeedbackPeriod();
                setShowResetAlert(false);
              }
            }
          ]}
        />

      </IonContent>
    </IonPage>
  );
};

export default User;

