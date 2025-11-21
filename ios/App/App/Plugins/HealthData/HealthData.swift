import Foundation
import Capacitor
import HealthKit
import BackgroundTasks

@objc(HealthData)
public class HealthData: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "HealthData"
    public let jsName = "HealthData"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "requestAuthorization", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getLatestHeartRate", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getLatestHeartRateVariability", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getLatestOxygenSaturation", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "startBackgroundMonitoring", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "saveUserInfo", returnType: CAPPluginReturnPromise)
    ]
    
    private var healthStore: HKHealthStore?
    private var backgroundQuery: HKObserverQuery?
    private var backgroundQueries: [HKObserverQuery] = [] // 여러 샘플 타입에 대한 observer
    private var anchoredQueries: [HKAnchoredObjectQuery] = [] // 주기적 체크용 anchored query (백그라운드에서도 동작)
    private var periodicCheckTimer: Timer? // 주기적 체크 타이머 (포그라운드용)
    private let backgroundTaskIdentifier = "com.poseul.app.health.refresh"
    private var lastCollectionTime: Date? // 마지막 데이터 수집 시간 (최소 간격 제한용)
    private var anchorDictionary: [HKSampleType: HKQueryAnchor] = [:] // Anchored query용 anchor 저장
    
    public override func load() {
        print("⚡️ HealthData plugin loaded! identifier: \(identifier), jsName: \(jsName)")
        if HKHealthStore.isHealthDataAvailable() {
            healthStore = HKHealthStore()
            print("⚡️ HealthData: HealthKit is available")
        } else {
            print("⚡️ HealthData: HealthKit is NOT available")
        }
        
        // 백그라운드 작업 알림 리스너 등록
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleBackgroundFetch),
            name: NSNotification.Name("HealthDataBackgroundFetch"),
            object: nil
        )
    }
    
    @objc private func handleBackgroundFetch() {
        // 최소 간격(10분) 체크
        let now = Date()
        if let lastTime = lastCollectionTime {
            let timeSinceLastCollection = now.timeIntervalSince(lastTime)
            let minInterval: TimeInterval = 10 * 60 // 10분 (600초)
            
            if timeSinceLastCollection < minInterval {
                let remainingSeconds = Int(minInterval - timeSinceLastCollection)
                print("⏰ 백그라운드 작업 알림 수신했지만 최소 간격(10분) 미달 - \(remainingSeconds)초 남음, 건너뜀")
                // 다음 작업 예약 (남은 시간 후, 최소 15분)
                let nextInterval = max(minInterval - timeSinceLastCollection, 900) // 최소 15분
                scheduleBackgroundTaskWithInterval(nextInterval)
                return
            }
        }
        
        print("📊 백그라운드에서 HealthKit 데이터 가져오기 시작 (10분 주기)")
        // fetchAndSendHealthDataInBackground 내부에서 lastCollectionTime 업데이트 수행
        fetchAndSendHealthDataInBackground()
        
        // 다음 작업 예약 (10분 후, 최소 15분)
        scheduleBackgroundTask()
    }
    
    private func fetchAndSendHealthDataInBackground() {
        // 최소 간격(10분) 체크 (중복 방지)
        let now = Date()
        if let lastTime = lastCollectionTime {
            let timeSinceLastCollection = now.timeIntervalSince(lastTime)
            let minInterval: TimeInterval = 10 * 60 // 10분 (600초)
            
            if timeSinceLastCollection < minInterval {
                let remainingSeconds = Int(minInterval - timeSinceLastCollection)
                print("⏰ 데이터 수집 시도했지만 최소 간격(10분) 미달 - \(remainingSeconds)초 남음, 건너뜀")
                return
            }
        }
        
        guard let healthStore = healthStore else {
            print("❌ HealthKit is not available")
            return
        }
        
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            print("❌ HealthKit types are not available")
            return
        }
        
        // 데이터 수집 시작 전에 시간 업데이트 (중복 방지)
        lastCollectionTime = now
        
        // 심박수, HRV, 혈중산소포화도 데이터 가져오기
        let group = DispatchGroup()
        var heartRate: Double? = nil
        var hrv: Double? = nil
        var oxygenSaturation: Double? = nil
        
        // 심박수 가져오기
        group.enter()
        let heartRateQuery = HKSampleQuery(sampleType: heartRateType, predicate: nil, limit: 1, sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)]) { _, results, error in
            if let error = error {
                let errorCode = (error as NSError).code
                if errorCode == 4 { // HKErrorCodeErrorHealthDataUnavailable
                    print("🔒 HealthKit 데이터 접근 불가 - 기기가 잠긴 지 10분 이상 지남 (iOS 보안 정책)")
                } else {
                    print("❌ 심박수 조회 실패: \(error.localizedDescription) (코드: \(errorCode))")
                }
            } else if let sample = results?.first as? HKQuantitySample {
                heartRate = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: HKUnit.minute()))
                print("✅ 심박수: \(heartRate ?? 0) bpm")
            }
            group.leave()
        }
        healthStore.execute(heartRateQuery)
        
        // HRV 가져오기
        group.enter()
        let hrvQuery = HKSampleQuery(sampleType: hrvType, predicate: nil, limit: 1, sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)]) { _, results, error in
            if let error = error {
                let errorCode = (error as NSError).code
                if errorCode == 4 { // HKErrorCodeErrorHealthDataUnavailable
                    print("🔒 HealthKit 데이터 접근 불가 - 기기가 잠긴 지 10분 이상 지남 (iOS 보안 정책)")
                } else {
                    print("❌ HRV 조회 실패: \(error.localizedDescription) (코드: \(errorCode))")
                }
            } else if let sample = results?.first as? HKQuantitySample {
                hrv = sample.quantity.doubleValue(for: HKUnit.secondUnit(with: .milli))
                print("✅ HRV: \(hrv ?? 0) ms")
            }
            group.leave()
        }
        healthStore.execute(hrvQuery)
        
        // 혈중산소포화도 가져오기
        group.enter()
        let oxygenQuery = HKSampleQuery(sampleType: oxygenType, predicate: nil, limit: 1, sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)]) { _, results, error in
            if let error = error {
                let errorCode = (error as NSError).code
                if errorCode == 4 { // HKErrorCodeErrorHealthDataUnavailable
                    print("🔒 HealthKit 데이터 접근 불가 - 기기가 잠긴 지 10분 이상 지남 (iOS 보안 정책)")
                } else {
                    print("❌ 혈중산소포화도 조회 실패: \(error.localizedDescription) (코드: \(errorCode))")
                }
            } else if let sample = results?.first as? HKQuantitySample {
                oxygenSaturation = sample.quantity.doubleValue(for: HKUnit.percent()) * 100
                print("✅ 혈중산소포화도: \(oxygenSaturation ?? 0)%")
            }
            group.leave()
        }
        healthStore.execute(oxygenQuery)
        
        // 모든 데이터 가져온 후 서버로 전송
        group.notify(queue: .main) {
            // 데이터가 하나라도 있으면 서버로 전송 (모두 있어야 하는 것은 아님)
            if let hr = heartRate {
                self.sendToServer(heartRate: hr, hrv: hrv ?? 0, oxygenSaturation: oxygenSaturation ?? 0)
            } else if let hrvValue = hrv {
                self.sendToServer(heartRate: 0, hrv: hrvValue, oxygenSaturation: oxygenSaturation ?? 0)
            } else if let oxy = oxygenSaturation {
                self.sendToServer(heartRate: 0, hrv: 0, oxygenSaturation: oxy)
            } else {
                print("⚠️ 모든 데이터가 없어 서버 전송을 건너뜁니다")
                print("💡 참고: 기기가 잠긴 지 10분 이상 지나면 HealthKit 데이터 접근이 제한됩니다 (iOS 보안 정책)")
                print("💡 해결: 기기를 잠금 해제하면 다시 데이터 수집이 가능합니다")
            }
            
            // 다음 백그라운드 작업 예약 (10분 후)
            self.scheduleBackgroundTask()
        }
    }
    
    private func sendToServer(heartRate: Double, hrv: Double, oxygenSaturation: Double) {
        // UserDefaults에서 서버 URL 읽기 (없으면 기본값 사용)
        let userDefaults = UserDefaults.standard
        var serverURL = userDefaults.string(forKey: "serverURL") ?? "http://192.168.68.77:3000"
        
        // /healthdata 엔드포인트 추가
        if !serverURL.hasSuffix("/healthdata") {
            if !serverURL.hasSuffix("/") {
                serverURL += "/"
            }
            serverURL += "healthdata"
        }
        
        print("📤 백그라운드 서버 전송 URL: \(serverURL)")
        
        // UserDefaults에서 age, bmi, gender 읽기
        let ageString = userDefaults.string(forKey: "userAge") ?? ""
        let bmiString = userDefaults.string(forKey: "userBmi") ?? ""
        let genderString = userDefaults.string(forKey: "userGender") ?? "0"
        
        let age: Double? = ageString.isEmpty ? nil : Double(ageString)
        let bmi: Double? = bmiString.isEmpty ? nil : Double(bmiString)
        let gender: Double? = genderString.isEmpty ? 0.0 : Double(genderString)
        
        let data: [String: Any?] = [
            "heartRate": heartRate,
            "HRV": hrv,
            "oxygenSaturation": oxygenSaturation,
            "bmi": bmi,
            "age": age,
            "gender": gender
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data) else {
            print("❌ JSON 직렬화 실패")
            return
        }
        
        var request = URLRequest(url: URL(string: serverURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData
        
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("❌ 서버 전송 실패: \(error.localizedDescription)")
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                print("✅ 백그라운드에서 서버로 데이터 전송 성공")
            } else {
                print("⚠️ 서버 응답 오류: \(response?.description ?? "unknown")")
            }
        }
        task.resume()
    }
    
    @objc public func requestAuthorization(_ call: CAPPluginCall) {
        print("⚡️ HealthData.requestAuthorization called!")
        guard let healthStore = healthStore else {
            print("⚡️ HealthData: HealthKit is not available")
            call.reject("HealthKit is not available on this device")
            return
        }
        
        let typesToRead: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,
            HKObjectType.quantityType(forIdentifier: .oxygenSaturation)!
        ]
        
        print("HealthData: Requesting authorization for types: heartRate, HRV, oxygenSaturation")
        
        healthStore.requestAuthorization(toShare: [], read: typesToRead) { success, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("HealthData: Authorization failed - \(error.localizedDescription)")
                    call.reject("Authorization failed: \(error.localizedDescription)")
                    return
                }
                
                print("HealthData: Authorization request submitted - success: \(success)")
                
                // 읽기 전용 타입의 경우 authorizationStatus가 정확하지 않을 수 있음
                // 실제 권한 확인은 데이터를 가져올 때 쿼리를 실행해서 확인하는 것이 더 정확함
                // 권한 요청이 성공적으로 제출되었다면 성공으로 반환
                // 실제 권한이 있는지는 데이터를 가져올 때 확인됨
                
                if success {
                    print("HealthData: Authorization request submitted successfully")
                    call.resolve(["success": true])
                } else {
                    print("HealthData: Authorization request failed")
                    call.resolve([
                        "success": false,
                        "message": "Authorization request failed. Please try again."
                    ])
                }
            }
        }
    }
    
    @objc public func getLatestHeartRate(_ call: CAPPluginCall) {
        guard let healthStore = healthStore else {
            call.reject("HealthKit is not available on this device")
            return
        }
        
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            call.reject("Heart rate type is not available")
            return
        }
        
        // 권한 상태 확인 (읽기 전용 타입의 경우 authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인)
        let authStatus = healthStore.authorizationStatus(for: heartRateType)
        print("HealthData: Heart rate authorization status: \(authStatus.rawValue)")
        
        // 읽기 전용 타입의 경우, authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인
        // 권한이 없으면 쿼리가 실패하거나 에러를 반환합니다
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: heartRateType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, samples, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("HealthData Error - Heart Rate: \(error.localizedDescription)")
                    let errorCode = (error as NSError).code
                    // HKError.errorAuthorizationDenied = 4
                    if errorCode == 4 {
                        call.reject("Heart rate data access is denied. Please grant permission in Settings > Health > Data Access & Devices > poseul")
                    } else {
                        call.reject("Failed to fetch heart rate: \(error.localizedDescription)")
                    }
                    return
                }
                
                guard let sample = samples?.first as? HKQuantitySample else {
                    print("HealthData: No heart rate data found in HealthKit (권한이 있지만 데이터가 없음)")
                    call.resolve([:])
                    return
                }
                
                let value = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: HKUnit.minute()))
                let date = ISO8601DateFormatter().string(from: sample.endDate)
                
                print("HealthData: Heart rate fetched - \(value) bpm at \(date)")
                call.resolve([
                    "value": value,
                    "date": date
                ])
            }
        }
        
        healthStore.execute(query)
    }
    
    @objc public func getLatestHeartRateVariability(_ call: CAPPluginCall) {
        guard let healthStore = healthStore else {
            call.reject("HealthKit is not available on this device")
            return
        }
        
        guard let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else {
            call.reject("Heart rate variability type is not available")
            return
        }
        
        // 권한 상태 확인 (읽기 전용 타입의 경우 authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인)
        let authStatus = healthStore.authorizationStatus(for: hrvType)
        print("HealthData: HRV authorization status: \(authStatus.rawValue)")
        
        // 읽기 전용 타입의 경우, authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인
        // 권한이 없으면 쿼리가 실패하거나 에러를 반환합니다
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: hrvType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, samples, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("HealthData Error - HRV: \(error.localizedDescription)")
                    let errorCode = (error as NSError).code
                    // HKError.errorAuthorizationDenied = 4
                    if errorCode == 4 {
                        call.reject("HRV data access is denied. Please grant permission in Settings > Health > Data Access & Devices > poseul")
                    } else {
                        call.reject("Failed to fetch HRV: \(error.localizedDescription)")
                    }
                    return
                }
                
                guard let sample = samples?.first as? HKQuantitySample else {
                    print("HealthData: No HRV data found in HealthKit (권한이 있지만 데이터가 없음)")
                    call.resolve([:])
                    return
                }
                
                let value = sample.quantity.doubleValue(for: HKUnit.secondUnit(with: .milli))
                let date = ISO8601DateFormatter().string(from: sample.endDate)
                
                print("HealthData: HRV fetched - \(value) ms at \(date)")
                call.resolve([
                    "value": value,
                    "date": date
                ])
            }
        }
        
        healthStore.execute(query)
    }
    
    @objc public func getLatestOxygenSaturation(_ call: CAPPluginCall) {
        guard let healthStore = healthStore else {
            call.reject("HealthKit is not available on this device")
            return
        }
        
        guard let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            call.reject("Oxygen saturation type is not available")
            return
        }
        
        // 권한 상태 확인 (읽기 전용 타입의 경우 authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인)
        let authStatus = healthStore.authorizationStatus(for: oxygenType)
        print("HealthData: Oxygen saturation authorization status: \(authStatus.rawValue)")
        
        // 읽기 전용 타입의 경우, authorizationStatus가 정확하지 않을 수 있으므로
        // 실제로 쿼리를 실행해서 권한이 있는지 확인
        // 권한이 없으면 쿼리가 실패하거나 에러를 반환합니다
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: oxygenType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, samples, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("HealthData Error - Oxygen Saturation: \(error.localizedDescription)")
                    let errorCode = (error as NSError).code
                    // HKError.errorAuthorizationDenied = 4
                    if errorCode == 4 {
                        call.reject("Oxygen saturation data access is denied. Please grant permission in Settings > Health > Data Access & Devices > poseul")
                    } else {
                        call.reject("Failed to fetch oxygen saturation: \(error.localizedDescription)")
                    }
                    return
                }
                
                guard let sample = samples?.first as? HKQuantitySample else {
                    print("HealthData: No oxygen saturation data found in HealthKit (권한이 있지만 데이터가 없음)")
                    call.resolve([:])
                    return
                }
                
                let value = sample.quantity.doubleValue(for: HKUnit.percent()) * 100
                let date = ISO8601DateFormatter().string(from: sample.endDate)
                
                print("HealthData: Oxygen saturation fetched - \(value)% at \(date)")
                call.resolve([
                    "value": value,
                    "date": date
                ])
            }
        }
        
        healthStore.execute(query)
    }
    
    @objc public func startBackgroundMonitoring(_ call: CAPPluginCall) {
        guard let enabled = call.getBool("enabled") else {
            call.reject("enabled parameter is required")
            return
        }
        
        if enabled {
            setupBackgroundMonitoring()
            scheduleBackgroundTask() // 10분마다 백그라운드 작업 예약
        } else {
            stopBackgroundMonitoring()
            cancelBackgroundTask() // 백그라운드 작업 취소
        }
        
        call.resolve(["success": true])
    }
    
    private func scheduleBackgroundTask() {
        // 10분 간격으로 요청 (iOS 최소 15분이지만 가능한 한 자주 시도)
        scheduleBackgroundTaskWithInterval(10 * 60) // 10분
    }
    
    private func scheduleBackgroundTaskWithInterval(_ interval: TimeInterval) {
        let request = BGAppRefreshTaskRequest(identifier: backgroundTaskIdentifier)
        // iOS는 BGAppRefreshTaskRequest의 최소 간격이 15분(900초)입니다
        let actualInterval = max(interval, 900) // 최소 15분
        request.earliestBeginDate = Date(timeIntervalSinceNow: actualInterval)
        
        do {
            try BGTaskScheduler.shared.submit(request)
            let minutes = Int(actualInterval / 60)
            print("✅ 백그라운드 작업 예약됨: \(minutes)분 후")
        } catch {
            print("❌ 백그라운드 작업 예약 실패: \(error.localizedDescription)")
        }
    }
    
    private func cancelBackgroundTask() {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: backgroundTaskIdentifier)
        print("✅ 백그라운드 작업 취소됨")
    }
    
    @objc public func saveUserInfo(_ call: CAPPluginCall) {
        guard let age = call.getString("age"),
              let bmi = call.getString("bmi") else {
            call.reject("age and bmi are required")
            return
        }
        
        // UserDefaults에 저장
        let userDefaults = UserDefaults.standard
        userDefaults.set(age, forKey: "userAge")
        userDefaults.set(bmi, forKey: "userBmi")
        
        // gender는 optional
        if let gender = call.getString("gender") {
            userDefaults.set(gender, forKey: "userGender")
        }
        
        // serverURL도 optional로 저장
        if let serverURL = call.getString("serverURL") {
            userDefaults.set(serverURL, forKey: "serverURL")
            print("✅ 서버 URL 저장됨: \(serverURL)")
        }
        
        userDefaults.synchronize()
        
        print("✅ 사용자 정보 저장됨: age=\(age), bmi=\(bmi), gender=\(call.getString("gender") ?? "없음"), serverURL=\(call.getString("serverURL") ?? "없음")")
        call.resolve(["success": true])
    }
    
    private func setupBackgroundMonitoring() {
        guard let healthStore = healthStore else { return }
        
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            return
        }
        
        // 기존 observer 제거
        backgroundQueries.forEach { healthStore.stop($0) }
        backgroundQueries.removeAll()
        if let query = backgroundQuery {
            healthStore.stop(query)
            backgroundQuery = nil
        }
        
        // 데이터 변경 알림 핸들러 (10분 간격 체크)
        let dataChangeHandler: (String) -> Void = { [weak self] sampleTypeName in
            guard let self = self else { return }
            
            // 최소 간격(10분) 체크 - 즉시 감지하지 않고 10분마다만 체크
            let now = Date()
            if let lastTime = self.lastCollectionTime {
                let timeSinceLastCollection = now.timeIntervalSince(lastTime)
                let minInterval: TimeInterval = 10 * 60 // 10분 (600초)
                
                if timeSinceLastCollection < minInterval {
                    let remainingSeconds = Int(minInterval - timeSinceLastCollection)
                    print("⏰ 데이터 변경 알림(\(sampleTypeName)) 수신했지만 최소 간격(10분) 미달 - \(remainingSeconds)초 남음, 건너뜀")
                    return
                }
            }
            
            print("📊 데이터 변경 알림(\(sampleTypeName)) - 10분 경과, 데이터 수집 시작")
            // 백그라운드에서 직접 데이터 가져오기 및 서버 전송
            self.fetchAndSendHealthDataInBackground()
        }
        
        // 각 샘플 타입에 대해 Observer Query 생성 (데이터 변경 시 알림 받기)
        let sampleTypes = [
            (heartRateType, "HeartRate"),
            (hrvType, "HRV"),
            (oxygenType, "OxygenSaturation")
        ]
        
        for (sampleType, name) in sampleTypes {
            let query = HKObserverQuery(sampleType: sampleType, predicate: nil) { query, completionHandler, error in
                if let error = error {
                    print("Background monitoring error for \(name): \(error.localizedDescription)")
                    completionHandler()
                    return
                }
                
                // 데이터 변경 알림 수신 - 10분 간격 체크 후 처리
                dataChangeHandler(name)
                completionHandler()
            }
            
            healthStore.execute(query)
            backgroundQueries.append(query)
            
            // 백그라운드 배달 활성화 (데이터 변경 시 알림 받기)
            // 알림은 받되, 실제 수집은 10분 간격으로만 수행
            healthStore.enableBackgroundDelivery(for: sampleType, frequency: .hourly) { success, error in
                if let error = error {
                    print("Failed to enable background delivery for \(name): \(error.localizedDescription)")
                } else {
                    print("✅ \(name) background delivery enabled: \(success) (10분 간격 체크)")
                }
            }
        }
        
        // 포그라운드에서 주기적 체크 (10분마다)
        setupPeriodicCheck()
        
        print("✅ 백그라운드 모니터링 설정 완료 - 데이터 변경 알림 활성화 (10분 간격 체크)")
    }
    
    // HKAnchoredObjectQuery로 주기적 체크 (백그라운드에서도 동작)
    private func setupAnchoredQueries() {
        guard let healthStore = healthStore else { return }
        
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            return
        }
        
        // 기존 anchored query 제거
        anchoredQueries.forEach { healthStore.stop($0) }
        anchoredQueries.removeAll()
        anchorDictionary.removeAll()
        
        // Anchored Query 제거 - 즉시 감지하지 않고 BGAppRefreshTask에서만 주기적 체크
        print("✅ Anchored Query 제거 완료 - BGAppRefreshTask에서만 주기적 체크 (10분 간격 시도, iOS 최소 15분)")
    }
    
    // 포그라운드에서 주기적으로 체크 (10분마다)
    private func setupPeriodicCheck() {
        // 기존 타이머 제거
        periodicCheckTimer?.invalidate()
        
        // 포그라운드에서만 동작하는 타이머 (백그라운드에서는 iOS가 제한)
        periodicCheckTimer = Timer.scheduledTimer(withTimeInterval: 10 * 60, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            
            // 최소 간격 체크
            let now = Date()
            if let lastTime = self.lastCollectionTime {
                let timeSinceLastCollection = now.timeIntervalSince(lastTime)
                let minInterval: TimeInterval = 10 * 60 // 10분
                
                if timeSinceLastCollection >= minInterval {
                    print("⏰ 주기적 체크 (10분) - 데이터 수집 시작")
                    self.fetchAndSendHealthDataInBackground()
                } else {
                    let remainingSeconds = Int(minInterval - timeSinceLastCollection)
                    print("⏰ 주기적 체크 - 최소 간격 미달, \(remainingSeconds)초 남음")
                }
            } else {
                // 첫 수집
                print("⏰ 주기적 체크 (10분) - 첫 데이터 수집")
                self.fetchAndSendHealthDataInBackground()
            }
        }
        
        print("✅ 주기적 체크 타이머 설정 완료 (10분 간격, 포그라운드에서만 동작)")
    }
    
    private func stopBackgroundMonitoring() {
        guard let healthStore = healthStore else { return }
        
        // 모든 observer 제거
        backgroundQueries.forEach { healthStore.stop($0) }
        backgroundQueries.removeAll()
        
        // 모든 anchored query 제거
        anchoredQueries.forEach { healthStore.stop($0) }
        anchoredQueries.removeAll()
        anchorDictionary.removeAll()
        
        if let query = backgroundQuery {
            healthStore.stop(query)
            backgroundQuery = nil
        }
        
        // 주기적 체크 타이머 제거
        periodicCheckTimer?.invalidate()
        periodicCheckTimer = nil
        
        print("✅ 백그라운드 모니터링 중지 완료")
    }
}

