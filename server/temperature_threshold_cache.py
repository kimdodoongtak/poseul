"""
에어컨 온도 임계값 캐시 관리 모듈
12시간 TTL을 가진 JSON 파일 기반 캐시로 온도 임계값을 저장
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import json
import os

logger = logging.getLogger(__name__)

# 캐시 파일 경로
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'temperature_threshold.json')

# 캐시 디렉토리가 없으면 생성
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    logger.info(f"✅ 캐시 디렉토리 생성: {CACHE_DIR}")

# 에어컨 온도 임계값 캐시 (12시간 TTL)
# 구조: { "min_temp": float, "max_temp": float, "target_temperature": float, "created_at": str, "expires_at": str }
_temperature_threshold_cache: Optional[Dict[str, Any]] = None

def _load_cache_from_file() -> Optional[Dict[str, Any]]:
    """파일에서 캐시 로드"""
    global _temperature_threshold_cache
    
    if not os.path.exists(CACHE_FILE):
        return None
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            logger.info(f"✅ 캐시 파일에서 로드: {CACHE_FILE}")
            return cache_data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"⚠️ 캐시 파일 로드 실패: {str(e)}")
        return None

def _save_cache_to_file(cache_data: Dict[str, Any]) -> bool:
    """캐시를 파일에 저장"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ 캐시 파일에 저장: {CACHE_FILE}")
            return True
    except IOError as e:
        logger.error(f"❌ 캐시 파일 저장 실패: {str(e)}")
        return False

# 서버 시작 시 파일에서 캐시 로드
_temperature_threshold_cache = _load_cache_from_file()
if _temperature_threshold_cache:
    # 만료 시간 확인
    expires_at = datetime.fromisoformat(_temperature_threshold_cache["expires_at"])
    if datetime.now() > expires_at:
        # 만료된 경우 삭제
        _temperature_threshold_cache = None
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            logger.info("⏰ 만료된 캐시 파일 삭제")
    else:
        logger.info(f"✅ 서버 시작 시 캐시 로드 완료: {_temperature_threshold_cache['target_temperature']}°C")


def save_temperature_threshold(target_temperature: float) -> Dict[str, Any]:
    """
    온도 임계값을 캐시에 저장 (12시간 유효)
    메모리와 JSON 파일 모두에 저장
    
    Args:
        target_temperature: 사용자가 설정한 온도 (예: 24도)
    
    Returns:
        저장된 임계값 정보
    """
    global _temperature_threshold_cache
    
    # 중앙값을 기준으로 ±1도 범위 설정
    min_temp = target_temperature - 1.0
    max_temp = target_temperature + 1.0
    
    # 12시간 후 만료
    expires_at = datetime.now() + timedelta(hours=12)
    
    # 캐시에 저장
    _temperature_threshold_cache = {
        "min_temp": min_temp,
        "max_temp": max_temp,
        "target_temperature": target_temperature,
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    # 파일에 저장
    _save_cache_to_file(_temperature_threshold_cache)
    
    logger.info("=" * 60)
    logger.info(f"🎯 [수동 조절] 온도 임계값 캐시 저장 완료!")
    logger.info(f"   목표 온도: {target_temperature}°C")
    logger.info(f"   임계값 범위: {min_temp}~{max_temp}°C")
    logger.info(f"   만료 시간: {expires_at.isoformat()}")
    logger.info(f"   ⏰ 이제 자동 조절 코드에서 이 범위를 12시간 동안 사용합니다!")
    logger.info("=" * 60)
    
    return _temperature_threshold_cache.copy()


def get_temperature_threshold() -> Optional[Dict[str, Any]]:
    """
    현재 저장된 온도 임계값 조회 (만료되지 않은 경우만)
    메모리에 없으면 파일에서 로드 시도
    
    Returns:
        임계값 정보 (만료되었거나 없으면 None)
    """
    global _temperature_threshold_cache
    
    # 메모리에 캐시가 없으면 파일에서 로드 시도
    if _temperature_threshold_cache is None:
        _temperature_threshold_cache = _load_cache_from_file()
        if _temperature_threshold_cache is None:
            return None
    
    # 만료 시간 확인
    expires_at = datetime.fromisoformat(_temperature_threshold_cache["expires_at"])
    if datetime.now() > expires_at:
        # 만료된 경우 캐시 삭제 (메모리 + 파일)
        _temperature_threshold_cache = None
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        logger.info("⏰ 저장된 온도 임계값이 만료되어 삭제되었습니다.")
        return None
    
    # 유효한 임계값 반환 (복사본 반환)
    return _temperature_threshold_cache.copy()


def check_and_cleanup_expired_cache():
    """
    만료된 캐시를 체크하고 삭제하는 함수
    백그라운드 스케줄러에서 주기적으로 호출
    """
    global _temperature_threshold_cache
    
    # 메모리에 캐시가 없으면 파일에서 로드 시도
    if _temperature_threshold_cache is None:
        _temperature_threshold_cache = _load_cache_from_file()
        if _temperature_threshold_cache is None:
            return  # 캐시가 없으면 종료
    
    # 만료 시간 확인
    try:
        expires_at = datetime.fromisoformat(_temperature_threshold_cache["expires_at"])
        if datetime.now() > expires_at:
            # 만료된 경우 캐시 삭제 (메모리 + 파일)
            _temperature_threshold_cache = None
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            logger.info("⏰ 백그라운드에서 만료된 온도 임계값 캐시 삭제 완료")
    except (KeyError, ValueError) as e:
        logger.warning(f"⚠️ 캐시 만료 시간 확인 실패: {str(e)}")


def clear_temperature_threshold():
    """온도 임계값 캐시 삭제 (메모리 + 파일)"""
    global _temperature_threshold_cache
    _temperature_threshold_cache = None
    
    # 파일도 삭제
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        logger.info(f"🗑️ 캐시 파일 삭제: {CACHE_FILE}")
    
    logger.info("🗑️ 온도 임계값 캐시 삭제 완료")

