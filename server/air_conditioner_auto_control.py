"""
에어컨 자동 온도 조절 시스템 모듈

주요 기능:
1. 초기 세팅: room_threshold에서 min_temp, max_temp 가져와서 목표 온도(중간값) 설정
2. 자동 조절: 30분마다 최근 3개 피드백을 다수결로 판단하여 에어컨 조절
"""

from sqlalchemy import text
from datetime import datetime
import logging
from temperature_threshold_cache import get_temperature_threshold

logger = logging.getLogger(__name__)

# 마지막 조절 시간 추적
last_adjustment_time = None


def initialize_air_conditioner_settings(engine, air_conditioner_available: bool, get_air_conditioner_state_func, set_temperature_func):
    """
    초기 세팅: room_threshold에서 min_temp, max_temp 가져와서 목표 온도(중간값) 설정
    
    Args:
        engine: SQLAlchemy 엔진
        air_conditioner_available: 에어컨 모듈 사용 가능 여부
        get_air_conditioner_state_func: 에어컨 상태 조회 함수
        set_temperature_func: 에어컨 온도 설정 함수
    """
    try:
        with engine.connect() as conn:
            # room_threshold 테이블에서 min_temp, max_temp 가져오기
            try:
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if not table_exists:
                    logger.warning("⚠️ room_threshold 테이블이 존재하지 않습니다.")
                    return
                
                threshold_query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                threshold_result = conn.execute(threshold_query).fetchone()
                
                if threshold_result and threshold_result.min_temp is not None and threshold_result.max_temp is not None:
                    min_temp = float(threshold_result.min_temp)
                    max_temp = float(threshold_result.max_temp)
                    target_temp = (min_temp + max_temp) / 2.0  # 중간값
                    
                    logger.info(f"🌡️ 초기 세팅: 목표 온도={target_temp}°C (범위: {min_temp}~{max_temp}°C)")
                    
                    # 에어컨에 목표 온도 설정
                    if air_conditioner_available:
                        try:
                            set_temperature_func(target_temp=target_temp, unit='C')
                            logger.info(f"✅ 에어컨 목표 온도 설정 완료: {target_temp}°C")
                        except Exception as e:
                            logger.warning(f"⚠️ 에어컨 목표 온도 설정 실패: {e}")
                else:
                    logger.warning("⚠️ room_threshold 테이블에 min_temp, max_temp가 없습니다.")
            except Exception as e:
                logger.error(f"❌ 초기 세팅 실패: {e}")
    except Exception as e:
        logger.error(f"❌ 초기 세팅 중 오류: {e}")


def get_majority_feedback(feedbacks: list) -> str:
    """
    최근 3개 피드백을 다수결로 판단
    
    Args:
        feedbacks: 피드백 리스트 (예: ['H', 'H', 'G'])
    
    Returns:
        다수결 결과 ('H', 'C', 'G')
    """
    if not feedbacks:
        return 'G'  # 피드백이 없으면 쾌적으로 판단
    
    # 다수결 계산
    feedback_counts = {'H': 0, 'C': 0, 'G': 0}
    for feedback in feedbacks:
        if feedback in feedback_counts:
            feedback_counts[feedback] += 1
    
    # 가장 많은 피드백 찾기
    max_count = max(feedback_counts.values())
    majority_feedbacks = [k for k, v in feedback_counts.items() if v == max_count]
    
    # 모두 다른 경우 (1개씩) → 쾌적으로 안전하게 판단
    if len(majority_feedbacks) == 3:
        return 'G'
    
    # 다수결 결과 반환
    return majority_feedbacks[0]


def adjust_air_conditioner(
    engine,
    air_conditioner_available: bool,
    get_air_conditioner_state_func,
    set_temperature_func,
    cold_threshold: float = 34.5,
    hot_threshold: float = 35.6,
    update_threshold_callback=None
):
    """
    30분마다 predicted_results에서 최근 3개 predicted_skin_temp를 분류하여 다수결로 판단하고 조절
    
    Args:
        engine: SQLAlchemy 엔진
        air_conditioner_available: 에어컨 모듈 사용 가능 여부
        get_air_conditioner_state_func: 에어컨 상태 조회 함수
        set_temperature_func: 에어컨 온도 설정 함수
        cold_threshold: 추움 분류 기준 (기본값: 34.5)
        hot_threshold: 더움 분류 기준 (기본값: 35.6)
        update_threshold_callback: 전역 변수 갱신 콜백 함수 (cold_threshold, hot_threshold) -> None
    """
    global last_adjustment_time
    
    try:
        # 마지막 조절 이후 2분이 지났는지 확인 (테스트용: 2분으로 변경)
        now = datetime.now()
        if last_adjustment_time is not None:
            time_diff = (now - last_adjustment_time).total_seconds() / 60.0  # 분 단위
            if time_diff < 2:
                logger.info(f"⏰ 조절 대기 중... (마지막 조절 이후 {time_diff:.1f}분 경과, 2분 필요)")
                return
        
        logger.info("🔄 에어컨 자동 조절 시작...")
        
        with engine.connect() as conn:
            # new_skinthreshold 테이블에서 min_skinthreshold, max_skinthreshold 확인 및 전역 변수 갱신
            try:
                threshold_table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'new_skinthreshold'
                """)
                threshold_table_exists = conn.execute(threshold_table_check).fetchone().count > 0
                
                if threshold_table_exists:
                    # min_skinthreshold, max_skinthreshold 값 가져오기
                    skin_threshold_query = text("SELECT min_skinthreshold, max_skinthreshold FROM new_skinthreshold LIMIT 1")
                    skin_threshold_result = conn.execute(skin_threshold_query).fetchone()
                    
                    if skin_threshold_result and skin_threshold_result.min_skinthreshold is not None and skin_threshold_result.max_skinthreshold is not None:
                        db_cold_threshold = float(skin_threshold_result.min_skinthreshold)
                        db_hot_threshold = float(skin_threshold_result.max_skinthreshold)
                        
                        # DB 값과 현재 전역 변수 값이 다르면 갱신
                        if db_cold_threshold != cold_threshold or db_hot_threshold != hot_threshold:
                            logger.info(f"🔄 DB에서 피부온도 분류 기준 변경 감지: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C (기존: cold={cold_threshold}°C, hot={hot_threshold}°C)")
                            
                            # 콜백 함수를 통해 전역 변수 갱신
                            if update_threshold_callback:
                                update_threshold_callback(db_cold_threshold, db_hot_threshold)
                                logger.info(f"✅ 전역 변수 갱신 완료: COLD_THRESHOLD={db_cold_threshold}°C, HOT_THRESHOLD={db_hot_threshold}°C")
                            
                            # 현재 함수에서 사용할 값도 갱신
                            cold_threshold = db_cold_threshold
                            hot_threshold = db_hot_threshold
                        else:
                            logger.debug(f"ℹ️ DB 피부온도 분류 기준 변경 없음: cold={cold_threshold}°C, hot={hot_threshold}°C")
                    else:
                        # 테이블은 있지만 레코드가 없으면 기본값 사용 (34.6, 35.6)
                        db_cold_threshold = 34.6
                        db_hot_threshold = 35.6
                        logger.info(f"ℹ️ new_skinthreshold 테이블에 레코드가 없습니다. 기본값 사용: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                        # 기본값으로 전역 변수 갱신
                        if update_threshold_callback:
                            update_threshold_callback(db_cold_threshold, db_hot_threshold)
                        cold_threshold = db_cold_threshold
                        hot_threshold = db_hot_threshold
                else:
                    # new_skinthreshold 테이블이 없으면 기본값 사용 (34.6, 35.6)
                    db_cold_threshold = 34.6
                    db_hot_threshold = 35.6
                    logger.info(f"ℹ️ new_skinthreshold 테이블이 없습니다. 기본값 사용: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                    # 기본값으로 전역 변수 갱신
                    if update_threshold_callback:
                        update_threshold_callback(db_cold_threshold, db_hot_threshold)
                    cold_threshold = db_cold_threshold
                    hot_threshold = db_hot_threshold
            except Exception as e:
                logger.warning(f"⚠️ 피부온도 분류 기준 확인 실패 (계속 진행): {e}")
            
            # predicted_results 테이블에서 최근 3개 predicted_skin_temp 가져오기
            try:
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'predicted_results'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if not table_exists:
                    logger.warning("⚠️ predicted_results 테이블이 존재하지 않습니다.")
                    return
                
                # 최근 3개 predicted_skin_temp 가져오기
                # 테이블에 정렬 컬럼이 없으므로 단순 LIMIT 사용 (삽입 순서대로 반환될 가능성)
                try:
                    # 먼저 전체 개수 확인
                    count_query = text("""
                        SELECT COUNT(*) as cnt 
                        FROM predicted_results 
                        WHERE predicted_skin_temp IS NOT NULL 
                          AND predicted_skin_temp > 0
                    """)
                    total_count = conn.execute(count_query).fetchone().cnt
                    logger.info(f"📊 유효한 predicted_skin_temp 개수: {total_count}개")
                    
                    if total_count < 3:
                        logger.info(f"⏳ predicted_skin_temp가 {total_count}개만 있습니다. 3개가 필요합니다.")
                        return
                    
                    # 단순 쿼리로 3개 가져오기 (정렬 컬럼이 없으므로 삽입 순서대로 반환될 가능성)
                    temp_query = text("""
                        SELECT predicted_skin_temp 
                        FROM predicted_results 
                        WHERE predicted_skin_temp IS NOT NULL 
                          AND predicted_skin_temp > 0
                        LIMIT 3
                    """)
                    temp_results = conn.execute(temp_query).fetchall()
                        
                except Exception as e:
                    logger.error(f"❌ 쿼리 실행 실패: {e}")
                    return
                
                if len(temp_results) < 3:
                    logger.info(f"⏳ predicted_skin_temp가 {len(temp_results)}개만 있습니다. 3개가 필요합니다.")
                    return
                
                # predicted_skin_temp 값을 분류 기준에 따라 분류
                feedbacks = []
                for row in temp_results:
                    predicted_temp = float(row.predicted_skin_temp)
                    if predicted_temp < cold_threshold:
                        classification = 'C'  # 추움
                    elif predicted_temp > hot_threshold:
                        classification = 'H'  # 더움
                    else:
                        classification = 'G'  # 쾌적
                    feedbacks.append(classification)
                
                logger.info(f"📊 최근 3개 predicted_skin_temp 분류 결과: {feedbacks} (온도값: {[float(row.predicted_skin_temp) for row in temp_results]})")
                
                # 다수결 판단
                majority_feedback = get_majority_feedback(feedbacks)
                logger.info(f"🎯 다수결 결과: {majority_feedback} ({'더움' if majority_feedback == 'H' else '추움' if majority_feedback == 'C' else '쾌적'})")
                
                # 에어컨 상태 가져오기
                if not air_conditioner_available:
                    logger.warning("⚠️ 에어컨 모듈을 사용할 수 없습니다.")
                    return
                
                try:
                    state_response = get_air_conditioner_state_func()
                    if not state_response or 'result' not in state_response or 'value' not in state_response['result']:
                        logger.warning("⚠️ 에어컨 상태를 가져올 수 없습니다.")
                        return
                    
                    state = state_response['result']['value']
                    current_temp = state.get('temperature', {}).get('currentTemperature')
                    target_temp = state.get('temperature', {}).get('targetTemperature')
                    
                    logger.info(f"🌡️ 현재 상태: 온도={current_temp}°C, 목표 온도={target_temp}°C")
                    
                    # 1. 먼저 수동 조절 범위 캐시 확인
                    cached_threshold = get_temperature_threshold()
                    
                    if cached_threshold and cached_threshold.get('min_temp') is not None and cached_threshold.get('max_temp') is not None:
                        # 캐시가 있고 유효하면 캐시 값 사용
                        min_temp = float(cached_threshold['min_temp'])
                        max_temp = float(cached_threshold['max_temp'])
                        logger.info(f"📦 수동 조절 범위 캐시 사용: {min_temp}~{max_temp}°C")
                    else:
                        # 캐시가 없거나 만료되었으면 DB에서 가져오기
                        threshold_query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                        threshold_result = conn.execute(threshold_query).fetchone()
                        
                        if not threshold_result or threshold_result.min_temp is None or threshold_result.max_temp is None:
                            logger.warning("⚠️ room_threshold 테이블에 min_temp, max_temp가 없습니다.")
                            return
                        
                        min_temp = float(threshold_result.min_temp)
                        max_temp = float(threshold_result.max_temp)
                        logger.info(f"💾 DB에서 온도 범위 가져옴: {min_temp}~{max_temp}°C")
                    
                    actions_taken = []
                    
                    # 온도 조절
                    if majority_feedback == 'G':
                        # 쾌적하면 조절 없음
                        logger.info("✅ 쾌적 상태 - 조절 없음")
                        actions_taken.append("none")
                    else:
                        # 목표 온도 조절 계산
                        if target_temp is not None:
                            new_target_temp = target_temp
                            
                            if majority_feedback == 'H':
                                # 더움 → 목표 온도 -0.5
                                new_target_temp = target_temp - 0.5
                                actions_taken.append("temp_down")
                            elif majority_feedback == 'C':
                                # 추움 → 목표 온도 +0.5
                                new_target_temp = target_temp + 0.5
                                actions_taken.append("temp_up")
                            
                            # 조절 후 목표 온도가 범위 내인지 확인
                            if min_temp <= new_target_temp <= max_temp:
                                try:
                                    set_temperature_func(target_temp=new_target_temp, unit='C')
                                    logger.info(f"🌡️ 온도 조절 완료: {target_temp}°C → {new_target_temp}°C (다수결: {majority_feedback}, 범위: {min_temp}~{max_temp}°C)")
                                    target_temp = new_target_temp
                                except Exception as e:
                                    logger.error(f"❌ 목표 온도 조절 실패: {e}")
                            else:
                                logger.warning(f"⚠️ 조절 후 온도 {new_target_temp}°C가 범위({min_temp}~{max_temp}°C)를 벗어남. 조절 취소")
                                actions_taken.append("temp_adjustment_cancelled")
                        else:
                            logger.warning("⚠️ 목표 온도를 가져올 수 없습니다.")
                    
                    # 조절 결과를 DB에 기록
                    try:
                        # temp_change 테이블에 조절 결과 저장
                        action_str = ", ".join(actions_taken) if actions_taken else "none"
                        adjustment_query = text("""
                            INSERT INTO temp_change 
                            (classification, current_temperature, target_temperature, action_taken, created_at)
                            VALUES 
                            (:classification, :current_temp, :target_temp, :action_taken, NOW())
                        """)
                        conn.execute(adjustment_query, {
                            'classification': majority_feedback,
                            'current_temp': current_temp,
                            'target_temp': target_temp,
                            'action_taken': action_str
                        })
                        conn.commit()
                        logger.info(f"✅ 조절 결과 DB 저장 완료: {action_str}")
                    except Exception as e:
                        logger.warning(f"⚠️ 조절 결과 DB 저장 실패: {e}")
                    
                    # 마지막 조절 시간 업데이트
                    last_adjustment_time = now
                    
                except Exception as e:
                    logger.error(f"❌ 에어컨 상태 조회 또는 조절 실패: {e}")
                    
            except Exception as e:
                logger.error(f"❌ 피드백 조회 실패: {e}")
                
    except Exception as e:
        logger.error(f"❌ 자동 조절 실패: {e}")
