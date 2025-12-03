"""
피드백 기반 온도 범위 조절 모듈

주요 기능:
1. 매일 아침 피드백을 받아서 마지막 예측값과 비교
2. 비교 결과에 따라 실내 온도 범위(room_threshold)와 피부온도 범위(new_skinthreshold) 조절
3. 일주일간 반복하여 임계값 조정
"""

from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import logging

# 한국 시간대 (KST, UTC+9) 전역 정의
KST = timezone(timedelta(hours=9))
import json
import os
import threading
try:
    import fcntl  # Unix/Linux/Mac
except ImportError:
    fcntl = None  # Windows에서는 사용 불가

logger = logging.getLogger(__name__)

# 피드백 횟수 저장 파일 경로
FEEDBACK_COUNT_FILE = os.path.join(os.path.dirname(__file__), 'feedback_count.json')

# JSON 파일 잠금을 위한 딕셔너리 (파일별 Lock 객체)
_json_file_locks = {}
_json_file_locks_lock = threading.Lock()

def get_file_lock(file_path: str):
    """
    파일 경로별 Lock 객체 반환 (동시성 제어용)
    """
    with _json_file_locks_lock:
        if file_path not in _json_file_locks:
            _json_file_locks[file_path] = threading.Lock()
        return _json_file_locks[file_path]

def safe_json_read(file_path: str) -> dict:
    """
    파일 잠금을 사용하여 JSON 파일을 안전하게 읽기
    
    Returns:
        JSON 파일 내용 (딕셔너리), 파일이 없거나 오류 시 빈 딕셔너리
    """
    lock = get_file_lock(file_path)
    with lock:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Unix/Linux/Mac에서 파일 레벨 잠금 추가
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 공유 잠금 (읽기)
                    try:
                        data = json.load(f)
                    finally:
                        if fcntl:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 잠금 해제
                    return data if isinstance(data, dict) else {}
            return {}
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.warning(f"⚠️ JSON 파일 읽기 실패 ({file_path}): {str(e)}")
            return {}

def safe_json_write(file_path: str, data: dict):
    """
    파일 잠금을 사용하여 JSON 파일을 안전하게 쓰기
    
    Args:
        file_path: 파일 경로
        data: 저장할 데이터 (딕셔너리)
    """
    lock = get_file_lock(file_path)
    with lock:
        try:
            # 임시 파일에 먼저 쓰기 (원자적 쓰기)
            temp_file = file_path + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                # Unix/Linux/Mac에서 파일 레벨 잠금 추가
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 배타적 잠금 (쓰기)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # 디스크에 강제 쓰기
                finally:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 잠금 해제
            
            # 임시 파일을 원본 파일로 이동 (원자적 연산)
            os.replace(temp_file, file_path)
            logger.debug(f"✅ JSON 파일 저장 완료: {file_path}")
        except (IOError, OSError) as e:
            logger.error(f"❌ JSON 파일 쓰기 실패 ({file_path}): {str(e)}")
            # 임시 파일 정리
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
            raise


def get_last_prediction(engine, user_no: Optional[int] = None) -> Optional[Tuple[float, str]]:
    """
    피드백 받기 전 마지막 예측값 가져오기
    
    Args:
        engine: SQLAlchemy 엔진
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        (predicted_skin_temp, classification) 또는 None
        classification: 'C' (춥다), 'H' (덥다), 'G' (쾌적)
    """
    try:
        with engine.connect() as conn:
            # predicted_results 테이블에서 최근 예측값 가져오기
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
            else:
                logger.warning("⚠️ 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
            
            # user_no 필터링 추가
            user_filter = ""
            query_params = {}
            if user_no is not None:
                user_filter = "AND (user_no = :user_no OR user_no IS NULL)"
                query_params['user_no'] = user_no
            
            query = text(f"""
                SELECT predicted_skin_temp 
                FROM predicted_results 
                WHERE predicted_skin_temp IS NOT NULL
                  {user_filter}
                {order_by_clause}
                LIMIT 1
            """)
            if query_params:
                result = conn.execute(query, query_params).fetchone()
            else:
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
                    # user_no 필터링 추가
                    threshold_user_filter = ""
                    threshold_query_params = {}
                    if user_no is not None:
                        threshold_user_filter = "WHERE (user_no = :user_no OR user_no IS NULL)"
                        threshold_query_params['user_no'] = user_no
                    
                    threshold_query = text(f"""
                        SELECT min_skinthreshold, max_skinthreshold 
                        FROM new_skinthreshold 
                        {threshold_user_filter}
                        ORDER BY no DESC
                        LIMIT 1
                    """)
                    if threshold_query_params:
                        threshold_result = conn.execute(threshold_query, threshold_query_params).fetchone()
                    else:
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


def get_current_thresholds(engine, user_no: Optional[int] = None) -> Optional[Tuple[float, float, float, float]]:
    """
    현재 임계값 가져오기 (가장 최신 값, user_no 필터링)
    - room_threshold 테이블: 실내 온도 범위 (no 컬럼 기준 최신)
    - new_skinthreshold 테이블: 피부온도 범위 (no 컬럼 기준 최신)
    
    Args:
        engine: SQLAlchemy 엔진
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        (room_min_temp, room_max_temp, skin_min_temp, skin_max_temp) 또는 None
    """
    try:
        with engine.connect() as conn:
            # 1. room_threshold 테이블에서 실내 온도 범위 가져오기 (no 컬럼 기준 최신)
            # 컬럼 확인
            room_columns_query = text("""
                SELECT COLUMN_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = 'main' 
                AND TABLE_NAME = 'room_threshold'
            """)
            room_columns = [row.COLUMN_NAME for row in conn.execute(room_columns_query).fetchall()]
            
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
            
            # user_no 필터링 추가
            room_user_filter = ""
            room_query_params = {}
            if user_no is not None:
                room_user_filter = "WHERE (user_no = :user_no OR user_no IS NULL)"
                room_query_params['user_no'] = user_no
            
            room_query = text(f"""
                SELECT min_temp, max_temp 
                FROM room_threshold 
                {room_user_filter}
                {room_order_by}
                LIMIT 1
            """)
            if room_query_params:
                room_result = conn.execute(room_query, room_query_params).fetchone()
            else:
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
                # new_skinthreshold 테이블에서 피부온도 범위 가져오기 (no 컬럼 기준 최신)
                # 컬럼 확인
                skin_columns_query = text("""
                    SELECT COLUMN_NAME 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'new_skinthreshold'
                """)
                skin_columns = [row.COLUMN_NAME for row in conn.execute(skin_columns_query).fetchall()]
                
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
                
                # user_no 필터링 추가
                skin_user_filter = ""
                skin_query_params = {}
                if user_no is not None:
                    skin_user_filter = "WHERE (user_no = :user_no OR user_no IS NULL)"
                    skin_query_params['user_no'] = user_no
                
                skin_query = text(f"""
                    SELECT min_skinthreshold, max_skinthreshold 
                    FROM new_skinthreshold 
                    {skin_user_filter}
                    {skin_order_by}
                    LIMIT 1
                """)
                if skin_query_params:
                    skin_result = conn.execute(skin_query, skin_query_params).fetchone()
                else:
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
    skin_max_temp: float,
    user_no: Optional[int] = None
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
            # 1. room_threshold 테이블에 순차적으로 저장 (실내 온도 범위)
            # 테이블이 비어있으면 AUTO_INCREMENT 리셋
            count_query = text("SELECT COUNT(*) as count FROM room_threshold")
            record_count = conn.execute(count_query).fetchone().count
            
            if record_count == 0:
                # 테이블이 비어있으면 AUTO_INCREMENT를 1로 리셋
                try:
                    reset_query = text("ALTER TABLE room_threshold AUTO_INCREMENT = 1")
                    conn.execute(reset_query)
                    logger.info("✅ room_threshold 테이블 AUTO_INCREMENT 리셋 완료")
                except Exception as e:
                    logger.warning(f"⚠️ AUTO_INCREMENT 리셋 실패 (무시): {e}")
            
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
                    logger.info("✅ room_threshold 테이블에 user_no 컬럼 추가 완료")
            except Exception as e:
                logger.warning(f"⚠️ user_no 컬럼 확인/추가 실패: {str(e)}")
            
            insert_room_query = text("""
                INSERT INTO room_threshold (min_temp, max_temp, user_no)
                VALUES (:room_min, :room_max, :user_no)
            """)
            conn.execute(insert_room_query, {
                'room_min': room_min_temp,
                'room_max': room_max_temp,
                'user_no': user_no
            })
            logger.info(f"✅ room_threshold 테이블에 임계값 저장: {room_min_temp}~{room_max_temp}°C, user_no={user_no}")
            
            # 2. new_skinthreshold 테이블 확인 및 업데이트 (피부온도 범위)
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'new_skinthreshold'
            """)
            has_new_table = conn.execute(table_check).fetchone().count > 0
            
            if has_new_table:
                # new_skinthreshold 테이블이 있으면 순차적으로 저장 (INSERT, user_no 포함)
                insert_skin_query = text("""
                    INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, user_no)
                    VALUES (:skin_min, :skin_max, :user_no)
                """)
                conn.execute(insert_skin_query, {
                    'skin_min': skin_min_temp,
                    'skin_max': skin_max_temp,
                    'user_no': user_no
                })
                logger.info(f"✅ new_skinthreshold 테이블에 임계값 저장: {skin_min_temp}~{skin_max_temp}°C")
            else:
                # new_skinthreshold 테이블이 없으면 생성하고 기본값 삽입
                create_table_query = text("""
                    CREATE TABLE IF NOT EXISTS new_skinthreshold (
                        no INT AUTO_INCREMENT PRIMARY KEY,
                        min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                        max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6
                    )
                """)
                conn.execute(create_table_query)
                
                # user_no 컬럼이 없으면 추가
                try:
                    column_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'new_skinthreshold'
                        AND COLUMN_NAME = 'user_no'
                    """)
                    has_user_no = conn.execute(column_check).fetchone() is not None
                    if not has_user_no:
                        alter_query = text("ALTER TABLE new_skinthreshold ADD COLUMN user_no INT DEFAULT NULL")
                        conn.execute(alter_query)
                        logger.info("✅ new_skinthreshold 테이블에 user_no 컬럼 추가 완료")
                except Exception as e:
                    logger.warning(f"⚠️ user_no 컬럼 확인/추가 실패: {str(e)}")
                
                insert_skin_query = text("""
                    INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, user_no)
                    VALUES (:skin_min, :skin_max, :user_no)
                """)
                conn.execute(insert_skin_query, {
                    'skin_min': skin_min_temp,
                    'skin_max': skin_max_temp,
                    'user_no': user_no
                })
                logger.info(f"✅ new_skinthreshold 테이블 생성 및 기본값 삽입: {skin_min_temp}~{skin_max_temp}°C, user_no={user_no}")
            
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


def get_feedback_count(engine, user_no: Optional[int] = None) -> int:
    """
    현재 피드백 기간의 피드백 횟수 가져오기 (user_no별로 분리)
    
    Args:
        engine: SQLAlchemy 엔진 (호환성을 위해 유지, 실제로는 사용 안 함)
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        피드백 횟수 (0부터 시작)
    """
    try:
        data = safe_json_read(FEEDBACK_COUNT_FILE)
        if not data:
            return 0
        
        # user_no별로 분리된 데이터 구조: {user_no: count}
        if user_no is not None:
            user_counts = data.get('user_counts', {})
            return user_counts.get(str(user_no), 0)
        else:
            # user_no가 없으면 전체 합계 반환 (하위 호환성)
            return data.get('feedback_count', 0)
    except Exception as e:
        logger.warning(f"⚠️ 피드백 횟수 조회 실패: {e}")
        return 0


def reset_feedback_period(engine, user_no: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    피드백 기반 조정 기간을 재시작 (피드백 횟수 리셋, user_no별로 분리)
    
    Args:
        engine: SQLAlchemy 엔진 (호환성을 위해 유지, 실제로는 사용 안 함)
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        (성공 여부, 메시지)
    """
    try:
        # 기존 데이터 읽기
        data = safe_json_read(FEEDBACK_COUNT_FILE)
        if not data:
            data = {}
        
        # user_no별로 분리된 데이터 구조
        if 'user_counts' not in data:
            data['user_counts'] = {}
        
        if user_no is not None:
            # 특정 사용자의 피드백 횟수를 0으로 리셋
            data['user_counts'][str(user_no)] = 0
        else:
            # user_no가 없으면 전체 리셋 (하위 호환성)
            data['feedback_count'] = 0
        
        data['updated_at'] = datetime.now(KST).isoformat()
        
        # 파일에 저장 (파일 잠금 사용)
        safe_json_write(FEEDBACK_COUNT_FILE, data)
        
        logger.info(f"✅ 피드백 기반 조정 기간 재시작: 피드백 횟수 리셋, user_no={user_no}")
        return True, "피드백 기반 조정 기간이 재시작되었습니다. 다시 7번의 피드백을 받습니다."
    except Exception as e:
        logger.error(f"❌ 피드백 기간 재시작 실패: {e}")
        return False, f"피드백 기간 재시작 실패: {str(e)}"


def is_within_feedback_limit(engine, user_no: Optional[int] = None) -> bool:
    """
    피드백 횟수가 7번 미만인지 확인
    
    Args:
        engine: SQLAlchemy 엔진
        user_no: 사용자 번호 (선택사항, 향후 사용자별 분리 시 사용)
    
    Returns:
        True: 7번 미만 (계속 가능), False: 7번 이상 (종료)
    """
    try:
        feedback_count = get_feedback_count(engine, user_no)
        return feedback_count < 7
    except Exception as e:
        logger.warning(f"⚠️ 피드백 횟수 확인 실패: {e}")
        return True  # 에러 시 계속 가능으로 간주


def process_daily_feedback(engine, feedback: str, user_no: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    피드백 처리 및 임계값 조정 (7번까지)
    
    Args:
        engine: SQLAlchemy 엔진
        feedback: 피드백 ('C': 춥다, 'H': 덥다, 'G': 쾌적)
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        (성공 여부, 메시지)
    """
    try:
        # 피드백 유효성 검사
        if feedback not in ['C', 'H', 'G']:
            return False, f"유효하지 않은 피드백: {feedback} (C, H, G 중 하나여야 함)"
        
        # 피드백 횟수 제한 확인 (7번까지, user_no별로 분리)
        feedback_count = get_feedback_count(engine, user_no)
        if feedback_count >= 7:
            logger.info(f"ℹ️ 피드백 기반 조정 기간이 지났습니다. (피드백 {feedback_count}번 완료)")
            return False, f"피드백 기반 조정은 7번까지만 가능합니다. (현재: {feedback_count}번)"
        
        logger.info(f"📝 피드백 수신: {feedback} ({'춥다' if feedback == 'C' else '덥다' if feedback == 'H' else '쾌적'})")
        
        # 2. 마지막 예측값 가져오기
        prediction_result = get_last_prediction(engine, user_no)
        if not prediction_result:
            return False, "마지막 예측값이 없습니다."
        
        predicted_temp, prediction = prediction_result
        logger.info(f"🔮 마지막 예측값: {predicted_temp}°C ({'춥다' if prediction == 'C' else '덥다' if prediction == 'H' else '쾌적'}), user_no={user_no}")
        
        # 3. 현재 임계값 가져오기
        current_thresholds = get_current_thresholds(engine, user_no)
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
                        no INT AUTO_INCREMENT PRIMARY KEY,
                        min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                        max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6
                    )
                """)
                conn.execute(create_table_query)
                logger.info("✅ new_skinthreshold 테이블 생성 완료")
            
            # 레코드 확인
            count_query = text("SELECT COUNT(*) as count FROM new_skinthreshold")
            record_count = conn.execute(count_query).fetchone().count
            
            if record_count == 0:
                # 레코드가 없으면 기본값으로 저장 (user_no는 NULL로 저장)
                insert_query = text("""
                    INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, user_no)
                    VALUES (34.6, 35.6, NULL)
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
            new_skin_max,
            user_no
        )
        
        if success:
            # 7. 피드백 횟수 증가
            try:
                # 기존 데이터 읽기 (파일 잠금 사용)
                data = safe_json_read(FEEDBACK_COUNT_FILE)
                if not data:
                    data = {}
                
                # user_no별로 분리된 데이터 구조
                if 'user_counts' not in data:
                    data['user_counts'] = {}
                
                if user_no is not None:
                    # 특정 사용자의 피드백 횟수 증가
                    user_counts = data.get('user_counts', {})
                    current_user_count = user_counts.get(str(user_no), 0)
                    user_counts[str(user_no)] = current_user_count + 1
                    data['user_counts'] = user_counts
                else:
                    # user_no가 없으면 전체 카운트 증가 (하위 호환성)
                    current_count = data.get('feedback_count', 0)
                    data['feedback_count'] = current_count + 1
                
                data['updated_at'] = datetime.now(KST).isoformat()
                
                # 파일에 저장 (파일 잠금 사용)
                safe_json_write(FEEDBACK_COUNT_FILE, data)
            except Exception as e:
                logger.warning(f"⚠️ 피드백 횟수 증가 실패: {e}")
            
            message = (
                f"✅ 임계값 조정 완료: "
                f"실내온도 {room_min}~{room_max}°C → {new_room_min}~{new_room_max}°C, "
                f"피부온도 {skin_min}~{skin_max}°C → {new_skin_min}~{new_skin_max}°C"
            )
            logger.info(f"🎯 {message} (피드백: {feedback}, 예측: {prediction}, 조정량: 실내온도 {room_adjustment}°C, 피부온도 {skin_adjustment}°C)")
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

