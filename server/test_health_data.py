#!/usr/bin/env python3
"""
건강데이터 테스트 스크립트
BMI, 나이, 성별은 통일하고, 심박수, 혈중 산소포화도, 심박변이에 임의의 값을 넣어서 전송
"""

import requests
import time
import random
import os
import sys
from datetime import datetime

# 서버 URL (로컬 테스트용)
BASE_URL = "http://localhost:3000"

# 통일된 사용자 정보
FIXED_BMI = 30.0
FIXED_AGE = 30
FIXED_GENDER = 0.0  # 1.0: 남성, 0.0: 여성

# 임의의 건강 데이터 범위 (변화폭을 크게 설정)
HEART_RATE_RANGE = (50, 120)  # 심박수 범위 (넓은 범위)
HRV_RANGE = (20, 80)  # 심박변이 범위
OXYGEN_SATURATION_RANGE = (90, 100)  # 혈중 산소포화도 범위 (넓은 범위)

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
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] 전송 성공:")
            print(f"   심박수: {heart_rate}, HRV: {hrv}, 산소포화도: {oxygen_saturation}")
            print(f"   예측 피부온도: {result.get('predicted_skin_temp', 'N/A')}°C")
            print(f"   예측 코드: {result.get('predicted_skin_code', 'N/A')}")
            return True
        else:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] 전송 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] 전송 중 오류: {e}")
        return False

def send_batch_of_3():
    """3개의 건강데이터를 연속으로 전송"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 3개 건강데이터 전송 시작...")
    
    for i in range(3):
        # 임의의 값 생성
        heart_rate = random.randint(*HEART_RATE_RANGE)
        hrv = random.uniform(*HRV_RANGE)
        oxygen_saturation = random.uniform(*OXYGEN_SATURATION_RANGE)
        
        # 소수점 1자리로 반올림
        hrv = round(hrv, 1)
        oxygen_saturation = round(oxygen_saturation, 1)
        
        success = send_health_data(heart_rate, hrv, oxygen_saturation)
        
        if not success:
            print("⚠️ 전송 실패했지만 계속 진행합니다...")
        
        # 마지막이 아니면 잠시 대기
        if i < 2:
            time.sleep(0.5)  # 0.5초 대기
    
    print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] 3개 건강데이터 전송 완료!")
    print("   → 2분 후 스케줄러가 최근 3개 데이터를 확인하여 온도 조절을 실행합니다.\n")

def main():
    """메인 함수: 2분마다 3개씩 건강데이터를 전송"""
    print("=" * 60)
    print("건강데이터 테스트 시작")
    print(f"통일된 사용자 정보: BMI={FIXED_BMI}, 나이={FIXED_AGE}, 성별={'남성' if FIXED_GENDER == 1.0 else '여성'}")
    print("=" * 60)
    print("\n📌 테스트 방식:")
    print("   1. 처음에 3개 데이터를 전송 (온도 조절을 위한 최소 데이터)")
    print("   2. 이후 2분마다 3개씩 추가 전송")
    print("   3. 스케줄러가 2분마다 실행되어 최근 3개 데이터로 온도 조절")
    print("=" * 60)
    print()
    
    # 처음에 3개 전송
    send_batch_of_3()
    
    # 이후 2분마다 3개씩 전송 (총 5번 = 약 10분간 테스트)
    batch_count = 1
    max_batches = 5
    
    print(f"🔄 2분마다 3개씩 데이터 전송 시작 (총 {max_batches}회 예정)...")
    print("   (Ctrl+C로 중단 가능)\n")
    
    try:
        while batch_count < max_batches:
            # 2분 대기
            print(f"⏳ 2분 대기 중... ({batch_count}/{max_batches-1})")
            time.sleep(120)  # 2분 = 120초
            
            # 3개 데이터 전송
            batch_count += 1
            send_batch_of_3()
        
        print("\n" + "=" * 60)
        print("✅ 테스트 완료!")
        print("서버 로그를 확인하여 온도 조절이 제대로 실행되었는지 확인하세요.")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
        print("=" * 60)

if __name__ == "__main__":
    # 중복 실행 방지: lock 파일 사용
    LOCK_FILE = os.path.join(os.path.dirname(__file__), '.test_health_data.lock')
    
    if os.path.exists(LOCK_FILE):
        # lock 파일이 있으면 실행 중인 프로세스 확인
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # 프로세스가 실제로 실행 중인지 확인
            try:
                os.kill(old_pid, 0)  # 프로세스가 존재하는지 확인 (시그널 0은 실제로 보내지 않음)
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

