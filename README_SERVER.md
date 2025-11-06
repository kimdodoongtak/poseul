# 서버 실행 가이드

## 서버 위치

- 모델 서버: `android/plus/model/server/`
- IoT 서버: `android/plus/IoT/` (모델 서버에 통합됨)

## 서버 실행 방법

### 1. 모델 서버 실행

```bash
cd android/plus/model/server
python app.py
```

또는

```bash
cd android/plus/model/server
python run_server.py
```

서버가 실행되면:
- 기본 포트: `5000`
- URL: `http://localhost:5000`

### 2. API 엔드포인트

#### 모델 서버
- `GET /health` - 서버 상태 확인
- `POST /predict` - 체온 예측
- `GET /model_info` - 모델 정보

#### IoT 서버 (에어컨 제어)
- `GET /air_conditioner/state` - 에어컨 상태 조회
- `POST /air_conditioner/control` - 에어컨 제어

### 3. 앱에서 서버 접속

#### 웹 개발 환경
- URL: `http://localhost:5000`
- `.env` 파일에 설정: `VITE_API_BASE_URL=http://localhost:5000`

#### 안드로이드 에뮬레이터
- URL: `http://10.0.2.2:5000`
- `.env` 파일에 설정: `VITE_API_BASE_URL=http://10.0.2.2:5000`

#### 실제 안드로이드 기기
1. 컴퓨터 IP 주소 확인:
   - Windows: `ipconfig`
   - Mac/Linux: `ifconfig`
2. URL: `http://YOUR_COMPUTER_IP:5000`
   - 예: `http://192.168.0.100:5000`
3. `.env` 파일에 설정: `VITE_API_BASE_URL=http://YOUR_COMPUTER_IP:5000`

#### iOS 시뮬레이터
- URL: `http://localhost:5000`
- `.env` 파일에 설정: `VITE_API_BASE_URL=http://localhost:5000`

#### 실제 iOS 기기
1. 컴퓨터 IP 주소 확인
2. URL: `http://YOUR_COMPUTER_IP:5000`
3. `.env` 파일에 설정: `VITE_API_BASE_URL=http://YOUR_COMPUTER_IP:5000`

### 4. 환경 변수 설정

`.env` 파일을 생성하고 설정:

```env
VITE_API_BASE_URL=http://localhost:5000
```

### 5. 서버 요구사항

Python 패키지 설치:

```bash
cd android/plus/model/server
pip install -r requirements.txt
```

### 6. 테스트

서버가 실행 중인지 확인:

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

