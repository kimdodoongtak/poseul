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
                        print(f"⏳ 데이터 부족: predicted_skin_temp가 {total_count}개만 있습니다. 3개가 필요합니다.")
                        return
                    
                    # 테이블 컬럼 확인하여 정렬 컬럼 찾기
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
                    
                    # 최신 3개 가져오기 (정렬된 순서로)
                    temp_query = text(f"""
                        SELECT predicted_skin_temp 
                        FROM predicted_results 
                        WHERE predicted_skin_temp IS NOT NULL 
                          AND predicted_skin_temp > 0
                        {order_by_clause}
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
                
                temp_values = [float(row.predicted_skin_temp) for row in temp_results]
                logger.info(f"📊 최근 3개 predicted_skin_temp 분류 결과: {feedbacks} (온도값: {temp_values})")
                print(f"📊 최근 3개 피부온도 데이터:")
                print(f"   온도값: {temp_values}°C")
                print(f"   분류 결과: {feedbacks} ({'더움' if feedbacks[0] == 'H' else '추움' if feedbacks[0] == 'C' else '쾌적'}, {'더움' if feedbacks[1] == 'H' else '추움' if feedbacks[1] == 'C' else '쾌적'}, {'더움' if feedbacks[2] == 'H' else '추움' if feedbacks[2] == 'C' else '쾌적'})")
                
                # 다수결 판단
                majority_feedback = get_majority_feedback(feedbacks)
                majority_text = '더움' if majority_feedback == 'H' else '추움' if majority_feedback == 'C' else '쾌적'
                logger.info(f"🎯 다수결 결과: {majority_feedback} ({majority_text})")
                print(f"🎯 다수결 결과: {majority_feedback} ({majority_text})")
                
                # 에어컨 상태 가져오기
                if not air_conditioner_available:
                    logger.warning("⚠️ 에어컨 모듈을 사용할 수 없습니다.")
                    return
                
                try:
                    state_response = get_air_conditioner_state_func()
                    
                    # 응답 구조 확인 및 다양한 경로 지원
                    state = None
                    
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
                    
                    if not state:
                        logger.warning("⚠️ 에어컨 상태를 가져올 수 없습니다.")
                        logger.warning(f"응답 구조: {list(state_response.keys()) if state_response else 'None'}")
                        if state_response:
                            import json
                            logger.warning(f"응답 내용 (일부): {json.dumps({k: str(v)[:100] for k, v in list(state_response.items())[:3]}, indent=2, ensure_ascii=False)}")
                        return
                    
                    current_temp = state.get('temperature', {}).get('currentTemperature')
                    target_temp = state.get('temperature', {}).get('targetTemperature')
                    
                    logger.info(f"🌡️ 현재 상태: 온도={current_temp}°C, 목표 온도={target_temp}°C")
                    print(f"🌡️ 에어컨 현재 상태:")
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
                            
                            # 조절 후 목표 온도가 범위 내인지 확인
                            if min_temp <= new_target_temp <= max_temp:
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
                                logger.warning(f"⚠️ 조절 후 온도 {new_target_temp}°C가 범위({min_temp}~{max_temp}°C)를 벗어남. 조절 취소")
                                print(f"⚠️ 조절 후 온도 {new_target_temp}°C가 범위({min_temp}~{max_temp}°C)를 벗어남. 조절 취소")
                                actions_taken.append("temp_adjustment_cancelled")
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
                    
                    # 테스트 스크립트 로그 테이블에 저장
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
                        previous_temp = original_target_temp
                        new_temp = actual_new_temp  # 실제로 설정된 온도 사용
                        
                        if majority_feedback == 'H':
                            temp_action = "down" if temperature_adjusted else "none"
                        elif majority_feedback == 'C':
                            temp_action = "up" if temperature_adjusted else "none"
                        
                        # 분류 결과를 문자열로 변환 (예: "C,H,G")
                        classification_str = ",".join(feedbacks)
                        
                        # test_script_logs 테이블에 저장
                        test_log_query = text("""
                            INSERT INTO test_script_logs 
                            (classification_results, majority_result, temperature_action, previous_temperature, new_temperature, created_at)
                            VALUES 
                            (:classification_results, :majority_result, :temperature_action, :previous_temperature, :new_temperature, NOW())
                        """)
                        conn.execute(test_log_query, {
                            'classification_results': classification_str,
                            'majority_result': majority_feedback,
                            'temperature_action': temp_action,
                            'previous_temperature': previous_temp,
                            'new_temperature': new_temp
                        })
                        conn.commit()
                        logger.info(f"✅ 테스트 스크립트 로그 저장 완료: 분류={classification_str}, 다수결={majority_feedback}, 조절={temp_action}")
                    except Exception as e:
                        logger.warning(f"⚠️ 테스트 스크립트 로그 저장 실패: {e}")
                    
                    # 마지막 조절 시간 업데이트
                    last_adjustment_time = now
                    
                except Exception as e:
                    logger.error(f"❌ 에어컨 상태 조회 또는 조절 실패: {e}")
                    
            except Exception as e:
                logger.error(f"❌ 피드백 조회 실패: {e}")
                
    except Exception as e:
        logger.error(f"❌ 자동 조절 실패: {e}")
