"""
에어컨 온도 임계값 캐시 관리 모듈 (사용자별 분리)
12시간 TTL을 가진 JSON 파일 기반 캐시로 온도 임계값을 저장
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import json
import os
import threading
try:
    import fcntl  # Unix/Linux/Mac
except ImportError:
    fcntl = None  # Windows에서는 사용 불가

logger = logging.getLogger(__name__)

# 캐시 파일 경로
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'temperature_threshold.json')

# 캐시 디렉토리가 없으면 생성
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    logger.info(f"✅ 캐시 디렉토리 생성: {CACHE_DIR}")

# 에어컨 온도 임계값 캐시 (12시간 TTL, 사용자별 분리)
# 구조: {user_no: { "min_temp": float, "max_temp": float, "target_temperature": float, "created_at": str, "expires_at": str } }
_temperature_threshold_cache: Dict[int, Dict[str, Any]] = {}

# JSON 파일 잠금을 위한 Lock 객체
_cache_file_lock = threading.Lock()

def _load_cache_from_file() -> Dict[int, Dict[str, Any]]:
    """파일에서 캐시 로드 (사용자별 분리된 구조)"""
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with _cache_file_lock:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                # Unix/Linux/Mac에서 파일 레벨 잠금 추가
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 공유 잠금 (읽기)
                try:
                    file_data = json.load(f)
                finally:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 잠금 해제
                
                # 파일 구조: {user_no: cache_data} 또는 {user_no: {...}}
                # user_no를 정수 키로 변환
                cache_dict = {}
                if isinstance(file_data, dict):
                    for key, value in file_data.items():
                        try:
                            user_no = int(key)
                            cache_dict[user_no] = value
                        except (ValueError, TypeError):
                            # 하위 호환성: user_no가 없는 경우 None으로 처리
                            if key == 'min_temp' or key == 'max_temp':
                                # 이전 형식 (user_no 없음) - 무시
                                continue
                            cache_dict[int(key)] = value
                
                logger.info(f"✅ 캐시 파일에서 로드: {CACHE_FILE} (사용자 수: {len(cache_dict)})")
                return cache_dict
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.warning(f"⚠️ 캐시 파일 로드 실패: {str(e)}")
        return {}

def _save_cache_to_file(cache_data: Dict[int, Dict[str, Any]]) -> bool:
    """캐시를 파일에 저장 (사용자별 분리된 구조, 파일 잠금 사용)"""
    try:
        with _cache_file_lock:
            # 임시 파일에 먼저 쓰기 (원자적 쓰기)
            temp_file = CACHE_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                # Unix/Linux/Mac에서 파일 레벨 잠금 추가
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 배타적 잠금 (쓰기)
                try:
                    # user_no를 문자열 키로 변환하여 저장
                    file_data = {str(user_no): data for user_no, data in cache_data.items()}
                    json.dump(file_data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # 디스크에 강제 쓰기
                finally:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 잠금 해제
            
            # 임시 파일을 원본 파일로 이동 (원자적 연산)
            os.replace(temp_file, CACHE_FILE)
            logger.info(f"✅ 캐시 파일에 저장: {CACHE_FILE} (사용자 수: {len(cache_data)})")
            return True
    except (IOError, OSError) as e:
        logger.error(f"❌ 캐시 파일 저장 실패: {str(e)}")
        # 임시 파일 정리
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        return False

# 서버 시작 시 파일에서 캐시 로드 (사용자별 분리)
_temperature_threshold_cache = _load_cache_from_file()
if _temperature_threshold_cache:
    # 만료된 캐시 제거
    expired_users = []
    for user_no, cache_data in list(_temperature_threshold_cache.items()):
        try:
            expires_at = datetime.fromisoformat(cache_data["expires_at"])
            if datetime.now() > expires_at:
                expired_users.append(user_no)
        except (KeyError, ValueError):
            expired_users.append(user_no)
    
    # 만료된 사용자 캐시 삭제
    for user_no in expired_users:
        del _temperature_threshold_cache[user_no]
    
    # 만료된 캐시가 있으면 파일에 저장
    if expired_users:
        _save_cache_to_file(_temperature_threshold_cache)
        logger.info(f"⏰ 만료된 캐시 삭제: {len(expired_users)}명")
    
    if _temperature_threshold_cache:
        logger.info(f"✅ 서버 시작 시 캐시 로드 완료: {len(_temperature_threshold_cache)}명의 사용자")


def save_temperature_threshold(target_temperature: float, user_no: Optional[int] = None) -> Dict[str, Any]:
    """
    온도 임계값을 캐시에 저장 (12시간 유효, 사용자별 분리)
    메모리와 JSON 파일 모두에 저장
    
    Args:
        target_temperature: 사용자가 설정한 온도 (예: 24도)
        user_no: 사용자 번호 (선택사항, None이면 저장하지 않음)
    
    Returns:
        저장된 임계값 정보
    """
    global _temperature_threshold_cache
    
    if user_no is None:
        logger.warning("⚠️ user_no가 없어 캐시를 저장할 수 없습니다.")
        return {}
    
    # 중앙값을 기준으로 ±1도 범위 설정
    min_temp = target_temperature - 1.0
    max_temp = target_temperature + 1.0
    
    # 12시간 후 만료
    expires_at = datetime.now() + timedelta(hours=12)
    
    # 캐시 데이터 생성
    cache_data = {
        "min_temp": min_temp,
        "max_temp": max_temp,
        "target_temperature": target_temperature,
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    # 메모리 캐시에 저장 (사용자별)
    _temperature_threshold_cache[user_no] = cache_data
    
    # 파일에 저장 (전체 캐시 저장)
    _save_cache_to_file(_temperature_threshold_cache)
    
    logger.info("=" * 60)
    logger.info(f"🎯 [수동 조절] 온도 임계값 캐시 저장 완료! (user_no={user_no})")
    logger.info(f"   목표 온도: {target_temperature}°C")
    logger.info(f"   임계값 범위: {min_temp}~{max_temp}°C")
    logger.info(f"   만료 시간: {expires_at.isoformat()}")
    logger.info(f"   ⏰ 이제 자동 조절 코드에서 이 범위를 12시간 동안 사용합니다!")
    logger.info("=" * 60)
    
    return cache_data.copy()


def get_temperature_threshold(user_no: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    현재 저장된 온도 임계값 조회 (만료되지 않은 경우만, 사용자별 분리)
    메모리에 없으면 파일에서 로드 시도
    
    Args:
        user_no: 사용자 번호 (선택사항, None이면 None 반환)
    
    Returns:
        임계값 정보 (만료되었거나 없으면 None)
    """
    global _temperature_threshold_cache
    
    if user_no is None:
        return None
    
    # 메모리에 캐시가 없으면 파일에서 로드 시도
    if not _temperature_threshold_cache:
        _temperature_threshold_cache = _load_cache_from_file()
    
    # 사용자별 캐시 확인
    if user_no not in _temperature_threshold_cache:
        return None
    
    cache_data = _temperature_threshold_cache[user_no]
    
    # 만료 시간 확인
    try:
        expires_at = datetime.fromisoformat(cache_data["expires_at"])
        if datetime.now() > expires_at:
            # 만료된 경우 캐시 삭제 (메모리 + 파일)
            del _temperature_threshold_cache[user_no]
            _save_cache_to_file(_temperature_threshold_cache)
            logger.info(f"⏰ 저장된 온도 임계값이 만료되어 삭제되었습니다. (user_no={user_no})")
            return None
    except (KeyError, ValueError) as e:
        logger.warning(f"⚠️ 캐시 만료 시간 확인 실패: {str(e)}")
        del _temperature_threshold_cache[user_no]
        _save_cache_to_file(_temperature_threshold_cache)
        return None
    
    # 유효한 임계값 반환 (복사본 반환)
    return cache_data.copy()


def check_and_cleanup_expired_cache():
    """
    만료된 캐시를 체크하고 삭제하는 함수 (사용자별 분리)
    백그라운드 스케줄러에서 주기적으로 호출
    """
    global _temperature_threshold_cache
    
    # 메모리에 캐시가 없으면 파일에서 로드 시도
    if not _temperature_threshold_cache:
        _temperature_threshold_cache = _load_cache_from_file()
        if not _temperature_threshold_cache:
            return  # 캐시가 없으면 종료
    
    # 만료된 사용자 캐시 찾기
    expired_users = []
    for user_no, cache_data in list(_temperature_threshold_cache.items()):
        try:
            expires_at = datetime.fromisoformat(cache_data["expires_at"])
            if datetime.now() > expires_at:
                expired_users.append(user_no)
        except (KeyError, ValueError):
            expired_users.append(user_no)
    
    # 만료된 사용자 캐시 삭제
    if expired_users:
        for user_no in expired_users:
            del _temperature_threshold_cache[user_no]
        _save_cache_to_file(_temperature_threshold_cache)
        logger.info(f"⏰ 백그라운드에서 만료된 온도 임계값 캐시 삭제 완료: {len(expired_users)}명")


def clear_temperature_threshold(user_no: Optional[int] = None):
    """
    온도 임계값 캐시 삭제 (메모리 + 파일, 사용자별 분리)
    
    Args:
        user_no: 사용자 번호 (선택사항, None이면 전체 삭제)
    """
    global _temperature_threshold_cache
    
    if user_no is None:
        # 전체 삭제
        _temperature_threshold_cache = {}
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        logger.info("🗑️ 온도 임계값 캐시 전체 삭제 완료")
    else:
        # 특정 사용자만 삭제
        if user_no in _temperature_threshold_cache:
            del _temperature_threshold_cache[user_no]
            _save_cache_to_file(_temperature_threshold_cache)
            logger.info(f"🗑️ 온도 임계값 캐시 삭제 완료 (user_no={user_no})")
        else:
            logger.info(f"ℹ️ 삭제할 캐시가 없습니다. (user_no={user_no})")

