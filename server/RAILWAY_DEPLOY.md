# Railway 배포 가이드

이 가이드는 서버를 Railway에 배포하는 방법을 설명합니다.

## 사전 준비

1. [Railway](https://railway.app) 계정 생성
2. GitHub 저장소 준비 (선택사항, 자동 배포를 위해)

## 배포 방법

### 방법 1: GitHub 연동 (권장)

1. **GitHub에 코드 푸시**
   ```bash
   git add .
   git commit -m "Railway 배포 준비"
   git push origin main
   ```

2. **Railway에서 새 프로젝트 생성**
   - Railway 대시보드에서 "New Project" 클릭
   - "Deploy from GitHub repo" 선택
   - 저장소 선택
   - `poseul/server` 디렉토리 선택

3. **환경 변수 설정**
   Railway 대시보드에서 다음 환경 변수를 설정:
   ```
   DB_URL=mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main
   ```

4. **배포 확인**
   - Railway가 자동으로 빌드 및 배포
   - 배포 완료 후 제공되는 URL 확인 (예: `https://your-app.railway.app`)

### 방법 2: Railway CLI 사용

1. **Railway CLI 설치**
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. **프로젝트 초기화**
   ```bash
   cd poseul/server
   railway init
   ```

3. **환경 변수 설정**
   ```bash
   railway variables set DB_URL="mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main"
   ```

4. **배포**
   ```bash
   railway up
   ```

## 환경 변수

Railway 대시보드에서 다음 환경 변수를 설정해야 합니다:

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `DB_URL` | `mysql+pymysql://...` | MySQL 데이터베이스 연결 URL |

## 포트 설정

Railway는 자동으로 `PORT` 환경 변수를 제공합니다. `server.py`는 이미 `PORT` 환경 변수를 사용하도록 수정되어 있습니다. Railway가 자동으로 포트를 할당하므로 추가 설정이 필요 없습니다.

## 배포 후 확인

1. **서버 상태 확인**
   ```bash
   curl https://your-app.railway.app/health
   ```

2. **응답 예시**
   ```json
   {
     "status": "healthy",
     "server_url": "https://your-app.railway.app",
     "model_loaded": true,
     "database_connected": true
   }
   ```

## 앱 설정 업데이트

배포 후 받은 Railway URL을 앱에 설정하는 방법:

### 방법 1: 환경 변수 사용 (권장)

프로젝트 루트에 `.env` 파일 생성:
```env
VITE_RAILWAY_URL=your-app.railway.app
```

또는 전체 URL:
```env
VITE_RAILWAY_URL=https://your-app.railway.app
```

### 방법 2: ServerConfig.ts에 직접 추가

`poseul/src/services/ServerConfig.ts` 파일에서:
```typescript
const RAILWAY_URL = 'your-app.railway.app';  // Railway URL로 변경
```

Railway URL이 설정되면 자동으로 최우선으로 사용됩니다.

## 트러블슈팅

### 데이터베이스 연결 실패
- AWS RDS 보안 그룹에서 Railway IP 허용 확인
- 또는 RDS를 공개적으로 접근 가능하도록 설정 (보안 주의)

### 빌드 실패
- `requirements.txt`에 모든 의존성이 포함되어 있는지 확인
- Python 버전이 `runtime.txt`와 일치하는지 확인

## 비용

Railway 무료 티어:
- $5 크레딧/월
- 500시간 실행 시간
- 1GB RAM
- 1GB 디스크

프로덕션 사용 시 유료 플랜 고려 필요.

