"""
온도 임계값 캐시 확인 스크립트
서버가 실행 중일 때 사용
"""

import requests

# 서버 URL (로컬 서버)
SERVER_URL = "http://localhost:3000"

def check_cache():
    """캐시 확인"""
    try:
        response = requests.get(f"{SERVER_URL}/air_conditioner/temperature_threshold")
        data = response.json()
        
        print("=" * 50)
        print("온도 임계값 캐시 상태")
        print("=" * 50)
        
        if data.get("has_threshold"):
            threshold = data["threshold"]
            print(f"✅ 캐시가 저장되어 있습니다!")
            print(f"   목표 온도: {threshold['target_temperature']}°C")
            print(f"   임계값 범위: {threshold['min_temp']}°C ~ {threshold['max_temp']}°C")
            print(f"   생성 시간: {threshold['created_at']}")
            print(f"   만료 시간: {threshold['expires_at']}")
        else:
            print("❌ 저장된 캐시가 없습니다.")
            print(f"   메시지: {data.get('message', 'N/A')}")
        
        print("=" * 50)
        
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다.")
        print(f"   서버가 {SERVER_URL}에서 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")

if __name__ == "__main__":
    check_cache()

