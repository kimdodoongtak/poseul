import UIKit
import Capacitor
import BackgroundTasks

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?
    
    private let backgroundTaskIdentifier = "com.poseul.app.health.refresh"

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Background Task 등록
        BGTaskScheduler.shared.register(forTaskWithIdentifier: backgroundTaskIdentifier, using: nil) { task in
            self.handleBackgroundTask(task: task as! BGAppRefreshTask)
        }
        
        return true
    }
    
    func handleBackgroundTask(task: BGAppRefreshTask) {
        print("🔄 Background Task 실행: HealthKit 데이터 가져오기")
        
        // 작업 완료 핸들러 설정 (작업이 취소될 경우 대비)
        task.expirationHandler = {
            print("⚠️ 백그라운드 작업이 만료되었습니다")
            task.setTaskCompleted(success: false)
        }
        
        // 다음 작업 예약 (현재 작업이 완료되기 전에 예약)
        scheduleNextBackgroundTask()
        
        // HealthKit 데이터 가져오기 및 서버 전송
        fetchHealthDataInBackground { success in
            task.setTaskCompleted(success: success)
        }
    }
    
    func scheduleNextBackgroundTask() {
        let request = BGAppRefreshTaskRequest(identifier: backgroundTaskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 600) // 10분(600초) 후
        
        do {
            try BGTaskScheduler.shared.submit(request)
            print("✅ 다음 백그라운드 작업 예약됨: 10분 후")
        } catch {
            print("❌ 백그라운드 작업 예약 실패: \(error.localizedDescription)")
        }
    }
    
    func fetchHealthDataInBackground(completion: @escaping (Bool) -> Void) {
        // HealthData 플러그인에 알림 전송하여 데이터 가져오기 및 서버 전송
        print("📊 백그라운드에서 HealthKit 데이터 가져오기 시작")
        
        // HealthData 플러그인에 알림 전송
        NotificationCenter.default.post(name: NSNotification.Name("HealthDataBackgroundFetch"), object: nil)
        
        // HealthData 플러그인이 데이터를 가져오는 동안 대기
        // 실제로는 HealthData 플러그인에서 비동기로 처리되므로, 짧은 대기 후 완료 처리
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
            completion(true)
        }
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the active to the background state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }

    func application(_ application: UIApplication, continue userActivity: NSUserActivity, restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
        // Called when the app was launched with an activity, including Universal Links.
        // Feel free to add additional processing here, but if you want the App API to support
        // tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(application, continue: userActivity, restorationHandler: restorationHandler)
    }
}
