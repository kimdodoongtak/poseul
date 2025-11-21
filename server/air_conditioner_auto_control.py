"""
에어컨 자동 온도 조절 시스템 모듈

주요 기능:
1. 초기 세팅: room_threshold에서 min_temp, max_temp 가져와서 목표 온도(중간값) 설정
2. 자동 조절: 2분마다 최근 3개 피드백을 다수결로 판단하여 에어컨 조절 (테스트 모드)
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
                
                # 최신 값 가져오기 (no 컬럼 기준)
                # 컬럼 확인
                room_columns_check = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'room_threshold'
                """)
                room_columns = [row.COLUMN_NAME for row in conn.execute(room_columns_check).fetchall()]
                
                # 정렬 컬럼 결정 (no 컬럼 우선 사용)
                room_order_by = ""
                if 'no' in room_columns:
                    room_order_by = "ORDER BY no DESC"
                elif 'id' in room_columns:
                    room_order_by = "ORDER BY id DESC"
                elif 'created_at' in room_columns:
                    room_order_by = "ORDER BY created_at DESC"
                else:
                    logger.warning("⚠️ room_threshold 테이블에 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
                
                threshold_query = text(f"""
                    SELECT min_temp, max_temp 
                    FROM room_threshold 
                    {room_order_by}
                    LIMIT 1
                """)
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
    실시간 데이터 수신 시 또는 스케줄러에 의해 호출되어 predicted_results에서 최근 30분 이내 predicted_skin_temp를 분류하여 다수결로 판단하고 조절
    - 실시간 데이터 수신 시: 데이터가 들어올 때마다 호출 (최소 10분 간격)
    - 스케줄러: 30분마다 백업용으로 실행
    
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
        # 마지막 조절 이후 최소 간격 확인 (10분: 데이터가 10분마다 들어오므로)
        now = datetime.now()
        if last_adjustment_time is not None:
            time_diff = (now - last_adjustment_time).total_seconds() / 60.0  # 분 단위
            if time_diff < 10:
                logger.info(f"⏰ 조절 대기 중... (마지막 조절 이후 {time_diff:.1f}분 경과, 최소 10분 간격 필요) - 다음 조절까지 {10 - time_diff:.1f}분 남음")
                print(f"⏰ 조절 대기 중... (마지막 조절 이후 {time_diff:.1f}분 경과, 최소 10분 간격 필요)")
                return
        else:
            logger.info("🔄 첫 번째 제어 실행 (마지막 조절 기록 없음)")
            print("🔄 첫 번째 제어 실행")
        
        logger.info("🔄 에어컨 자동 조절 시작...")
        print("🔄 에어컨 자동 조절 시작...")
        
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
                    # min_skinthreshold, max_skinthreshold 값 가져오기 (최신 값, no 컬럼 기준)
                    # 컬럼 확인
                    skin_columns_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'new_skinthreshold'
                    """)
                    skin_columns = [row.COLUMN_NAME for row in conn.execute(skin_columns_check).fetchall()]
                    
                    # 정렬 컬럼 결정 (no 컬럼 우선 사용)
                    skin_order_by = ""
                    if 'no' in skin_columns:
                        skin_order_by = "ORDER BY no DESC"
                    elif 'id' in skin_columns:
                        skin_order_by = "ORDER BY id DESC"
                    elif 'created_at' in skin_columns:
                        skin_order_by = "ORDER BY created_at DESC"
                    else:
                        logger.warning("⚠️ new_skinthreshold 테이블에 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
                    
                    skin_threshold_query = text(f"""
                        SELECT min_skinthreshold, max_skinthreshold 
                        FROM new_skinthreshold 
                        {skin_order_by}
                        LIMIT 1
                    """)
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
                        # 테이블은 있지만 레코드가 없으면 기본값 저장 (34.6, 35.6)
                        db_cold_threshold = 34.6
                        db_hot_threshold = 35.6
                        logger.info(f"ℹ️ new_skinthreshold 테이블에 레코드가 없습니다. 기본값 저장: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                        
                        # 기본값을 DB에 저장
                        try:
                            insert_query = text("""
                                INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold)
                                VALUES (:min_skin, :max_skin)
                            """)
                            conn.execute(insert_query, {
                                'min_skin': db_cold_threshold,
                                'max_skin': db_hot_threshold
                            })
                            conn.commit()
                            logger.info(f"✅ 기본값 저장 완료: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                        except Exception as insert_error:
                            logger.warning(f"⚠️ 기본값 저장 실패: {insert_error}")
                        
                        # 기본값으로 전역 변수 갱신
                        if update_threshold_callback:
                            update_threshold_callback(db_cold_threshold, db_hot_threshold)
                        cold_threshold = db_cold_threshold
                        hot_threshold = db_hot_threshold
                else:
                    # new_skinthreshold 테이블이 없으면 테이블 생성 후 기본값 저장 (34.6, 35.6)
                    db_cold_threshold = 34.6
                    db_hot_threshold = 35.6
                    logger.info(f"ℹ️ new_skinthreshold 테이블이 없습니다. 테이블 생성 후 기본값 저장: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                    
                    # 테이블 생성 및 기본값 저장
                    try:
                        create_table_query = text("""
                            CREATE TABLE IF NOT EXISTS new_skinthreshold (
                                no INT AUTO_INCREMENT PRIMARY KEY,
                                min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                                max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6
                            )
                        """)
                        conn.execute(create_table_query)
                        
                        insert_query = text("""
                            INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold)
                            VALUES (:min_skin, :max_skin)
                        """)
                        conn.execute(insert_query, {
                            'min_skin': db_cold_threshold,
                            'max_skin': db_hot_threshold
                        })
                        conn.commit()
                        logger.info(f"✅ 테이블 생성 및 기본값 저장 완료: cold={db_cold_threshold}°C, hot={db_hot_threshold}°C")
                    except Exception as create_error:
                        logger.warning(f"⚠️ 테이블 생성 또는 기본값 저장 실패: {create_error}")
                    
                    # 기본값으로 전역 변수 갱신
                    if update_threshold_callback:
                        update_threshold_callback(db_cold_threshold, db_hot_threshold)
                    cold_threshold = db_cold_threshold
                    hot_threshold = db_hot_threshold
            except Exception as e:
                logger.warning(f"⚠️ 피부온도 분류 기준 확인 실패 (계속 진행): {e}")
            
            # predicted_results 테이블에서 최근 30분 이내 predicted_skin_temp 가져오기
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
                
                # 최근 30분 이내 predicted_skin_temp 가져오기
                try:
                    # 테이블 컬럼 확인하여 정렬 컬럼 및 시간 컬럼 찾기
                    columns_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns = [row.COLUMN_NAME for row in conn.execute(columns_check).fetchall()]
                    
                    # 정렬 컬럼 결정 (no 컬럼 우선 사용)
                    order_by_clause = ""
                    if 'no' in columns:
                        order_by_clause = "ORDER BY no DESC"
                    elif 'id' in columns:
                        order_by_clause = "ORDER BY id DESC"
                    elif 'created_at' in columns:
                        order_by_clause = "ORDER BY created_at DESC"
                    elif 'timestamp' in columns:
                        order_by_clause = "ORDER BY timestamp DESC"
                    elif 'date' in columns:
                        order_by_clause = "ORDER BY date DESC"
                    else:
                        logger.warning("⚠️ 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
                    
                    # 시간 필터 조건 (30분 이내)
                    time_filter = ""
                    if 'created_at' in columns:
                        time_filter = "AND created_at >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)"
                    elif 'timestamp' in columns:
                        time_filter = "AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)"
                    elif 'date' in columns:
                        time_filter = "AND date >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)"
                    else:
                        # 시간 컬럼이 없으면 최근 데이터만 가져오기 (기존 방식)
                        logger.warning("⚠️ 시간 컬럼을 찾을 수 없습니다. 최근 데이터만 사용합니다.")
                    
                    # 최근 30분 이내 데이터 가져오기
                    temp_query = text(f"""
                        SELECT predicted_skin_temp 
                        FROM predicted_results 
                        WHERE predicted_skin_temp IS NOT NULL 
                          AND predicted_skin_temp > 0
                          {time_filter}
                        {order_by_clause}
                    """)
                    temp_results = conn.execute(temp_query).fetchall()
                        
                except Exception as e:
                    logger.error(f"❌ 쿼리 실행 실패: {e}")
                    return
                
                if len(temp_results) < 1:
                    logger.info(f"⏳ 최근 30분 이내 predicted_skin_temp가 없습니다.")
                    print(f"⏳ 데이터 부족: 최근 30분 이내 predicted_skin_temp가 없습니다.")
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
                
                temp_values = [float(row.predicted_skin_temp) for row in temp_results]
                logger.info(f"📊 최근 30분 이내 predicted_skin_temp 분류 결과: {feedbacks} (온도값: {temp_values}, 개수: {len(feedbacks)}개)")
                print(f"📊 최근 30분 이내 피부온도 데이터 ({len(feedbacks)}개):")
                print(f"   온도값: {temp_values}°C")
                print(f"   분류 결과: {feedbacks}")
                
                # 다수결 판단
                majority_feedback = get_majority_feedback(feedbacks)
                majority_text = '더움' if majority_feedback == 'H' else '추움' if majority_feedback == 'C' else '쾌적'
                logger.info(f"🎯 다수결 결과: {majority_feedback} ({majority_text})")
                print(f"🎯 다수결 결과: {majority_feedback} ({majority_text})")
                
                # 에어컨 상태 가져오기
                state = None
                is_power_on = False
                current_temp = None
                target_temp = None
                
                if not air_conditioner_available:
                    logger.warning("⚠️ 에어컨 모듈을 사용할 수 없습니다.")
                else:
                    try:
                        state_response = get_air_conditioner_state_func()
                        
                        # 응답 구조 확인 및 다양한 경로 지원
                        # 1. result.value 경로 확인
                        if state_response and 'result' in state_response:
                            result = state_response['result']
                            if isinstance(result, dict) and 'value' in result:
                                state = result['value']
                        
                        # 2. response.value 경로 확인
                        if state is None and state_response and 'response' in state_response:
                            response = state_response['response']
                            if isinstance(response, dict):
                                if 'value' in response:
                                    state = response['value']
                                else:
                                    state = response
                            elif isinstance(response, list) and len(response) > 0:
                                state = response[0]
                        
                        # 3. 최상위 value 경로 확인
                        if state is None and state_response and 'value' in state_response:
                            state = state_response['value']
                        
                        if state:
                            # 에어컨 전원 상태 확인
                            power_state = state.get('operation', {}).get('airConOperationMode')
                            is_power_on = power_state == 'POWER_ON'
                            current_temp = state.get('temperature', {}).get('currentTemperature')
                            target_temp = state.get('temperature', {}).get('targetTemperature')
                        else:
                            logger.warning("⚠️ 에어컨 상태를 가져올 수 없습니다.")
                            if state_response:
                                import json
                                logger.warning(f"응답 내용 (일부): {json.dumps({k: str(v)[:100] for k, v in list(state_response.items())[:3]}, indent=2, ensure_ascii=False)}")
                    except Exception as e:
                        logger.warning(f"⚠️ 에어컨 상태 조회 실패: {e}")
                
                # 에어컨이 꺼져있으면 조절은 하지 않지만 다수결 결과는 저장
                actions_taken = []
                # 에어컨 상태와 관계없이 target_temp는 가져올 수 있으므로 초기화
                original_target_temp = target_temp  # 에어컨이 꺼져있어도 이전 목표 온도 저장
                temperature_adjusted = False
                actual_new_temp = target_temp  # 에어컨이 꺼져있어도 현재 목표 온도 저장
                
                if not is_power_on:
                    logger.info("⏸️ 에어컨이 꺼져있습니다. 조절은 건너뛰지만 다수결 결과는 저장합니다.")
                    print(f"⏸️ 에어컨이 꺼져있습니다. 조절은 건너뛰지만 다수결 결과는 저장합니다.")
                    # 다수결 결과만 저장하고 조절은 건너뜀
                    actions_taken = ["none"]
                else:
                    logger.info(f"🌡️ 현재 상태: 전원=ON, 온도={current_temp}°C, 목표 온도={target_temp}°C")
                    print(f"🌡️ 에어컨 현재 상태:")
                    print(f"   전원: ON")
                    print(f"   현재 온도: {current_temp}°C")
                    print(f"   목표 온도: {target_temp}°C")
                    
                    # 1. 먼저 수동 조절 범위 캐시 확인
                    cached_threshold = get_temperature_threshold()
                    
                    if cached_threshold and cached_threshold.get('min_temp') is not None and cached_threshold.get('max_temp') is not None:
                        # 캐시가 있고 유효하면 캐시 값 사용
                        min_temp = float(cached_threshold['min_temp'])
                        max_temp = float(cached_threshold['max_temp'])
                        logger.info(f"📦 수동 조절 범위 캐시 사용: {min_temp}~{max_temp}°C")
                    else:
                        # 캐시가 없거나 만료되었으면 DB에서 가져오기 (최신 값, no 컬럼 기준)
                        # 컬럼 확인
                        room_columns_check = text("""
                            SELECT COLUMN_NAME 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'main' 
                            AND TABLE_NAME = 'room_threshold'
                        """)
                        room_columns = [row.COLUMN_NAME for row in conn.execute(room_columns_check).fetchall()]
                        
                        # 정렬 컬럼 결정 (no 컬럼 우선 사용)
                        room_order_by = ""
                        if 'no' in room_columns:
                            room_order_by = "ORDER BY no DESC"
                        elif 'id' in room_columns:
                            room_order_by = "ORDER BY id DESC"
                        elif 'created_at' in room_columns:
                            room_order_by = "ORDER BY created_at DESC"
                        else:
                            logger.warning("⚠️ room_threshold 테이블에 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
                        
                        threshold_query = text(f"""
                            SELECT min_temp, max_temp 
                            FROM room_threshold 
                            {room_order_by}
                            LIMIT 1
                        """)
                        threshold_result = conn.execute(threshold_query).fetchone()
                        
                        if not threshold_result or threshold_result.min_temp is None or threshold_result.max_temp is None:
                            logger.warning("⚠️ room_threshold 테이블에 min_temp, max_temp가 없습니다.")
                            return
                        
                        min_temp = float(threshold_result.min_temp)
                        max_temp = float(threshold_result.max_temp)
                        logger.info(f"💾 DB에서 온도 범위 가져옴: {min_temp}~{max_temp}°C")
                    
                    actions_taken = []
                    original_target_temp = target_temp  # 원래 목표 온도 저장 (로그 저장용)
                    temperature_adjusted = False  # 온도 조절이 실제로 실행되었는지 여부
                    actual_new_temp = target_temp  # 실제로 설정된 새 온도
                    
                    # 온도 조절
                    if majority_feedback == 'G':
                        # 쾌적하면 조절 없음
                        logger.info("✅ 쾌적 상태 - 조절 없음")
                        print(f"✅ 쾌적 상태 - 온도 조절 없음")
                        actions_taken.append("none")
                    else:
                        # 목표 온도 조절 계산
                        if target_temp is not None:
                            new_target_temp = target_temp
                            
                            if majority_feedback == 'H':
                                # 더움 → 목표 온도 -0.5
                                new_target_temp = target_temp - 0.5
                                actions_taken.append("temp_down")
                                print(f"🔥 더움 감지 → 목표 온도 낮춤: {target_temp}°C → {new_target_temp}°C")
                            elif majority_feedback == 'C':
                                # 추움 → 목표 온도 +0.5
                                new_target_temp = target_temp + 0.5
                                actions_taken.append("temp_up")
                                print(f"❄️ 추움 감지 → 목표 온도 높임: {target_temp}°C → {new_target_temp}°C")
                            
                            # 조절 후 목표 온도가 범위 내인지 확인하고, 범위를 벗어나면 최소값/최대값으로 조정
                            if new_target_temp < min_temp:
                                # 최소값보다 낮으면 최소값으로 조정
                                new_target_temp = min_temp
                                logger.info(f"📈 조절 후 온도가 최소값({min_temp}°C)보다 낮아 최소값으로 조정: {new_target_temp}°C")
                                print(f"📈 조절 후 온도가 최소값({min_temp}°C)보다 낮아 최소값으로 조정: {new_target_temp}°C")
                            elif new_target_temp > max_temp:
                                # 최대값보다 높으면 최대값까지 내림
                                new_target_temp = max_temp
                                logger.info(f"📉 조절 후 온도가 최대값({max_temp}°C)보다 높아 최대값까지 내림: {new_target_temp}°C")
                                print(f"📉 조절 후 온도가 최대값({max_temp}°C)보다 높아 최대값까지 내림: {new_target_temp}°C")
                            
                            # 조정된 온도로 설정
                            try:
                                set_temperature_func(target_temp=new_target_temp, unit='C')
                                logger.info(f"🌡️ 온도 조절 완료: {target_temp}°C → {new_target_temp}°C (다수결: {majority_feedback}, 범위: {min_temp}~{max_temp}°C)")
                                print(f"✅ 온도 조절 완료: {target_temp}°C → {new_target_temp}°C (조절 범위: {min_temp}~{max_temp}°C)")
                                target_temp = new_target_temp
                                temperature_adjusted = True
                                actual_new_temp = new_target_temp
                            except Exception as e:
                                logger.error(f"❌ 목표 온도 조절 실패: {e}")
                                print(f"❌ 목표 온도 조절 실패: {e}")
                                actual_new_temp = original_target_temp
                        else:
                            logger.warning("⚠️ 목표 온도를 가져올 수 없습니다.")
                            print(f"⚠️ 목표 온도를 가져올 수 없습니다.")
                            actual_new_temp = original_target_temp
                    

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
                    
                    # 마지막 조절 시간 업데이트 (에어컨이 켜져있을 때만)
                    if is_power_on:
                        last_adjustment_time = now
                
                # test_script_logs 테이블에 다수결 결과 저장 (에어컨이 꺼져있어도 저장)
                try:
                    # test_script_logs 테이블 존재 여부 확인 및 생성
                    test_log_table_check = text("""
                        SELECT COUNT(*) as count
                        FROM information_schema.tables 
                        WHERE table_schema = 'main' 
                        AND table_name = 'test_script_logs'
                    """)
                    test_log_table_exists = conn.execute(test_log_table_check).fetchone().count > 0
                    
                    if not test_log_table_exists:
                        # 테이블 생성
                        create_test_log_table = text("""
                            CREATE TABLE IF NOT EXISTS test_script_logs (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                classification_results VARCHAR(50) NOT NULL COMMENT '3개 분류 결과 (예: C,H,G)',
                                majority_result VARCHAR(1) NOT NULL COMMENT '다수결 결과 (H, C, G)',
                                temperature_action VARCHAR(20) NOT NULL COMMENT '온도 조절 방향 (up, down, none)',
                                previous_temperature FLOAT COMMENT '이전 목표 온도',
                                new_temperature FLOAT COMMENT '새로운 목표 온도',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        conn.execute(create_test_log_table)
                        conn.commit()
                        logger.info("✅ test_script_logs 테이블 생성 완료")
                    
                    # 온도 조절 방향 결정
                    temp_action = "none"
                    # previous_temperature: 에어컨의 이전 목표 온도 (original_target_temp)
                    previous_temp = original_target_temp if original_target_temp is not None else None
                    # new_temperature: 에어컨의 새로운 목표 온도 (actual_new_temp, 에어컨 설정 온도)
                    new_temp = actual_new_temp if actual_new_temp is not None else None
                    
                    if is_power_on:
                        # 에어컨이 켜져있을 때만 조절 방향 결정
                        if majority_feedback == 'H':
                            # 더움 → 온도 낮춤
                            temp_action = "down" if temperature_adjusted else "none"
                        elif majority_feedback == 'C':
                            # 추움 → 온도 높임
                            temp_action = "up" if temperature_adjusted else "none"
                        elif majority_feedback == 'G':
                            # 쾌적 → 조절 없음
                            temp_action = "none"
                    else:
                        # 에어컨이 꺼져있으면 조절 없음
                        temp_action = "none"
                    
                    # 분류 결과를 문자열로 변환 (예: "C,H,G")
                    classification_str = ",".join(feedbacks)
                    
                    # test_script_logs 테이블에 저장
                    from datetime import datetime
                    current_datetime = datetime.now()
                    test_log_query = text("""
                        INSERT INTO test_script_logs 
                        (classification_results, majority_result, temperature_action, previous_temperature, new_temperature, created_at)
                        VALUES 
                        (:classification_results, :majority_result, :temperature_action, :previous_temperature, :new_temperature, :created_at)
                    """)
                    conn.execute(test_log_query, {
                        'classification_results': classification_str,
                        'majority_result': majority_feedback,
                        'temperature_action': temp_action,
                        'previous_temperature': previous_temp,
                        'new_temperature': new_temp,
                        'created_at': current_datetime
                    })
                    conn.commit()
                    logger.info(f"✅ 다수결 결과 저장 완료: 분류={classification_str}, 다수결={majority_feedback}, 조절={temp_action} (에어컨 전원: {'ON' if is_power_on else 'OFF'})")
                except Exception as e:
                    logger.warning(f"⚠️ 다수결 결과 저장 실패: {e}")
                    
            except Exception as e:
                logger.error(f"❌ 피드백 조회 실패: {e}")
                
    except Exception as e:
        logger.error(f"❌ 자동 조절 실패: {e}")
