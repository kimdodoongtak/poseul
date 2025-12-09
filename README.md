# 🌡️ 포슬 (Poseul)

> AI 기반 개인 맞춤형 체온 예측 및 IoT 에어컨 자동 제어 서비스

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.1+-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19.0-blue.svg)](https://reactjs.org/)
[![Ionic](https://img.shields.io/badge/Ionic-8.5-purple.svg)](https://ionicframework.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3+-orange.svg)](https://scikit-learn.org/)

---

## 📋 목차

- [프로젝트 소개](#-프로젝트-소개)
- [주요 기능](#-주요-기능)
- [데이터 설명](#-데이터-설명)
- [AI 모델](#-ai-모델)
- [기술 스택](#-기술-스택)
- [프로젝트 구조](#-프로젝트-구조)
- [설치 및 실행](#-설치-및-실행)
- [개발 도구](#-개발-도구)

---

## 🎯 프로젝트 소개

**포슬(Poseul)**은 사용자의 건강 데이터(심박수, 심박변이도, 산소포화도, BMI, 나이, 성별)를 기반으로 AI가 체온을 예측하고, 예측된 체온에 따라 IoT 에어컨을 자동으로 제어하는 개인 맞춤형 건강 관리 서비스입니다.

### 핵심 가치

- 🤖 **AI 기반 예측**: 머신러닝 모델을 통한 정확한 체온 예측
- 🎯 **개인 맞춤형**: 사용자의 나이, 성별, BMI 등을 고려한 맞춤형 서비스
- 🏠 **스마트 홈 연동**: 예측된 체온에 따른 자동 에어컨 제어
- 📱 **크로스 플랫폼**: iOS, Android 지원

---
### 센서와의 차별점
센서는 환경온도에 매우 민감하게 반응
온도센서 하나만을 사용하는데, 이는 신뢰성 있는 결과를 얻기 어려움

이에 모델예측을 사용함으로써, 환경민감성이 낮아지고 여러 생체데이터(심박수,산소포화도,심박변이)를 사용하여 지능적으로 예측한다는 차별점이 있음음


## ✨ 주요 기능

### 1. 건강 데이터 수집 및 분석
- 📊 실시간 심박수, 심박변이도(HRV), 산소포화도 모니터링
- 📈 건강 데이터 시각화 (차트)
- 💾 건강 데이터 히스토리 관리

### 2. AI 체온 예측
- 🔮 사용자 건강 데이터 기반 체온 예측
- 🎯 개인 특성(나이, 성별, BMI) 반영
- ⚡ 실시간 예측 (평균 예측 시간: < 1ms)

### 3. IoT 에어컨 자동 제어
- 🌡️ 예측된 체온에 따른 자동 온도 조절
- 🎚️ 사용자 맞춤형 쾌적 온도 범위 계산
- 🔄 피드백 기반 온도 임계값 자동 조정

### 4. 사용자 인증 및 관리
- 🔐 JWT 기반 인증 시스템
- 👤 사용자별 개인화 설정
- 📱 iOS HealthKit 연동

---
## 📊 데이터 설명

### 원데이터 출처

- **데이터셋**: DREAMT (멀티센서 웨어러블 기술을 이용한 실시간 수면 단계 추정 데이터셋)
- **파일 출처**: [PhysioNet - DREAMT Dataset](https://physionet.org/content/dreamt/2.1.0/data_64Hz/#files-panel)
- **원본 코드**: [DREAMT_FE GitHub Repository](https://github.com/WillKeWang/DREAMT_FE)

DREAMT 데이터셋은 멀티센서 웨어러블 장치를 통해 수집된 수면 단계 추정 데이터로, 본 프로젝트에서는 체온 예측을 위한 학습 데이터로 활용되었습니다.


## 🤖 AI 모델

### 모델 개요

본 프로젝트는 **Gradient Boosting Regressor**를 사용하여 체온을 예측하는 회귀 모델을 구현했습니다.

### 모델 아키텍처

```
┌─────────────────────────────────────────┐
│         입력 피처 (9개)                  │
├─────────────────────────────────────────┤
│ • BMI (체질량지수)                       │
│ • mean_sa02 (평균 산소포화도)            │
│ • HRV_SDNN (심박변이도)                  │
│ • hrv_hr_ratio (HRV/HR 비율)            │
│ • bmi_hr_interaction (BMI × HR)         │
│ • age (나이)                            │
│ • age_bmi_interaction (나이 × BMI)      │
│ • age_hrv_ratio (나이/HRV 비율)         │
│ • gender (성별: M/F)                    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      전처리 파이프라인                    │
├─────────────────────────────────────────┤
│ • StandardScaler (수치형 피처)          │
│ • OneHotEncoder (범주형 피처)            │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   GradientBoostingRegressor              │
├─────────────────────────────────────────┤
│ • n_estimators: 1000                     │
│ • learning_rate: 0.01                   │
│ • max_depth: 6                           │
│ • subsample: 0.9                         │
│ • random_state: 42                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      예측 체온 (°C)                      │
└─────────────────────────────────────────┘
```

### 모델 성능 지표

| 지표 | 값 | 설명 |
|------|-----|------|
| **R² Score** | **0.6472** | 생리적 데이터의 개인·환경 요인 고려 시 R² > 0.5는 우수한 지표 |
| **CV R² Score** | **0.5728** | CV에서도 안정적인 결과 → 과적합 위험 낮음 |
| **MAE** | **0.8872°C** | 피부온도의 변동성을 생각하였을 때, MAE의 값은 나쁘지 않음 |
| **예측 속도** | **< 1ms** | 평균 예측 시간 (단일 샘플) |

#### 성능 지표 타당성 근거

- **R² Score 0.6472의 의미**: 
  - 임상 데이터에서 R² 평균 0.15~0.25도 의미 있음 (Cureus, 2023)
  - 심전도 신호를 활용한 체온 추정 연구에서 R² ≈ 0.460 (PLOS ONE, 2022)
  - 본 모델의 R² 0.6472는 생리적 데이터 예측 모델로서 우수한 성능을 보임

- **CV R² Score 0.5728의 의미**:
  - 교차 검증에서도 안정적인 성능 유지
  - 과적합 위험이 낮음을 의미

- **MAE 0.8872°C의 의미**:
  - 피부 온도는 조절되지 않아 변동성이 매우 큼 (Werner, J., 2014)
  - 이러한 변동성을 고려할 때 MAE 0.8872°C는 실용적으로 충분한 정확도

### 피처 중요도

모델에서 사용하는 주요 피처들의 중요도는 다음과 같습니다:

| 순위 | 변수명 | 중요도 (%) | 설명 |
|------|--------|-----------|------|
| 1 | **BMI** | **23.2** | 체질량지수가 높을수록 체열 보존 능력이 큼 |
| 2 | **mean_saO₂** | **16.2** | 산소포화도가 낮으면 조직 대사율이 감소 |
| 3 | **HRV_HR_ratio** | **14.8** | 심박수 변동과 심박 비율의 복합 지표 |
| 4 | **HRV_SDNN** | **11.3** | 심박변이도 자율신경 반응 반영 |
| 5 | **BMI_HR_interaction** | **10.5** | BMI와 심박수의 상호작용 효과 |
| 6 | **Age** | **8.7** | 나이에 따른 체온 변화 특성 |

### 피처 엔지니어링

모델은 다음과 같은 파생 피처를 생성하여 사용합니다:

1. **hrv_hr_ratio**: 심박변이도와 심박수의 비율
2. **bmi_hr_interaction**: BMI와 심박수의 상호작용
3. **age_bmi_interaction**: 나이와 BMI의 상호작용
4. **age_hrv_ratio**: 나이와 심박변이도의 비율

### 온도 분류

신체 쾌적온도는 다음온도를 기반으로 성별,나이,bmi로 분류합니다:

- **냉기**: 체온 < 34.6°C
- **적정**: 34.6°C ≤ 체온 ≤ 35.6°C
- **더위**: 체온 > 35.6°C

### 환경온도 설정 기준

예측된 체온에 따라 사용자의 개인 특성(나이, BMI, 성별)을 기반으로 환경 온도를 조절합니다.

#### 나이별 온도 조절

| 나이 | 온도 조절 | 관련 연구 |
|------|----------|----------|
| 20-70세 | 기준온도 적용 | - |
| 70-79세 | **+0.5°C** | 나이가 들수록 추위를 더 예민하게 느끼고, 편안함을 위해 더 높은 온도를 선호 (Rewitz & Müller, 2022; Wang et al., 2025) |
| 80세 이상 | **+2°C** | - |

#### BMI별 온도 조절

| BMI | 온도 조절 | 관련 연구 |
|-----|----------|----------|
| 저체중 (<18.5) | **+1°C** | BMI가 낮을수록 추위에 더 민감 (Rewitz & Müller, 2022; worldhome.co.kr 건강가이드) |
| 정상체중 (18.5-23) | 기준온도 적용 | - |
| 과체중 (23-25) | **-0.5°C** | BMI가 높을수록 더위에 더 민감 |
| 비만 (>25) | **-1°C** | - |

#### 성별별 온도 조절

| 성별 | 온도 조절 | 관련 연구 |
|------|----------|----------|
| 남성 | 기준온도 적용 | 남성은 열 조절이 강함 (Xu et al., 2024, Sci Total Environ) |
| 여성 | **+0.5°C** | 여성은 추위를 더 타며 약 0.7°C 더 높은 온도를 선호 (Maykot et al., 2022, Sustainability) |



---

## 🛠️ 기술 스택

### 프론트엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| **React** | 19.0.0 | UI 프레임워크 |
| **TypeScript** | 5.1.6 | 타입 안정성 |
| **Ionic** | 8.5.0 | 모바일 UI 컴포넌트 |
| **Capacitor** | 7.0.0 | 네이티브 기능 접근 |
| **Recharts** | 3.4.1 | 데이터 시각화 |
| **Vite** | 5.4.21 | 빌드 도구 |

### 백엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| **FastAPI** | 0.115.0+ | REST API 서버 |
| **Python** | 3.8+ | 백엔드 언어 |
| **scikit-learn** | 1.3.0+ | 머신러닝 라이브러리 |
| **pandas** | 2.0.0+ | 데이터 처리 |
| **SQLAlchemy** | 2.0.23+ | ORM |
| **PyMySQL** | 1.1.0+ | MySQL 연결 |
| **APScheduler** | 3.10.0+ | 스케줄링 |

### 데이터베이스

- **MySQL** (AWS RDS)

### 모바일 플랫폼

- **iOS**: HealthKit 연동
- **Android**: Health Data API 연동

---

## 📁 프로젝트 구조

```
poseul/
├── 📱 src/                          # 프론트엔드 소스 코드
│   ├── components/                  # React 컴포넌트
│   │   ├── SignIn.tsx              # 로그인 컴포넌트
│   │   ├── SignUp.tsx              # 회원가입 컴포넌트
│   │   ├── HeartRateChart.tsx      # 심박수 차트
│   │   └── TemperatureChart.tsx    # 체온 차트
│   ├── pages/                       # 페이지 컴포넌트
│   │   ├── Home.tsx                # 홈 페이지
│   │   ├── Health_ios.tsx          # iOS 건강 데이터
│   │   ├── Iot.tsx                 # IoT 제어
│   │   └── User.tsx                # 사용자 설정
│   ├── services/                    # API 서비스
│   └── plugins/                     # Capacitor 플러그인
│
├── 🖥️ server/                        # 백엔드 서버
│   ├── server.py                    # FastAPI 메인 서버
│   ├── model_utils.py               # 모델 유틸리티
│   ├── temperature_control_logic.py # 온도 제어 로직
│   ├── air_conditioner_auto_control.py # 에어컨 제어
│   ├── feedback_based_adjustment.py  # 피드백 기반 조정
│   ├── predict_missing.py           # 결측값 예측
│   ├── ai_thermal_model_final.pkl  # 학습된 모델 파일
│   └── requirements.txt             # Python 의존성
│
├── 🤖 aI_service_model_final.py      # 모델 학습 스크립트
│
├── 📱 ios/                          # iOS 네이티브 코드
│   └── App/
│       └── HealthKit.swift          # HealthKit 연동
│
├── 🤖 android/                      # Android 네이티브 코드
│   └── app/src/                     # Android 소스
│
└── 📄 package.json                  # Node.js 의존성
```

---

## 🚀 설치 및 실행

### 사전 요구사항

- **Node.js** 18.0 이상
- **Python** 3.8 이상
- **MySQL** 데이터베이스
- **iOS**: Xcode 14.0 이상 (macOS만)
- **Android**: Android Studio

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/poseul.git
cd poseul
```

### 2. 프론트엔드 설정

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build
```

### 3. 백엔드 설정

```bash
# Python 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
cd server
pip install -r requirements.txt

# 서버 실행
python server.py
```

또는 npm 스크립트 사용:

```bash
# 서버 의존성 설치
npm run server:install

# 서버 실행
npm run server:start

# PM2로 실행 (프로덕션)
npm run server:pm2:start
```

### 4. 모바일 앱 빌드

#### iOS

```bash
# iOS 빌드
npm run build:ios

# Xcode에서 열기
npx cap open ios
```

#### Android

```bash
# Android 빌드
npm run build
npx cap sync android

# Android Studio에서 열기
npx cap open android
```

### 5. 환경 변수 설정

`.env` 파일 생성:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🛠️ 개발 도구

### 코드 품질

- **ESLint**: JavaScript/TypeScript 린팅
- **TypeScript**: 타입 체크
- **Prettier**: 코드 포맷팅 (권장)

### 테스팅

- **Cypress**: E2E 테스트
- **Vitest**: 단위 테스트

```bash
# E2E 테스트 실행
npm run test.e2e

# 단위 테스트 실행
npm run test.unit
```

### 빌드 도구

- **Vite**: 빠른 개발 서버 및 빌드
- **TypeScript Compiler**: 타입 체크 및 컴파일

### 버전 관리

- **Git**: 소스 코드 관리

### 배포

- **PM2**: Node.js 프로세스 관리 (서버)
- **Railway**: 서버 배포 플랫폼 (참고: `server/RAILWAY_DEPLOY.md`)

---

## 📚 추가 문서

- [HealthKit 설정 가이드](HEALTHKIT_SETUP.md)
- [Railway 배포 가이드](server/RAILWAY_DEPLOY.md)

---

## 📝 라이선스

이 프로젝트는 개인 프로젝트입니다.

---

## 👥 기여자

- 프로젝트 개발자
- @wehaveeraser
---

## 📧 문의

프로젝트에 대한 문의사항이 있으시면 이슈를 등록해주세요.

---

<div align="center">

**Made with ❤️ using AI and IoT**

</div>

