#!/usr/bin/env python3
"""
데이터 수집 및 다수결 조절 테스트 스크립트

1. 데이터 수집: 1분마다 건강 데이터 전송
2. 다수결 조절: 3분마다 에어컨 조절 트리거
"""

import requests
import time
import random
import os
import sys
from datetime import datetime
from threading import Thread, Event

# 서버 URL
BASE_URL = "http://localhost:3000"

# 통일된 사용자 정보 (고정값)
FIXED_BMI = 22.0
FIXED_AGE = 23
FIXED_GENDER = 0.0  # 1.0: 남성, 0.0: 여성

# 건강 데이터 범위 (작은 범위 내에서 변동)
HEART_RATE_RANGE = (60, 80)  # 심박수 범위 (작은 범위)
HRV_RANGE = (40, 60)  # 심박변이 범위 (작은 범위)
OXYGEN_SATURATION_RANGE = (95, 100)  # 혈중 산소포화도 범위 (작은 범위)

# 데이터 수집 간격 (초)
DATA_COLLECTION_INTERVAL = 60  # 1분

# 다수결 조절 간격 (초)
ADJUSTMENT_INTERVAL = 180  # 3분

# 종료 이벤트
stop_event = Event()

def send_health_data(heart_rate, hrv, oxygen_saturation, bmi=FIXED_BMI, age=FIXED_AGE, gender=FIXED_GENDER):
    """건강데이터 전송"""
    url = f"{BASE_URL}/healthdata"
    
    data = {
        "heartRate": heart_rate,
        "HRV": hrv,
        "oxygenSaturation": oxygen_saturation,
        "bmi": bmi,
        "age": age,
        "gender": gender
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] 데이터 수집 성공:")
            print(f"   심박수: {heart_rate}, HRV: {hrv}, 산소포화도: {oxygen_saturation}")
            print(f"   예측 피부온도: {result.get('predicted_skin_temp', 'N/A')}°C")
            print(f"   예측 코드: {result.get('predicted_skin_code', 'N/A')}")
            return True
        else:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] 데이터 수집 실패: {response.status_code}")
            print(f"   응답: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] 데이터 수집 중 오류: {e}")
        return False

def trigger_adjustment():
    """에어컨 조절 트리거 (다수결 로직 실행)"""
    # 서버의 adjust_air_conditioner를 직접 호출할 수 있는 엔드포인트가 없으므로
    # healthdata를 보내서 자동으로 조절이 트리거되도록 함
    # 또는 별도의 트리거 엔드포인트가 있다면 사용
    
    # 방법 1: healthdata를 보내서 자동 조절 트리거 (수면 모드가 활성화되어 있어야 함)
    # 방법 2: 서버에 직접 조절 요청 (엔드포인트가 있다면)
    
    # 일단 healthdata를 보내서 조절이 트리거되도록 함
    # 실제 조절은 서버의 adjust_air_conditioner 함수가 실행됨
    heart_rate = random.randint(*HEART_RATE_RANGE)
    hrv = random.uniform(*HRV_RANGE)
    oxygen_saturation = random.uniform(*OXYGEN_SATURATION_RANGE)
    hrv = round(hrv, 1)
    oxygen_saturation = round(oxygen_saturation, 1)
    
    print(f"\n🎯 [{datetime.now().strftime('%H:%M:%S')}] 다수결 조절 트리거 시도...")
    success = send_health_data(heart_rate, hrv, oxygen_saturation)
    
    if success:
        print(f"   → 서버가 최근 데이터를 기반으로 다수결 조절을 실행합니다.\n")
    else:
        print(f"   ⚠️ 조절 트리거 실패\n")
    
    return success

def data_collection_loop():
    """데이터 수집 루프 (1분마다)"""
    collection_count = 0
    
    print(f"📊 데이터 수집 시작 (간격: {DATA_COLLECTION_INTERVAL}초 = {DATA_COLLECTION_INTERVAL // 60}분)")
    
    while not stop_event.is_set():
        try:
            # 임의의 건강 데이터 생성
            heart_rate = random.randint(*HEART_RATE_RANGE)
            hrv = random.uniform(*HRV_RANGE)
            oxygen_saturation = random.uniform(*OXYGEN_SATURATION_RANGE)
            
            # 소수점 1자리로 반올림
            hrv = round(hrv, 1)
            oxygen_saturation = round(oxygen_saturation, 1)
            
            # 데이터 전송
            send_health_data(heart_rate, hrv, oxygen_saturation)
            collection_count += 1
            
            # 대기 (중간에 종료 신호가 오면 즉시 종료)
            if stop_event.wait(DATA_COLLECTION_INTERVAL):
                break
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 데이터 수집 루프 오류: {e}")
            if stop_event.wait(DATA_COLLECTION_INTERVAL):
                break
    
    print(f"\n📊 데이터 수집 종료 (총 {collection_count}회 전송)")

def adjustment_loop():
    """다수결 조절 루프 (3분마다)"""
    adjustment_count = 0
    
    print(f"🎯 다수결 조절 시작 (간격: {ADJUSTMENT_INTERVAL}초 = {ADJUSTMENT_INTERVAL // 60}분)")
    
    # 첫 조절은 3분 후에 실행
    if stop_event.wait(ADJUSTMENT_INTERVAL):
        return
    
    while not stop_event.is_set():
        try:
            # 조절 트리거
            trigger_adjustment()
            adjustment_count += 1
            
            # 대기 (중간에 종료 신호가 오면 즉시 종료)
            if stop_event.wait(ADJUSTMENT_INTERVAL):
                break
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 조절 루프 오류: {e}")
            if stop_event.wait(ADJUSTMENT_INTERVAL):
                break
    
    print(f"\n🎯 다수결 조절 종료 (총 {adjustment_count}회 실행)")

def main():
    """메인 함수"""
    print("=" * 70)
    print("데이터 수집 및 다수결 조절 테스트")
    print("=" * 70)
    print(f"통일된 사용자 정보: BMI={FIXED_BMI}, 나이={FIXED_AGE}, 성별={'남성' if FIXED_GENDER == 1.0 else '여성'}")
    print("=" * 70)
    print("\n📌 테스트 설정:")
    print(f"   • 데이터 수집: {DATA_COLLECTION_INTERVAL}초마다 (1분)")
    print(f"   • 다수결 조절: {ADJUSTMENT_INTERVAL}초마다 (3분)")
    print("\n📊 건강 데이터 변동 범위:")
    print(f"   • 심박수: {HEART_RATE_RANGE[0]}-{HEART_RATE_RANGE[1]} bpm")
    print(f"   • HRV: {HRV_RANGE[0]}-{HRV_RANGE[1]}")
    print(f"   • 산소포화도: {OXYGEN_SATURATION_RANGE[0]}-{OXYGEN_SATURATION_RANGE[1]}%")
    print("=" * 70)
    print("\n⚠️ 주의사항:")
    print("   • 서버가 실행 중이어야 합니다.")
    print("   • 수면 모드가 활성화되어 있어야 에어컨 조절이 실행됩니다.")
    print("   • Ctrl+C로 중단할 수 있습니다.")
    print("=" * 70)
    print()
    
    # 서버 연결 확인
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ 서버 연결 확인: {BASE_URL}")
            print(f"   모델 로드: {'✅' if health_data.get('model_loaded') else '❌'}")
            print(f"   에어컨 사용 가능: {'✅' if health_data.get('air_conditioner_available') else '❌'}")
            print(f"   DB 연결: {'✅' if health_data.get('database_connected') else '❌'}")
            print()
        else:
            print(f"❌ 서버 연결 실패: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        print(f"   서버가 {BASE_URL}에서 실행 중인지 확인해주세요.")
        return
    
    # 초기 데이터 3개 전송 (다수결 판단을 위한 최소 데이터)
    print("📊 초기 데이터 3개 전송 중...")
    for i in range(3):
        heart_rate = random.randint(*HEART_RATE_RANGE)
        hrv = random.uniform(*HRV_RANGE)
        oxygen_saturation = random.uniform(*OXYGEN_SATURATION_RANGE)
        hrv = round(hrv, 1)
        oxygen_saturation = round(oxygen_saturation, 1)
        send_health_data(heart_rate, hrv, oxygen_saturation)
        if i < 2:
            time.sleep(1)  # 1초 간격
    print("✅ 초기 데이터 전송 완료\n")
    
    # 두 개의 스레드 시작
    data_thread = Thread(target=data_collection_loop, daemon=True)
    adjustment_thread = Thread(target=adjustment_loop, daemon=True)
    
    data_thread.start()
    adjustment_thread.start()
    
    print("🔄 테스트 시작 (Ctrl+C로 중단)\n")
    
    try:
        # 메인 스레드는 두 스레드가 실행되는 동안 대기
        while data_thread.is_alive() or adjustment_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
        stop_event.set()
        
        # 스레드 종료 대기
        data_thread.join(timeout=5)
        adjustment_thread.join(timeout=5)
    
    print("\n" + "=" * 70)
    print("✅ 테스트 종료")
    print("=" * 70)

if __name__ == "__main__":
    # 중복 실행 방지: lock 파일 사용
    LOCK_FILE = os.path.join(os.path.dirname(__file__), '.test_data_collection.lock')
    
    if os.path.exists(LOCK_FILE):
        # lock 파일이 있으면 실행 중인 프로세스 확인
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # 프로세스가 실제로 실행 중인지 확인
            try:
                os.kill(old_pid, 0)  # 프로세스가 존재하는지 확인
                print(f"⚠️ 이미 실행 중인 프로세스가 있습니다 (PID: {old_pid})")
                print("기존 프로세스를 종료하거나 잠시 기다려주세요.")
                sys.exit(1)
            except OSError:
                # 프로세스가 없으면 lock 파일 삭제
                os.remove(LOCK_FILE)
        except (ValueError, IOError):
            # lock 파일이 손상되었으면 삭제
            os.remove(LOCK_FILE)
    
    # lock 파일 생성
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            main()
        finally:
            # 스크립트 종료 시 lock 파일 삭제
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
    except KeyboardInterrupt:
        # Ctrl+C로 중단 시에도 lock 파일 삭제
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        raise

