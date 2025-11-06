# 안드로이드 빌드 및 변경사항 적용 가이드

## 변경사항 적용 방법

웹 코드를 수정한 후 안드로이드 앱에 반영하려면 다음 단계를 따라야 합니다:

### 1. 웹 빌드
```bash
npm run build
```
또는
```bash
vite build
```

이 명령어는 `dist` 폴더에 빌드된 파일을 생성합니다.

### 2. Capacitor 동기화
```bash
npx cap sync android
```

이 명령어는:
- `dist` 폴더의 빌드된 파일을 안드로이드 앱의 `assets` 폴더로 복사
- 플러그인 변경사항을 안드로이드 프로젝트에 반영
- 네이티브 코드 변경사항 동기화

### 3. 안드로이드 스튜디오에서 재빌드

안드로이드 스튜디오에서:
1. **Build > Clean Project** (선택사항, 캐시 문제 시)
2. **Build > Rebuild Project**
3. 앱 실행

## 빠른 적용 방법 (개발 중)

개발 중에는 다음 명령어를 순서대로 실행:

```bash
# 1. 웹 빌드
npm run build

# 2. Capacitor 동기화
npx cap sync android

# 3. 안드로이드 스튜디오에서 재빌드 및 실행
```

## 자동화 스크립트 (선택사항)

`package.json`에 스크립트를 추가할 수 있습니다:

```json
{
  "scripts": {
    "build:android": "npm run build && npx cap sync android",
    "sync:android": "npx cap sync android"
  }
}
```

사용 방법:
```bash
npm run build:android
```

## 문제 해결

### 변경사항이 반영되지 않는 경우

1. **빌드 확인**
   ```bash
   npm run build
   ```
   `dist` 폴더에 파일이 생성되었는지 확인

2. **동기화 확인**
   ```bash
   npx cap sync android
   ```
   에러 메시지 확인

3. **안드로이드 스튜디오 캐시 클리어**
   - Build > Clean Project
   - File > Invalidate Caches / Restart

4. **앱 재설치**
   - 안드로이드 스튜디오에서 앱 Uninstall
   - 다시 Run

5. **dist 폴더 확인**
   - `android/app/src/main/assets/public/` 폴더에 최신 파일이 있는지 확인

### 자주 하는 실수

- ❌ 웹 코드만 수정하고 빌드 안함
- ❌ 빌드만 하고 sync 안함
- ❌ sync만 하고 안드로이드 스튜디오에서 재빌드 안함

### 올바른 순서

1. ✅ 웹 코드 수정
2. ✅ `npm run build` 실행
3. ✅ `npx cap sync android` 실행
4. ✅ 안드로이드 스튜디오에서 재빌드 및 실행

## 개발 팁

### Live Reload (개발 중)

개발 중에는 웹 개발 서버를 사용할 수 있습니다:
```bash
npm run dev
```

하지만 안드로이드 앱에서는 네이티브 기능 테스트를 위해 빌드된 버전을 사용하는 것이 좋습니다.

### 빠른 테스트

변경사항을 빠르게 테스트하려면:
1. 웹 브라우저에서 `npm run dev`로 테스트
2. 문제없으면 `npm run build && npx cap sync android`로 안드로이드에 적용

