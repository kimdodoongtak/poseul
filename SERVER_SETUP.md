# 서버 실행 가이드 (안드로이드 스튜디오용)

## 서버 실행 방법

### 1. 서버 위치
```
android/plus/model/server/app.py
```

### 2. 서버 실행

터미널에서 다음 명령어 실행:

```bash
cd android/plus/model/server
python app.py
```

또는

```bash
cd android/plus/model/server
python run_server.py
```

### 3. 서버 실행 확인

서버가 정상적으로 실행되면 다음과 같은 메시지가 표시됩니다:
```
INFO:__main__:앙상블 모델 로드 완료
INFO:__main__:서버 시작 중...
 * Running on http://0.0.0.0:5000
```

### 4. 안드로이드 스튜디오에서 서버 접속 설정

#### 안드로이드 에뮬레이터 사용 시
- 서버 URL: `http://10.0.2.2:5000`
- 에뮬레이터는 `10.0.2.2`를 호스트 컴퓨터의 `localhost`로 매핑합니다.

#### 실제 안드로이드 기기 사용 시
1. 컴퓨터 IP 주소 확인:
   - Windows: `ipconfig` (IPv4 주소 확인)
   - Mac/Linux: `ifconfig` 또는 `ip addr`
   - 예: `192.168.0.100`

2. 서버 URL: `http://YOUR_COMPUTER_IP:5000`
   - 예: `http://192.168.0.100:5000`

3. **중요**: 안드로이드 기기와 컴퓨터가 같은 Wi-Fi 네트워크에 연결되어 있어야 합니다.

### 5. 서버 테스트

브라우저나 curl로 테스트:
```bash
curl http://localhost:5000/health
```

응답 예시:
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

### 6. 필요한 Python 패키지

서버 실행 전에 패키지 설치:
```bash
cd android/plus/model/server
pip install -r requirements.txt
```

필요한 패키지:
- Flask>=2.3.0
- Flask-CORS>=4.0.0
- pandas>=2.0.0
- numpy>=1.24.0
- scikit-learn>=1.3.0
- joblib>=1.3.0
- requests>=2.31.0

### 7. 서버 API 엔드포인트

#### 모델 관련
- `GET /health` - 서버 상태 확인
- `POST /predict` - 체온 예측
- `GET /model_info` - 모델 정보

#### IoT 관련 (LG ThinQ API)
- `GET /air_conditioner/state` - 에어컨 상태 조회
- `POST /air_conditioner/control` - 에어컨 제어

#### 건강 데이터 공유
- `POST /health_data/save` - iOS HealthKit 데이터 저장
- `GET /health_data/latest` - 저장된 건강 데이터 조회

### 8. 주의사항

1. **서버는 먼저 실행해야 합니다**: 안드로이드 앱 실행 전에 서버가 실행 중이어야 합니다.
2. **방화벽 설정**: 실제 안드로이드 기기 사용 시 방화벽에서 포트 5000을 허용해야 할 수 있습니다.
3. **모델 파일**: `ai_thermal_model_with_age.pkl` 파일이 `android/plus/model/pycode/` 폴더에 있어야 합니다.
4. **LG ThinQ API**: IoT 기능 사용 시 `android/plus/IoT/test.py`에 설정된 API 키와 토큰이 필요합니다.

### 9. 문제 해결

#### 서버 연결 실패
- 서버가 실행 중인지 확인
- 포트 5000이 다른 프로그램에서 사용 중인지 확인
- 안드로이드 기기와 컴퓨터가 같은 네트워크에 있는지 확인

#### 모델 로드 실패
- 모델 파일 경로 확인: `android/plus/model/pycode/ai_thermal_model_with_age.pkl`
- Python 패키지가 모두 설치되었는지 확인

#### 안드로이드 앱에서 서버 연결 실패
- 에뮬레이터: `http://10.0.2.2:5000` 사용
- 실제 기기: 컴퓨터 IP 주소 사용 (예: `http://192.168.0.100:5000`)
- 서버가 `0.0.0.0:5000`으로 실행 중인지 확인 (외부 접속 허용)

