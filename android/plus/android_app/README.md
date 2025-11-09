# AI Service Poseul - 안드로이드 앱

AI 기반 온도 예측 및 IOT 기기 관리 안드로이드 애플리케이션입니다.

## 주요 기능

### 1. 홈 페이지
- **온도 예측**: AI 모델을 통한 개인화된 온도 예측
- **쾌적도 표시**: 더움/추움/쾌적함 상태 표시
- **심박수 그래프**: 실시간 심박수 데이터를 선 그래프로 표시

### 2. 사용자 페이지
- **사용자 정보**: 로그인/로그아웃 기능
- **모델 재학습**: 새로운 데이터로 AI 모델 재학습 기능

### 3. IOT 기기 페이지
- **에어컨 상태**: 현재 온도, 설정 온도, 온라인/오프라인 상태
- **기타 IOT 기기**: 연결된 모든 IOT 기기의 상태 확인

## 기술 스택

- **언어**: Kotlin
- **UI**: Material Design 3
- **아키텍처**: MVVM (Model-View-ViewModel)
- **네비게이션**: Navigation Component
- **차트**: MPAndroidChart
- **네트워킹**: Retrofit2
- **비동기 처리**: Coroutines

## 프로젝트 구조

```
app/
├── src/main/java/com/aiservice/poseul/
│   ├── MainActivity.kt                 # 메인 액티비티
│   ├── ui/
│   │   ├── home/                      # 홈 페이지
│   │   │   ├── HomeFragment.kt
│   │   │   └── HomeViewModel.kt
│   │   ├── user/                      # 사용자 페이지
│   │   │   ├── UserFragment.kt
│   │   │   └── UserViewModel.kt
│   │   └── iot/                       # IOT 기기 페이지
│   │       ├── IotFragment.kt
│   │       └── IotViewModel.kt
│   └── service/                       # 서비스 클래스
│       ├── ModelService.kt
│       └── IotService.kt
└── src/main/res/                      # 리소스 파일
    ├── layout/                        # 레이아웃 파일
    ├── values/                        # 문자열, 색상, 테마
    ├── drawable/                      # 아이콘
    └── navigation/                    # 네비게이션 그래프
```

## 설치 및 실행

1. Android Studio에서 프로젝트를 엽니다
2. Gradle 동기화를 완료합니다
3. 에뮬레이터 또는 실제 기기에서 앱을 실행합니다

## 주요 의존성

```gradle
implementation 'androidx.core:core-ktx:1.12.0'
implementation 'androidx.appcompat:appcompat:1.6.1'
implementation 'com.google.android.material:material:1.11.0'
implementation 'androidx.navigation:navigation-fragment-ktx:2.7.6'
implementation 'androidx.navigation:navigation-ui-ktx:2.7.6'
implementation 'com.github.PhilJay:MPAndroidChart:v3.1.0'
implementation 'com.squareup.retrofit2:retrofit:2.9.0'
implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
```

## 향후 개발 계획

1. **실제 AI 모델 연동**: CatBoost 모델을 실제로 로드하고 예측 수행
2. **실시간 데이터 수집**: 심박수 센서와 IOT 기기에서 실시간 데이터 수집
3. **사용자 인증**: 실제 로그인/회원가입 기능 구현
4. **푸시 알림**: 온도 이상이나 IOT 기기 상태 변화 알림
5. **데이터 저장**: 로컬 데이터베이스 (Room) 연동

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
