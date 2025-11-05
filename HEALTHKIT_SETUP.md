# HealthKit 설정 가이드

## Xcode에서 해야 할 작업

### 1. HealthKit.swift 파일을 프로젝트에 추가
1. Xcode에서 `ios/App/App.xcodeproj` 열기
2. 왼쪽 프로젝트 네비게이터에서 `App` 폴더 우클릭
3. "Add Files to App..." 선택
4. `ios/App/App/Plugins/HealthKit/HealthKit.swift` 파일 선택
5. "Copy items if needed" 체크 해제
6. "Add to targets: App" 체크
7. "Add" 클릭

### 2. HealthKit 프레임워크 추가
1. Xcode에서 프로젝트 설정 (프로젝트 이름 클릭)
2. "App" 타겟 선택
3. "General" 탭
4. "Frameworks, Libraries, and Embedded Content" 섹션
5. "+" 버튼 클릭
6. "HealthKit.framework" 검색 후 추가
7. "Embed & Sign" 선택

### 3. HealthKit 플러그인 등록
`ios/App/App/AppDelegate.swift` 파일이 이미 Capacitor를 사용하도록 설정되어 있으므로 추가 작업 불필요합니다.

## 앱 실행 후 확인사항

1. 앱 실행 시 HealthKit 권한 요청 팝업이 나타납니다
2. 권한을 허용하면 Tab1 화면에서 데이터를 볼 수 있습니다
3. 백그라운드 모니터링 토글을 켜면 백그라운드에서도 데이터를 모니터링합니다

## 테스트 방법

1. iPhone 시뮬레이터는 HealthKit을 지원하지 않으므로 실제 기기에서 테스트해야 합니다
2. 또는 Health 앱에서 샘플 데이터를 추가한 후 테스트할 수 있습니다

