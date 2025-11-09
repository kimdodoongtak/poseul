#!/usr/bin/env python3
"""
AI 체온 예측 서버 테스트 클라이언트
"""

import requests
import json

SERVER_URL = "http://localhost:5000"

def test_health():
    """서버 상태 확인"""
    print("🔍 서버 상태 확인...")
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 서버 상태: {data['status']}")
            print(f"✅ 모델 로드됨: {data['model_loaded']}")
            return True
        else:
            print(f"❌ 서버 응답 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return False

def test_model_info():
    """모델 정보 확인"""
    print("\n📊 모델 정보 확인...")
    try:
        response = requests.get(f"{SERVER_URL}/model_info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 모델 타입: {data['model_type']}")
            print(f"✅ 피처: {data['features']}")
            print(f"✅ 타겟: {data['target']}")
            return True
        else:
            print(f"❌ 모델 정보 조회 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 모델 정보 조회 실패: {e}")
        return False

def test_prediction():
    """체온 예측 테스트"""
    print("\n🌡️ 체온 예측 테스트...")
    
    # 테스트 데이터
    test_cases = [
        {
            "name": "정상 체온 예상 (30대 여성)",
            "data": {
                "hr_mean": 72.0,
                "hrv_sdnn": 45.2,
                "bmi": 22.5,
                "mean_sa02": 98.5,
                "gender": "F",
                "age": 30
            }
        {
            "name": "높은 심박수 (40대 남성)",
            "data": {
                "hr_mean": 95.0,
                "hrv_sdnn": 35.8,
                "bmi": 25.1,
                "mean_sa02": 97.2,
                "gender": "M",
                "age": 45
            }
        },
        {
            "name": "낮은 BMI (20대 여성)",
            "data": {
                "hr_mean": 65.0,
                "hrv_sdnn": 52.1,
                "bmi": 18.5,
                "mean_sa02": 99.1,
                "gender": "F",
                "age": 25
            }
        },
        {
            "name": "고령자 (70대 남성)",
            "data": {
                "hr_mean": 68.0,
                "hrv_sdnn": 28.5,
                "bmi": 24.0,
                "mean_sa02": 96.8,
                "gender": "M",
                "age": 72
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n테스트 {i}: {test_case['name']}")
        print(f"입력 데이터: {test_case['data']}")
        
        try:
            response = requests.post(
                f"{SERVER_URL}/predict",
                json=test_case['data'],
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    print(f"✅ 예측 체온: {data['predicted_temperature']:.2f}°C")
                    print(f"✅ 온도 분류: {data['temperature_category']}")
                else:
                    print(f"❌ 예측 실패: {data['error']}")
            else:
                print(f"❌ 서버 오류: {response.status_code}")
                print(f"응답: {response.text}")
                
        except Exception as e:
            print(f"❌ 예측 요청 실패: {e}")

def main():
    """메인 테스트 함수"""
    print("🚀 AI 체온 예측 서버 테스트 시작")
    print("=" * 50)
    
    # 1. 서버 상태 확인
    if not test_health():
        print("\n❌ 서버가 실행되지 않았습니다.")
        print("서버를 먼저 실행하세요: python run_server.py")
        return
    
    # 2. 모델 정보 확인
    test_model_info()
    
    # 3. 예측 테스트
    test_prediction()
    
    print("\n" + "=" * 50)
    print("✅ 테스트 완료!")

if __name__ == "__main__":
    main()
