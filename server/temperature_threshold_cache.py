"""
에어컨 온도 임계값 캐시 관리 모듈
12시간 TTL을 가진 메모리 캐시로 온도 임계값을 저장
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 에어컨 온도 임계값 캐시 (12시간 TTL)
# 구조: { "min_temp": float, "max_temp": float, "target_temperature": float, "created_at": str, "expires_at": str }
_temperature_threshold_cache: Optional[Dict[str, Any]] = None


def save_temperature_threshold(target_temperature: float) -> Dict[str, Any]:
    """
    온도 임계값을 캐시에 저장 (12시간 유효)
    
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
    
    logger.info(f"✅ 온도 임계값 캐시 저장: {min_temp}~{max_temp}°C (만료: {expires_at.isoformat()})")
    
    return _temperature_threshold_cache.copy()


def get_temperature_threshold() -> Optional[Dict[str, Any]]:
    """
    현재 저장된 온도 임계값 조회 (만료되지 않은 경우만)
    
    Returns:
        임계값 정보 (만료되었거나 없으면 None)
    """
    global _temperature_threshold_cache
    
    # 캐시가 없으면 None 반환
    if _temperature_threshold_cache is None:
        return None
    
    # 만료 시간 확인
    expires_at = datetime.fromisoformat(_temperature_threshold_cache["expires_at"])
    if datetime.now() > expires_at:
        # 만료된 경우 캐시 삭제
        _temperature_threshold_cache = None
        logger.info("⏰ 저장된 온도 임계값이 만료되어 삭제되었습니다.")
        return None
    
    # 유효한 임계값 반환 (복사본 반환)
    return _temperature_threshold_cache.copy()


def clear_temperature_threshold():
    """온도 임계값 캐시 삭제"""
    global _temperature_threshold_cache
    _temperature_threshold_cache = None
    logger.info("🗑️ 온도 임계값 캐시 삭제 완료")

