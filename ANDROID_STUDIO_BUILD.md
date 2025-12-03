# 안드로이드 스튜디오 빌드 가이드

## 안드로이드 스튜디오에서 빌드하기

### 1. 프로젝트 열기
1. 안드로이드 스튜디오 실행
2. **File > Open** 선택
3. `C:\aisurvice\poseul\android` 폴더 선택
4. 프로젝트가 로드될 때까지 대기

### 2. 빌드 전 확인사항

#### 서버 IP 주소 확인
- 현재 서버 IP: `172.15.5.72:3000`
- `android/app/build.gradle` 파일의 `SERVER_URL`이 올바른지 확인
- 실제 기기 사용 시: `http://172.15.5.72:3000`
- 에뮬레이터 사용 시: `http://10.0.2.2:3000`

### 3. 빌드 단계

#### 방법 1: Gradle을 통한 빌드 (권장)
1. 안드로이드 스튜디오 우측의 **Gradle** 탭 열기
2. `android > app > Tasks > build` 확장
3. `assembleDebug` 더블클릭 (디버그 APK 생성)
4. 또는 `assembleRelease` 더블클릭 (릴리즈 APK 생성)

#### 방법 2: 메뉴를 통한 빌드
1. 상단 메뉴에서 **Build > Make Project** (Ctrl+F9)
2. 또는 **Build > Rebuild Project** (캐시 클리어 후 빌드)

#### 방법 3: APK 직접 생성
1. 상단 메뉴에서 **Build > Build Bundle(s) / APK(s) > Build APK(s)**
2. 빌드 완료 후 **locate** 링크 클릭하여 APK 위치 확인
3. APK 위치: `android/app/build/outputs/apk/debug/app-debug.apk`

### 4. 앱 실행

#### 에뮬레이터에서 실행
1. 상단 툴바에서 에뮬레이터 선택
2. **Run** 버튼 클릭 (Shift+F10)
3. 또는 **Run > Run 'app'**

#### 실제 기기에서 실행
1. USB 디버깅 활성화된 안드로이드 기기를 연결
2. 기기가 인식되면 상단 툴바에 표시됨
3. 기기 선택 후 **Run** 버튼 클릭

### 5. 빌드 문제 해결

#### Java 버전 문제
- 안드로이드 스튜디오는 자체 JDK를 포함하고 있음
- **File > Project Structure > SDK Location**에서 JDK 경로 확인
- JDK 17 이상 권장

#### Gradle 동기화 문제
- **File > Sync Project with Gradle Files** 실행
- 또는 상단의 **Sync Now** 링크 클릭

#### 캐시 문제
- **File > Invalidate Caches / Restart**
- **Invalidate and Restart** 선택

#### 의존성 다운로드 실패
- **File > Settings > Build, Execution, Deployment > Gradle**
- **Use Gradle from** 설정 확인
- 인터넷 연결 확인

### 6. 빌드 출력 확인

빌드가 완료되면:
- APK 파일: `android/app/build/outputs/apk/debug/app-debug.apk`
- 빌드 로그: 하단의 **Build** 탭에서 확인

### 7. 서버 연결 확인

앱 실행 후:
- 실제 기기: 서버 IP가 `172.15.5.72:3000`인지 확인
- 에뮬레이터: 서버 IP가 `10.0.2.2:3000`인지 확인
- 서버가 실행 중인지 확인 (`python server/server.py`)

## 빠른 빌드 체크리스트

- [ ] 안드로이드 스튜디오에서 프로젝트 열기
- [ ] Gradle 동기화 완료
- [ ] 서버 IP 주소 확인 (`build.gradle`의 `SERVER_URL`)
- [ ] 서버 실행 중 확인
- [ ] Build > Build APK(s) 실행
- [ ] APK 파일 생성 확인
- [ ] 앱 설치 및 실행

## 참고사항

- 첫 빌드는 의존성 다운로드로 인해 시간이 오래 걸릴 수 있습니다
- 빌드 중 에러가 발생하면 **Build** 탭에서 상세 로그 확인
- 네트워크 문제 시 Gradle 오프라인 모드 비활성화 확인

