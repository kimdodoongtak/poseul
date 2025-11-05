import Foundation
import Capacitor
import HealthKit

@objc(HealthKitPlugin)
public class HealthKitPlugin: CAPPlugin {
    private let healthStore = HKHealthStore()
    private var backgroundQuery: HKObserverQuery?
    
    public override func load() {
        // 백그라운드 모니터링을 위한 observer query 설정
    }
    
    @objc func requestAuthorization(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.reject("HealthKit is not available on this device")
            return
        }
        
        let typesToRead: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,
            HKObjectType.quantityType(forIdentifier: .oxygenSaturation)!
        ]
        
        healthStore.requestAuthorization(toShare: nil, read: typesToRead) { success, error in
            if let error = error {
                call.reject("Authorization failed: \(error.localizedDescription)")
                return
            }
            
            call.resolve(["success": success])
        }
    }
    
    @objc func getLatestHeartRate(_ call: CAPPluginCall) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            call.reject("Heart rate type is not available")
            return
        }
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: heartRateType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, results, error in
            if let error = error {
                call.reject("Failed to fetch heart rate: \(error.localizedDescription)")
                return
            }
            
            guard let sample = results?.first as? HKQuantitySample else {
                call.resolve(nil)
                return
            }
            
            let heartRateUnit = HKUnit.count().unitDivided(by: HKUnit.minute())
            let value = sample.quantity.doubleValue(for: heartRateUnit)
            let date = ISO8601DateFormatter().string(from: sample.endDate)
            
            call.resolve([
                "value": value,
                "date": date
            ])
        }
        
        healthStore.execute(query)
    }
    
    @objc func getLatestHeartRateVariability(_ call: CAPPluginCall) {
        guard let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else {
            call.reject("Heart rate variability type is not available")
            return
        }
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: hrvType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, results, error in
            if let error = error {
                call.reject("Failed to fetch HRV: \(error.localizedDescription)")
                return
            }
            
            guard let sample = results?.first as? HKQuantitySample else {
                call.resolve(nil)
                return
            }
            
            let hrvUnit = HKUnit.secondUnit(with: .milli)
            let value = sample.quantity.doubleValue(for: hrvUnit)
            let date = ISO8601DateFormatter().string(from: sample.endDate)
            
            call.resolve([
                "value": value,
                "date": date
            ])
        }
        
        healthStore.execute(query)
    }
    
    @objc func getLatestOxygenSaturation(_ call: CAPPluginCall) {
        guard let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            call.reject("Oxygen saturation type is not available")
            return
        }
        
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        let query = HKSampleQuery(sampleType: oxygenType, predicate: nil, limit: 1, sortDescriptors: [sortDescriptor]) { _, results, error in
            if let error = error {
                call.reject("Failed to fetch oxygen saturation: \(error.localizedDescription)")
                return
            }
            
            guard let sample = results?.first as? HKQuantitySample else {
                call.resolve(nil)
                return
            }
            
            let percentUnit = HKUnit.percent()
            let value = sample.quantity.doubleValue(for: percentUnit) * 100 // 0-100으로 변환
            let date = ISO8601DateFormatter().string(from: sample.endDate)
            
            call.resolve([
                "value": value,
                "date": date
            ])
        }
        
        healthStore.execute(query)
    }
    
    @objc func startBackgroundMonitoring(_ call: CAPPluginCall) {
        guard let enabled = call.getBool("enabled") else {
            call.reject("enabled parameter is required")
            return
        }
        
        if enabled {
            setupBackgroundMonitoring()
        } else {
            stopBackgroundMonitoring()
        }
        
        call.resolve(["success": true])
    }
    
    private func setupBackgroundMonitoring() {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let oxygenType = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else {
            return
        }
        
        let types: Set<HKSampleType> = [heartRateType, hrvType, oxygenType]
        
        // 기존 observer 제거
        if let query = backgroundQuery {
            healthStore.stop(query)
        }
        
        // 새로운 observer 생성
        backgroundQuery = HKObserverQuery(sampleType: heartRateType, predicate: nil) { [weak self] query, completionHandler, error in
            if let error = error {
                print("Background monitoring error: \(error.localizedDescription)")
                completionHandler()
                return
            }
            
            // 백그라운드에서 데이터 업데이트 감지
            DispatchQueue.main.async {
                self?.notifyListeners("healthDataUpdated", data: [:])
            }
            completionHandler()
        }
        
        if let query = backgroundQuery {
            healthStore.execute(query)
            healthStore.enableBackgroundDelivery(for: heartRateType, frequency: .immediate) { success, error in
                if let error = error {
                    print("Failed to enable background delivery: \(error.localizedDescription)")
                }
            }
            healthStore.enableBackgroundDelivery(for: hrvType, frequency: .immediate) { success, error in
                if let error = error {
                    print("Failed to enable background delivery: \(error.localizedDescription)")
                }
            }
            healthStore.enableBackgroundDelivery(for: oxygenType, frequency: .immediate) { success, error in
                if let error = error {
                    print("Failed to enable background delivery: \(error.localizedDescription)")
                }
            }
        }
    }
    
    private func stopBackgroundMonitoring() {
        if let query = backgroundQuery {
            healthStore.stop(query)
            backgroundQuery = nil
        }
    }
}

