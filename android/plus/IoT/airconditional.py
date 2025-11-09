"""
LG ThinQ 에어컨 상태 조회 및 조작 모듈

참고 문서:
https://smartsolution.developer.lge.com/ko/apiManage/thinq_connect?s=1762326746590#tag/Device-API/paths/~1devices/get
"""

import sys
from typing import Dict, Any, Optional
import json

# test.py에서 필요한 함수들 import
from test import (
    THINQ_API_BASE_URL,
    generate_device_api_header,
    get_device_state,
    send_device_command
)
import requests

# 에어컨 디바이스 ID (이미지에서 확인된 ID)
AIR_CONDITIONER_DEVICE_ID = "d9464856ccf8457aa9b09712905eca9f48eee5ebdb468400efd8569752302075"


def get_air_conditioner_state(device_id: str = None, country: str = "KR") -> Dict[str, Any]:
    """
    에어컨의 현재 상태를 조회합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
    
    Returns:
        API 응답 (JSON) - 에어컨 상태 포함
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    print(f"\n{'=' * 80}")
    print(f"❄️  에어컨 상태 조회")
    print(f"{'=' * 80}")
    print(f"디바이스 ID: {device_id}")
    
    try:
        state_response = get_device_state(device_id, country=country)
        
        # 다양한 응답 구조 지원
        state = None
        
        # 응답 구조 분석
        print(f"\n🔍 응답 구조 분석:")
        print(f"   최상위 키: {list(state_response.keys())}")
        
        # 1. response 객체 확인 (OpenAPI 스펙에 따르면 여기에 있음)
        if 'response' in state_response:
            response = state_response['response']
            print(f"   'response' 타입: {type(response)}")
            if isinstance(response, dict):
                # response가 객체인 경우
                if 'value' in response:
                    state = response['value']
                else:
                    # response 자체가 상태 데이터인 경우
                    state = response
            elif isinstance(response, list):
                # response가 배열인 경우 (첫 번째 요소 사용)
                if len(response) > 0:
                    state = response[0]
        
        # 2. result.value 경로 확인
        if state is None and 'result' in state_response:
            result = state_response['result']
            print(f"   'result' 타입: {type(result)}")
            if isinstance(result, dict):
                if 'value' in result:
                    state = result['value']
                else:
                    # result 자체가 상태 데이터인 경우
                    state = result
        
        # 3. 최상위 레벨에서 직접 확인
        if state is None:
            if 'value' in state_response:
                state = state_response['value']
        
        if state:
            print(f"   ✅ 상태 정보를 찾았습니다!")
            print_state_info(state)
            return state_response
        else:
            print(f"\n⚠️  상태 정보를 찾을 수 없습니다.")
            print(f"응답 구조:")
            print(json.dumps(state_response, indent=2, ensure_ascii=False))
            return state_response
    
    except Exception as e:
        print(f"❌ 에어컨 상태 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        raise


def print_state_info(state: Dict[str, Any]):
    """
    에어컨 상태 정보를 보기 좋게 출력합니다.
    
    Args:
        state: 에어컨 상태 데이터
    """
    print(f"\n📊 현재 상태:")
    print(f"{'─' * 80}")
    
    # 작동 모드
    if 'airConJobMode' in state:
        job_mode = state['airConJobMode'].get('currentJobMode', 'N/A')
        print(f"   🔧 작동 모드: {job_mode}")
    
    # 전원 상태
    if 'operation' in state:
        operation = state['operation']
        if 'airConOperationMode' in operation:
            power_status = operation['airConOperationMode']
            print(f"   ⚡ 전원: {power_status}")
        if 'airCleanOperationMode' in operation:
            air_clean = operation['airCleanOperationMode']
            print(f"   🌬️  공기청정 모드: {air_clean}")
    
    # 온도 정보
    if 'temperature' in state:
        temp = state['temperature']
        current = temp.get('currentTemperature', 'N/A')
        target = temp.get('targetTemperature', 'N/A')
        unit = temp.get('unit', 'C')
        print(f"   🌡️  현재 온도: {current}°{unit}")
        print(f"   🎯 목표 온도: {target}°{unit}")
    
    # 풍량
    if 'airFlow' in state:
        wind_strength = state['airFlow'].get('windStrength', 'N/A')
        print(f"   💨 풍량: {wind_strength}")
    
    # 풍향
    if 'windDirection' in state:
        wind_dir = state['windDirection']
        print(f"   🧭 풍향 설정:")
        for key, value in wind_dir.items():
            if value:
                print(f"      • {key}: {'ON' if value else 'OFF'}")
    
    # 공기질 센서
    if 'airQualitySensor' in state:
        sensor = state['airQualitySensor']
        print(f"   🌍 공기질 정보:")
        if 'PM1' in sensor:
            print(f"      • PM1: {sensor['PM1']}")
        if 'PM2' in sensor:
            print(f"      • PM2.5: {sensor['PM2']}")
        if 'PM10' in sensor:
            print(f"      • PM10: {sensor['PM10']}")
        if 'humidity' in sensor:
            print(f"      • 습도: {sensor['humidity']}%")
    
    # 필터 정보
    if 'filterInfo' in state:
        filter_info = state['filterInfo']
        if 'filterRemainPercent' in filter_info:
            print(f"   🔍 필터 잔여율: {filter_info['filterRemainPercent']}%")
    
    # 타이머
    if 'timer' in state:
        timer = state['timer']
        print(f"   ⏰ 타이머:")
        if 'absoluteStartTimer' in timer:
            print(f"      • 시작 타이머: {timer['absoluteStartTimer']}")
        if 'absoluteStopTimer' in timer:
            print(f"      • 종료 타이머: {timer['absoluteStopTimer']}")
    
    if 'sleepTimer' in state:
        sleep_timer = state['sleepTimer']
        if 'relativeStopTimer' in sleep_timer:
            print(f"   😴 수면 타이머: {sleep_timer['relativeStopTimer']}")
    
    print(f"{'─' * 80}")


def set_temperature(device_id: str = None, target_temp: float = None, unit: str = "C", 
                   country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 목표 온도를 설정합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        target_temp: 목표 온도
        unit: 온도 단위 ("C" 또는 "F")
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    if target_temp is None:
        raise ValueError("목표 온도를 지정해주세요.")
    
    command = {
        "temperature": {
            "targetTemperature": target_temp,
            "unit": unit
        }
    }
    
    print(f"\n{'=' * 80}")
    print(f"🌡️  온도 설정: {target_temp}°{unit}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, command, country=country)
        print(f"✅ 온도 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 온도 설정 실패: {e}")
        raise


def set_job_mode(device_id: str = None, mode: str = "COOL", country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 작동 모드를 설정합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        mode: 작동 모드 ("COOL", "AIR_DRY", "AIR_CLEAN", "AUTO" 등)
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    mode_map = {
        "냉방": "COOL",
        "제습": "AIR_DRY",
        "공기청정": "AIR_CLEAN",
        "자동": "AUTO"
    }
    
    # 한글 입력 시 영어로 변환
    if mode in mode_map:
        mode = mode_map[mode]
    
    command = {
        "airConJobMode": {
            "currentJobMode": mode
        }
    }
    
    print(f"\n{'=' * 80}")
    print(f"🔧 작동 모드 설정: {mode}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, command, country=country)
        print(f"✅ 작동 모드 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 작동 모드 설정 실패: {e}")
        raise


def set_wind_strength(device_id: str = None, strength: str = "AUTO", country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 풍량을 설정합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        strength: 풍량 ("HIGH", "MID", "LOW", "AUTO")
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    strength_map = {
        "강": "HIGH",
        "중": "MID",
        "약": "LOW",
        "자동": "AUTO"
    }
    
    # 한글 입력 시 영어로 변환
    if strength in strength_map:
        strength = strength_map[strength]
    
    command = {
        "airFlow": {
            "windStrength": strength
        }
    }
    
    print(f"\n{'=' * 80}")
    print(f"💨 풍량 설정: {strength}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, command, country=country)
        print(f"✅ 풍량 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 풍량 설정 실패: {e}")
        raise


def set_wind_direction(device_id: str = None, direction: str = None, enabled: bool = True,
                      country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 풍향을 설정합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        direction: 풍향 종류 ("swirlWind", "forestWind", "airGuideWind", 
                  "highCeilingWind", "autoFitWind", "concentrationWind")
        enabled: 활성화 여부
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    if direction is None:
        raise ValueError("풍향 종류를 지정해주세요.")
    
    command = {
        "windDirection": {
            direction: enabled
        }
    }
    
    print(f"\n{'=' * 80}")
    print(f"🧭 풍향 설정: {direction} = {enabled}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, command, country=country)
        print(f"✅ 풍향 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 풍향 설정 실패: {e}")
        raise


def set_power(device_id: str = None, power_on: bool = True, country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 전원을 켜거나 끕니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        power_on: True면 켜기, False면 끄기
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    power_mode = "POWER_ON" if power_on else "POWER_OFF"
    
    command = {
        "operation": {
            "airConOperationMode": power_mode
        }
    }
    
    print(f"\n{'=' * 80}")
    print(f"⚡ 전원 {'켜기' if power_on else '끄기'}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, command, country=country)
        print(f"✅ 전원 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 전원 설정 실패: {e}")
        raise


def set_timer(device_id: str = None, start_hour: int = None, start_minute: int = None,
             stop_hour: int = None, stop_minute: int = None, country: str = "KR") -> Dict[str, Any]:
    """
    에어컨 타이머를 설정합니다.
    
    Args:
        device_id: 디바이스 ID (None이면 기본값 사용)
        start_hour: 시작 시간 (시)
        start_minute: 시작 시간 (분)
        stop_hour: 종료 시간 (시)
        stop_minute: 종료 시간 (분)
        country: ISO 3166-1 alpha-2 국가 코드
    
    Returns:
        API 응답 (JSON)
    """
    if device_id is None:
        device_id = AIR_CONDITIONER_DEVICE_ID
    
    command = {}
    
    if start_hour is not None and start_minute is not None:
        command["absoluteHourToStart"] = start_hour
        command["absoluteMinuteToStart"] = start_minute
    
    if stop_hour is not None and stop_minute is not None:
        command["absoluteHourToStop"] = stop_hour
        command["absoluteMinuteToStop"] = stop_minute
    
    if not command:
        raise ValueError("타이머 정보를 입력해주세요.")
    
    timer_command = {
        "timer": command
    }
    
    print(f"\n{'=' * 80}")
    print(f"⏰ 타이머 설정")
    if start_hour is not None:
        print(f"   시작: {start_hour:02d}:{start_minute:02d}")
    if stop_hour is not None:
        print(f"   종료: {stop_hour:02d}:{stop_minute:02d}")
    print(f"{'=' * 80}")
    
    try:
        response = send_device_command(device_id, timer_command, country=country)
        print(f"✅ 타이머 설정 성공!")
        return response
    except Exception as e:
        print(f"❌ 타이머 설정 실패: {e}")
        raise


if __name__ == "__main__":
    """
    에어컨 테스트 실행
    """
    print("=" * 80)
    print("❄️  LG ThinQ 에어컨 제어 테스트")
    print("=" * 80)
    
    # 1. 현재 상태 조회
    try:
        print("\n[1단계] 에어컨 상태 조회")
        state = get_air_conditioner_state()
    except Exception as e:
        print(f"❌ 상태 조회 실패: {e}")
        sys.exit(1)
    
    # 사용 예시 (주석 해제하여 사용)
    """
    # 2. 온도 설정 (예: 24도)
    try:
        print("\n[2단계] 온도 설정")
        set_temperature(target_temp=24, unit="C")
    except Exception as e:
        print(f"❌ 온도 설정 실패: {e}")
    
    # 3. 작동 모드 변경 (예: 냉방 모드)
    try:
        print("\n[3단계] 작동 모드 변경")
        set_job_mode(mode="COOL")
    except Exception as e:
        print(f"❌ 작동 모드 변경 실패: {e}")
    
    # 4. 풍량 설정 (예: 자동)
    try:
        print("\n[4단계] 풍량 설정")
        set_wind_strength(strength="AUTO")
    except Exception as e:
        print(f"❌ 풍량 설정 실패: {e}")
    
    # 5. 전원 켜기
    try:
        print("\n[5단계] 전원 켜기")
        set_power(power_on=True)
    except Exception as e:
        print(f"❌ 전원 켜기 실패: {e}")
    """
    
    print("\n" + "=" * 80)
    print("✅ 테스트 완료")
    print("=" * 80)

