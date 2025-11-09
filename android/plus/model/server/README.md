# AI 체온 예측 서버

앙상블 모델을 사용한 체온 예측 API 서버입니다.

## 🚀 빠른 시작

### 1. 서버 실행
```bash
cd model/server
python run_server.py
```

### 2. 서버 테스트
```bash
python test_client.py
```

## 📊 API 엔드포인트

### GET /health
서버 상태 및 모델 로드 상태 확인

**응답:**
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

### POST /predict
체온 예측 수행

**요청:**
```json
{
  "hr_mean": 72.0,
  "hrv_sdnn": 45.2,
  "bmi": 22.5,
  "mean_sa02": 98.5,
  "gender": "F"
}
```

**응답:**
```json
{
  "success": true,
  "predicted_temperature": 34.2,
  "temperature_category": "적정",
  "input_data": { ... }
}
```

### GET /model_info
모델 정보 조회

**응답:**
```json
{
  "model_type": "앙상블 모델 (RandomForest + ExtraTrees + GradientBoosting)",
  "features": ["bmi", "mean_sa02", "HRV_SDNN", "hrv_hr_ratio", "bmi_hr_interaction", "gender"],
  "target": "TEMP_median (체온)",
  "model_loaded": true
}
```

## 🔧 모델 정보

- **모델 타입**: 앙상블 모델 (RandomForest + ExtraTrees + GradientBoosting)
- **입력 피처**: 
  - `bmi`: 체질량지수
  - `mean_sa02`: 평균 산소포화도
  - `HRV_SDNN`: 심박변이도
  - `hrv_hr_ratio`: HRV/HR 비율 (자동 계산)
  - `bmi_hr_interaction`: BMI × HR 상호작용 (자동 계산)
  - `gender`: 성별 ('M' 또는 'F')

- **출력**: 
  - 예측 체온 (°C)
  - 온도 분류 (냉기/적정/더위)

## 📱 Android 앱 연동

Android 앱에서 이 서버를 사용하려면:

1. **서버 URL 설정**: `ModelService.kt`에서 `SERVER_URL` 수정
2. **네트워크 권한**: `AndroidManifest.xml`에 인터넷 권한 추가 (이미 완료)
3. **API 호출**: `ModelService.predictTemperature()` 메서드 사용

### 사용 예시 (Android)
```kotlin
val modelService = ModelService()
val result = modelService.predictTemperature(
    heartRate = 72,
    hrvSdnn = 45.2,
    bmi = 22.5,
    meanSa02 = 98.5,
    userGender = "female"
)

when (result) {
    is PredictionResult.Success -> {
        println("예측 체온: ${result.temperature}°C")
        println("온도 분류: ${result.category}")
    }
    is PredictionResult.Error -> {
        println("예측 실패: ${result.message}")
    }
}
```

## 🛠️ 개발 환경

- Python 3.8+
- Flask 2.3.3
- scikit-learn 1.3.0
- pandas 2.0.3
- numpy 1.24.3

## 📝 주의사항

1. **모델 파일**: `ai_thermal_model.pkl2.zip` 파일이 상위 디렉토리에 있어야 합니다.
2. **포트**: 기본 포트는 5000입니다. 변경하려면 `app.py`를 수정하세요.
3. **CORS**: 개발 환경에서만 CORS가 활성화되어 있습니다.
4. **Android 에뮬레이터**: `10.0.2.2`는 Android 에뮬레이터에서 localhost를 가리킵니다.

## 🔍 문제 해결

### 모델 로드 실패
- `ai_thermal_model.pkl2.zip` 파일이 올바른 위치에 있는지 확인
- 파일 권한 확인

### Android 앱 연결 실패
- 서버가 실행 중인지 확인
- Android 에뮬레이터 사용 시 `10.0.2.2:5000` 사용
- 실제 기기 사용 시 컴퓨터의 IP 주소 사용

### 예측 실패
- 입력 데이터 형식 확인
- 필수 파라미터 누락 확인
- 서버 로그 확인
