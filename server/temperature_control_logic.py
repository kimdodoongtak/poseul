"""
온도 조절 로직 모듈

주요 기능:
1. 사용자 특성(나이, BMI, 성별)에 따른 쾌적 온도 범위 계산
2. 계산된 온도 범위를 DB의 room_threshold 테이블에 저장
3. 에어컨 자동 온도 조절
4. 사용자가 수동으로 설정한 임계값 캐시 우선 사용 (12시간 유효)
"""

from sqlalchemy import text
from datetime import datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# temperature_threshold_cache 모듈 import (순환 참조 방지를 위해 함수 내부에서 import)

# 마지막 조절 시간 추적
last_adjustment_time = None


def calculate_comfortable_temperature_range(
    age: int,
    bmi: float,
    gender: str
) -> Tuple[float, float]:
    """
    사용자 특성에 따른 쾌적 온도 범위 계산
    
    기준:
    - 기본: 20-70세 남자, BMI 정상일 때 19도 이상, 21도 이하
    - 성별: 남자 +0도, 여자 +0.5도
    - 나이: 20-69세 +0도, 70-80세 +0.5도, 80세 이상 +2도
    - BMI: 저체중 +1도, 정상체중 +0도, 과체중 +0.5도, 비만 +1도
    
    Args:
        age: 나이
        bmi: 체질량지수
        gender: 성별 ('M' 또는 'F', 또는 'MALE'/'FEMALE', 또는 0/1)
    
    Returns:
        (min_temp, max_temp): 쾌적 온도 범위 (최소 온도, 최대 온도)
    """
    # 기본 온도 범위 (20-70세 남자, BMI 정상 기준)
    base_min_temp = 19.0
    base_max_temp = 21.0
    
    # 온도 조정값 초기화
    temp_adjustment = 0.0
    
    # 1. 성별 기준 조정
    # 성별 정규화 (M/MALE/1 -> 'M', F/FEMALE/0 -> 'F')
    if isinstance(gender, str):
        gender_upper = gender.upper()
        if gender_upper in ['M', 'MALE', '1']:
            gender_value = 'M'
        elif gender_upper in ['F', 'FEMALE', '0']:
            gender_value = 'F'
        else:
            gender_value = 'M'  # 기본값
    elif isinstance(gender, (int, float)):
        gender_value = 'M' if gender == 1 else 'F'
    else:
        gender_value = 'M'  # 기본값
    
    if gender_value == 'F':
        temp_adjustment += 0.5  # 여자 +0.5도
    
    # 2. 나이 기준 조정
    if age >= 80:
        temp_adjustment += 2.0  # 80세 이상 +2도
    elif age >= 70:
        temp_adjustment += 0.5  # 70-80세 +0.5도
    # 20-69세는 +0도 (조정 없음)
    
    # 3. BMI 기준 조정
    # BMI 분류: 저체중(<18.5), 정상(18.5-23), 과체중(23-25), 비만(>=25)
    if bmi < 18.5:
        temp_adjustment += 1.0  # 저체중 +1도
    elif 18.5 <= bmi < 23.0:
        temp_adjustment += 0.0  # 정상체중 +0도
    elif 23.0 <= bmi < 25.0:
        temp_adjustment += 0.5  # 과체중 +0.5도
    else:  # bmi >= 25.0
        temp_adjustment += 1.0  # 비만 +1도
    
    # 최종 온도 범위 계산
    min_temp = base_min_temp + temp_adjustment
    max_temp = base_max_temp + temp_adjustment
    
    logger.info(
        f"🌡️ 쾌적 온도 범위 계산: "
        f"나이={age}세, BMI={bmi:.1f}, 성별={gender_value} → "
        f"조정값={temp_adjustment}°C → "
        f"범위: {min_temp}~{max_temp}°C"
    )
    
    return min_temp, max_temp


def save_temperature_range_to_db(
    engine,
    age: int,
    bmi: float,
    gender: str,
    min_temp: float,
    max_temp: float,
    force_update: bool = False,
    user_no: Optional[int] = None
) -> bool:
    """
    계산된 온도 범위를 DB의 room_threshold 테이블에 저장
    (처음 한번만 저장, 이미 있으면 업데이트하지 않음)
    
    Args:
        engine: SQLAlchemy 엔진
        age: 나이
        bmi: 체질량지수
        gender: 성별
        min_temp: 최소 온도
        max_temp: 최대 온도
        force_update: True면 기존 값이 있어도 강제 업데이트 (기본값: False)
    
    Returns:
        저장 성공 여부
    """
    try:
        with engine.connect() as conn:
            # room_threshold 테이블 존재 여부 확인
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'room_threshold'
            """)
            table_exists = conn.execute(table_check).fetchone().count > 0
            
            if not table_exists:
                # 테이블이 없으면 생성 (min_temp, max_temp, user_no 포함)
                create_table = text("""
                    CREATE TABLE IF NOT EXISTS room_threshold (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        min_temp DECIMAL(4,1) NOT NULL,
                        max_temp DECIMAL(4,1) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        user_no INT DEFAULT NULL
                    )
                """)
                conn.execute(create_table)
                conn.commit()
                logger.info("✅ room_threshold 테이블 생성 완료 (min_temp, max_temp, user_no 포함)")
            else:
                # user_no 컬럼이 없으면 추가
                try:
                    column_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'room_threshold'
                        AND COLUMN_NAME = 'user_no'
                    """)
                    has_user_no = conn.execute(column_check).fetchone() is not None
                    if not has_user_no:
                        alter_query = text("ALTER TABLE room_threshold ADD COLUMN user_no INT DEFAULT NULL")
                        conn.execute(alter_query)
                        conn.commit()
                        logger.info("✅ room_threshold 테이블에 user_no 컬럼 추가 완료")
                except Exception as e:
                    logger.warning(f"⚠️ user_no 컬럼 확인/추가 실패: {str(e)}")
            
            # 기존 레코드 확인 (user_no 필터링)
            user_filter = ""
            query_params = {}
            if user_no is not None:
                user_filter = "WHERE (user_no = :user_no OR user_no IS NULL)"
                query_params['user_no'] = user_no
            
            check_existing = text(f"SELECT COUNT(*) as count FROM room_threshold {user_filter}")
            if query_params:
                existing_count = conn.execute(check_existing, query_params).fetchone().count
            else:
                existing_count = conn.execute(check_existing).fetchone().count
            
            if existing_count > 0:
                # 이미 설정되어 있으면
                if force_update:
                    # 강제 업데이트 모드면 업데이트 (user_no 필터링)
                    update_query = text(f"""
                        UPDATE room_threshold 
                        SET min_temp = :min_temp,
                            max_temp = :max_temp,
                            updated_at = NOW()
                        {user_filter.replace('WHERE', 'WHERE') if user_filter else 'WHERE 1=1'}
                        LIMIT 1
                    """)
                    update_params = {
                        'min_temp': min_temp,
                        'max_temp': max_temp
                    }
                    update_params.update(query_params)
                    conn.execute(update_query, update_params)
                    logger.info(f"✅ room_threshold 강제 업데이트: {min_temp}~{max_temp}°C, user_no={user_no}")
                    conn.commit()
                    return True
                else:
                    # 강제 업데이트가 아니면 기존 값 유지 (처음 한번만 적용)
                    existing_query = text(f"SELECT min_temp, max_temp FROM room_threshold {user_filter} LIMIT 1")
                    if query_params:
                        existing_result = conn.execute(existing_query, query_params).fetchone()
                    else:
                        existing_result = conn.execute(existing_query).fetchone()
                    logger.info(
                        f"ℹ️ room_threshold가 이미 설정되어 있습니다. "
                        f"기존 값 유지: {existing_result.min_temp}~{existing_result.max_temp}°C "
                        f"(새로 계산된 값: {min_temp}~{max_temp}°C는 무시됨), user_no={user_no}"
                    )
                    return True
            else:
                # 새 레코드 삽입 (처음 한번만, min_temp, max_temp, user_no 포함)
                insert_query = text("""
                    INSERT INTO room_threshold 
                    (min_temp, max_temp, user_no)
                    VALUES 
                    (:min_temp, :max_temp, :user_no)
                """)
                conn.execute(insert_query, {
                    'min_temp': min_temp,
                    'max_temp': max_temp,
                    'user_no': user_no
                })
                logger.info(f"✅ room_threshold 처음 저장: {min_temp}~{max_temp}°C, user_no={user_no}")
                conn.commit()
                return True
            
    except Exception as e:
        logger.error(f"❌ room_threshold 저장 실패: {e}")
        return False


def initialize_user_temperature_range(
    engine,
    age: int,
    bmi: float,
    gender: str,
    air_conditioner_available: bool = False,
    set_temperature_func = None,
    force_update: bool = False,
    user_no: Optional[int] = None
) -> Tuple[bool, float, float]:
    """
    사용자 특성에 따라 쾌적 온도 범위를 계산하고 DB에 저장
    (처음 한번만 적용, 이미 설정되어 있으면 기존 값 유지)
    
    Args:
        engine: SQLAlchemy 엔진
        age: 나이
        bmi: 체질량지수
        gender: 성별
        air_conditioner_available: 에어컨 모듈 사용 가능 여부
        set_temperature_func: 에어컨 온도 설정 함수 (선택사항)
        force_update: True면 기존 값이 있어도 강제 업데이트 (기본값: False)
    
    Returns:
        (성공 여부, min_temp, max_temp) - 실제 저장된 온도 범위
    """
    try:
        # 먼저 기존 값이 있는지 확인 (user_no 필터링)
        existing_range = get_temperature_range_from_db(engine, user_no)
        
        if existing_range is not None and not force_update:
            # 이미 설정되어 있고 강제 업데이트가 아니면 기존 값 반환
            min_temp, max_temp = existing_range
            logger.info(
                f"ℹ️ 온도 범위가 이미 설정되어 있습니다. "
                f"기존 값 사용: {min_temp}~{max_temp}°C "
                f"(처음 한번만 적용 정책)"
            )
            return True, min_temp, max_temp
        
        # 쾌적 온도 범위 계산
        min_temp, max_temp = calculate_comfortable_temperature_range(
            age=age,
            bmi=bmi,
            gender=gender
        )
        
        # DB에 저장 (처음 한번만 또는 강제 업데이트)
        success = save_temperature_range_to_db(
            engine=engine,
            age=age,
            bmi=bmi,
            gender=gender,
            min_temp=min_temp,
            max_temp=max_temp,
            force_update=force_update,
            user_no=user_no
        )
        
        if not success:
            return False, min_temp, max_temp
        
        # 에어컨이 사용 가능하고 설정 함수가 제공되면 초기 온도 설정
        # (처음 저장할 때만 에어컨 설정)
        if success and (existing_range is None or force_update):
            if air_conditioner_available and set_temperature_func:
                try:
                    # 목표 온도는 범위의 중간값
                    target_temp = (min_temp + max_temp) / 2.0
                    set_temperature_func(target_temp=target_temp, unit='C')
                    logger.info(f"✅ 에어컨 초기 온도 설정: {target_temp}°C")
                except Exception as e:
                    logger.warning(f"⚠️ 에어컨 초기 온도 설정 실패: {e}")
        
        return True, min_temp, max_temp
        
    except Exception as e:
        logger.error(f"❌ 초기 온도 범위 설정 실패: {e}")
        return False, 0.0, 0.0


def get_temperature_range_from_db(engine, user_no: Optional[int] = None) -> Optional[Tuple[float, float]]:
    """
    온도 범위 가져오기 (캐시 우선, DB 차선)
    
    우선순위:
    1. 사용자가 수동으로 설정한 임계값 캐시 (12시간 유효) - temperature_threshold_cache
    2. DB의 room_threshold 테이블에서 가져오기
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        (min_temp, max_temp) 또는 None
    """
    try:
        # 1. 먼저 캐시에서 확인 (사용자가 수동으로 설정한 임계값, user_no별 분리)
        try:
            from temperature_threshold_cache import get_temperature_threshold
            cached_threshold = get_temperature_threshold(user_no)
            
            if cached_threshold is not None:
                min_temp = cached_threshold.get("min_temp")
                max_temp = cached_threshold.get("max_temp")
                target_temp = cached_threshold.get("target_temperature")
                
                if min_temp is not None and max_temp is not None:
                    logger.info("=" * 60)
                    logger.info(f"🎯 [자동 조절] 수동 조절로 설정된 캐시 임계값 사용 중! (user_no={user_no})")
                    logger.info(f"   임계값 범위: {min_temp}~{max_temp}°C")
                    logger.info(f"   목표 온도: {target_temp}°C")
                    logger.info(f"   만료 시간: {cached_threshold.get('expires_at')}")
                    logger.info(f"   ✅ 이 범위로 에어컨 자동 조절이 진행됩니다!")
                    logger.info("=" * 60)
                    return float(min_temp), float(max_temp)
                else:
                    logger.debug(f"ℹ️ 캐시에 임계값이 있지만 min_temp 또는 max_temp가 없습니다. (user_no={user_no})")
        except ImportError as e:
            logger.warning(f"⚠️ temperature_threshold_cache 모듈 import 실패: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 캐시 조회 중 오류 발생 (DB에서 가져오기로 전환): {e}")
        
        # 2. 캐시가 없거나 만료되었으면 DB에서 가져오기
        logger.debug("ℹ️ 캐시된 임계값이 없어 DB에서 가져옵니다.")
        with engine.connect() as conn:
            # 컬럼 확인하여 최신 데이터 가져오기
            try:
                columns_check = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'room_threshold'
                """)
                columns = [row.COLUMN_NAME for row in conn.execute(columns_check).fetchall()]
                
                # 정렬 컬럼 결정 (no 컬럼 우선 사용)
                order_by = ""
                if 'no' in columns:
                    order_by = "ORDER BY no DESC"
                elif 'id' in columns:
                    order_by = "ORDER BY id DESC"
                elif 'created_at' in columns:
                    order_by = "ORDER BY created_at DESC"
                else:
                    logger.debug("ℹ️ room_threshold 테이블에 정렬 컬럼을 찾을 수 없습니다. 첫 번째 행을 사용합니다.")
                
                # user_no 필터링 추가
                user_filter = ""
                query_params = {}
                if user_no is not None:
                    user_filter = "WHERE (user_no = :user_no OR user_no IS NULL)"
                    query_params['user_no'] = user_no
                
                query = text(f"SELECT min_temp, max_temp FROM room_threshold {user_filter} {order_by} LIMIT 1")
                if query_params:
                    result = conn.execute(query, query_params).fetchone()
                else:
                    result = conn.execute(query).fetchone()
                
                if result and result.min_temp is not None and result.max_temp is not None:
                    min_temp = float(result.min_temp)
                    max_temp = float(result.max_temp)
                    logger.info("=" * 60)
                    logger.info(f"📋 [자동 조절] DB에서 기본 온도 범위 사용")
                    logger.info(f"   임계값 범위: {min_temp}~{max_temp}°C")
                    logger.info(f"   (캐시된 수동 조절 임계값이 없거나 만료됨)")
                    logger.info("=" * 60)
                    return min_temp, max_temp
                else:
                    logger.warning("⚠️ room_threshold 테이블에 온도 범위가 없습니다.")
                    return None
            except Exception as e:
                logger.error(f"❌ room_threshold 테이블 조회 중 오류: {e}")
                return None
                
    except Exception as e:
        logger.error(f"❌ 온도 범위 조회 실패: {e}")
        return None

