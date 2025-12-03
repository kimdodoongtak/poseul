#!/usr/bin/env python3
"""
사용자별 기능 테스트 스크립트
- 피드백 갱신이 사용자별로 적용되는지
- 갱신된 온도 범위가 사용자별로 적용되는지
- 하룻밤 온도 변화 그래프가 사용자별로 잘 들어오는지

테스트 사용자: 33번, 31번
"""

import requests
import time
import random
import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text

# 서버 URL
BASE_URL = "http://localhost:3000"

# DB 연결 (server.py와 동일한 설정 사용)
DB_URL = "mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main"
engine = None

def get_user_info_from_db(user_no: int) -> Optional[str]:
    """DB에서 사용자 정보 조회 (user_no로 id 조회)"""
    global engine
    if engine is None:
        try:
            engine = create_engine(
                DB_URL,
                connect_args={
                    "ssl_disabled": True,
                    "connect_timeout": 10,
                    "read_timeout": 10,
                    "write_timeout": 10,
                },
                pool_pre_ping=True
            )
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            return None
    
    try:
        with engine.connect() as conn:
            query = text("SELECT id FROM login WHERE no = :user_no")
            result = conn.execute(query, {"user_no": user_no})
            row = result.fetchone()
            if row:
                return row.id
            else:
                print(f"⚠️ user_no {user_no}에 해당하는 사용자를 찾을 수 없습니다.")
                return None
    except Exception as e:
        print(f"❌ DB 조회 중 오류: {e}")
        return None

# 테스트할 사용자 정보 (user_no)
TEST_USERS = [33, 31]

# 테스트용 건강 데이터
HEART_RATE_RANGE = (60, 100)
HRV_RANGE = (30, 70)
OXYGEN_SATURATION_RANGE = (95, 100)

def login_user(user_id: str, password: str) -> Optional[str]:
    """사용자 로그인 및 토큰 반환"""
    url = f"{BASE_URL}/auth/login"
    data = {
        "id": user_id,
        "password": password
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            token = result.get('token')
            user_no = result.get('user_no')
            print(f"✅ 로그인 성공: user_id={user_id}, user_no={user_no}")
            return token
        else:
            print(f"❌ 로그인 실패: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"❌ 로그인 중 오류: {e}")
        return None

def get_auth_headers(token: str) -> Dict[str, str]:
    """인증 헤더 생성"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def send_health_data(token: str, user_no: int, heart_rate: float, hrv: float, oxygen_saturation: float):
    """건강 데이터 전송"""
    url = f"{BASE_URL}/healthdata"
    headers = get_auth_headers(token)
    
    data = {
        "heartRate": heart_rate,
        "HRV": hrv,
        "oxygenSaturation": oxygen_saturation,
        "bmi": 25.0,
        "age": 30,
        "gender": "M"
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ 건강 데이터 전송 성공 (user_no={user_no})")
            print(f"     예측 피부온도: {result.get('predicted_skin_temp', 'N/A')}°C")
            return True
        else:
            print(f"  ❌ 건강 데이터 전송 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 건강 데이터 전송 중 오류: {e}")
        return False

def send_feedback(token: str, user_no: int, feedback: str):
    """온도 피드백 전송"""
    url = f"{BASE_URL}/temperature_feedback"
    headers = get_auth_headers(token)
    
    data = {
        "feedback": feedback,  # "cold", "hot", "comfortable"
        "date": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ 피드백 전송 성공 (user_no={user_no}, feedback={feedback})")
            if result.get('threshold_updated'):
                print(f"     임계값 조정됨: {result.get('message', '')}")
            return True
        else:
            print(f"  ❌ 피드백 전송 실패: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ 피드백 전송 중 오류: {e}")
        return False

def get_temperature_range(token: str, user_no: int):
    """온도 범위 조회"""
    url = f"{BASE_URL}/temperature-range"
    headers = get_auth_headers(token)
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                data = result.get('data', {})
                min_temp = data.get('min_temp')
                max_temp = data.get('max_temp')
                print(f"  ✅ 온도 범위 조회 성공 (user_no={user_no})")
                print(f"     범위: {min_temp}~{max_temp}°C")
                return min_temp, max_temp
            else:
                print(f"  ⚠️ 온도 범위 조회 실패: {result.get('message', '')}")
                return None, None
        else:
            print(f"  ❌ 온도 범위 조회 실패: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"  ❌ 온도 범위 조회 중 오류: {e}")
        return None, None

def get_temperature_chart(token: str, user_no: int, hours: int = 12):
    """하룻밤 온도 변화 그래프 데이터 조회"""
    url = f"{BASE_URL}/chart/temperature?hours={hours}"
    headers = get_auth_headers(token)
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                data = result.get('data', [])
                count = result.get('count', 0)
                print(f"  ✅ 온도 차트 데이터 조회 성공 (user_no={user_no})")
                print(f"     데이터 개수: {count}개")
                if count > 0:
                    print(f"     첫 번째 데이터: {data[0].get('timestamp', 'N/A')}")
                    print(f"     마지막 데이터: {data[-1].get('timestamp', 'N/A')}")
                return data
            else:
                print(f"  ⚠️ 온도 차트 데이터 조회 실패: {result.get('message', '')}")
                return []
        else:
            print(f"  ❌ 온도 차트 데이터 조회 실패: {response.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ 온도 차트 데이터 조회 중 오류: {e}")
        return []

def test_user_features(user_no: int, user_id: str, password: str):
    """특정 사용자의 기능 테스트"""
    print(f"\n{'='*60}")
    print(f"🧪 사용자 {user_no}번 ({user_id}) 테스트 시작")
    print(f"{'='*60}")
    
    # 1. 로그인
    print(f"\n[1단계] 로그인")
    token = login_user(user_id, password)
    if not token:
        print(f"❌ 사용자 {user_no}번 로그인 실패, 테스트 중단")
        return False
    
    # 2. 건강 데이터 전송 (예측값 생성용)
    print(f"\n[2단계] 건강 데이터 전송 (예측값 생성용)")
    for i in range(3):
        heart_rate = random.randint(*HEART_RATE_RANGE)
        hrv = random.uniform(*HRV_RANGE)
        oxygen_saturation = random.uniform(*OXYGEN_SATURATION_RANGE)
        send_health_data(token, user_no, heart_rate, round(hrv, 1), round(oxygen_saturation, 1))
        time.sleep(1)
    
    # 3. 온도 범위 조회 (초기값)
    print(f"\n[3단계] 온도 범위 조회 (초기값)")
    min_temp_initial, max_temp_initial = get_temperature_range(token, user_no)
    
    # 4. 피드백 전송 (추움)
    print(f"\n[4단계] 피드백 전송 (추움)")
    send_feedback(token, user_no, "cold")
    time.sleep(2)
    
    # 5. 온도 범위 조회 (피드백 후)
    print(f"\n[5단계] 온도 범위 조회 (피드백 후)")
    min_temp_after, max_temp_after = get_temperature_range(token, user_no)
    
    # 6. 온도 범위 비교
    print(f"\n[6단계] 온도 범위 비교")
    if min_temp_initial and min_temp_after:
        if min_temp_initial != min_temp_after or max_temp_initial != max_temp_after:
            print(f"  ✅ 온도 범위가 변경되었습니다!")
            print(f"     초기: {min_temp_initial}~{max_temp_initial}°C")
            print(f"     변경 후: {min_temp_after}~{max_temp_after}°C")
        else:
            print(f"  ⚠️ 온도 범위가 변경되지 않았습니다 (예측값과 피드백이 일치하거나 다른 이유)")
    else:
        print(f"  ⚠️ 온도 범위를 조회할 수 없습니다")
    
    # 7. 하룻밤 온도 변화 그래프 조회
    print(f"\n[7단계] 하룻밤 온도 변화 그래프 조회")
    chart_data = get_temperature_chart(token, user_no, hours=12)
    
    print(f"\n{'='*60}")
    print(f"✅ 사용자 {user_no}번 테스트 완료")
    print(f"{'='*60}\n")
    
    return True

def main():
    """메인 함수"""
    print("="*60)
    print("사용자별 기능 테스트 시작")
    print("="*60)
    print("\n테스트 항목:")
    print("  1. 피드백 갱신이 사용자별로 적용되는지")
    print("  2. 갱신된 온도 범위가 사용자별로 적용되는지")
    print("  3. 하룻밤 온도 변화 그래프가 사용자별로 잘 들어오는지")
    print("\n테스트 사용자: 33번, 31번")
    print("="*60)
    
    # 사용자 정보 (user_no와 실제 로그인 아이디 매핑 필요)
    # 실제 아이디/비밀번호는 환경변수나 설정 파일에서 가져와야 함
    # 여기서는 예시로 하드코딩 (실제로는 DB에서 조회하거나 설정 파일 사용)
    
    # 사용자 정보 조회 (DB에서 id 조회, 비밀번호는 입력받기)
    print("\n⚠️ 각 사용자의 비밀번호가 필요합니다.")
    print("   (아이디는 DB에서 자동 조회됩니다)")
    
    user_credentials = {}
    for user_no in TEST_USERS:
        user_id = get_user_info_from_db(user_no)
        if not user_id:
            print(f"❌ 사용자 {user_no}번 정보를 조회할 수 없습니다. 건너뜁니다.")
            continue
        
        print(f"\n사용자 {user_no}번 (아이디: {user_id})")
        password = input(f"  비밀번호: ").strip()
        if not password:
            print(f"⚠️ 비밀번호가 입력되지 않았습니다. 건너뜁니다.")
            continue
        user_credentials[user_no] = (user_id, password)
    
    # 각 사용자별로 테스트 실행
    for user_no in TEST_USERS:
        user_id, password = user_credentials[user_no]
        test_user_features(user_no, user_id, password)
        time.sleep(2)  # 사용자 간 간격
    
    print("\n" + "="*60)
    print("✅ 모든 테스트 완료!")
    print("="*60)
    print("\n결과 확인:")
    print("  - 각 사용자의 온도 범위가 독립적으로 변경되었는지 확인")
    print("  - 각 사용자의 차트 데이터가 올바르게 조회되는지 확인")
    print("  - 서버 로그에서 사용자별 피드백 처리 확인")
    print("="*60)

if __name__ == "__main__":
    main()

