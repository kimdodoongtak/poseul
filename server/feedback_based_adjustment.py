"""
피드백 기반 온도 범위 조절 모듈

주요 기능:
1. 매일 아침 피드백을 받아서 마지막 예측값과 비교
2. 비교 결과에 따라 실내 온도 범위(room_threshold)와 피부온도 범위(new_skinthreshold) 조절
3. 일주일간 반복하여 임계값 조정
"""

from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def get_last_prediction(engine) -> Optional[Tuple[float, str]]:
    """
    피드백 받기 전 마지막 예측값 가져오기
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        (predicted_skin_temp, classification) 또는 None
        classification: 'C' (춥다), 'H' (덥다), 'G' (쾌적)
    """
    try:
        with engine.connect() as conn:
            # predicted_results 테이블에서 최근 예측값 가져오기
            query = text("""
                SELECT predicted_skin_temp 
                FROM predicted_results 
                WHERE predicted_skin_temp IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
            """)
            result = conn.execute(query).fetchone()
            
            if result and result.predicted_skin_temp is not None:
                predicted_temp = float(result.predicted_skin_temp)
                
                # 피부온도 분류 기준 가져오기 (new_skinthreshold 테이블)
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'new_skinthreshold'
                """)
                has_new_table = conn.execute(table_check).fetchone().count > 0
                
                min_skin = 34.6  # 기본값
                max_skin = 35.6  # 기본값
                
                if has_new_table:
                    threshold_query = text("""
                        SELECT min_skinthreshold, max_skinthreshold 
                        FROM new_skinthreshold 
                        LIMIT 1
                    """)
                    threshold_result = conn.execute(threshold_query).fetchone()
                    
                    if threshold_result and threshold_result.min_skinthreshold is not None and threshold_result.max_skinthreshold is not None:
                        min_skin = float(threshold_result.min_skinthreshold)
                        max_skin = float(threshold_result.max_skinthreshold)
                
                # 분류
                if predicted_temp < min_skin:
                    classification = 'C'  # 춥다
                elif predicted_temp > max_skin:
                    classification = 'H'  # 덥다
                else:
                    classification = 'G'  # 쾌적
                
                return predicted_temp, classification
            
            return None
    except Exception as e:
        logger.error(f"❌ 마지막 예측값 조회 실패: {e}")
        return None


def get_current_thresholds(engine) -> Optional[Tuple[float, float, float, float]]:
    """
    현재 임계값 가져오기
    - room_threshold 테이블: 실내 온도 범위
    - new_skinthreshold 테이블: 피부온도 범위
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        (room_min_temp, room_max_temp, skin_min_temp, skin_max_temp) 또는 None
    """
    try:
        with engine.connect() as conn:
            # 1. room_threshold 테이블에서 실내 온도 범위 가져오기
            room_query = text("""
                SELECT min_temp, max_temp 
                FROM room_threshold 
                LIMIT 1
            """)
            room_result = conn.execute(room_query).fetchone()
            
            if not room_result or not room_result.min_temp or not room_result.max_temp:
                return None
            
            room_min = float(room_result.min_temp)
            room_max = float(room_result.max_temp)
            
            # 2. new_skinthreshold 테이블 확인
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'new_skinthreshold'
            """)
            has_new_table = conn.execute(table_check).fetchone().count > 0
            
            skin_min = 34.6  # 기본값
            skin_max = 35.6  # 기본값
            
            if has_new_table:
                # new_skinthreshold 테이블에서 피부온도 범위 가져오기
                skin_query = text("""
                    SELECT min_skinthreshold, max_skinthreshold 
                    FROM new_skinthreshold 
                    LIMIT 1
                """)
                skin_result = conn.execute(skin_query).fetchone()
                
                if skin_result and skin_result.min_skinthreshold is not None and skin_result.max_skinthreshold is not None:
                    skin_min = float(skin_result.min_skinthreshold)
                    skin_max = float(skin_result.max_skinthreshold)
            
            return room_min, room_max, skin_min, skin_max
    except Exception as e:
        logger.error(f"❌ 현재 임계값 조회 실패: {e}")
        return None


def calculate_threshold_adjustment(
    feedback: str,
    prediction: str
) -> Tuple[float, float]:
    """
    피드백과 예측값을 비교하여 임계값 조정량 계산
    
    Args:
        feedback: 피드백 ('C': 춥다, 'H': 덥다, 'G': 쾌적)
        prediction: 예측값 ('C': 춥다, 'H': 덥다, 'G': 쾌적)
    
    Returns:
        (room_adjustment, skin_adjustment): (실내온도 조정량, 피부온도 조정량)
    """
    # 같을 때: 외부온도만 조절
    if feedback == prediction:
        if feedback == 'H':  # 둘 다 덥다
            return -0.5, 0.0  # 외부온도 -0.5도, 피부온도 변화 없음
        elif feedback == 'C':  # 둘 다 춥다
            return 0.5, 0.0  # 외부온도 +0.5도, 피부온도 변화 없음
        else:  # 둘 다 쾌적
            return 0.0, 0.0  # 변화 없음
    
    # 다를 때: 피부온도 & 외부온도 모두 조절
    if feedback == 'C' and prediction == 'H':  # 피드백: 춥다, 예측: 덥다
        return 1.0, 1.0  # 외부온도 +1도, 피부온도 +1도
    elif feedback == 'C' and prediction == 'G':  # 피드백: 춥다, 예측: 쾌적
        return 0.5, 0.5  # 외부온도 +0.5도, 피부온도 +0.5도
    elif feedback == 'H' and prediction == 'C':  # 피드백: 덥다, 예측: 춥다
        return -1.0, -1.0  # 외부온도 -1도, 피부온도 -1도
    elif feedback == 'H' and prediction == 'G':  # 피드백: 덥다, 예측: 쾌적
        return -0.5, -0.5  # 외부온도 -0.5도, 피부온도 -0.5도
    elif feedback == 'G' and prediction == 'C':  # 피드백: 쾌적, 예측: 춥다
        return 0.0, -0.5  # 외부온도 변화 없음, 피부온도 -0.5도
    elif feedback == 'G' and prediction == 'H':  # 피드백: 쾌적, 예측: 덥다
        return 0.0, 0.5  # 외부온도 변화 없음, 피부온도 +0.5도
    
    return 0.0, 0.0  # 기본값: 변화 없음


def update_thresholds_in_db(
    engine,
    room_min_temp: float,
    room_max_temp: float,
    skin_min_temp: float,
    skin_max_temp: float
) -> bool:
    """
    조정된 임계값을 DB에 저장
    - room_threshold 테이블: 실내 온도 범위 저장
    - new_skinthreshold 테이블: 피부온도 범위 저장 (있으면)
    
    Args:
        engine: SQLAlchemy 엔진
        room_min_temp: 실내 최소 온도
        room_max_temp: 실내 최대 온도
        skin_min_temp: 피부 최소 온도
        skin_max_temp: 피부 최대 온도
    
    Returns:
        저장 성공 여부
    """
    try:
        with engine.connect() as conn:
            # 1. room_threshold 테이블 업데이트 (실내 온도 범위)
            update_room_query = text("""
                UPDATE room_threshold 
                SET min_temp = :room_min,
                    max_temp = :room_max,
                    updated_at = NOW()
                LIMIT 1
            """)
            conn.execute(update_room_query, {
                'room_min': room_min_temp,
                'room_max': room_max_temp
            })
            
            # 2. new_skinthreshold 테이블 확인 및 업데이트 (피부온도 범위)
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'new_skinthreshold'
            """)
            has_new_table = conn.execute(table_check).fetchone().count > 0
            
            if has_new_table:
                # new_skinthreshold 테이블이 있으면 레코드 확인
                count_query = text("SELECT COUNT(*) as count FROM new_skinthreshold")
                record_count = conn.execute(count_query).fetchone().count
                
                if record_count > 0:
                    # 레코드가 있으면 업데이트
                    update_skin_query = text("""
                        UPDATE new_skinthreshold 
                        SET min_skinthreshold = :skin_min,
                            max_skinthreshold = :skin_max,
                            updated_at = NOW()
                        LIMIT 1
                    """)
                    conn.execute(update_skin_query, {
                        'skin_min': skin_min_temp,
                        'skin_max': skin_max_temp
                    })
                else:
                    # 레코드가 없으면 기본값으로 삽입
                    insert_skin_query = text("""
                        INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, created_at, updated_at)
                        VALUES (:skin_min, :skin_max, NOW(), NOW())
                    """)
                    conn.execute(insert_skin_query, {
                        'skin_min': skin_min_temp,
                        'skin_max': skin_max_temp
                    })
                    logger.info(f"✅ new_skinthreshold 테이블에 기본값 삽입: {skin_min_temp}~{skin_max_temp}°C")
            else:
                # new_skinthreshold 테이블이 없으면 생성하고 기본값 삽입
                create_table_query = text("""
                    CREATE TABLE IF NOT EXISTS new_skinthreshold (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                        max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                conn.execute(create_table_query)
                
                insert_skin_query = text("""
                    INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, created_at, updated_at)
                    VALUES (:skin_min, :skin_max, NOW(), NOW())
                """)
                conn.execute(insert_skin_query, {
                    'skin_min': skin_min_temp,
                    'skin_max': skin_max_temp
                })
                logger.info(f"✅ new_skinthreshold 테이블 생성 및 기본값 삽입: {skin_min_temp}~{skin_max_temp}°C")
            
            conn.commit()
            
            logger.info(
                f"✅ 임계값 업데이트 완료: "
                f"실내온도={room_min_temp}~{room_max_temp}°C, "
                f"피부온도={skin_min_temp}~{skin_max_temp}°C"
            )
            return True
    except Exception as e:
        logger.error(f"❌ 임계값 업데이트 실패: {e}")
        return False


def get_feedback_count(engine) -> int:
    """
    현재 피드백 기간의 피드백 횟수 가져오기
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        피드백 횟수 (0부터 시작)
    """
    try:
        with engine.connect() as conn:
            # feedback_reset_date 테이블 확인 (재갱신 시점 저장용)
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'feedback_reset_date'
            """)
            has_reset_table = conn.execute(table_check).fetchone().count > 0
            
            reset_date = None
            if has_reset_table:
                reset_query = text("SELECT reset_date FROM feedback_reset_date ORDER BY reset_date DESC LIMIT 1")
                reset_result = conn.execute(reset_query).fetchone()
                if reset_result and reset_result.reset_date:
                    reset_date = reset_result.reset_date
            
            # reset_date 이후의 피드백 개수 세기
            if reset_date:
                query = text("""
                    SELECT COUNT(*) as count
                    FROM temperature_feedback
                    WHERE created_at >= :reset_date
                """)
                result = conn.execute(query, {'reset_date': reset_date}).fetchone()
            else:
                # reset_date가 없으면 전체 피드백 개수
                query = text("""
                    SELECT COUNT(*) as count
                    FROM temperature_feedback
                """)
                result = conn.execute(query).fetchone()
            
            if result:
                return result.count or 0
            
            return 0
    except Exception as e:
        logger.warning(f"⚠️ 피드백 횟수 조회 실패: {e}")
        return 0


def reset_feedback_period(engine) -> Tuple[bool, Optional[str]]:
    """
    피드백 기반 조정 기간을 재시작 (피드백 횟수 리셋)
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        (성공 여부, 메시지)
    """
    try:
        with engine.connect() as conn:
            # feedback_reset_date 테이블 생성 또는 확인
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'feedback_reset_date'
            """)
            has_table = conn.execute(table_check).fetchone().count > 0
            
            if not has_table:
                create_table = text("""
                    CREATE TABLE IF NOT EXISTS feedback_reset_date (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        reset_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute(create_table)
                logger.info("✅ feedback_reset_date 테이블 생성 완료")
            
            # 현재 날짜로 재갱신 날짜 저장 (이후 피드백부터 카운트)
            insert_query = text("""
                INSERT INTO feedback_reset_date (reset_date, created_at)
                VALUES (NOW(), NOW())
            """)
            conn.execute(insert_query)
            conn.commit()
            
            logger.info("✅ 피드백 기반 조정 기간 재시작: 피드백 횟수 리셋")
            return True, "피드백 기반 조정 기간이 재시작되었습니다. 다시 7번의 피드백을 받습니다."
    except Exception as e:
        logger.error(f"❌ 피드백 기간 재시작 실패: {e}")
        return False, f"피드백 기간 재시작 실패: {str(e)}"


def is_within_feedback_limit(engine) -> bool:
    """
    피드백 횟수가 7번 미만인지 확인
    
    Args:
        engine: SQLAlchemy 엔진
    
    Returns:
        True: 7번 미만 (계속 가능), False: 7번 이상 (종료)
    """
    try:
        feedback_count = get_feedback_count(engine)
        return feedback_count < 7
    except Exception as e:
        logger.warning(f"⚠️ 피드백 횟수 확인 실패: {e}")
        return True  # 에러 시 계속 가능으로 간주


def process_daily_feedback(engine, feedback: str) -> Tuple[bool, Optional[str]]:
    """
    피드백 처리 및 임계값 조정 (7번까지)
    
    Args:
        engine: SQLAlchemy 엔진
        feedback: 피드백 ('C': 춥다, 'H': 덥다, 'G': 쾌적)
    
    Returns:
        (성공 여부, 메시지)
    """
    try:
        # 피드백 유효성 검사
        if feedback not in ['C', 'H', 'G']:
            return False, f"유효하지 않은 피드백: {feedback} (C, H, G 중 하나여야 함)"
        
        # 피드백 횟수 제한 확인 (7번까지)
        feedback_count = get_feedback_count(engine)
        if feedback_count >= 7:
            logger.info(f"ℹ️ 피드백 기반 조정 기간이 지났습니다. (피드백 {feedback_count}번 완료)")
            return False, f"피드백 기반 조정은 7번까지만 가능합니다. (현재: {feedback_count}번)"
        
        logger.info(f"📝 피드백 수신: {feedback} ({'춥다' if feedback == 'C' else '덥다' if feedback == 'H' else '쾌적'})")
        
        # 2. 마지막 예측값 가져오기
        prediction_result = get_last_prediction(engine)
        if not prediction_result:
            return False, "마지막 예측값이 없습니다."
        
        predicted_temp, prediction = prediction_result
        logger.info(f"🔮 마지막 예측값: {predicted_temp}°C ({'춥다' if prediction == 'C' else '덥다' if prediction == 'H' else '쾌적'})")
        
        # 3. 현재 임계값 가져오기
        current_thresholds = get_current_thresholds(engine)
        if not current_thresholds:
            return False, "현재 실내온도 임계값을 가져올 수 없습니다."
        
        room_min, room_max, skin_min, skin_max = current_thresholds
        
        # new_skinthreshold 테이블에 값이 없으면 기본값(34.6, 35.6)으로 저장
        with engine.connect() as conn:
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'new_skinthreshold'
            """)
            has_table = conn.execute(table_check).fetchone().count > 0
            
            if not has_table:
                # 테이블이 없으면 생성
                create_table_query = text("""
                    CREATE TABLE IF NOT EXISTS new_skinthreshold (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                        max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                conn.execute(create_table_query)
                logger.info("✅ new_skinthreshold 테이블 생성 완료")
            
            # 레코드 확인
            count_query = text("SELECT COUNT(*) as count FROM new_skinthreshold")
            record_count = conn.execute(count_query).fetchone().count
            
            if record_count == 0:
                # 레코드가 없으면 기본값으로 저장
                insert_query = text("""
                    INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, created_at, updated_at)
                    VALUES (34.6, 35.6, NOW(), NOW())
                """)
                conn.execute(insert_query)
                conn.commit()
                logger.info("✅ new_skinthreshold 테이블에 기본값 저장: 34.6~35.6°C")
                # 기본값으로 재설정
                skin_min = 34.6
                skin_max = 35.6
        
        logger.info(
            f"🌡️ 현재 임계값: "
            f"실내온도={room_min}~{room_max}°C, "
            f"피부온도={skin_min}~{skin_max}°C"
        )
        
        # 4. 조정량 계산
        room_adjustment, skin_adjustment = calculate_threshold_adjustment(feedback, prediction)
        logger.info(
            f"📊 조정량 계산: "
            f"피드백={feedback}, 예측={prediction} → "
            f"실내온도 조정={room_adjustment}°C, 피부온도 조정={skin_adjustment}°C"
        )
        
        # 5. 새로운 임계값 계산
        new_room_min = room_min + room_adjustment
        new_room_max = room_max + room_adjustment
        new_skin_min = skin_min + skin_adjustment
        new_skin_max = skin_max + skin_adjustment
        
        # 6. DB에 저장
        success = update_thresholds_in_db(
            engine,
            new_room_min,
            new_room_max,
            new_skin_min,
            new_skin_max
        )
        
        if success:
            message = (
                f"✅ 임계값 조정 완료: "
                f"실내온도 {room_min}~{room_max}°C → {new_room_min}~{new_room_max}°C, "
                f"피부온도 {skin_min}~{skin_max}°C → {new_skin_min}~{skin_max}°C"
            )
            return True, message
        else:
            return False, "임계값 업데이트 실패"
        
    except Exception as e:
        logger.error(f"❌ 피드백 처리 실패: {e}")
        return False, f"피드백 처리 실패: {str(e)}"


def get_adjustment_history(engine, days: int = 7) -> list:
    """
    최근 N일간의 조정 이력 조회
    
    Args:
        engine: SQLAlchemy 엔진
        days: 조회할 일수 (기본값: 7)
    
    Returns:
        조정 이력 리스트
    """
    try:
        with engine.connect() as conn:
            # new_skinthreshold 테이블 존재 여부 확인
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'new_skinthreshold'
            """)
            has_new_table = conn.execute(table_check).fetchone().count > 0
            
            if has_new_table:
                # new_skinthreshold 테이블이 있으면 JOIN으로 조회
                query = text("""
                    SELECT 
                        r.min_temp, r.max_temp, 
                        s.min_skinthreshold, s.max_skinthreshold,
                        r.updated_at as room_updated_at,
                        s.updated_at as skin_updated_at
                    FROM room_threshold r
                    LEFT JOIN new_skinthreshold s ON 1=1
                    WHERE r.updated_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                       OR s.updated_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    ORDER BY GREATEST(COALESCE(r.updated_at, '1970-01-01'), COALESCE(s.updated_at, '1970-01-01')) DESC
                """)
            else:
                # new_skinthreshold 테이블이 없으면 room_threshold만 조회
                query = text("""
                    SELECT 
                        min_temp, max_temp, 
                        min_skinthreshold, max_skinthreshold,
                        updated_at
                    FROM room_threshold
                    WHERE updated_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                    ORDER BY updated_at DESC
                """)
            
            results = conn.execute(query, {'days': days}).fetchall()
            
            history = []
            for row in results:
                updated_at = None
                if hasattr(row, 'room_updated_at') and row.room_updated_at:
                    updated_at = row.room_updated_at.isoformat() if hasattr(row.room_updated_at, 'isoformat') else str(row.room_updated_at)
                elif hasattr(row, 'updated_at') and row.updated_at:
                    updated_at = row.updated_at.isoformat() if hasattr(row.updated_at, 'isoformat') else str(row.updated_at)
                
                history.append({
                    'room_min_temp': float(row.min_temp) if row.min_temp else None,
                    'room_max_temp': float(row.max_temp) if row.max_temp else None,
                    'skin_min_temp': float(row.min_skinthreshold) if row.min_skinthreshold else None,
                    'skin_max_temp': float(row.max_skinthreshold) if row.max_skinthreshold else None,
                    'updated_at': updated_at
                })
            
            return history
    except Exception as e:
        logger.error(f"❌ 조정 이력 조회 실패: {e}")
        return []

