# Android Studio 빌드 상태 확인 가이드

## 빌드 탭 찾는 방법

### 방법 1: 하단 탭 확인
1. Android Studio 화면 **가장 아래쪽**을 확인
2. 다음과 같은 탭들이 보일 수 있습니다:
   - **Terminal** (터미널)
   - **TODO** (할 일)
   - **Problems** (문제)
   - **Logcat** (로그)
   - **Build** 또는 **Build Output** ← 이게 빌드 결과 탭!

### 방법 2: 메뉴로 열기
1. 상단 메뉴: `View` → `Tool Windows` 
2. 다음 중 하나 선택:
   - `Build` 
   - `Build Output`

### 방법 3: 단축키 사용
- `Alt + 0` (영문 숫자 0) - Build Tool Window 열기
- 또는 `Alt + 0` → `Build Output` 선택

### 방법 4: 실제 빌드 실행하기
1. `Build` → `Rebuild Project` 클릭
2. 빌드가 시작되면 **자동으로 하단에 "Build" 탭이 열립니다**
3. 빌드 결과를 실시간으로 볼 수 있습니다

## 빌드 결과 확인

### 성공 시:
```
BUILD SUCCESSFUL in 30s
```

### 실패 시:
```
BUILD FAILED
...오류 메시지...
```

## 만약 탭이 안 보이면:

1. **최소화되어 있을 수 있습니다**
   - 화면 하단 가장자리를 위로 드래그해서 확인

2. **숨겨져 있을 수 있습니다**
   - `View` → `Tool Windows` → `Build Output` 선택

3. **빌드를 한 번 실행해보세요**
   - `Build` → `Rebuild Project`
   - 그러면 자동으로 Build 탭이 나타납니다

## 빠른 확인 방법

1. `Build` → `Rebuild Project` 클릭
2. 화면 하단에 자동으로 "Build" 탭이 나타남
3. "BUILD SUCCESSFUL" 메시지 확인

