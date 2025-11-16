"""
에어컨 자동 온도 조절 시스템 모듈

주요 기능:
1. 초기 세팅: room_threshold에서 min_temp, max_temp 가져와서 목표 온도(중간값) 및 목표 습도(60%) 설정
2. 피드백 분류: predicted_skin_temp 예측값이 들어올 때마다 분류값에 따라 H/C/G로 분류하여 temp_change 테이블에 저장
3. 자동 조절: 30분마다 최근 3개 피드백을 다수결로 판단하여 에어컨 조절
"""

from sqlalchemy import text
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 마지막 조절 시간 추적
last_adjustment_time = None


def initialize_air_conditioner_settings(engine, air_conditioner_available: bool, get_air_conditioner_state_func, set_temperature_func):
    """
    초기 세팅: room_threshold에서 min_temp, max_temp 가져와서 목표 온도(중간값) 및 목표 습도(60%) 설정
    
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
                    target_humidity = 60.0  # 목표 습도 60%
                    
                    logger.info(f"🌡️ 초기 세팅: 목표 온도={target_temp}°C (범위: {min_temp}~{max_temp}°C), 목표 습도={target_humidity}%")
                    
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


def classify_and_save_feedback(
    engine,
    predicted_skin_temp: float,
    air_conditioner_available: bool,
    get_air_conditioner_state_func,
    cold_threshold: float = 34.5,
    hot_threshold: float = 35.6
):
    """
    predicted_skin_temp 예측값이 들어올 때마다 분류값에 따라 H/C/G로 분류하여 temp_change 테이블에 저장
    
    Args:
        engine: SQLAlchemy 엔진
        predicted_skin_temp: 예측된 피부 온도
        air_conditioner_available: 에어컨 모듈 사용 가능 여부
        get_air_conditioner_state_func: 에어컨 상태 조회 함수
        cold_threshold: 추움 분류 기준 (기본값: 34.5)
        hot_threshold: 더움 분류 기준 (기본값: 35.6)
    """
    try:
        # 피부온도 분류 (cold_threshold 미만: 추움(C), hot_threshold 초과: 더움(H), 그 외: 쾌적(G))
        if predicted_skin_temp < cold_threshold:
            classification = 'C'  # 추움
        elif predicted_skin_temp > hot_threshold:
            classification = 'H'  # 더움
        else:
            classification = 'G'  # 쾌적
        
        # 에어컨 상태 가져오기
        current_temp = None
        current_humidity = None
        target_temp = None
        target_humidity = None
        
        if air_conditioner_available:
            try:
                state_response = get_air_conditioner_state_func()
                if state_response and 'result' in state_response and 'value' in state_response['result']:
                    state = state_response['result']['value']
                    current_temp = state.get('temperature', {}).get('currentTemperature')
                    target_temp = state.get('temperature', {}).get('targetTemperature')
                    current_humidity = state.get('airQualitySensor', {}).get('humidity')
                    # 목표 습도는 기본값 60%로 설정 (에어컨에서 직접 가져올 수 없으면)
                    target_humidity = 60.0
            except Exception as e:
                logger.warning(f"⚠️ 에어컨 상태 조회 실패 (temp_change 저장 계속): {e}")
        
        # temp_change 테이블에 저장
        with engine.connect() as conn:
            try:
                # temp_change 테이블 존재 여부 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'temp_change'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # temp_change 테이블에 데이터 삽입
                    insert_temp_change = text("""
                        INSERT INTO temp_change 
                        (classification, current_temperature, current_humidity, target_temperature, target_humidity, created_at)
                        VALUES 
                        (:classification, :current_temp, :current_humidity, :target_temp, :target_humidity, NOW())
                    """)
                    conn.execute(insert_temp_change, {
                        'classification': classification,
                        'current_temp': current_temp,
                        'current_humidity': current_humidity,
                        'target_temp': target_temp,
                        'target_humidity': target_humidity
                    })
                    conn.commit()
                    logger.info(f"✅ temp_change 테이블에 분류 저장: {classification} (predicted_skin_temp: {predicted_skin_temp})")
                else:
                    logger.warning("⚠️ temp_change 테이블이 존재하지 않습니다.")
            except Exception as e:
                logger.warning(f"⚠️ temp_change 테이블 저장 실패: {e}")
    except Exception as e:
        logger.warning(f"⚠️ 피드백 분류 및 저장 실패: {e}")


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
    set_temperature_func
):
    """
    30분마다 최근 3개 피드백을 다수결로 판단하여 조절
    
    Args:
        engine: SQLAlchemy 엔진
        air_conditioner_available: 에어컨 모듈 사용 가능 여부
        get_air_conditioner_state_func: 에어컨 상태 조회 함수
        set_temperature_func: 에어컨 온도 설정 함수
    """
    global last_adjustment_time
    
    try:
        # 마지막 조절 이후 30분이 지났는지 확인
        now = datetime.now()
        if last_adjustment_time is not None:
            time_diff = (now - last_adjustment_time).total_seconds() / 60.0  # 분 단위
            if time_diff < 30:
                logger.info(f"⏰ 조절 대기 중... (마지막 조절 이후 {time_diff:.1f}분 경과, 30분 필요)")
                return
        
        logger.info("🔄 에어컨 자동 조절 시작...")
        
        with engine.connect() as conn:
            # temp_change 테이블에서 최근 3개 피드백 가져오기
            try:
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'temp_change'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if not table_exists:
                    logger.warning("⚠️ temp_change 테이블이 존재하지 않습니다.")
                    return
                
                # 최근 3개 피드백 가져오기
                feedback_query = text("""
                    SELECT classification 
                    FROM temp_change 
                    ORDER BY created_at DESC 
                    LIMIT 3
                """)
                feedback_results = conn.execute(feedback_query).fetchall()
                
                if len(feedback_results) < 3:
                    logger.info(f"⏳ 피드백이 {len(feedback_results)}개만 있습니다. 3개가 필요합니다.")
                    return
                
                feedbacks = [row.classification for row in feedback_results]
                logger.info(f"📊 최근 3개 피드백: {feedbacks}")
                
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
                    current_humidity = state.get('airQualitySensor', {}).get('humidity')
                    target_temp = state.get('temperature', {}).get('targetTemperature')
                    
                    logger.info(f"🌡️ 현재 상태: 온도={current_temp}°C, 습도={current_humidity}%, 목표 온도={target_temp}°C")
                    
                    # room_threshold에서 범위 가져오기
                    threshold_query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                    threshold_result = conn.execute(threshold_query).fetchone()
                    
                    if not threshold_result or threshold_result.min_temp is None or threshold_result.max_temp is None:
                        logger.warning("⚠️ room_threshold 테이블에 min_temp, max_temp가 없습니다.")
                        return
                    
                    min_temp = float(threshold_result.min_temp)
                    max_temp = float(threshold_result.max_temp)
                    target_humidity = 60.0  # 목표 습도 60%
                    
                    # 조절 순서: 습도 먼저, 그 다음 온도
                    actions_taken = []
                    
                    # 1️⃣ 습도 조절
                    if current_humidity is not None and current_humidity > target_humidity:
                        # 현재 습도가 목표 습도에 도달했다면 (현재 습도가 60%보다 높으면)
                        # 습도는 에어컨에서 직접 조절할 수 없으므로 로그만 남김
                        logger.info(f"💧 습도 조절 필요: 현재 {current_humidity}% > 목표 {target_humidity}% (에어컨에서 직접 조절 불가)")
                        actions_taken.append("humidity_check")
                    else:
                        logger.info(f"💧 습도 적정: 현재 {current_humidity}% <= 목표 {target_humidity}%")
                    
                    # 2️⃣ 온도 조절
                    if majority_feedback == 'G':
                        # 쾌적하면 조절 없음
                        logger.info("✅ 쾌적 상태 - 조절 없음")
                        actions_taken.append("none")
                    else:
                        # 현재 온도가 목표 온도에 도달했다면
                        if current_temp is not None and target_temp is not None:
                            # 온도 차이가 0.5도 이내면 도달한 것으로 간주
                            if abs(current_temp - target_temp) <= 0.5:
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
                                        logger.info(f"✅ 목표 온도 조절: {target_temp}°C → {new_target_temp}°C")
                                        target_temp = new_target_temp
                                    except Exception as e:
                                        logger.error(f"❌ 목표 온도 조절 실패: {e}")
                                else:
                                    logger.warning(f"⚠️ 조절 후 온도 {new_target_temp}°C가 범위({min_temp}~{max_temp}°C)를 벗어남. 조절 취소")
                                    actions_taken.append("temp_adjustment_cancelled")
                            else:
                                logger.info(f"⏳ 목표 온도 도달 대기 중... (현재: {current_temp}°C, 목표: {target_temp}°C)")
                                actions_taken.append("waiting_for_target")
                        else:
                            logger.warning("⚠️ 현재 온도 또는 목표 온도를 가져올 수 없습니다.")
                    
                    # 조절 결과를 DB에 기록
                    try:
                        # temp_change 테이블에 조절 결과 저장
                        action_str = ", ".join(actions_taken) if actions_taken else "none"
                        adjustment_query = text("""
                            INSERT INTO temp_change 
                            (classification, current_temperature, current_humidity, target_temperature, target_humidity, action_taken, created_at)
                            VALUES 
                            (:classification, :current_temp, :current_humidity, :target_temp, :target_humidity, :action_taken, NOW())
                        """)
                        conn.execute(adjustment_query, {
                            'classification': majority_feedback,
                            'current_temp': current_temp,
                            'current_humidity': current_humidity,
                            'target_temp': target_temp,
                            'target_humidity': target_humidity,
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

