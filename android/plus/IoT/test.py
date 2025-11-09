import base64
import requests
import uuid
import socket
from typing import Optional, Dict, Any

# ThinQ API 베이스 URL (OpenAPI 스펙 기준)
# Region별 Base URL:
# - South Asia, East Asia and Pacific: https://api-kic.lgthinq.com
# - America: https://api-aic.lgthinq.com
# - Europe, Middle East, Africa: https://api-eic.lgthinq.com
THINQ_API_BASE_URL = "https://api-kic.lgthinq.com"  # 한국 기준

# API Key (OpenAPI 스펙에 명시된 고정값)
THINQ_API_KEY = "v6GFvkweNo7DK7yD3ylIZ9w52aKBU0eJ7wLXkSR3"

# PAT Token (개인 API 토큰 - https://connect-pat.lgthinq.com 에서 발급)
PAT_TOKEN = "thinqpat_6db40a76ffca2c2476f106133c69125c94493ac0e028a973aa9b"

# Client ID (고유한 클라이언트 식별자)
CLIENT_ID = "test-client-123456"


def generate_message_id() -> str:
    """
    UUID Version 4를 url-safe-base64-no-padding 방식으로 인코딩하여 
    22자 길이의 message-id를 생성합니다.
    
    Returns:
        22자 길이의 message-id 문자열
    """
    uuid_v4 = uuid.uuid4()
    # UUID를 16바이트 바이너리로 변환
    uuid_bytes = uuid_v4.bytes
    # url-safe-base64 인코딩 (패딩 제거)
    encoded = base64.urlsafe_b64encode(uuid_bytes).decode('utf-8').rstrip('=')
    # 22자로 제한
    return encoded[:22]


def generate_route_api_header(country: str = "KR", service_phase: str = "OP") -> dict:
    """
    Route API 호출을 위한 헤더를 생성합니다.
    Route API는 PAT 토큰이 필요 없습니다.
    
    Args:
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        service_phase: 서비스 형상 (예: OP)
    
    Returns:
        API 헤더 딕셔너리
    """
    return {
        "x-message-id": generate_message_id(),
        "x-country": country,
        "x-service-phase": service_phase,
        "x-api-key": THINQ_API_KEY
    }


def generate_device_api_header(country: str = "KR", client_id: str = None) -> dict:
    """
    Device API 호출을 위한 헤더를 생성합니다.
    Device API는 PAT 토큰과 client-id가 필요합니다.
    
    Args:
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        client_id: 클라이언트 식별자 (None이면 기본값 사용)
    
    Returns:
        API 헤더 딕셔너리
    """
    if client_id is None:
        client_id = CLIENT_ID
    
    # PAT 토큰 검증
    if not PAT_TOKEN or PAT_TOKEN == "":
        raise ValueError("PAT_TOKEN이 설정되지 않았습니다. https://connect-pat.lgthinq.com 에서 토큰을 발급받으세요.")
    
    if not PAT_TOKEN.startswith("thinqpat_"):
        print(f"⚠️  경고: PAT 토큰이 'thinqpat_'로 시작하지 않습니다. 올바른 형식인지 확인하세요.")
    
    return {
        "Authorization": f"Bearer {PAT_TOKEN}",
        "x-message-id": generate_message_id(),
        "x-country": country,
        "x-client-id": client_id,
        "x-api-key": THINQ_API_KEY
    }


def check_domain_resolution(domain: str) -> bool:
    """
    도메인이 DNS에서 해석 가능한지 확인합니다.
    
    Args:
        domain: 확인할 도메인 (예: "api-kic.lgthinq.com")
    
    Returns:
        해석 가능하면 True, 아니면 False
    """
    try:
        # URL에서 도메인 추출
        if domain.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(domain)
            domain = parsed.netloc
        
        # 도메인에서 포트 제거
        if ':' in domain:
            domain = domain.split(':')[0]
        
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False
    except Exception as e:
        print(f"도메인 확인 중 오류: {e}")
        return False


def get_route_domain(country: str = "KR", service_phase: str = "OP", base_url: str = None) -> Dict[str, Any]:
    """
    ThinQ Platform의 Backend 주소를 조회합니다.
    리전별, 형상별 도메인 이름을 조회하는 API입니다.
    
    Args:
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        service_phase: 서비스 형상 (예: OP)
        base_url: 사용할 베이스 URL (None이면 기본값 사용)
    
    Returns:
        API 응답 (JSON)
    """
    if base_url is None:
        base_url = THINQ_API_BASE_URL
    
    # 도메인 해석 확인
    print(f"\n도메인 확인 중: {base_url}")
    if not check_domain_resolution(base_url):
        print(f"❌ 도메인을 해석할 수 없습니다: {base_url}")
        print("\n💡 가능한 해결 방법:")
        print("1. 인터넷 연결을 확인하세요")
        print("2. VPN이나 프록시 설정을 확인하세요")
        raise ConnectionError(f"도메인을 해석할 수 없습니다: {base_url}")
    
    print(f"✅ 도메인 해석 성공")
    
    url = f"{base_url}/route"
    headers = generate_route_api_header(country=country, service_phase=service_phase)
    
    print(f"\nAPI 호출 중: {url}")
    print(f"헤더: {headers}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"❌ 요청 시간 초과")
        raise
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 연결 실패: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 에러 발생")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise


def get_devices(country: str = "KR", base_url: str = None, debug: bool = True) -> Dict[str, Any]:
    """
    ThinQ Platform에 등록한 디바이스 목록을 조회합니다.
    다른 API를 사용하기 전에 반드시 한 번은 호출되어야 합니다.
    
    Args:
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        base_url: 사용할 베이스 URL (None이면 기본값 사용)
        debug: 디버그 정보 출력 여부
    
    Returns:
        API 응답 (JSON) - 디바이스 목록 포함
    """
    import json
    
    if base_url is None:
        base_url = THINQ_API_BASE_URL
    
    url = f"{base_url}/devices"
    headers = generate_device_api_header(country=country)
    
    print(f"\nAPI 호출 중: {url}")
    if debug:
        print(f"헤더: {json.dumps(headers, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # 응답 상태 코드 확인
        print(f"응답 상태 코드: {response.status_code}")
        
        if debug:
            print(f"\n응답 헤더:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
        
        response.raise_for_status()
        
        # 응답 본문 확인
        response_data = response.json()
        
        if debug:
            print(f"\n📥 API 응답 (전체):")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            print(f"\n📥 API 응답 구조 분석:")
            print(f"  최상위 키: {list(response_data.keys())}")
            
            # 사용자 정보 확인
            print(f"\n👤 사용자/인증 정보 확인:")
            if 'result' in response_data:
                result = response_data['result']
                if isinstance(result, dict):
                    # 사용자 관련 키 확인
                    user_keys = [k for k in result.keys() if 'user' in k.lower() or 'account' in k.lower() or 'auth' in k.lower()]
                    if user_keys:
                        print(f"  사용자 관련 키: {user_keys}")
                    # 메시지 ID 확인 (요청 추적)
                    if 'messageId' in response_data:
                        print(f"  응답 메시지 ID: {response_data.get('messageId')}")
                    if 'timestamp' in response_data:
                        print(f"  응답 타임스탬프: {response_data.get('timestamp')}")
            
            # 디바이스 정보 확인
            if 'result' in response_data:
                print(f"  result 타입: {type(response_data['result'])}")
                if isinstance(response_data['result'], dict):
                    print(f"  result 키: {list(response_data['result'].keys())}")
                    if 'devices' in response_data['result']:
                        devices = response_data['result']['devices']
                        print(f"  devices 개수: {len(devices) if isinstance(devices, list) else 'N/A'}")
                        if isinstance(devices, list) and len(devices) > 0:
                            print(f"  첫 번째 디바이스 키: {list(devices[0].keys())}")
                        elif isinstance(devices, list) and len(devices) == 0:
                            print(f"  ⚠️  디바이스 목록이 비어있습니다!")
                            print(f"     - PAT 토큰이 올바른 계정의 것인지 확인하세요")
                            print(f"     - 해당 계정에 등록된 디바이스가 있는지 확인하세요")
                            print(f"     - ThinQ 앱에서 디바이스가 정상적으로 등록되어 있는지 확인하세요")
        
        return response_data
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 에러 발생")
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            print(f"응답 상태 코드: {status_code}")
            
            # 인증 관련 에러 체크
            if status_code == 401:
                print(f"\n🔐 인증 실패 (401 Unauthorized)")
                print(f"   가능한 원인:")
                print(f"   1. PAT 토큰이 잘못되었거나 만료되었습니다")
                print(f"   2. PAT 토큰이 다른 계정의 것입니다")
                print(f"   3. Authorization 헤더 형식이 잘못되었습니다")
                print(f"   해결 방법:")
                print(f"   - https://connect-pat.lgthinq.com 에서 새로운 PAT 토큰을 발급받으세요")
                print(f"   - 코드의 PAT_TOKEN 변수를 올바른 토큰으로 업데이트하세요")
            elif status_code == 400:
                print(f"\n⚠️  잘못된 요청 (400 Bad Request)")
                print(f"   가능한 원인:")
                print(f"   1. 필수 헤더가 누락되었습니다")
                print(f"   2. 헤더 형식이 잘못되었습니다")
                print(f"   3. x-client-id가 올바르지 않습니다")
            
            print(f"\n응답 내용: {e.response.text}")
            try:
                error_json = e.response.json()
                print(f"에러 응답 (JSON): {json.dumps(error_json, indent=2, ensure_ascii=False)}")
            except:
                pass
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise


def get_device_profile(device_id: str, country: str = "KR", base_url: str = None) -> Dict[str, Any]:
    """
    디바이스 프로파일을 조회합니다.
    디바이스 프로파일은 LG 가전의 속성을 기술한 정보입니다.
    
    Args:
        device_id: 디바이스 ID
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        base_url: 사용할 베이스 URL (None이면 기본값 사용)
    
    Returns:
        API 응답 (JSON) - 디바이스 프로파일 포함
    """
    if base_url is None:
        base_url = THINQ_API_BASE_URL
    
    url = f"{base_url}/devices/{device_id}/profile"
    headers = generate_device_api_header(country=country)
    
    print(f"\nAPI 호출 중: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 에러 발생")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise


def get_device_state(device_id: str, country: str = "KR", base_url: str = None) -> Dict[str, Any]:
    """
    디바이스 현재 상태를 조회합니다.
    
    Args:
        device_id: 디바이스 ID
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        base_url: 사용할 베이스 URL (None이면 기본값 사용)
    
    Returns:
        API 응답 (JSON) - 디바이스 상태 포함
    """
    if base_url is None:
        base_url = THINQ_API_BASE_URL
    
    url = f"{base_url}/devices/{device_id}/state"
    headers = generate_device_api_header(country=country)
    
    print(f"\nAPI 호출 중: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 에러 발생")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise


def send_device_command(device_id: str, command: Dict[str, Any], country: str = "KR", 
                       conditional_control: bool = False, base_url: str = None) -> Dict[str, Any]:
    """
    디바이스에 제어 명령을 전송합니다.
    
    Args:
        device_id: 디바이스 ID
        command: 제어 명령 (JSON 객체)
        country: ISO 3166-1 alpha-2 국가 코드 (예: KR, US, GB)
        conditional_control: 조건부 제어 여부 (True면 상태 조회 후 제어 가능한 상태에서만 제어)
        base_url: 사용할 베이스 URL (None이면 기본값 사용)
    
    Returns:
        API 응답 (JSON)
    """
    if base_url is None:
        base_url = THINQ_API_BASE_URL
    
    url = f"{base_url}/devices/{device_id}/control"
    headers = generate_device_api_header(country=country)
    
    if conditional_control:
        headers["x-conditional-control"] = "true"
    
    print(f"\nAPI 호출 중: {url}")
    print(f"제어 명령: {command}")
    
    try:
        response = requests.post(url, headers=headers, json=command, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 에러 발생")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        raise


def get_device_type_korean(device_type: str) -> str:
    """
    디바이스 타입을 한글로 변환합니다.
    
    Args:
        device_type: 영문 디바이스 타입
    
    Returns:
        한글 디바이스 타입
    """
    device_type_map = {
        "DEVICE_REFRIGERATOR": "냉장고",
        "DEVICE_WATER_PURIFIER": "정수기",
        "DEVICE_WINE_CELLAR": "와인냉장고",
        "DEVICE_KIMCHI_REFRIGERATOR": "김치냉장고",
        "DEVICE_HOME_BREW": "맥주제조기",
        "DEVICE_PLANT_CULTIVATOR": "식물재배기",
        "DEVICE_WASHER": "세탁기",
        "DEVICE_DRYER": "건조기",
        "DEVICE_STYLER": "스타일러",
        "DEVICE_DISH_WASHER": "식기세척기",
        "DEVICE_WASHTOWER_WASHER": "워시타워 (세탁기)",
        "DEVICE_WASHTOWER_DRYER": "워시타워 (건조기)",
        "DEVICE_WASHTOWER": "워시타워",
        "DEVICE_MAIN_WASHCOMBO": "워시콤보세탁기",
        "DEVICE_MINI_WASHCOMBO": "워시콤보미니세탁기",
        "DEVICE_OVEN": "오븐",
        "DEVICE_COOKTOP": "쿡탑",
        "DEVICE_HOOD": "후드",
        "DEVICE_MICROWAVE_OVEN": "전자레인지",
        "DEVICE_AIR_CONDITIONER": "에어컨",
        "DEVICE_SYSTEM_BOILER": "시스템보일러",
        "DEVICE_AIR_PURIFIER": "공기청정기",
        "DEVICE_DEHUMIDIFIER": "제습기",
        "DEVICE_HUMIDIFIER": "가습기",
        "DEVICE_WATER_HEATER": "온수기",
        "DEVICE_CEILING_FAN": "실링팬",
        "DEVICE_AIR_PURIFIER_FAN": "공기청정팬",
        "DEVICE_ROBOT_CLEANER": "로봇청소기",
        "DEVICE_STICK_CLEANER": "스틱청소기",
    }
    return device_type_map.get(device_type, device_type)


def print_devices_list(devices_result: Dict[str, Any], detailed: bool = True):
    """
    디바이스 목록을 보기 좋게 출력합니다.
    
    Args:
        devices_result: get_devices() 함수의 응답 결과
        detailed: 상세 정보 출력 여부
    """
    import json
    
    # 다양한 응답 구조를 지원하도록 개선
    devices = None
    
    # 응답 구조 분석
    print(f"\n🔍 응답 구조 분석:")
    print(f"  최상위 키: {list(devices_result.keys())}")
    
    # 가능한 경로들을 시도 (우선순위 순서)
    # 1. response가 배열인 경우 (실제 API 응답 구조)
    if 'response' in devices_result:
        response = devices_result['response']
        print(f"  'response' 타입: {type(response)}")
        if isinstance(response, list):
            print(f"  'response' 배열 길이: {len(response)}")
            devices = response
        elif isinstance(response, dict):
            print(f"  'response' 키: {list(response.keys())}")
            if 'devices' in response:
                devices = response['devices']
            elif 'deviceList' in response:
                devices = response['deviceList']
    
    # 2. result 경로 확인
    if devices is None and 'result' in devices_result:
        result = devices_result['result']
        print(f"  'result' 타입: {type(result)}")
        if isinstance(result, dict):
            print(f"  'result' 키: {list(result.keys())}")
            if 'devices' in result:
                devices = result['devices']
            elif 'deviceList' in result:
                devices = result['deviceList']
        elif isinstance(result, list):
            devices = result
    
    # 3. 최상위 레벨에서 직접 확인
    if devices is None:
        if 'devices' in devices_result:
            devices = devices_result['devices']
        elif 'deviceList' in devices_result:
            devices = devices_result['deviceList']
        elif isinstance(devices_result, list):
            devices = devices_result
    
    if devices is None:
        print(f"\n⚠️  디바이스 목록을 찾을 수 없습니다.")
        print(f"전체 응답 구조:")
        print(json.dumps(devices_result, indent=2, ensure_ascii=False))
        return
    
    if not isinstance(devices, list):
        print(f"\n⚠️  디바이스 목록이 리스트 형식이 아닙니다. 타입: {type(devices)}")
        print(f"전체 응답 구조:")
        print(json.dumps(devices_result, indent=2, ensure_ascii=False))
        return
    
    if not devices:
        print("\n❌ 등록된 디바이스가 없습니다.")
        print(f"응답 데이터:")
        print(json.dumps(devices_result, indent=2, ensure_ascii=False))
        return
    
    print(f"\n{'=' * 80}")
    print(f"📱 등록된 디바이스 목록 (총 {len(devices)}개)")
    print(f"{'=' * 80}")
    
    for idx, device in enumerate(devices, 1):
        device_id = device.get('deviceId', 'N/A')
        
        # deviceInfo 객체에서 정보 추출 (OpenAPI 스펙에 따르면 정보가 여기에 있음)
        device_info = device.get('deviceInfo', {})
        
        # deviceInfo에서 정보 추출, 없으면 최상위 레벨에서 찾기
        device_type = device_info.get('type') or device.get('deviceType') or device.get('type', 'N/A')
        device_type_kr = get_device_type_korean(device_type)
        alias = device_info.get('alias') or device.get('alias', 'N/A')
        model_name = device_info.get('modelName') or device.get('modelName', 'N/A')
        service_id = device.get('serviceId', 'N/A')
        group_id = device_info.get('groupId') or device.get('groupId')
        reportable = device_info.get('reportable') or device.get('reportable')
        
        # 디바이스 식별을 위한 주요 정보 강조
        print(f"\n{'─' * 80}")
        print(f"[{idx}] 🏠 {device_type_kr}")
        print(f"{'─' * 80}")
        print(f"   📛 별명 (Alias): {alias}")
        print(f"   🏷️  모델명: {model_name}")
        print(f"   🔢 디바이스 타입: {device_type}")
        print(f"   🆔 디바이스 ID: {device_id}")
        if service_id != 'N/A':
            print(f"   🔑 서비스 ID: {service_id}")
        if group_id:
            print(f"   👥 그룹 ID: {group_id}")
        if reportable is not None:
            print(f"   📡 이벤트 구독 가능: {'예' if reportable else '아니오'}")
        
        if detailed:
            # 추가 정보 출력
            print(f"\n   📊 추가 정보:")
            if 'fwVer' in device:
                print(f"      • 펌웨어 버전: {device.get('fwVer')}")
            if 'online' in device:
                online_status = "🟢 온라인" if device.get('online') else "🔴 오프라인"
                print(f"      • 연결 상태: {online_status}")
            if 'macAddress' in device:
                print(f"      • MAC 주소: {device.get('macAddress')}")
            if 'sn' in device:
                print(f"      • 시리얼 번호: {device.get('sn')}")
            if 'userNumber' in device:
                print(f"      • 사용자 번호: {device.get('userNumber')}")
            
            # deviceInfo 객체 정보 출력
            if device_info:
                print(f"\n   📦 deviceInfo 객체:")
                device_info_keys = list(device_info.keys())
                print(f"      deviceInfo 필드: {', '.join(device_info_keys)}")
                for key, value in device_info.items():
                    if key not in ['type', 'modelName', 'alias', 'groupId', 'reportable']:
                        print(f"      • {key}: {value}")
            
            # 디바이스 객체의 모든 키 출력 (디버깅용)
            print(f"\n   🔍 디바이스 데이터 구조:")
            all_keys = list(device.keys())
            print(f"      사용 가능한 필드: {', '.join(all_keys)}")
            
            # 주요 필드가 없는 경우 경고
            if alias == 'N/A' or alias == '':
                print(f"      ⚠️  별명이 설정되지 않았습니다. ThinQ 앱에서 별명을 설정하세요.")
            if model_name == 'N/A' or model_name == '':
                print(f"      ⚠️  모델명 정보가 없습니다.")
            if device_type == 'N/A':
                print(f"      ⚠️  디바이스 타입 정보가 없습니다.")
    
    print(f"\n{'=' * 80}")
    
    # JSON 형식으로도 출력 (옵션)
    if detailed:
        print("\n📋 전체 응답 (JSON):")
        print(json.dumps(devices_result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # 테스트 실행
    print("=" * 60)
    print("LG ThinQ Platform API 테스트 시작...")
    print("=" * 60)
    print(f"생성된 message-id: {generate_message_id()}")
    
    # 1. Route API 테스트 (Backend 주소 조회)
    print("\n" + "=" * 60)
    print("1. Route API 테스트 - Backend 주소 조회")
    print("=" * 60)
    try:
        route_result = get_route_domain(country="KR", service_phase="OP")
        print("\n✅ Route API 호출 성공!")
        print(f"API 서버: {route_result.get('response', {}).get('apiServer', 'N/A')}")
        print(f"MQTT 서버: {route_result.get('response', {}).get('mqttServer', 'N/A')}")
        print(f"WebSocket 서버: {route_result.get('response', {}).get('webSocketServer', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Route API 호출 실패: {e}")
    
    # 2. Device API 테스트 (디바이스 목록 조회)
    print("\n" + "=" * 60)
    print("2. Device API 테스트 - 디바이스 목록 조회")
    print("=" * 60)
    
    # PAT 토큰 확인
    print(f"\n🔐 인증 정보 확인:")
    print(f"  PAT 토큰: {PAT_TOKEN[:20]}... (처음 20자만 표시)")
    if not PAT_TOKEN.startswith("thinqpat_"):
        print(f"  ⚠️  경고: PAT 토큰 형식이 올바르지 않을 수 있습니다")
    print(f"  Client ID: {CLIENT_ID}")
    print(f"  Country: KR")
    
    try:
        # 디버그 모드로 호출하여 상세 정보 확인
        devices_result = get_devices(country="KR", debug=True)
        print("\n✅ Device API 호출 성공!")
        
        # 디바이스 목록을 보기 좋게 출력
        print_devices_list(devices_result, detailed=True)
        
        # 디바이스 목록 추출 (다양한 응답 구조 지원)
        devices = None
        
        # 1. response가 배열인 경우 (실제 API 응답 구조)
        if 'response' in devices_result:
            response = devices_result['response']
            if isinstance(response, list):
                devices = response
            elif isinstance(response, dict):
                devices = response.get('devices') or response.get('deviceList')
        
        # 2. result 경로 확인
        if devices is None and 'result' in devices_result:
            result = devices_result['result']
            if isinstance(result, dict):
                devices = result.get('devices') or result.get('deviceList')
            elif isinstance(result, list):
                devices = result
        
        # 3. 최상위 레벨에서 직접 확인
        if devices is None:
            if 'devices' in devices_result:
                devices = devices_result['devices']
            elif 'deviceList' in devices_result:
                devices = devices_result['deviceList']
            elif isinstance(devices_result, list):
                devices = devices_result
        
        if devices and isinstance(devices, list) and len(devices) > 0:
            # 모든 디바이스의 상세 정보 조회
            print(f"\n{'=' * 80}")
            print(f"📊 디바이스 상세 정보 조회")
            print(f"{'=' * 80}")
            
            for idx, device in enumerate(devices, 1):
                device_id = device.get('deviceId')
                device_alias = device.get('alias', 'N/A')
                device_type = device.get('deviceType', 'N/A')
                device_type_kr = get_device_type_korean(device_type)
                model_name = device.get('modelName', 'N/A')
                
                print(f"\n{'─' * 80}")
                print(f"[{idx}] {device_type_kr} - {device_alias}")
                print(f"   모델명: {model_name}")
                print(f"   디바이스 ID: {device_id}")
                print(f"{'─' * 80}")
                
                # 각 디바이스의 프로파일 조회
                try:
                    print(f"\n   📋 프로파일 조회 중...")
                    profile = get_device_profile(device_id, country="KR")
                    print(f"   ✅ 프로파일 조회 성공")
                    # 프로파일의 주요 정보 출력
                    if 'result' in profile:
                        result = profile.get('result', {})
                        if 'deviceType' in result:
                            print(f"      • 디바이스 타입: {result.get('deviceType')}")
                        if 'modelName' in result:
                            print(f"      • 모델명: {result.get('modelName')}")
                except Exception as e:
                    print(f"   ❌ 프로파일 조회 실패: {e}")
                
                # 각 디바이스의 상태 조회
                try:
                    print(f"\n   ⚡ 상태 조회 중...")
                    state = get_device_state(device_id, country="KR")
                    print(f"   ✅ 상태 조회 성공")
                    # 상태의 주요 정보 출력
                    if 'result' in state:
                        result = state.get('result', {})
                        if 'value' in result:
                            print(f"      • 상태 데이터가 있습니다.")
                            # 상태 데이터의 키 출력
                            value = result.get('value', {})
                            if isinstance(value, dict):
                                state_keys = list(value.keys())
                                if state_keys:
                                    print(f"      • 상태 항목: {', '.join(state_keys[:5])}{'...' if len(state_keys) > 5 else ''}")
                except Exception as e:
                    print(f"   ❌ 상태 조회 실패: {e}")
    except Exception as e:
        print(f"\n❌ Device API 호출 실패: {e}")
        import traceback
        traceback.print_exc()
