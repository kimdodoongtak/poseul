# 안드로이드 에어컨 연동 문제 해결 가이드

## ✅ 수정 완료 사항

1. **서버 URL 설정 통일**
   - `android/plus/android_app/app/build.gradle`: `192.168.0.143:3000`으로 변경 완료
   - `src/services/IotService.ts`: `192.168.0.143:3000`으로 변경 완료
   - `ModelService.kt`: `BuildConfig.SERVER_URL` 사용하도록 변경 완료

2. **네트워크 보안 설정 확인**
   - `network_security_config.xml`에 `192.168.0.143` 도메인 허용 확인 완료

## 🔧 다음 단계: 앱 다시 빌드

### 방법 1: Android Studio에서 빌드
1. Android Studio에서 프로젝트 열기: `android/plus/android_app`
2. **Build > Clean Project**
3. **Build > Rebuild Project**
4. 앱 실행 (실제 기기에 설치)

### 방법 2: 명령줄에서 빌드
```bash
cd android/plus/android_app
./gradlew clean
./gradlew assembleDebug
```

### 방법 3: Gradle Wrapper가 없는 경우
```bash
cd android/plus/android_app
gradle clean
gradle assembleDebug
```

## 🔍 문제 진단

### 1. 서버 상태 확인
서버가 실행 중인지 확인:
```bash
curl http://localhost:3000/health
curl http://192.168.0.143:3000/air_conditioner/state
```

### 2. 네트워크 연결 확인
- 컴퓨터와 폰이 **같은 Wi-Fi 네트워크**에 연결되어 있는지 확인
- 컴퓨터의 IP 주소가 `192.168.0.143`인지 확인:
  ```bash
  # Windows
  ipconfig
  
  # Mac/Linux
  ifconfig
  ```

### 3. 방화벽 확인
Windows 방화벽이 포트 3000을 차단하지 않는지 확인:
```powershell
# 방화벽 규칙 확인
netsh advfirewall firewall show rule name=all | findstr 3000
```

필요시 포트 3000 허용:
```powershell
netsh advfirewall firewall add rule name="Python Server" dir=in action=allow protocol=TCP localport=3000
```

### 4. 안드로이드 로그 확인
앱 실행 후 Logcat에서 에러 확인:
- 필터: `IotService` 또는 `IotViewModel`
- 확인할 로그:
  - `🌐 [AIR CONDITIONER] 요청 URL: http://192.168.0.143:3000/air_conditioner/state`
  - `📡 [AIR CONDITIONER] HTTP 응답 코드: ...`
  - 에러 메시지

## 📱 현재 설정 요약

- **서버 포트**: 3000
- **컴퓨터 IP**: 192.168.0.143
- **서버 URL**: `http://192.168.0.143:3000`
- **에어컨 API 엔드포인트**: 
  - 상태 조회: `GET /air_conditioner/state`
  - 제어: `POST /air_conditioner/control`

## ⚠️ 주의사항

1. **앱을 다시 빌드해야** `build.gradle`의 변경사항이 반영됩니다
2. 컴퓨터 IP가 변경되면 `build.gradle`의 `SERVER_URL`도 변경해야 합니다
3. 에뮬레이터 사용 시: `10.0.2.2:3000`으로 변경 필요

## 🐛 여전히 문제가 발생하는 경우

1. **Logcat 로그 확인**
   - Android Studio > Logcat
   - 필터: `IotService` 또는 `IotViewModel`
   - 에러 메시지 복사

2. **서버 로그 확인**
   - 서버 콘솔에서 에러 메시지 확인
   - `📱 앱에서 에어컨 상태 조회 요청` 로그가 나타나는지 확인

3. **네트워크 테스트**
   - 폰의 브라우저에서 `http://192.168.0.143:3000/health` 접속 테스트
   - 접속이 안 되면 네트워크 문제

