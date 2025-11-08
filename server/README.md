# Health Data Server

HealthKit 데이터를 받아서 MySQL DB에 저장하는 FastAPI 서버입니다.

## 설치

```bash
# Python 가상환경 생성 (선택사항)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows

# 패키지 설치
pip install -r requirements.txt
```

## 실행

### 방법 1: 직접 실행
```bash
python3 server.py
```

### 방법 2: uvicorn으로 실행
```bash
uvicorn server:app --host 0.0.0.0 --port 3000
```

### 방법 3: 백그라운드 실행 (nohup)
```bash
nohup python3 server.py > server.log 2>&1 &
```

### 방법 4: PM2 사용 (권장)
```bash
# PM2 설치
npm install -g pm2

# 서버 실행
pm2 start server.py --name health-server --interpreter python3

# 서버 상태 확인
pm2 status

# 로그 확인
pm2 logs health-server

# 서버 중지
pm2 stop health-server

# 서버 재시작
pm2 restart health-server

# 서버 삭제
pm2 delete health-server
```

### 방법 5: systemd 서비스 (Linux)
```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/health-server.service
```

서비스 파일 내용:
```ini
[Unit]
Description=Health Data Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/poseul/server
ExecStart=/usr/bin/python3 /path/to/poseul/server/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화 및 시작
sudo systemctl enable health-server
sudo systemctl start health-server

# 상태 확인
sudo systemctl status health-server
```

## API 엔드포인트

### POST /healthdata
HealthKit 데이터를 받아서 DB에 저장합니다.

**Request Body:**
```json
{
  "heartRate": 72.0,
  "HRV": 45.2,
  "oxygenSaturation": 98.5,
  "bmi": 22.5,
  "age": 25
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Data saved successfully"
}
```

### GET /
서버 상태 확인

### GET /health
헬스 체크

## 환경 변수

DB 연결 정보는 `server.py` 파일에서 직접 설정되어 있습니다.
프로덕션 환경에서는 환경 변수로 관리하는 것을 권장합니다.

