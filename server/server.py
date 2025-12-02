from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Tuple
from sqlalchemy import text
from datetime import datetime, timedelta
import logging
import os
import sys
import json
import numpy as np
import pandas as pd
import joblib
import time
import threading
try:
    import fcntl  # Unix/Linux/Mac
except ImportError:
    fcntl = None  # Windows에서는 사용 불가
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from passlib.context import CryptContext
from jose import JWTError, jwt
import air_conditioner_auto_control
import temperature_control_logic
import feedback_based_adjustment

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS 설정 (모든 origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 연결 오류 추적
connectivity_error_count = 0
last_connectivity_error = None

# Android 앱 건강 로그 저장소 (미들웨어에서 사용하기 위해 여기서 초기화)
android_app_health_logs = []

# 수면 모드 상태 관리 (사용자별)
sleep_mode_states = {}  # {user_no: {"active": bool, "start_time": str, "end_time": str, "duration_hours": float}}

# 온도 임계값 캐시 모듈 import
from temperature_threshold_cache import (
    save_temperature_threshold as save_threshold, 
    get_temperature_threshold as get_threshold,
    check_and_cleanup_expired_cache
)

@app.middleware("http")
async def track_connectivity_errors(request: Request, call_next):
    """연결 오류 추적 미들웨어"""
    global connectivity_error_count, last_connectivity_error, android_app_health_logs
    start_time = time.time()
    
    # PAT 토큰 관련 요청 로깅 (요청 도달 확인)
    if request.url.path == "/iot/auto-register":
        logger.info(f"📥 PAT 토큰 등록 요청 수신: {request.method} {request.url.path}")
        logger.info(f"   클라이언트 IP: {request.client.host if request.client else 'N/A'}")
        logger.info(f"   User-Agent: {request.headers.get('user-agent', 'N/A')[:50]}")
    elif request.url.path == "/iot/test-pat-token":
        logger.info(f"🧪 PAT 토큰 연결 테스트 요청 수신: {request.method} {request.url.path}")
        logger.info(f"   클라이언트 IP: {request.client.host if request.client else 'N/A'}")
        logger.info(f"   User-Agent: {request.headers.get('user-agent', 'N/A')[:50]}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 응답 시간이 너무 길면 경고
        if process_time > 5.0:
            logger.warning(f"⚠️ 느린 응답 시간: {request.url.path} - {process_time:.2f}초")
        
        return response
    except Exception as e:
        error_msg = str(e)
        connectivity_error_count += 1
        last_connectivity_error = {
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "method": request.method,
            "error": error_msg
        }
        
        logger.error(f"❌ 연결 오류 발생: {request.url.path} - {error_msg}")
        
        # Android 앱 건강 로그에 연결 오류 기록
        android_app_health_logs.append({
            "timestamp": datetime.now().isoformat(),
            "type": "connectivity_error",
            "path": str(request.url.path),
            "method": request.method,
            "error": error_msg
        })
        # 최근 1000개만 유지
        if len(android_app_health_logs) > 1000:
            android_app_health_logs.pop(0)
        
        raise

# DB 연결 설정
# DBeaver 연결 정보에 맞게 수정:
# Host: aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com
# Username: iriskimhs
# Port: 3306
# Database: main (URL에서 확인)
# Password: dyvVyn-kihxe0-parxes
DB_URL = "mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main"
# 연결 옵션 추가 (SSL, 타임아웃 등)
# pymysql의 SSL 설정: ssl_disabled=True로 비활성화하거나, ssl_ca 인증서 경로 지정
# DBeaver에서 연결이 되면 SSL 없이도 연결 가능할 수 있음
import sqlalchemy
engine = sqlalchemy.create_engine(
    DB_URL,
    connect_args={
        "ssl_disabled": True,  # SSL 비활성화 (DBeaver와 동일한 설정)
        "connect_timeout": 10,  # 연결 타임아웃 10초
        "read_timeout": 10,  # 읽기 타임아웃 10초
        "write_timeout": 10,  # 쓰기 타임아웃 10초
    },
    pool_pre_ping=True,  # 연결 유효성 사전 확인
    pool_recycle=3600,  # 1시간마다 연결 재사용
    echo=False  # SQL 쿼리 로깅 (디버깅 시 True로 변경)
)

# ==================== 인증 설정 ====================
# JWT 설정
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30일

# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer 토큰
security = HTTPBearer()

# ==================== 인증 유틸리티 함수 ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    # hashed_password가 문자열이 아닌 경우 문자열로 변환
    if not isinstance(hashed_password, str):
        hashed_password = str(hashed_password)
    # 빈 문자열이면 False 반환
    if not hashed_password or not hashed_password.strip():
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError) as e:
        logger.error(f"❌ 비밀번호 검증 오류: {str(e)}, 타입: {type(hashed_password)}, 값: {hashed_password[:20] if hashed_password else 'None'}")
        return False

def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """JWT 토큰 검증"""
    token = credentials.credentials
    logger.info(f"🔍 verify_token - 토큰 검증 시작: {token[:20] if token else 'None'}...")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            logger.warning(f"⚠️ verify_token - sub가 None입니다. payload: {payload}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # sub는 문자열로 저장되므로 정수로 변환
        user_no: int = int(sub)
        logger.info(f"✅ verify_token - 토큰 검증 성공: user_no={user_no}")
        return user_no
    except JWTError as e:
        logger.error(f"❌ verify_token - JWT 검증 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"❌ verify_token - 예상치 못한 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_token_optional(request: Request) -> Optional[int]:
    """JWT 토큰 선택적 검증 (토큰이 있으면 user_no 반환, 없으면 None)"""
    try:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return None
        
        token = authorization.split(" ")[1]
        if not token:
            return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        
        user_no: int = int(sub)
        logger.info(f"✅ verify_token_optional - 토큰 검증 성공: user_no={user_no}")
        return user_no
    except Exception:
        # 토큰이 없거나 유효하지 않으면 None 반환 (에러 발생하지 않음)
        return None

# 모델 로드
# 서버 디렉토리 기준으로 모델 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # server 디렉토리의 상위 디렉토리 (프로젝트 루트)

# ==================== 공통 유틸리티 함수 ====================

def build_user_filter(user_no: Optional[int], allow_null: bool = False) -> Tuple[str, dict]:
    """
    user_no 필터링을 위한 SQL 조건과 파라미터 생성
    
    Args:
        user_no: 사용자 번호 (선택사항)
        allow_null: user_no가 NULL인 레코드도 포함할지 여부 (기본값: False)
    
    Returns:
        (filter_clause, query_params): SQL WHERE 절과 쿼리 파라미터
    """
    if user_no is None:
        return "", {}
    
    if allow_null:
        return "AND (user_no = :user_no OR user_no IS NULL)", {"user_no": user_no}
    else:
        return "AND user_no = :user_no", {"user_no": user_no}

def get_table_columns(conn, table_name: str, schema: str = "main") -> list:
    """
    테이블의 컬럼 목록 조회 (캐싱 가능하지만 현재는 매번 조회)
    
    Args:
        conn: SQLAlchemy 연결 객체
        table_name: 테이블 이름
        schema: 스키마 이름 (기본값: "main")
    
    Returns:
        컬럼 이름 리스트
    """
    try:
        columns_check = text("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = :schema 
            AND TABLE_NAME = :table_name
        """)
        result = conn.execute(columns_check, {"schema": schema, "table_name": table_name})
        return [row.COLUMN_NAME for row in result.fetchall()]
    except Exception as e:
        logger.warning(f"⚠️ 컬럼 조회 실패 ({table_name}): {str(e)}")
        return []

def get_order_by_clause(columns: list, table_name: str = "") -> str:
    """
    정렬 컬럼 결정 (no > id > created_at 우선순위)
    
    Args:
        columns: 컬럼 이름 리스트
        table_name: 테이블 이름 (로깅용)
    
    Returns:
        ORDER BY 절 (예: "ORDER BY no DESC")
    """
    if 'no' in columns:
        return "ORDER BY no DESC"
    elif 'id' in columns:
        return "ORDER BY id DESC"
    elif 'created_at' in columns:
        return "ORDER BY created_at DESC"
    else:
        if table_name:
            logger.warning(f"⚠️ {table_name} 테이블에 정렬 컬럼을 찾을 수 없습니다. 최신 데이터가 아닐 수 있습니다.")
        return ""

def table_exists(conn, table_name: str, schema: str = "main") -> bool:
    """
    테이블 존재 여부 확인
    
    Args:
        conn: SQLAlchemy 연결 객체
        table_name: 테이블 이름
        schema: 스키마 이름 (기본값: "main")
    
    Returns:
        테이블 존재 여부
    """
    try:
        table_check = text("""
            SELECT COUNT(*) as count
            FROM information_schema.tables 
            WHERE table_schema = :schema 
            AND table_name = :table_name
        """)
        result = conn.execute(table_check, {"schema": schema, "table_name": table_name})
        return result.fetchone().count > 0
    except Exception as e:
        logger.warning(f"⚠️ 테이블 존재 여부 확인 실패 ({table_name}): {str(e)}")
        return False

def check_and_add_user_no_column(conn, table_name: str, schema: str = "main") -> bool:
    """
    테이블에 user_no 컬럼이 있는지 확인하고 없으면 추가
    
    Args:
        conn: SQLAlchemy 연결 객체
        table_name: 테이블 이름
        schema: 스키마 이름 (기본값: "main")
    
    Returns:
        user_no 컬럼 존재 여부 (추가했거나 이미 있으면 True)
    """
    try:
        column_check = text("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = :schema 
            AND TABLE_NAME = :table_name
            AND COLUMN_NAME = 'user_no'
        """)
        has_user_no = conn.execute(column_check, {"schema": schema, "table_name": table_name}).fetchone() is not None
        
        if not has_user_no:
            alter_query = text(f"ALTER TABLE {table_name} ADD COLUMN user_no INT DEFAULT NULL")
            conn.execute(alter_query)
            conn.commit()
            logger.info(f"✅ {table_name} 테이블에 user_no 컬럼 추가 완료")
            return True
        
        return True
    except Exception as e:
        logger.warning(f"⚠️ {table_name} 테이블 user_no 컬럼 확인/추가 실패: {str(e)}")
        return False

def execute_query_with_params(conn, query: text, params: dict = None):
    """
    쿼리 파라미터가 있으면 파라미터와 함께 실행, 없으면 그냥 실행
    
    Args:
        conn: SQLAlchemy 연결 객체
        query: SQL 쿼리
        params: 쿼리 파라미터 (선택사항)
    
    Returns:
        쿼리 실행 결과
    """
    if params:
        return conn.execute(query, params)
    else:
        return conn.execute(query)

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

def safe_json_read(file_path: str) -> list:
    """
    파일 잠금을 사용하여 JSON 파일을 안전하게 읽기
    
    Returns:
        JSON 파일 내용 (리스트 또는 딕셔너리), 파일이 없거나 오류 시 빈 리스트/딕셔너리
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
                    return data
            return []
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.warning(f"⚠️ JSON 파일 읽기 실패 ({file_path}): {str(e)}")
            return []

def safe_json_write(file_path: str, data: list, default_user_no: Optional[int] = None):
    """
    파일 잠금을 사용하여 JSON 파일을 안전하게 쓰기
    
    Args:
        file_path: 파일 경로
        data: 저장할 데이터 (리스트 또는 딕셔너리)
        default_user_no: 기본 user_no (데이터가 딕셔너리이고 user_no가 없을 때 사용)
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
# ai_thermal_model_final.pkl 파일 경로 (server 디렉토리에 있음)
MODEL_FILE = os.path.join(BASE_DIR, 'ai_thermal_model_final.pkl')

model = None
model_loaded = False

def load_model():
    """모델/함수 로드 - pickle 파일에서 로드"""
    global model, model_loaded
    if model is not None:
        model_loaded = True
        return model
    
    # pickle 파일에서 로드 시도
    if not os.path.exists(MODEL_FILE):
        logger.warning(f"⚠️ 모델 파일을 찾을 수 없습니다: {MODEL_FILE}")
        return None
    
    try:
        import pickle
        
        # pickle 파일에서 함수 로드 시도
        with open(MODEL_FILE, 'rb') as f:
            loaded_obj = pickle.load(f)
        
        # 함수인지 확인
        if callable(loaded_obj) and not hasattr(loaded_obj, 'predict'):
            # 함수를 모델로 사용
            model = loaded_obj
            model_loaded = True
            logger.info("✅ 예측 함수 로드 성공! (pickle)")
            return model
        else:
            # 모델 객체인 경우
            model = loaded_obj
            model_loaded = True
            logger.info("✅ 모델 로드 성공! (pickle)")
            return model
    except Exception as e1:
        logger.error(f"❌ pickle 로드 실패: {e1}")
        try:
            # joblib로 시도
            model = joblib.load(MODEL_FILE)
            model_loaded = True
            logger.info("✅ 모델 로드 성공! (joblib)")
            return model
        except Exception as e2:
            logger.error(f"❌ joblib 로드 실패: {e2}")
            return None

# 서버 시작 시 모델 로드
model = load_model()

# ==================== 피부온도 분류 기준 설정 ====================
# 사용자별로 분리된 딕셔너리로 관리
# 구조: {user_no: {"cold": float, "hot": float}}
user_thresholds = {}  # 사용자별 피부온도 분류 기준

# 기본값
DEFAULT_COLD_THRESHOLD = 34.5  # 추움 분류 기준
DEFAULT_HOT_THRESHOLD = 35.6    # 더움 분류 기준

def get_user_thresholds(user_no: Optional[int] = None) -> Tuple[float, float]:
    """
    사용자별 피부온도 분류 기준 가져오기 (없으면 기본값 반환)
    
    Args:
        user_no: 사용자 번호 (선택사항)
    
    Returns:
        (cold_threshold, hot_threshold)
    """
    if user_no is None:
        return DEFAULT_COLD_THRESHOLD, DEFAULT_HOT_THRESHOLD
    
    if user_no in user_thresholds:
        thresholds = user_thresholds[user_no]
        return thresholds.get("cold", DEFAULT_COLD_THRESHOLD), thresholds.get("hot", DEFAULT_HOT_THRESHOLD)
    
    # 기본값 반환
    return DEFAULT_COLD_THRESHOLD, DEFAULT_HOT_THRESHOLD

def set_user_thresholds(user_no: int, cold_threshold: float, hot_threshold: float):
    """
    사용자별 피부온도 분류 기준 설정
    
    Args:
        user_no: 사용자 번호
        cold_threshold: 추움 분류 기준
        hot_threshold: 더움 분류 기준
    """
    user_thresholds[user_no] = {
        "cold": cold_threshold,
        "hot": hot_threshold
    }
    logger.info(f"🔄 사용자별 피부온도 분류 기준 설정 (user_no={user_no}): COLD={cold_threshold}°C, HOT={hot_threshold}°C")

# 에어컨 제어 모듈 import
# IoT 폴더의 모듈 import를 위한 경로 추가
IOT_MODULE_PATH = os.path.join(PROJECT_ROOT, 'android', 'plus', 'IoT')
sys.path.insert(0, IOT_MODULE_PATH)

AIR_CONDITIONER_AVAILABLE = False
try:
    from airconditional import (
        get_air_conditioner_state,
        set_temperature,
        set_job_mode,
        set_wind_strength,
        set_power,
        set_timer,
        AIR_CONDITIONER_DEVICE_ID
    )
    # test.py에서 get_devices 함수 import
    from test import get_devices, generate_device_api_header
    AIR_CONDITIONER_AVAILABLE = True
    logger.info("✅ 에어컨 모듈 로드 성공 (PAT 토큰 등록과는 독립적으로 동작합니다)")
except ImportError as e:
    logger.warning(f"⚠️  에어컨 모듈을 불러올 수 없습니다: {e}")
    logger.info("ℹ️  PAT 토큰 등록 기능은 정상적으로 동작합니다 (에어컨 모듈과 독립적)")
    AIR_CONDITIONER_AVAILABLE = False

# 사용자별 PAT 토큰과 디바이스 ID 저장소
# 이전에는 메모리(딕셔너리)에만 저장되어 서버 재시작 시 사라졌지만,
# 이제는 DB에 저장하여 영구 보존됩니다.
# 메모리 캐시도 유지하여 빠른 접근을 위해 사용
user_iot_devices = {}  # 메모리 캐시 (빠른 접근용)

def init_iot_devices_table():
    """IoT 디바이스 등록 테이블 초기화 (없으면 생성, 있으면 컬럼 확인 및 추가)"""
    try:
        with engine.connect() as conn:
            # 테이블 존재 여부 확인
            table_check = text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                AND TABLE_NAME = 'iot_devices'
            """)
            has_table = conn.execute(table_check).fetchone().count > 0
            
            if not has_table:
                # 테이블 생성
                create_table_query = text("""
                    CREATE TABLE IF NOT EXISTS iot_devices (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(100) NOT NULL,
                        pat_token TEXT NOT NULL,
                        device_id VARCHAR(255) NOT NULL,
                        device_name VARCHAR(255),
                        model_name VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY unique_user_device (user_id, device_id),
                        UNIQUE KEY unique_device_id (device_id)
                    )
                """)
                conn.execute(create_table_query)
                conn.commit()
                logger.info("✅ iot_devices 테이블 생성 완료 (device_id UNIQUE 제약 포함)")
            else:
                logger.info("✅ iot_devices 테이블 이미 존재 - 컬럼 확인 중...")
                # 컬럼 존재 여부 확인 및 추가
                columns_to_check = [
                    ('device_name', 'VARCHAR(255)'),
                    ('model_name', 'VARCHAR(255)'),
                    ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                    ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
                ]
                
                for column_name, column_type in columns_to_check:
                    column_check = text("""
                        SELECT COUNT(*) as count
                        FROM information_schema.columns 
                        WHERE table_schema = DATABASE()
                        AND TABLE_NAME = 'iot_devices'
                        AND COLUMN_NAME = :column_name
                    """)
                    result = conn.execute(column_check, {'column_name': column_name})
                    has_column = result.fetchone().count > 0
                    
                    if not has_column:
                        logger.info(f"📝 iot_devices 테이블에 {column_name} 컬럼 추가 중...")
                        if column_name in ['created_at', 'updated_at']:
                            alter_query = text(f"ALTER TABLE iot_devices ADD COLUMN {column_name} {column_type}")
                        else:
                            alter_query = text(f"ALTER TABLE iot_devices ADD COLUMN {column_name} {column_type}")
                        conn.execute(alter_query)
                        conn.commit()
                        logger.info(f"✅ {column_name} 컬럼 추가 완료")
                    else:
                        logger.info(f"✅ {column_name} 컬럼 이미 존재")
                
                # UNIQUE KEY 확인 및 추가
                unique_key_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.table_constraints 
                    WHERE table_schema = DATABASE()
                    AND TABLE_NAME = 'iot_devices'
                    AND CONSTRAINT_NAME = 'unique_user_device'
                """)
                result = conn.execute(unique_key_check)
                has_unique_key = result.fetchone().count > 0
                
                if not has_unique_key:
                    logger.info("📝 iot_devices 테이블에 UNIQUE KEY 추가 중...")
                    try:
                        alter_query = text("ALTER TABLE iot_devices ADD UNIQUE KEY unique_user_device (user_id, device_id)")
                        conn.execute(alter_query)
                        conn.commit()
                        logger.info("✅ UNIQUE KEY 추가 완료")
                    except Exception as e:
                        logger.warning(f"⚠️ UNIQUE KEY 추가 실패 (이미 존재할 수 있음): {str(e)}")
                
                # device_id UNIQUE 제약 확인 및 추가 (같은 기기는 한 명만 등록 가능)
                device_id_unique_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.table_constraints 
                    WHERE table_schema = DATABASE()
                    AND TABLE_NAME = 'iot_devices'
                    AND CONSTRAINT_NAME = 'unique_device_id'
                """)
                result = conn.execute(device_id_unique_check)
                has_device_id_unique = result.fetchone().count > 0
                
                if not has_device_id_unique:
                    logger.info("📝 iot_devices 테이블에 device_id UNIQUE 제약 추가 중...")
                    try:
                        alter_query = text("ALTER TABLE iot_devices ADD UNIQUE KEY unique_device_id (device_id)")
                        conn.execute(alter_query)
                        conn.commit()
                        logger.info("✅ device_id UNIQUE 제약 추가 완료 (같은 기기는 한 명만 등록 가능)")
                    except Exception as e:
                        logger.warning(f"⚠️ device_id UNIQUE 제약 추가 실패 (이미 존재할 수 있음): {str(e)}")
    except Exception as e:
        logger.error(f"❌ iot_devices 테이블 초기화 실패: {str(e)}")
        import traceback
        logger.error(f"❌ 상세 에러: {traceback.format_exc()}")

def load_iot_devices_from_db():
    """DB에서 등록된 IoT 디바이스 정보를 메모리로 로드"""
    global user_iot_devices
    user_iot_devices = {}
    
    try:
        with engine.connect() as conn:
            # 먼저 테이블에 데이터가 있는지 확인
            count_query = text("SELECT COUNT(*) as count FROM iot_devices")
            count_result = conn.execute(count_query)
            total_count = count_result.fetchone().count
            logger.info(f"🔍 iot_devices 테이블에 총 {total_count}개의 레코드가 있습니다.")
            
            if total_count == 0:
                logger.info("📭 iot_devices 테이블이 비어있습니다.")
                return
            
            # DB에서 모든 IoT 디바이스 정보 조회
            query = text("""
                SELECT user_id, pat_token, device_id, device_name, model_name
                FROM iot_devices
                ORDER BY updated_at DESC
            """)
            result = conn.execute(query)
            rows = result.fetchall()
            
            logger.info(f"📥 DB에서 {len(rows)}개의 레코드를 조회했습니다.")
            
            # 메모리 캐시에 로드 (같은 user_id가 여러 개면 최신 것만 사용)
            for row in rows:
                user_id = row.user_id
                # 이미 있으면 스킵 (최신 것이 우선)
                if user_id not in user_iot_devices:
                    user_iot_devices[user_id] = {
                        'pat_token': row.pat_token,
                        'device_id': row.device_id,
                        'device_name': row.device_name or '',
                        'model_name': row.model_name or ''
                    }
                    logger.info(f"✅ 메모리 캐시에 로드: user_id={user_id}, device_id={row.device_id[:20] if row.device_id else 'None'}..., device_name={row.device_name or 'None'}")
            
            logger.info(f"✅ DB에서 {len(user_iot_devices)}개의 사용자 IoT 디바이스 정보 로드 완료")
    except Exception as e:
        logger.error(f"❌ DB에서 IoT 디바이스 정보 로드 실패: {str(e)}")
        import traceback
        logger.error(f"❌ 상세 에러: {traceback.format_exc()}")
        logger.info("🔄 메모리 캐시 초기화만 수행 (빈 상태로 시작)")

def save_iot_device_to_db(user_id: str, pat_token: str, device_id: str, device_name: str, model_name: str = ''):
    """IoT 디바이스 등록 정보를 DB와 메모리에 저장 (같은 기기는 한 명만 등록 가능)"""
    try:
        logger.info(f"💾 IoT 디바이스 DB 저장 시작: user_id={user_id}, device_id={device_id[:20] if device_id else 'None'}..., device_name={device_name}")
        
        with engine.connect() as conn:
            # 먼저 같은 device_id가 다른 사용자에게 등록되어 있는지 확인
            existing_device_check = text("""
                SELECT user_id, device_name 
                FROM iot_devices 
                WHERE device_id = :device_id
            """)
            existing_result = conn.execute(existing_device_check, {'device_id': device_id})
            existing_device = existing_result.fetchone()
            
            if existing_device:
                existing_user_id = existing_device.user_id
                existing_device_name = existing_device.device_name or '알 수 없음'
                
                # 같은 사용자가 다시 등록하는 경우는 허용 (업데이트)
                if existing_user_id == user_id:
                    logger.info(f"🔄 같은 사용자가 기기 재등록: user_id={user_id}, device_id={device_id[:20]}...")
                else:
                    # [테스트 모드] 다른 사용자가 이미 등록한 경우에도 허용 (기존 레코드 삭제 후 새로 등록)
                    logger.warning(f"⚠️ [테스트 모드] 기기 중복 등록 허용: user_id={user_id}, device_id={device_id[:20]}..., 기존 등록자: {existing_user_id} (기존 레코드 삭제 후 새로 등록)")
                    # 기존 레코드 삭제
                    delete_query = text("DELETE FROM iot_devices WHERE device_id = :device_id")
                    conn.execute(delete_query, {'device_id': device_id})
                    conn.commit()
                    logger.info(f"🗑️ 기존 등록 정보 삭제 완료: device_id={device_id[:20]}...")
                    # 에러 발생하지 않고 계속 진행
                    # error_msg = f"이 기기는 이미 다른 사용자({existing_user_id})에게 등록되어 있습니다. (기기명: {existing_device_name})"
                    # raise HTTPException(status_code=409, detail=error_msg)
            
            # UPSERT 쿼리 (이미 있으면 업데이트, 없으면 삽입)
            query = text("""
                INSERT INTO iot_devices (user_id, pat_token, device_id, device_name, model_name, updated_at)
                VALUES (:user_id, :pat_token, :device_id, :device_name, :model_name, NOW())
                ON DUPLICATE KEY UPDATE
                    pat_token = VALUES(pat_token),
                    device_id = VALUES(device_id),
                    device_name = VALUES(device_name),
                    model_name = VALUES(model_name),
                    updated_at = NOW()
            """)
            result = conn.execute(query, {
                'user_id': user_id,
                'pat_token': pat_token,
                'device_id': device_id,
                'device_name': device_name,
                'model_name': model_name
            })
            conn.commit()
            
            # 저장 확인
            check_query = text("""
                SELECT user_id, device_id, device_name FROM iot_devices WHERE user_id = :user_id
            """)
            check_result = conn.execute(check_query, {'user_id': user_id})
            saved_row = check_result.fetchone()
            
            logger.info(f"🔍 DB 저장 확인 쿼리 실행: user_id={user_id}")
            
            if saved_row:
                logger.info(f"✅ IoT 디바이스 등록 정보 DB 저장 완료 및 확인: user_id={user_id}, device_id={saved_row.device_id[:20] if saved_row.device_id else 'None'}..., device_name={saved_row.device_name}")
            else:
                logger.warning(f"⚠️ IoT 디바이스 DB 저장 후 확인 실패: user_id={user_id} - 저장된 레코드를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"❌ IoT 디바이스 DB 저장 실패: user_id={user_id}, error={str(e)}")
        import traceback
        logger.error(f"❌ 상세 에러: {traceback.format_exc()}")
        raise
    
    # 메모리 캐시도 업데이트
    user_iot_devices[user_id] = {
        'pat_token': pat_token,
        'device_id': device_id,
        'device_name': device_name,
        'model_name': model_name
    }
    logger.info(f"✅ IoT 디바이스 등록 정보 메모리 캐시 업데이트 완료: {user_id}")

# ==================== 쾌적 온도 계산 함수 ====================

def calculate_comfort_temperature(gender: str, age: int, bmi: float) -> tuple[float, float]:
    """
    성별, 나이, BMI 기반 실내 쾌적 온도 범위 계산
    
    Args:
        gender: 성별 ('F': 여성, 'M': 남성)
        age: 나이
        bmi: 체질량지수
    
    Returns:
        (min_temp, max_temp): 쾌적 온도 범위 (최소 온도, 최대 온도)
    """
    # 기본 온도 범위
    base_min, base_max = 19.0, 21.0
    
    # 1️⃣ 성별 조정
    if gender.upper() == 'F':  # 여성
        delta_gender = 1.0
    else:  # 남성 ('M')
        delta_gender = 0.0
    
    # 2️⃣ 나이 조정
    if 60 <= age < 70:
        delta_age = 0.5
    elif 70 <= age <= 80:
        delta_age = 1.0
    else:
        delta_age = 0.0
    
    # 3️⃣ BMI 조정
    # BMI 분류: 저체중(<18.5), 정상(18.5-23), 과체중(23-25), 비만(>=25)
    if bmi < 18.5:
        delta_bmi = 1.0  # 저체중 +1도
    elif 18.5 <= bmi < 23.0:
        delta_bmi = 0.0  # 정상체중 +0도
    elif 23.0 <= bmi < 25.0:
        delta_bmi = -0.5  # 과체중 -0.5도
    else:  # bmi >= 25.0
        delta_bmi = -1.0  # 비만 -1도
    
    # 최종 온도 계산
    min_temp = base_min + delta_gender + delta_age + delta_bmi
    max_temp = base_max + delta_gender + delta_age + delta_bmi
    
    return round(min_temp, 1), round(max_temp, 1)

# ==================== 모델 예측 함수 ====================

def predict_temperature_with_model(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
    """
    체온 예측 함수 (pandas DataFrame 기반 또는 저장된 함수 사용)
    
    Parameters:
    - hr_mean: 평균 심박수
    - hrv_sdnn: 심박변이도 (SDNN)
    - bmi: 체질량지수
    - mean_sa02: 평균 산소포화도
    - gender: 성별 (0: 여성, 1: 남성 또는 'F': 여성, 'M': 남성)
    - age: 나이
    
    Returns:
    - 예측된 체온 (°C)
    """
    if not model_loaded or model is None:
        raise ValueError("모델이 로드되지 않았습니다.")
    
    # 성별 변환 (0/1 -> F/M 또는 그대로)
    if isinstance(gender, (int, float)):
        gender_str = 'F' if gender == 0 else 'M'
    else:
        gender_str = str(gender)
    
    # 모델이 함수인 경우 (pickle로 저장된 함수)
    if callable(model) and not hasattr(model, 'predict'):
        try:
            # 저장된 함수 직접 호출
            temp_pred = model(hr_mean, hrv_sdnn, bmi, mean_sa02, gender_str, age)
            return float(temp_pred)
        except Exception as e:
            logger.error(f"저장된 함수 호출 실패: {e}")
            raise
    
    # 모델 객체인 경우 (기존 방식)
    # 파생 피처 계산
    hrv_hr_ratio = hrv_sdnn / hr_mean if hr_mean > 0 else 0
    bmi_hr_interaction = bmi * hr_mean
    age_bmi_interaction = age * bmi
    age_hrv_ratio = age / (hrv_sdnn + 1) if hrv_sdnn > 0 else 0  # 0으로 나누기 방지
    
    # pandas DataFrame으로 데이터 준비 (Flask 서버와 동일한 형식)
    try:
        data = pd.DataFrame({
            'bmi': [bmi],
            'mean_sa02': [mean_sa02], 
            'HRV_SDNN': [hrv_sdnn],
            'hrv_hr_ratio': [hrv_hr_ratio],
            'bmi_hr_interaction': [bmi_hr_interaction],
            'age': [age],
            'age_bmi_interaction': [age_bmi_interaction],
            'age_hrv_ratio': [age_hrv_ratio],
            'gender': [gender_str]
        })
        
        # 예측
        temp_pred = model.predict(data)[0]
        return float(temp_pred)
    except Exception as e:
        logger.error(f"pandas DataFrame 예측 실패, numpy 배열로 재시도: {e}")
        # pandas 실패 시 numpy 배열로 재시도 (기존 server.py 방식)
        age_hrv_ratio = age / (hrv_sdnn + 1e-8) if hrv_sdnn > 0 else 0
        age_bmi_interaction = age * bmi
        bmi_hr_interaction = bmi * hr_mean
        hrv_hr_ratio = hrv_sdnn / (hr_mean + 1e-8) if hr_mean > 0 else 0
        
        # 성별을 숫자로 변환 (0: 여성, 1: 남성)
        gender_num = 0 if gender_str == 'F' else 1
        
        X = np.array([[
            hr_mean,
            hrv_sdnn,
            gender_num,
            bmi,
            age,
            mean_sa02,
            age_hrv_ratio,
            age_bmi_interaction,
            bmi_hr_interaction,
            hrv_hr_ratio
        ]])
        
        temp_pred = model.predict(X)[0]
        return float(temp_pred)

# ==================== Pydantic 모델 ====================

class HealthData(BaseModel):
    heartRate: Optional[float] = None
    HRV: Optional[float] = None
    oxygenSaturation: Optional[float] = None
    bmi: Optional[float] = None
    age: Optional[float] = None
    gender: Optional[float] = None  # 0: 여성, 1: 남성

class PredictRequest(BaseModel):
    hr_mean: float
    hrv_sdnn: float
    bmi: float
    mean_sa02: float
    gender: str  # 'M' 또는 'F'
    age: int

class AirConditionerControlRequest(BaseModel):
    action: str
    target_temperature: Optional[float] = None
    unit: Optional[str] = 'C'
    mode: Optional[str] = None
    strength: Optional[str] = None
    power_on: Optional[bool] = True

class TemperatureFeedbackRequest(BaseModel):
    feedback: str  # 'hot', 'cold', 'comfortable'
    date: Optional[str] = None  # ISO format date string

# ==================== 인증 관련 모델 ====================

class RegisterRequest(BaseModel):
    id: str  # 이메일 또는 사용자 아이디
    password: str
    device: Optional[str] = None  # IoT 디바이스 정보 (PAT 토큰 또는 device_id)

class LoginRequest(BaseModel):
    id: str  # 이메일 또는 사용자 아이디
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_no: int

class AndroidAppHealthMetrics(BaseModel):
    """Android 앱 건강 지표 모델"""
    timestamp: Optional[str] = None
    package_name: Optional[str] = None
    cpu_usage_percent: Optional[float] = None
    cpu_user_percent: Optional[float] = None
    cpu_kernel_percent: Optional[float] = None
    memory_pressure_some: Optional[float] = None
    memory_pressure_full: Optional[float] = None
    io_pressure_some: Optional[float] = None
    io_pressure_full: Optional[float] = None
    cpu_pressure_some: Optional[float] = None
    cpu_pressure_full: Optional[float] = None
    anr_count: Optional[int] = None
    connectivity_errors: Optional[int] = None
    load_avg_1min: Optional[float] = None
    load_avg_5min: Optional[float] = None
    load_avg_15min: Optional[float] = None
    error_log: Optional[str] = None

# ==================== 인증 API ====================

@app.post("/auth/register", response_model=TokenResponse)
async def register(data: RegisterRequest):
    """
    회원가입 API
    """
    try:
        with engine.connect() as conn:
            # 이메일 중복 확인
            check_query = text("""
                SELECT no FROM login WHERE id = :id
            """)
            result = conn.execute(check_query, {"id": data.id})
            existing_user = result.fetchone()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 등록된 아이디입니다."
                )
            
            # 비밀번호 해싱
            hashed_password = get_password_hash(data.password)
            
            # login 테이블에 device 컬럼이 있는지 확인하고 없으면 추가
            try:
                column_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE()
                    AND TABLE_NAME = 'login'
                    AND COLUMN_NAME = 'device'
                """)
                result = conn.execute(column_check)
                has_device_column = result.fetchone().count > 0
                
                if not has_device_column:
                    logger.info("📝 login 테이블에 device 컬럼 추가 중...")
                    alter_query = text("ALTER TABLE login ADD COLUMN device VARCHAR(255) DEFAULT NULL")
                    conn.execute(alter_query)
                    conn.commit()
                    logger.info("✅ login 테이블 device 컬럼 추가 완료")
            except Exception as e:
                logger.warning(f"⚠️ login 테이블 device 컬럼 확인/추가 실패: {str(e)}")
            
            # 사용자 등록
            if data.device:
                insert_query = text("""
                    INSERT INTO login (id, password, device)
                    VALUES (:id, :password, :device)
                """)
                conn.execute(insert_query, {
                    "id": data.id,
                    "password": hashed_password,
                    "device": data.device
                })
            else:
                insert_query = text("""
                    INSERT INTO login (id, password)
                    VALUES (:id, :password)
                """)
                conn.execute(insert_query, {
                    "id": data.id,
                    "password": hashed_password
                })
            conn.commit()
            
            # 등록된 사용자 정보 가져오기
            get_user_query = text("""
                SELECT no FROM login WHERE id = :id
            """)
            user_result = conn.execute(get_user_query, {"id": data.id})
            user = user_result.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="회원가입 후 사용자 정보를 가져올 수 없습니다."
                )
            
            # new_skinthreshold 테이블에 사용자별 기본값 저장 (처음 한 번만)
            try:
                # 테이블 존재 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'new_skinthreshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if not table_exists:
                    # 테이블이 없으면 생성
                    create_table = text("""
                        CREATE TABLE IF NOT EXISTS new_skinthreshold (
                            no INT AUTO_INCREMENT PRIMARY KEY,
                            min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                            max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6,
                            user_no INT DEFAULT NULL
                        )
                    """)
                    conn.execute(create_table)
                    conn.commit()
                    logger.info("✅ new_skinthreshold 테이블 생성 완료")
                
                # user_no 컬럼 확인 및 추가
                check_and_add_user_no_column(conn, "new_skinthreshold")
                
                # 해당 사용자의 레코드가 있는지 확인
                user_filter, query_params = build_user_filter(user.no, allow_null=False)
                if user_filter:
                    user_filter = "WHERE 1=1 " + user_filter.replace("AND", "")
                
                check_threshold = text(f"SELECT COUNT(*) as count FROM new_skinthreshold {user_filter}")
                result = execute_query_with_params(conn, check_threshold, query_params)
                threshold_count = result.fetchone().count
                
                # 레코드가 없을 때만 삽입 (처음 한 번만)
                if threshold_count == 0:
                    try:
                        insert_threshold = text("""
                            INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, user_no)
                            VALUES (:min_skinthreshold, :max_skinthreshold, :user_no)
                        """)
                        insert_params = {
                            'min_skinthreshold': 34.6,
                            'max_skinthreshold': 35.6,
                            'user_no': user.no
                        }
                        conn.execute(insert_threshold, insert_params)
                        conn.commit()
                        logger.info(f"✅ new_skinthreshold 테이블에 기본값 저장 (회원가입): 34.6~35.6°C, user_no={user.no}")
                    except Exception as e:
                        logger.warning(f"new_skinthreshold 저장 실패: {e}")
                else:
                    logger.debug(f"📋 new_skinthreshold 테이블에 이미 임계값이 저장되어 있습니다. (건너뜀, user_no={user.no})")
            except Exception as e:
                logger.warning(f"⚠️ new_skinthreshold 초기화 실패 (무시): {e}")
            
            # JWT 토큰 생성
            access_token = create_access_token(data={"sub": str(user.no)})
            
            logger.info(f"✅ 회원가입 성공: {data.id} (no: {user.no})")
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                user_no=user.no
            )
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"❌ 회원가입 실패: {error_detail}")
        logger.error(f"❌ 회원가입 실패 상세:\n{error_traceback}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회원가입 실패: {error_detail}"
        )

@app.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """
    로그인 API
    """
    try:
        with engine.connect() as conn:
            # 사용자 조회
            query = text("""
                SELECT no, id, CAST(password AS CHAR) as password FROM login WHERE id = :id
            """)
            result = conn.execute(query, {"id": data.id})
            user = result.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="아이디 또는 비밀번호가 올바르지 않습니다."
                )
            
            # 비밀번호 검증 (DB에서 가져온 값을 문자열로 변환)
            stored_password = str(user.password) if user.password is not None else ""
            logger.debug(f"🔍 로그인 시도 - 사용자: {data.id}, 저장된 비밀번호 타입: {type(user.password)}, 길이: {len(stored_password) if stored_password else 0}")
            
            if not stored_password or not stored_password.strip():
                logger.error(f"❌ 저장된 비밀번호가 비어있음: {data.id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="아이디 또는 비밀번호가 올바르지 않습니다."
                )
            
            if not verify_password(data.password, stored_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="아이디 또는 비밀번호가 올바르지 않습니다."
                )
            
            # 마지막 로그인 시간 업데이트 (컬럼이 있다면)
            try:
                update_query = text("""
                    UPDATE login SET last_login = NOW() WHERE no = :no
                """)
                conn.execute(update_query, {"no": user.no})
                conn.commit()
            except Exception as e:
                # last_login 컬럼이 없어도 계속 진행
                logger.debug(f"last_login 업데이트 실패 (무시): {e}")
            
            # new_skinthreshold 테이블에 사용자별 기본값 저장 (처음 한 번만, room_threshold와 일관성 유지)
            try:
                logger.info(f"🔍 new_skinthreshold 초기화 시작 (user_no={user.no})")
                
                # 테이블 존재 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'new_skinthreshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                logger.info(f"🔍 new_skinthreshold 테이블 존재 여부: {table_exists}")
                
                if not table_exists:
                    # 테이블이 없으면 생성
                    create_table = text("""
                        CREATE TABLE IF NOT EXISTS new_skinthreshold (
                            no INT AUTO_INCREMENT PRIMARY KEY,
                            min_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 34.6,
                            max_skinthreshold DECIMAL(4,1) NOT NULL DEFAULT 35.6,
                            user_no INT DEFAULT NULL
                        )
                    """)
                    conn.execute(create_table)
                    conn.commit()
                    logger.info("✅ new_skinthreshold 테이블 생성 완료")
                
                # user_no 컬럼 확인 및 추가
                check_and_add_user_no_column(conn, "new_skinthreshold")
                
                # 해당 사용자의 레코드가 있는지 확인
                user_filter, query_params = build_user_filter(user.no, allow_null=False)
                logger.info(f"🔍 user_filter: {user_filter}, query_params: {query_params}")
                
                if user_filter:
                    # WHERE 절 구성
                    where_clause = f"WHERE {user_filter.replace('AND ', '')}"
                else:
                    where_clause = f"WHERE user_no = :user_no"
                    query_params = {'user_no': user.no}
                
                check_threshold = text(f"SELECT COUNT(*) as count FROM new_skinthreshold {where_clause}")
                logger.info(f"🔍 실행할 쿼리: SELECT COUNT(*) as count FROM new_skinthreshold {where_clause}")
                result = execute_query_with_params(conn, check_threshold, query_params)
                threshold_count = result.fetchone().count
                logger.info(f"🔍 기존 레코드 수: {threshold_count}")
                
                # 레코드가 없을 때만 삽입 (처음 한 번만)
                if threshold_count == 0:
                    try:
                        insert_threshold = text("""
                            INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, user_no)
                            VALUES (:min_skinthreshold, :max_skinthreshold, :user_no)
                        """)
                        insert_params = {
                            'min_skinthreshold': 34.6,
                            'max_skinthreshold': 35.6,
                            'user_no': user.no
                        }
                        conn.execute(insert_threshold, insert_params)
                        conn.commit()
                        logger.info(f"✅ new_skinthreshold 테이블에 기본값 저장 (로그인): 34.6~35.6°C, user_no={user.no}")
                    except Exception as e:
                        logger.error(f"❌ new_skinthreshold 저장 실패: {e}")
                        import traceback
                        logger.error(f"❌ 저장 실패 상세:\n{traceback.format_exc()}")
                else:
                    logger.info(f"📋 new_skinthreshold 테이블에 이미 임계값이 저장되어 있습니다. (건너뜀, user_no={user.no})")
            except Exception as e:
                logger.error(f"❌ new_skinthreshold 초기화 실패: {e}")
                import traceback
                logger.error(f"❌ 초기화 실패 상세:\n{traceback.format_exc()}")
            
            # JWT 토큰 생성
            access_token = create_access_token(data={"sub": str(user.no)})
            
            logger.info(f"✅ 로그인 성공: {data.id} (no: {user.no})")
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                user_no=user.no
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 로그인 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그인 실패: {str(e)}"
        )

@app.get("/auth/me")
async def get_current_user_info(user_no: int = Depends(verify_token)):
    """
    현재 로그인한 사용자 정보 조회 API
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT no, id FROM login WHERE no = :no
            """)
            result = conn.execute(query, {"no": user_no})
            user = result.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="사용자를 찾을 수 없습니다."
                )
            
            return {
                "user_no": user.no,
                "id": user.id
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 사용자 정보 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 정보 조회 실패: {str(e)}"
        )

@app.get("/auth/me")
async def get_current_user(user_no: int = Depends(verify_token)):
    """
    현재 로그인한 사용자 정보 조회 (내부 함수)
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT no, id FROM login WHERE no = :no
            """)
            result = conn.execute(query, {"no": user_no})
            user = result.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="사용자를 찾을 수 없습니다."
                )
            
            return {
                "user_no": user.no,
                "id": user.id
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 사용자 정보 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 정보 조회 실패: {str(e)}"
        )

@app.get("/auth/me")
async def get_current_user_info(user_no: int = Depends(verify_token)):
    """
    현재 로그인한 사용자 정보 조회 API
    """
    return await get_current_user(user_no)

# ==================== Health Data API ====================

@app.post("/healthdata")
async def receive_health_data(data: HealthData, user_no: Optional[int] = Depends(verify_token_optional)):
    """
    HealthKit 데이터를 받아서 DB에 저장하고 모델로 예측
    user_no는 JWT 토큰에서 가져오며, 토큰이 없으면 None으로 처리
    """
    try:
        logger.info(f"💌 받은 데이터: {data.model_dump()}")
        
        # 필수 데이터 확인
        if data.heartRate is None or data.HRV is None or data.oxygenSaturation is None:
            raise HTTPException(status_code=400, detail="heartRate, HRV, oxygenSaturation은 필수입니다.")
        
        # 기본값 설정
        # gender: 0.0 또는 1.0을 'F' 또는 'M'으로 변환
        gender_value = data.gender if data.gender is not None else 0.0  # 기본값: 여성
        gender = 'F' if gender_value == 0.0 else 'M'  # 0.0: 여성(F), 1.0: 남성(M)
        bmi = data.bmi if data.bmi is not None else 0.0
        age = data.age if data.age is not None else 0.0
        
        logger.info(f"📊 처리된 데이터 - gender: {gender} (원본: {gender_value}), bmi: {bmi}, age: {age}")
        
        # 모델로 예측
        predicted_skin_temp = 0.0  # 기본값 설정 (데이터베이스 NOT NULL 제약 조건 대응)
        if model is not None:
            try:
                predicted_skin_temp = predict_temperature_with_model(
                    hr_mean=data.heartRate,
                    hrv_sdnn=data.HRV,
                    bmi=bmi,
                    mean_sa02=data.oxygenSaturation,
                    gender=gender,
                    age=age
                )
                logger.info(f"🔮 예측 결과: {predicted_skin_temp}")
            except Exception as e:
                logger.error(f"❌ 예측 실패: {str(e)}")
                logger.error(f"❌ 예측 실패 상세 - 입력 피처 수: 9, 모델 기대: 9")
                # 예측 실패 시 기본값 유지 (0.0)
        
        # DB에 데이터 저장
        comfort_min = None
        comfort_max = None
        
        with engine.connect() as conn:
            # 중복 데이터 체크: 최근 2분 이내 동일한 데이터가 있으면 건너뛰기
            date_column = None
            order_by = "ORDER BY 1 DESC"
            
            try:
                # 테이블 구조 확인
                columns = get_table_columns(conn, "predicted_results")
                logger.debug(f"📋 predicted_results 테이블 컬럼: {columns}")
                
                # 날짜 컬럼 찾기
                for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                    if col in columns or col.lower() in [c.lower() for c in columns]:
                        date_column = col
                        logger.info(f"✅ 날짜 컬럼 발견: {date_column}")
                        break
                
                # ORDER BY 절 생성
                if date_column:
                    order_by = f"ORDER BY {date_column} DESC"
                else:
                    logger.warning("⚠️ 날짜 컬럼을 찾을 수 없습니다. 중복 체크가 제한적일 수 있습니다.")
                    order_by = "ORDER BY 1 DESC"
                
                # 최근 2분 이내 동일한 데이터 확인 (MySQL 형식)
                if date_column:
                    duplicate_check_query = text(f"""
                        SELECT HR_mean, HRV_SDNN, mean_sa02, {date_column}
                        FROM predicted_results
                        WHERE HR_mean = :hr 
                          AND ABS(HRV_SDNN - :hrv) < 0.01
                          AND ABS(mean_sa02 - :o2) < 0.1
                          AND {date_column} >= DATE_SUB(NOW(), INTERVAL 2 MINUTE)
                        {order_by}
                        LIMIT 1
                    """)
                    logger.debug(f"🔍 중복 체크 쿼리 실행 (날짜 컬럼 사용: {date_column})")
                else:
                    # 날짜 컬럼이 없으면 최근 10개만 확인
                    duplicate_check_query = text("""
                        SELECT HR_mean, HRV_SDNN, mean_sa02
                        FROM predicted_results
                        WHERE HR_mean = :hr 
                          AND ABS(HRV_SDNN - :hrv) < 0.01
                          AND ABS(mean_sa02 - :o2) < 0.1
                        ORDER BY 1 DESC
                        LIMIT 10
                    """)
                    logger.debug("🔍 중복 체크 쿼리 실행 (날짜 컬럼 없음, 최근 10개 확인)")
                
                try:
                    duplicate_result = conn.execute(duplicate_check_query, {
                        'hr': data.heartRate,
                        'hrv': data.HRV,
                        'o2': data.oxygenSaturation
                    }).fetchone()
                    
                    if duplicate_result:
                        # 중복 데이터 발견
                        logger.info(f"⏭️ 중복 데이터 감지 - 최근 2분 이내 동일한 데이터가 있습니다. 건너뜀 (HR: {data.heartRate}, HRV: {data.HRV}, O2: {data.oxygenSaturation})")
                        print(f"⏭️ 중복 데이터 감지 - 건너뜀")
                        return {
                            "status": "ok",
                            "message": "Duplicate data skipped",
                            "predicted_skin_temp": predicted_skin_temp,
                            "duplicate": True
                        }
                    else:
                        logger.debug(f"✅ 중복 데이터 없음 - 계속 진행 (HR: {data.heartRate}, HRV: {data.HRV}, O2: {data.oxygenSaturation})")
                except Exception as dup_e:
                    # SQLite와 MySQL의 날짜 함수 차이 처리
                    logger.warning(f"⚠️ 중복 체크 실패 (계속 진행): {dup_e}")
                    import traceback
                    logger.error(f"❌ 중복 체크 실패 상세: {traceback.format_exc()}")
            except Exception as e:
                logger.warning(f"⚠️ 테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                import traceback
                logger.error(f"❌ 테이블 구조 확인 실패 상세: {traceback.format_exc()}")
                order_by = "ORDER BY 1 DESC"
            
            # 기존 사용자 정보 확인 (나이, BMI, 성별이 있는지)
            if 'order_by' not in locals():
                try:
                    columns_query = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns_result = conn.execute(columns_query)
                    columns = [row.COLUMN_NAME for row in columns_result]
                    
                    # 날짜 컬럼 찾기
                    date_column = None
                    for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                        if col in columns or col.lower() in [c.lower() for c in columns]:
                            date_column = col
                            break
                    
                    # ORDER BY 절 생성
                    if date_column:
                        order_by = f"ORDER BY {date_column} DESC"
                    else:
                        order_by = "ORDER BY 1 DESC"
                except Exception as e:
                    logger.warning(f"테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                    order_by = "ORDER BY 1 DESC"
            
            # predicted_results에서 기존 사용자 정보 확인 (나이, BMI, 성별만, user_no 필터링)
            user_filter, query_params = build_user_filter(user_no, allow_null=False)
            
            check_query = text(f"""
                SELECT age, bmi, gender
                FROM predicted_results
                WHERE age IS NOT NULL 
                  AND bmi IS NOT NULL 
                  AND gender IS NOT NULL
                  {user_filter}
                {order_by}
                LIMIT 1
            """)
            
            existing_user = execute_query_with_params(conn, check_query, query_params).fetchone()
            
            # room_threshold 테이블에서 기존 쾌적 온도 범위 확인
            try:
                if table_exists(conn, "room_threshold"):
                    # room_threshold에서 기존 임계값 확인 (user_no 필터링)
                    user_filter, query_params = build_user_filter(user_no, allow_null=False)
                    if user_filter:
                        user_filter = "WHERE 1=1 " + user_filter.replace("AND", "")
                    
                    threshold_query = text(f"SELECT min_temp, max_temp FROM room_threshold {user_filter} ORDER BY id DESC LIMIT 1")
                    threshold_result = execute_query_with_params(conn, threshold_query, query_params).fetchone()
                    
                    # 기존 사용자 정보가 있고, 나이/BMI/성별이 동일하고, room_threshold에 값이 있으면 사용
                    if existing_user and existing_user.age == age and existing_user.bmi == bmi and existing_user.gender == gender:
                        if threshold_result and threshold_result.min_temp is not None and threshold_result.max_temp is not None:
                            comfort_min = float(threshold_result.min_temp)
                            comfort_max = float(threshold_result.max_temp)
                            logger.info(f"📋 기존 쾌적 온도 범위 사용 (room_threshold): {comfort_min}~{comfort_max}°C, user_no={user_no}")
            except Exception as e:
                logger.warning(f"room_threshold 확인 실패: {e}")
            
            # 쾌적 온도 범위가 없으면 계산 (처음 입력이거나 정보가 변경된 경우)
            if comfort_min is None or comfort_max is None:
                comfort_min, comfort_max = calculate_comfort_temperature(gender, int(age), bmi)
                logger.info(f"🌡️ 쾌적 온도 범위 계산 (새로 계산): {comfort_min}~{comfort_max}°C (gender: {gender}, age: {int(age)}, bmi: {bmi})")
            
            # room_threshold 테이블에 임계값 저장 (처음 한 번만, 로그인한 사용자만)
            try:
                if table_exists(conn, "room_threshold"):
                    # user_no 컬럼이 없으면 추가
                    check_and_add_user_no_column(conn, "room_threshold")
                    
                    # user_no가 None이면 저장하지 않음 (로그인하지 않은 경우)
                    if user_no is not None:
                        # 테이블이 있으면 레코드가 있는지 확인 (user_no 필터링)
                        user_filter, query_params = build_user_filter(user_no, allow_null=False)
                        if user_filter:
                            user_filter = "WHERE 1=1 " + user_filter.replace("AND", "")
                        
                        check_threshold = text(f"SELECT COUNT(*) as count FROM room_threshold {user_filter}")
                        result = execute_query_with_params(conn, check_threshold, query_params)
                        threshold_count = result.fetchone().count
                        
                        # 레코드가 없을 때만 삽입 (처음 한 번만)
                        if threshold_count == 0:
                            try:
                                insert_threshold = text("""
                                    INSERT INTO room_threshold (min_temp, max_temp, user_no)
                                    VALUES (:min_temp, :max_temp, :user_no)
                                """)
                                insert_params = {
                                    'min_temp': comfort_min,
                                    'max_temp': comfort_max,
                                    'user_no': user_no
                                }
                                conn.execute(insert_threshold, insert_params)
                                conn.commit()
                                logger.info(f"✅ room_threshold 테이블에 임계값 저장 (처음 저장): {comfort_min}~{comfort_max}°C, user_no={user_no}")
                            except Exception as e:
                                logger.warning(f"room_threshold 저장 실패: {e}")
                        else:
                            logger.info(f"📋 room_threshold 테이블에 이미 임계값이 저장되어 있습니다. (건너뜀, user_no={user_no})")
                    else:
                        logger.warning("⚠️ user_no가 None이어서 room_threshold를 저장하지 않습니다. (로그인하지 않은 상태)")
                else:
                    logger.warning("⚠️ room_threshold 테이블이 존재하지 않습니다.")
            except Exception as e:
                logger.warning(f"room_threshold 테이블 처리 중 오류: {e}")
            
            # predicted_results 테이블에 데이터 삽입 (쾌적 온도 범위는 저장하지 않음)
            # predicted_skin 컬럼이 있는지 확인
            predicted_skin_code = None
            try:
                # 테이블 컬럼 확인
                columns_check = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'predicted_results'
                """)
                columns_result = conn.execute(columns_check)
                columns = [row.COLUMN_NAME for row in columns_result]
                
                # predicted_skin 컬럼 존재 여부 확인
                has_predicted_skin_column = 'predicted_skin' in columns
                
                # created_at 컬럼 존재 여부 확인 및 추가
                has_created_at_column = 'created_at' in columns
                if not has_created_at_column:
                    try:
                        # created_at 컬럼 추가
                        alter_query = text("""
                            ALTER TABLE predicted_results 
                            ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        """)
                        conn.execute(alter_query)
                        conn.commit()
                        logger.info("✅ predicted_results 테이블에 created_at 컬럼 추가 완료")
                        has_created_at_column = True
                    except Exception as e:
                        logger.warning(f"⚠️ created_at 컬럼 추가 실패: {str(e)}")
                
                # 예측값을 코드로 변환 (임계값 사용)
                if predicted_skin_temp > 0 and has_predicted_skin_column:
                    # 임계값 가져오기 (new_skinthreshold 테이블에서 최신 값 또는 기본값)
                    temp_min_threshold = 32.5
                    temp_max_threshold = 34.5
                    
                    try:
                        # new_skinthreshold 테이블 존재 여부 확인
                        if table_exists(conn, "new_skinthreshold"):
                            # 컬럼 확인 및 정렬 컬럼 결정
                            skin_columns = get_table_columns(conn, "new_skinthreshold")
                            skin_order_by = get_order_by_clause(skin_columns, "new_skinthreshold")
                            
                            # 최신 임계값 가져오기
                            latest_threshold_query = text(f"""
                                SELECT min_skinthreshold, max_skinthreshold
                                FROM new_skinthreshold
                                {skin_order_by}
                                LIMIT 1
                            """)
                            latest_threshold = conn.execute(latest_threshold_query).fetchone()
                            
                            if latest_threshold and latest_threshold.min_skinthreshold is not None:
                                temp_min_threshold = float(latest_threshold.min_skinthreshold)
                                temp_max_threshold = float(latest_threshold.max_skinthreshold)
                    except Exception as e:
                        logger.warning(f"⚠️ 임계값 조회 실패, 기본값 사용: {str(e)}")
                    
                    # 예측값을 코드로 변환
                    predicted_skin_code = convert_predicted_temp_to_code(predicted_skin_temp, temp_min_threshold, temp_max_threshold)
                    logger.info(f"🔮 예측값 코드 변환: {predicted_skin_temp}°C → {predicted_skin_code} (임계값: {temp_min_threshold}~{temp_max_threshold}°C)")
                
                # INSERT 전에 한 번 더 중복 체크 (트랜잭션 내에서)
                try:
                    # 날짜 컬럼 다시 확인 (created_at 컬럼이 추가되었을 수 있음)
                    columns_check_final = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns_final = [row.COLUMN_NAME for row in conn.execute(columns_check_final)]
                    
                    date_column_final = None
                    for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                        if col in columns_final or col.lower() in [c.lower() for c in columns_final]:
                            date_column_final = col
                            break
                    
                    if date_column_final:
                        final_duplicate_check = text(f"""
                            SELECT COUNT(*) as cnt
                            FROM predicted_results
                            WHERE HR_mean = :hr 
                              AND ABS(HRV_SDNN - :hrv) < 0.01
                              AND ABS(mean_sa02 - :o2) < 0.1
                              AND {date_column_final} >= DATE_SUB(NOW(), INTERVAL 2 MINUTE)
                        """)
                    else:
                        # 날짜 컬럼이 없으면 최근 10개만 확인
                        final_duplicate_check = text("""
                            SELECT COUNT(*) as cnt
                            FROM predicted_results
                            WHERE HR_mean = :hr 
                              AND ABS(HRV_SDNN - :hrv) < 0.01
                              AND ABS(mean_sa02 - :o2) < 0.1
                            ORDER BY 1 DESC
                            LIMIT 10
                        """)
                    
                    duplicate_count = conn.execute(final_duplicate_check, {
                        'hr': data.heartRate,
                        'hrv': data.HRV,
                        'o2': data.oxygenSaturation
                    }).fetchone()
                    
                    if duplicate_count and duplicate_count.cnt > 0:
                        logger.info(f"⏭️ INSERT 전 중복 데이터 재확인 - 최근 2분 이내 동일한 데이터 {duplicate_count.cnt}개 발견. 건너뜀 (HR: {data.heartRate}, HRV: {data.HRV}, O2: {data.oxygenSaturation})")
                        print(f"⏭️ INSERT 전 중복 데이터 재확인 - 건너뜀")
                        conn.commit()
                        return {
                            "status": "ok",
                            "message": "Duplicate data skipped (final check)",
                            "predicted_skin_temp": predicted_skin_temp,
                            "duplicate": True
                        }
                except Exception as final_dup_e:
                    logger.warning(f"⚠️ INSERT 전 중복 체크 실패 (계속 진행): {final_dup_e}")
                    import traceback
                    logger.debug(f"중복 체크 실패 상세: {traceback.format_exc()}")
                
                data_inserted = False
                # 현재 시간 가져오기
                from datetime import datetime
                current_time = datetime.now()
                
                if has_predicted_skin_column and predicted_skin_code is not None:
                    # predicted_skin 컬럼이 있으면 함께 저장
                    if has_created_at_column:
                        insert_query = text("""
                            INSERT INTO predicted_results 
                            (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, predicted_skin, created_at, user_no)
                            VALUES 
                            (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :predicted_skin, :created_at, :user_no)
                        """)
                        conn.execute(insert_query, {
                            'heart_rate': data.heartRate,
                            'hrv': data.HRV,
                            'oxygen_sat': data.oxygenSaturation,
                            'bmi': bmi,
                            'age': age,
                            'gender': gender,
                            'predicted_temp': predicted_skin_temp,
                            'predicted_skin': predicted_skin_code,
                            'created_at': current_time,
                            'user_no': user_no
                        })
                        logger.info(f"✅ 데이터 저장 완료 (predicted_skin 포함, created_at 포함): HR={data.heartRate}, HRV={data.HRV}, O2={data.oxygenSaturation}, 예측온도={predicted_skin_temp}°C, 시간={current_time}")
                    else:
                        insert_query = text("""
                            INSERT INTO predicted_results 
                            (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, predicted_skin, user_no)
                            VALUES 
                            (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :predicted_skin, :user_no)
                        """)
                        conn.execute(insert_query, {
                            'heart_rate': data.heartRate,
                            'hrv': data.HRV,
                            'oxygen_sat': data.oxygenSaturation,
                            'bmi': bmi,
                            'age': age,
                            'gender': gender,
                            'predicted_temp': predicted_skin_temp,
                            'predicted_skin': predicted_skin_code,
                            'user_no': user_no
                        })
                        logger.info(f"✅ 데이터 저장 완료 (predicted_skin 포함, created_at 없음): HR={data.heartRate}, HRV={data.HRV}, O2={data.oxygenSaturation}, 예측온도={predicted_skin_temp}°C")
                    data_inserted = True
                else:
                    # predicted_skin 컬럼이 없으면 기존 방식으로 저장
                    if has_created_at_column:
                        insert_query = text("""
                            INSERT INTO predicted_results 
                            (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, created_at, user_no)
                            VALUES 
                            (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :created_at, :user_no)
                        """)
                        conn.execute(insert_query, {
                            'heart_rate': data.heartRate,
                            'hrv': data.HRV,
                            'oxygen_sat': data.oxygenSaturation,
                            'bmi': bmi,
                            'age': age,
                            'gender': gender,
                            'predicted_temp': predicted_skin_temp,
                            'created_at': current_time,
                            'user_no': user_no
                        })
                        logger.info(f"✅ 데이터 저장 완료 (predicted_skin 없음, created_at 포함): HR={data.heartRate}, HRV={data.HRV}, O2={data.oxygenSaturation}, 예측온도={predicted_skin_temp}°C, 시간={current_time}")
                    else:
                        insert_query = text("""
                            INSERT INTO predicted_results 
                            (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, user_no)
                            VALUES 
                            (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :user_no)
                        """)
                        conn.execute(insert_query, {
                            'heart_rate': data.heartRate,
                            'hrv': data.HRV,
                            'oxygen_sat': data.oxygenSaturation,
                            'bmi': bmi,
                            'age': age,
                            'gender': gender,
                            'predicted_temp': predicted_skin_temp,
                            'user_no': user_no
                        })
                        logger.info(f"✅ 데이터 저장 완료 (predicted_skin 없음, created_at 없음): HR={data.heartRate}, HRV={data.HRV}, O2={data.oxygenSaturation}, 예측온도={predicted_skin_temp}°C")
                    data_inserted = True
            except Exception as e:
                logger.warning(f"⚠️ predicted_skin 컬럼 확인 실패, 기존 방식으로 저장: {str(e)}")
                # 예외 발생 시에만 기존 방식으로 저장 (중복 방지)
                if not data_inserted:
                    from datetime import datetime
                    current_time = datetime.now()
                    
                    # created_at 컬럼 확인
                    try:
                        columns_check = text("""
                            SELECT COLUMN_NAME 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'main' 
                            AND TABLE_NAME = 'predicted_results'
                            AND COLUMN_NAME = 'created_at'
                        """)
                        has_created_at = conn.execute(columns_check).fetchone() is not None
                        
                        if has_created_at:
                            insert_query = text("""
                                INSERT INTO predicted_results 
                                (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, created_at)
                                VALUES 
                                (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :created_at)
                            """)
                            conn.execute(insert_query, {
                                'heart_rate': data.heartRate,
                                'hrv': data.HRV,
                                'oxygen_sat': data.oxygenSaturation,
                                'bmi': bmi,
                                'age': age,
                                'gender': gender,
                                'predicted_temp': predicted_skin_temp,
                                'created_at': current_time
                            })
                        else:
                            insert_query = text("""
                                INSERT INTO predicted_results 
                                (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp)
                                VALUES 
                                (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp)
                            """)
                            conn.execute(insert_query, {
                                'heart_rate': data.heartRate,
                                'hrv': data.HRV,
                                'oxygen_sat': data.oxygenSaturation,
                                'bmi': bmi,
                                'age': age,
                                'gender': gender,
                                'predicted_temp': predicted_skin_temp
                            })
                    except Exception as e2:
                        logger.warning(f"⚠️ created_at 컬럼 확인 실패: {str(e2)}")
                        insert_query = text("""
                            INSERT INTO predicted_results 
                            (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, user_no)
                            VALUES 
                            (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :user_no)
                        """)
                        conn.execute(insert_query, {
                            'heart_rate': data.heartRate,
                            'hrv': data.HRV,
                            'oxygen_sat': data.oxygenSaturation,
                            'bmi': bmi,
                            'age': age,
                            'gender': gender,
                            'predicted_temp': predicted_skin_temp,
                            'user_no': user_no
                        })
            
            conn.commit()
            
            # test_script_logs에 실제 건강 데이터 로그 저장
            try:
                # test_script_logs 테이블 존재 여부 확인
                test_log_table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'test_script_logs'
                """)
                test_log_table_exists = conn.execute(test_log_table_check).fetchone().count > 0
                
                if test_log_table_exists:
                    # 실제 건강 데이터를 로그로 저장
                    # predicted_skin_temp를 기반으로 분류 (더움/추움/적정)
                    # 임계값 가져오기
                    temp_min_threshold = 32.5
                    temp_max_threshold = 34.5
                    
                    try:
                        new_table_check = text("""
                            SELECT COUNT(*) as count
                            FROM information_schema.tables 
                            WHERE table_schema = 'main' 
                            AND table_name = 'new_skinthreshold'
                        """)
                        new_table_exists = conn.execute(new_table_check).fetchone().count > 0
                        
                        if new_table_exists:
                            # 컬럼 확인하여 정렬 컬럼 결정
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
                                skin_order_by = ""  # 정렬 없이 LIMIT만 사용
                            
                            latest_threshold_query = text(f"""
                                SELECT min_skinthreshold, max_skinthreshold
                                FROM new_skinthreshold
                                {skin_order_by}
                                LIMIT 1
                            """)
                            latest_threshold = conn.execute(latest_threshold_query).fetchone()
                            
                            if latest_threshold and latest_threshold.min_skinthreshold is not None:
                                temp_min_threshold = float(latest_threshold.min_skinthreshold)
                                temp_max_threshold = float(latest_threshold.max_skinthreshold)
                    except Exception as e:
                        logger.warning(f"⚠️ 임계값 조회 실패, 기본값 사용: {str(e)}")
                    
                    # 예측 온도를 기반으로 분류 결정
                    if predicted_skin_temp > 0:
                        if predicted_skin_temp < temp_min_threshold:
                            majority_result = 'C'  # 추움
                        elif predicted_skin_temp > temp_max_threshold:
                            majority_result = 'H'  # 더움
                        else:
                            majority_result = 'G'  # 적정
                        
                        # 실제 건강 데이터 로그 저장 (이 API는 건강 데이터만 받으므로 test_script_logs에 저장하지 않음)
                        # test_script_logs는 air_conditioner_auto_control.py에서만 저장
                        # 여기서는 predicted_results에만 저장
                        logger.info(f"✅ 실제 건강 데이터 저장 완료: 예측온도={predicted_skin_temp}°C, 분류={majority_result} (test_script_logs는 에어컨 조절 시 저장)")
                else:
                    logger.warning("⚠️ test_script_logs 테이블이 존재하지 않습니다.")
            except Exception as e:
                logger.warning(f"⚠️ 실제 데이터 로그 저장 실패: {str(e)}")
            
            # 실시간 데이터 수신 시 제어 로직 실행 (최소 10분 간격)
            try:
                # 수면 모드 확인 (사용자별, user_no가 None이면 제어 로직 건너뜀)
                if user_no is None:
                    logger.info(f"⏸️ user_no가 없음 - 제어 로직 건너뜀 (예측온도: {predicted_skin_temp}°C)")
                    print(f"⏸️ user_no가 없음 - 제어 로직 건너뜀")
                else:
                    global sleep_mode_states
                    sleep_mode_state = sleep_mode_states.get(user_no, {
                        "active": False,
                        "start_time": None,
                        "end_time": None,
                        "duration_hours": None
                    })
                    sleep_mode_active = sleep_mode_state.get("active", False)
                    
                    # 종료 시간 확인
                    if sleep_mode_active and sleep_mode_state.get("end_time"):
                        from datetime import datetime
                        end_time = datetime.fromisoformat(sleep_mode_state["end_time"])
                        if datetime.now() >= end_time:
                            # 수면 모드 자동 종료
                            sleep_mode_states[user_no] = {
                                "active": False,
                                "start_time": None,
                                "end_time": None,
                                "duration_hours": None
                            }
                            sleep_mode_active = False
                            logger.info(f"😴 수면 모드 자동 종료 (user_no: {user_no}, 설정된 시간 경과)")
                    
                    logger.info(f"🔍 제어 로직 실행 체크 - 수면 모드: {'활성화' if sleep_mode_active else '비활성화'}, 예측온도: {predicted_skin_temp}°C, user_no: {user_no}")
                    print(f"🔍 제어 로직 실행 체크 - 수면 모드: {'활성화' if sleep_mode_active else '비활성화'}, 예측온도: {predicted_skin_temp}°C")
                    
                    if sleep_mode_active:
                        logger.info(f"🔄 실시간 데이터 수신 - 제어 로직 실행 시도 (수면 모드 활성화, 예측온도: {predicted_skin_temp}°C)")
                        print(f"🔄 실시간 데이터 수신 - 제어 로직 실행 시도")
                        # 제어 로직 실행 (최소 간격 제한은 adjust_air_conditioner 내부에서 처리)
                        try:
                            # 사용자별 임계값 가져오기
                            cold_threshold, hot_threshold = get_user_thresholds(user_no)
                            
                            # 콜백 함수 래퍼 (user_no 포함)
                            def update_thresholds_wrapper(new_cold: float, new_hot: float):
                                update_thresholds(new_cold, new_hot, user_no)
                            
                            # user_no를 사용하여 사용자별 PAT 토큰과 device_id를 가져오는 래퍼 함수 생성
                            def get_air_conditioner_state_with_user():
                                try:
                                    # user_no로 user_id 조회 (login 테이블 사용)
                                    with engine.connect() as conn:
                                        user_query = text("SELECT id FROM login WHERE no = :user_no")
                                        user_result = conn.execute(user_query, {'user_no': user_no})
                                        user_row = user_result.fetchone()
                                        if not user_row:
                                            logger.warning(f"⚠️ user_no={user_no}에 해당하는 사용자를 찾을 수 없습니다.")
                                            return None
                                        user_id = user_row.id
                                    
                                    # user_id로 PAT 토큰과 device_id 조회
                                    with engine.connect() as conn:
                                        device_query = text("""
                                            SELECT pat_token, device_id
                                            FROM iot_devices
                                            WHERE user_id = :user_id
                                            ORDER BY updated_at DESC
                                            LIMIT 1
                                        """)
                                        device_result = conn.execute(device_query, {'user_id': user_id})
                                        device_row = device_result.fetchone()
                                        if not device_row:
                                            logger.warning(f"⚠️ user_id={user_id}에 등록된 디바이스가 없습니다.")
                                            return None
                                        pat_token = device_row.pat_token
                                        device_id = device_row.device_id
                                    
                                    # PAT 토큰으로 상태 조회
                                    return get_device_state_with_pat_token(pat_token, device_id)
                                except Exception as e:
                                    logger.error(f"❌ 사용자별 에어컨 상태 조회 실패 (user_no={user_no}): {e}")
                                    return None
                            
                            air_conditioner_auto_control.adjust_air_conditioner(
                                engine=engine,
                                air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
                                get_air_conditioner_state_func=get_air_conditioner_state_with_user,
                                set_temperature_func=set_temperature,
                                cold_threshold=cold_threshold,
                                hot_threshold=hot_threshold,
                                update_threshold_callback=update_thresholds_wrapper,
                                min_interval_minutes=30.0,  # 30분 간격으로 조절
                                user_no=user_no
                            )
                            logger.info("✅ 실시간 제어 로직 실행 완료")
                            print("✅ 실시간 제어 로직 실행 완료")
                        except Exception as control_error:
                            logger.warning(f"⚠️ 제어 로직 실행 중 오류 (최소 간격 제한 또는 기타 오류): {control_error}")
                            print(f"⚠️ 제어 로직 실행 중 오류: {control_error}")
                    else:
                        logger.info(f"⏸️ 수면 모드 비활성화 - 제어 로직 건너뜀 (예측온도: {predicted_skin_temp}°C)")
                        print(f"⏸️ 수면 모드 비활성화 - 제어 로직 건너뜀")
            except Exception as e:
                logger.warning(f"⚠️ 실시간 제어 로직 실행 실패 (스케줄러가 처리할 예정): {e}")
                print(f"⚠️ 실시간 제어 로직 실행 실패: {e}")
                import traceback
                logger.debug(f"⚠️ 제어 로직 실행 실패 상세: {traceback.format_exc()}")
        
        logger.info(f"✅ 데이터가 DB에 저장되었습니다. (gender: {gender}, bmi: {bmi}, age: {age}, predicted_skin_temp: {predicted_skin_temp})")
        return {
            "status": "ok", 
            "message": "Data saved successfully",
            "predicted_skin_temp": predicted_skin_temp,
            "comfort_temperature_range": {
                "min": comfort_min,
                "max": comfort_max
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 데이터 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/healthdata/latest")
async def get_latest_health_data(user_no: int = Depends(verify_token)):
    """서버에 저장된 최신 건강 데이터 조회 (사용자별 필터링)"""
    try:
        logger.info(f"📱 최신 건강 데이터 조회 요청 (user_no: {user_no})")
        
        try:
            with engine.connect() as conn:
                # 먼저 테이블 구조 확인 (created_at 컬럼 존재 여부)
                try:
                    # 테이블 컬럼 정보 조회
                    columns_query = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns_result = conn.execute(columns_query)
                    columns = [row.COLUMN_NAME for row in columns_result]
                    
                    # 날짜 컬럼 찾기 (created_at, timestamp, date 등)
                    date_column = None
                    for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                        if col in columns or col.lower() in [c.lower() for c in columns]:
                            date_column = col
                            break
                    
                    # ORDER BY 절 생성 (날짜 컬럼이 있으면 사용, 없으면 ID 사용)
                    order_by = f"ORDER BY {date_column} DESC" if date_column else "ORDER BY 1 DESC"  # 1은 첫 번째 컬럼
                    
                    # SELECT 절 생성 (created_at이 있으면 포함, 없으면 제외)
                    select_columns = """
                        HR_mean as heartRate,
                        HRV_SDNN as hrv,
                        mean_sa02 as oxygenSaturation,
                        bmi,
                        age,
                        gender
                    """
                    if date_column:
                        select_columns += f", {date_column} as created_at"
                    
                    # predicted_results 테이블에서 최신 데이터 조회 (user_no 필터링)
                    query = text(f"""
                        SELECT 
                            {select_columns}
                        FROM predicted_results
                        WHERE user_no = :user_no
                        {order_by}
                        LIMIT 1
                    """)
                except Exception as e:
                    logger.warning(f"테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                    # 기본 쿼리 (created_at 없이, user_no 필터링)
                    query = text("""
                        SELECT 
                            HR_mean as heartRate,
                            HRV_SDNN as hrv,
                            mean_sa02 as oxygenSaturation,
                            bmi,
                            age,
                            gender
                        FROM predicted_results
                        WHERE user_no = :user_no
                        ORDER BY 1 DESC
                        LIMIT 1
                    """)
                
                result = conn.execute(query, {"user_no": user_no})
                row = result.fetchone()
                
                if row is None:
                    logger.info("📊 저장된 건강 데이터가 없습니다.")
                    return {
                        "success": True,
                        "data": {},
                        "message": "저장된 건강 데이터가 없습니다."
                    }
                
                # 데이터 변환
                health_data = {
                    "heartRate": float(row.heartRate) if row.heartRate else None,
                    "hrv": float(row.hrv) if row.hrv else None,
                    "oxygenSaturation": float(row.oxygenSaturation) if row.oxygenSaturation else None,
                }
                
                # 날짜 포맷팅 (created_at 컬럼이 있으면 사용, 없으면 현재 시간 사용)
                try:
                    created_at = getattr(row, 'created_at', None)
                    if created_at is None:
                        # created_at 컬럼이 없으면 현재 시간 사용
                        created_at = datetime.now()
                        date_str = created_at.isoformat()
                    elif isinstance(created_at, datetime):
                        date_str = created_at.isoformat()
                    else:
                        date_str = str(created_at)
                except AttributeError:
                    # created_at 속성이 없으면 현재 시간 사용
                    created_at = datetime.now()
                    date_str = created_at.isoformat()
                
                logger.info(f"✅ 최신 건강 데이터 조회 성공: {health_data}")
                
                return {
                    "success": True,
                    "data": {
                        "heartRate": health_data["heartRate"] and {
                            "value": health_data["heartRate"],
                            "date": date_str
                        } or None,
                        "hrv": health_data["hrv"] and {
                            "value": health_data["hrv"],
                            "date": date_str
                        } or None,
                        "oxygenSaturation": health_data["oxygenSaturation"] and {
                            "value": health_data["oxygenSaturation"],
                            "date": date_str
                        } or None,
                    },
                    "lastUpdated": date_str
                }
        except Exception as db_error:
            logger.error(f"❌ DB 조회 실패: {str(db_error)}")
            # DB 오류 시 빈 데이터 반환 (서버는 정상 응답)
            return {
                "success": True,
                "data": {},
                "message": f"데이터 조회 실패: {str(db_error)}"
            }
    
    except Exception as e:
        logger.error(f"❌ 최신 건강 데이터 조회 실패: {str(e)}")
        # 에러 발생 시에도 빈 데이터 반환 (500 에러 방지)
        return {
            "success": True,
            "data": {},
            "message": f"데이터 조회 실패: {str(e)}"
        }

# ==================== 모델 예측 API ====================

@app.post("/predict")
async def predict(data: PredictRequest):
    """체온 예측 API"""
    try:
        if not model_loaded:
            raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")
        
        logger.info(f"📱 앱에서 예측 요청 받음: {data.model_dump()}")
        
        # 예측 수행
        predicted_temp = predict_temperature_with_model(
            hr_mean=data.hr_mean,
            hrv_sdnn=data.hrv_sdnn,
            bmi=data.bmi,
            mean_sa02=data.mean_sa02,
            gender=data.gender,
            age=data.age
        )
        
        # 온도 분류 (앱과 동일한 기준: 34.5도부터 35.6도까지 쾌적 범위에 포함)
        def classify_temperature(temp, cold_threshold=34.5, hot_threshold=35.6):
            if temp < 34.5:
                return "추움"
            elif temp > 35.6:
                return "더움"
            else:
                # 34.5 <= temp <= 35.6: 쾌적함 (경계값 포함)
                return "적정"
        
        temperature_category = classify_temperature(predicted_temp)
        
        result = {
            'success': True,
            'predicted_temperature': predicted_temp,
            'temperature_category': temperature_category,
            'input_data': data.model_dump()
        }
        logger.info(f"✅ 예측 완료: {predicted_temp:.2f}°C ({temperature_category})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"예측 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'예측 실패: {str(e)}')

@app.get("/model_info")
async def model_info():
    """모델 정보 반환"""
    if not model_loaded:
        raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")
    
    return {
        'model_type': '앙상블 모델 (RandomForest + ExtraTrees + GradientBoosting) - 나이 포함',
        'features': ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio', 'gender'],
        'target': 'TEMP_median (체온)',
        'model_loaded': model_loaded
    }

@app.get("/comfort_temperature")
async def get_comfort_temperature():
    """DB에서 저장된 쾌적 온도 범위 조회 (계산하지 않고 저장된 값 사용)"""
    try:
        logger.info("🌡️ 쾌적 온도 범위 조회 요청")
        
        with engine.connect() as conn:
            # 먼저 테이블 구조 확인
            try:
                columns_query = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'predicted_results'
                """)
                columns_result = conn.execute(columns_query)
                columns = [row.COLUMN_NAME for row in columns_result]
                
                # 날짜 컬럼 찾기
                date_column = None
                for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                    if col in columns or col.lower() in [c.lower() for c in columns]:
                        date_column = col
                        break
                
                # ORDER BY 절 생성
                if date_column:
                    order_by = f"ORDER BY {date_column} DESC"
                else:
                    order_by = "ORDER BY 1 DESC"
                
                # 쾌적 온도 컬럼 존재 여부 확인
                has_comfort_columns = 'comfort_min_temp' in columns or 'comfort_min_temp'.lower() in [c.lower() for c in columns]
                
            except Exception as e:
                logger.warning(f"테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                order_by = "ORDER BY 1 DESC"
                has_comfort_columns = False
            
            # 저장된 쾌적 온도 범위가 있으면 사용
            if has_comfort_columns:
                query = text(f"""
                    SELECT gender, age, bmi, comfort_min_temp, comfort_max_temp
                    FROM predicted_results
                    WHERE gender IS NOT NULL 
                      AND age IS NOT NULL 
                      AND bmi IS NOT NULL
                      AND comfort_min_temp IS NOT NULL
                      AND comfort_max_temp IS NOT NULL
                    {order_by}
                    LIMIT 1
                """)
            else:
                # 쾌적 온도 컬럼이 없으면 사용자 정보만 조회
                query = text(f"""
                    SELECT gender, age, bmi
                    FROM predicted_results
                    WHERE gender IS NOT NULL 
                      AND age IS NOT NULL 
                      AND bmi IS NOT NULL
                    {order_by}
                    LIMIT 1
                """)
            
            result = conn.execute(query)
            row = result.fetchone()
            
            if row is None:
                logger.warning("⚠️ 사용자 정보가 없습니다.")
                return {
                    "success": False,
                    "message": "사용자 정보가 없습니다. 먼저 건강 데이터를 저장해주세요.",
                    "comfort_temperature_range": None
                }
            
            # 저장된 쾌적 온도 범위가 있으면 사용
            if has_comfort_columns and row.comfort_min_temp is not None and row.comfort_max_temp is not None:
                comfort_min = float(row.comfort_min_temp)
                comfort_max = float(row.comfort_max_temp)
                logger.info(f"📋 저장된 쾌적 온도 범위 사용: {comfort_min}~{comfort_max}°C")
            else:
                # 저장된 값이 없으면 계산 (하지만 이 경우는 거의 발생하지 않아야 함)
                gender = row.gender
                age = int(row.age) if row.age else 0
                bmi = float(row.bmi) if row.bmi else 0.0
                comfort_min, comfort_max = calculate_comfort_temperature(gender, age, bmi)
                logger.info(f"🌡️ 쾌적 온도 범위 계산 (저장된 값 없음): {comfort_min}~{comfort_max}°C")
            
            return {
                "success": True,
                "comfort_temperature_range": {
                    "min": comfort_min,
                    "max": comfort_max
                },
                "user_info": {
                    "gender": row.gender,
                    "age": int(row.age) if row.age else 0,
                    "bmi": float(row.bmi) if row.bmi else 0.0
                }
            }
            
    except Exception as e:
        logger.error(f"❌ 쾌적 온도 범위 조회 실패: {str(e)}")
        return {
            "success": False,
            "message": f"쾌적 온도 범위 조회 실패: {str(e)}",
            "comfort_temperature_range": None
        }

# ==================== 에어컨 제어 API ====================

def get_device_state_with_pat_token(pat_token: str, device_id: str, country: str = "KR"):
    """
    PAT 토큰과 device_id를 사용하여 디바이스 상태를 조회합니다.
    """
    import base64
    import uuid
    import requests
    
    THINQ_API_BASE_URL = "https://api-kic.lgthinq.com"
    THINQ_API_KEY = "v6GFvkweNo7DK7yD3ylIZ9w52aKBU0eJ7wLXkSR3"
    CLIENT_ID = "poseul-app"
    
    def generate_message_id():
        uuid_v4 = uuid.uuid4()
        uuid_bytes = uuid_v4.bytes
        encoded = base64.urlsafe_b64encode(uuid_bytes).decode('utf-8').rstrip('=')
        return encoded[:22]
    
    url = f"{THINQ_API_BASE_URL}/devices/{device_id}/state"
    headers = {
        "Authorization": f"Bearer {pat_token}",
        "x-message-id": generate_message_id(),
        "x-country": country,
        "x-client-id": CLIENT_ID,
        "x-api-key": THINQ_API_KEY
    }
    
    try:
        # 타임아웃을 5초로 줄여서 더 빠른 응답
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"❌ 디바이스 상태 조회 타임아웃 (5초 초과)")
        raise HTTPException(status_code=504, detail="LG ThinQ API 응답 시간 초과.")
    except Exception as e:
        logger.error(f"❌ 디바이스 상태 조회 실패: {str(e)}")
        raise

def send_device_command_with_pat_token(pat_token: str, device_id: str, command: dict, country: str = "KR"):
    """
    PAT 토큰과 device_id를 사용하여 디바이스에 명령을 전송합니다.
    """
    import base64
    import uuid
    import requests
    
    THINQ_API_BASE_URL = "https://api-kic.lgthinq.com"
    THINQ_API_KEY = "v6GFvkweNo7DK7yD3ylIZ9w52aKBU0eJ7wLXkSR3"
    CLIENT_ID = "poseul-app"
    
    def generate_message_id():
        uuid_v4 = uuid.uuid4()
        uuid_bytes = uuid_v4.bytes
        encoded = base64.urlsafe_b64encode(uuid_bytes).decode('utf-8').rstrip('=')
        return encoded[:22]
    
    url = f"{THINQ_API_BASE_URL}/devices/{device_id}/control"
    headers = {
        "Authorization": f"Bearer {pat_token}",
        "x-message-id": generate_message_id(),
        "x-country": country,
        "x-client-id": CLIENT_ID,
        "x-api-key": THINQ_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # 타임아웃을 5초로 줄여서 더 빠른 응답
        response = requests.post(url, headers=headers, json=command, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"❌ 디바이스 제어 타임아웃 (5초 초과)")
        raise HTTPException(status_code=504, detail="LG ThinQ API 응답 시간 초과.")
    except Exception as e:
        logger.error(f"❌ 디바이스 제어 실패: {str(e)}")
        raise

@app.get("/air_conditioner/state")
async def get_air_conditioner_state_api(request: Request):
    """에어컨 상태 조회 API (사용자별 PAT 토큰 사용)"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="에어컨 모듈을 사용할 수 없습니다.")
    
    try:
        # 쿼리 파라미터에서 user_id 가져오기 (없으면 기본값)
        user_id = request.query_params.get('user_id', 'default')
        
        # 항상 DB에서 직접 조회 (캐시 사용 안 함)
        logger.info(f"🔍 DB에서 직접 조회: user_id={user_id}")
        try:
            with engine.connect() as conn:
                device_query = text("""
                    SELECT user_id, pat_token, device_id, device_name, model_name
                    FROM iot_devices
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                device_result = conn.execute(device_query, {'user_id': user_id})
                device_row = device_result.fetchone()
                
                if not device_row:
                    logger.warning(f"❌ 등록된 디바이스 없음: user_id={user_id}")
                    raise HTTPException(status_code=404, detail="등록된 디바이스가 없습니다. 먼저 PAT 토큰을 등록해주세요.")
                
                # DB에서 조회한 정보 사용
                device_info = {
                    'pat_token': device_row.pat_token,
                    'device_id': device_row.device_id,
                    'device_name': device_row.device_name or '',
                    'model_name': device_row.model_name or ''
                }
                logger.info(f"✅ DB에서 조회 성공: user_id={user_id}, device_id={device_row.device_id[:20] if device_row.device_id else 'None'}...")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ DB 조회 실패: {str(e)}")
            import traceback
            logger.error(f"❌ 상세 에러: {traceback.format_exc()}")
            raise HTTPException(status_code=404, detail="등록된 디바이스가 없습니다. 먼저 PAT 토큰을 등록해주세요.")
        
        pat_token = device_info['pat_token']
        device_id = device_info['device_id']
        
        logger.info(f"📱 앱에서 에어컨 상태 조회 요청 (사용자: {user_id}, 디바이스: {device_id[:20]}...)")
        
        # PAT 토큰으로 상태 조회
        state_response = get_device_state_with_pat_token(pat_token, device_id)
        
        # 응답 구조 분석 및 상태 정보 추출
        state = None
        if 'result' in state_response and 'value' in state_response['result']:
            state = state_response['result']['value']
        elif 'response' in state_response:
            response = state_response['response']
            if isinstance(response, dict):
                if 'value' in response:
                    state = response['value']
                else:
                    state = response
        
        if state:
            # 상태 정보를 앱에서 사용하기 쉬운 형태로 변환
            result = {
                'success': True,
                'device_id': device_id,
                'state': {
                    'power': state.get('operation', {}).get('airConOperationMode') == 'POWER_ON',
                    'currentTemperature': state.get('temperature', {}).get('currentTemperature'),
                    'targetTemperature': state.get('temperature', {}).get('targetTemperature'),
                    'temperature_unit': state.get('temperature', {}).get('unit', 'C'),
                    'mode': state.get('airConJobMode', {}).get('currentJobMode'),
                    'fanSpeed': state.get('airFlow', {}).get('windStrength'),
                    'airQuality': state.get('airQualitySensor', {}).get('PM2') or state.get('airQualitySensor', {}).get('PM10') or 0,
                    'raw_state': state  # 전체 상태 정보도 포함
                }
            }
            logger.info(f"✅ 에어컨 상태 조회 성공")
            return result
        else:
            raise HTTPException(status_code=500, detail="상태 정보를 찾을 수 없습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에어컨 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'에어컨 상태 조회 실패: {str(e)}')

@app.post("/air_conditioner/control")
async def control_air_conditioner_api(data: AirConditionerControlRequest, request: Request):
    """에어컨 제어 API (사용자별 PAT 토큰 사용)"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="에어컨 모듈을 사용할 수 없습니다.")
    
    try:
        # 쿼리 파라미터에서 user_id 가져오기 (없으면 기본값)
        user_id = request.query_params.get('user_id', 'default')
        
        # 항상 DB에서 직접 조회 (캐시 사용 안 함)
        logger.info(f"🔍 DB에서 직접 조회: user_id={user_id}")
        try:
            with engine.connect() as conn:
                device_query = text("""
                    SELECT user_id, pat_token, device_id, device_name, model_name
                    FROM iot_devices
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                device_result = conn.execute(device_query, {'user_id': user_id})
                device_row = device_result.fetchone()
                
                if not device_row:
                    logger.warning(f"❌ 등록된 디바이스 없음: user_id={user_id}")
                    raise HTTPException(status_code=404, detail="등록된 디바이스가 없습니다. 먼저 PAT 토큰을 등록해주세요.")
                
                # DB에서 조회한 정보 사용
                device_info = {
                    'pat_token': device_row.pat_token,
                    'device_id': device_row.device_id,
                    'device_name': device_row.device_name or '',
                    'model_name': device_row.model_name or ''
                }
                logger.info(f"✅ DB에서 조회 성공: user_id={user_id}, device_id={device_row.device_id[:20] if device_row.device_id else 'None'}...")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ DB 조회 실패: {str(e)}")
            import traceback
            logger.error(f"❌ 상세 에러: {traceback.format_exc()}")
            raise HTTPException(status_code=404, detail="등록된 디바이스가 없습니다. 먼저 PAT 토큰을 등록해주세요.")
        
        pat_token = device_info['pat_token']
        device_id = device_info['device_id']
        
        logger.info(f"📱 앱에서 에어컨 제어 요청: {data.model_dump()} (사용자: {user_id})")
        
        if not data.action:
            raise HTTPException(status_code=400, detail="action 파라미터가 필요합니다.")
        
        # 명령 생성
        command = {}
        
        if data.action == 'set_temperature':
            if data.target_temperature is None:
                raise HTTPException(status_code=400, detail="target_temperature 파라미터가 필요합니다.")
            command = {
                "temperature": {
                    "targetTemperature": float(data.target_temperature),
                    "unit": data.unit or 'C'
                }
            }
            
        elif data.action == 'set_mode':
            if not data.mode:
                raise HTTPException(status_code=400, detail="mode 파라미터가 필요합니다.")
            command = {
                "airConJobMode": {
                    "currentJobMode": data.mode
                }
            }
            
        elif data.action == 'set_wind_strength':
            if not data.strength:
                raise HTTPException(status_code=400, detail="strength 파라미터가 필요합니다.")
            command = {
                "airFlow": {
                    "windStrength": data.strength
                }
            }
            
        elif data.action == 'set_power':
            power_mode = "POWER_ON" if bool(data.power_on) else "POWER_OFF"
            command = {
                "operation": {
                    "airConOperationMode": power_mode
                }
            }
            
        else:
            raise HTTPException(status_code=400, detail=f'지원하지 않는 action: {data.action}')
        
        # PAT 토큰으로 제어 명령 전송
        result = send_device_command_with_pat_token(pat_token, device_id, command)
        
        logger.info(f"✅ 에어컨 제어 성공: {data.action}")
        
        # 액션별 메시지 생성
        messages = {
            'set_power': f"전원 {'켜기' if data.power_on else '끄기'} 성공",
            'set_temperature': f"목표 온도 {data.target_temperature}°C 설정 성공",
            'set_mode': f"모드 {data.mode} 설정 성공",
            'set_wind_strength': f"풍량 {data.strength} 설정 성공",
        }
        
        return {
            'success': True,
            'action': data.action,
            'message': messages.get(data.action, '제어 성공'),
            'result': result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에어컨 제어 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'에어컨 제어 실패: {str(e)}')

class TemperatureThresholdRequest(BaseModel):
    """온도 임계값 저장 요청"""
    target_temperature: float  # 사용자가 설정한 온도 (예: 24도)

@app.post("/air_conditioner/temperature_threshold")
async def save_temperature_threshold_api(data: TemperatureThresholdRequest, user_no: int = Depends(verify_token)):
    """에어컨 온도 임계값을 캐시에 저장 (유효, 사용자별 분리)"""
    try:
        threshold = save_threshold(data.target_temperature, user_no)
        
        return {
            "success": True,
            "message": "온도 임계값이 저장되었습니다.",
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"❌ 온도 임계값 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 임계값 저장 실패: {str(e)}')

@app.get("/air_conditioner/temperature_threshold")
async def get_temperature_threshold_api(user_no: int = Depends(verify_token)):
    """현재 저장된 온도 임계값 조회 (만료되지 않은 경우만, 사용자별 분리)"""
    try:
        threshold = get_threshold(user_no)
        
        if threshold is None:
            return {
                "success": True,
                "has_threshold": False,
                "message": "저장된 임계값이 없습니다."
            }
        
        return {
            "success": True,
            "has_threshold": True,
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"❌ 온도 임계값 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 임계값 조회 실패: {str(e)}')

# ==================== IoT 디바이스 등록 API ====================

class PatTokenRequest(BaseModel):
    """PAT 토큰 등록 요청"""
    pat_token: str
    user_id: Optional[str] = "default"  # 기본값, 나중에 실제 사용자 ID로 확장 가능

def get_devices_with_pat_token(pat_token: str, country: str = "KR"):
    """
    PAT 토큰을 사용하여 디바이스 목록을 조회합니다.
    test.py의 get_devices를 래핑하여 PAT 토큰을 동적으로 사용할 수 있게 합니다.
    """
    import base64
    import uuid
    import requests
    
    # test.py의 상수들
    THINQ_API_BASE_URL = "https://api-kic.lgthinq.com"
    THINQ_API_KEY = "v6GFvkweNo7DK7yD3ylIZ9w52aKBU0eJ7wLXkSR3"
    CLIENT_ID = "poseul-app"
    
    def generate_message_id():
        uuid_v4 = uuid.uuid4()
        uuid_bytes = uuid_v4.bytes
        encoded = base64.urlsafe_b64encode(uuid_bytes).decode('utf-8').rstrip('=')
        return encoded[:22]
    
    url = f"{THINQ_API_BASE_URL}/devices"
    headers = {
        "Authorization": f"Bearer {pat_token}",
        "x-message-id": generate_message_id(),
        "x-country": country,
        "x-client-id": CLIENT_ID,
        "x-api-key": THINQ_API_KEY
    }
    
    try:
        # 타임아웃을 15초로 증가 (LG ThinQ API 응답이 느릴 수 있음)
        logger.info(f"🔍 LG ThinQ API 호출 시작: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        logger.info(f"✅ LG ThinQ API 응답 성공: {response.status_code}")
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"❌ 디바이스 목록 조회 타임아웃 (15초 초과)")
        logger.error(f"   URL: {url}")
        logger.error(f"   PAT 토큰 시작: {pat_token[:20]}...")
        raise HTTPException(status_code=504, detail="LG ThinQ API 응답 시간 초과. 네트워크 연결을 확인해주세요.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP 에러 발생: {e.response.status_code if e.response else 'N/A'}")
        if e.response:
            logger.error(f"   응답 내용: {e.response.text[:200]}")
        raise HTTPException(status_code=e.response.status_code if e.response else 500, detail=f"LG ThinQ API 오류: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 디바이스 목록 조회 실패: {str(e)}")
        logger.error(f"   에러 타입: {type(e).__name__}")
        raise

@app.post("/iot/auto-register")
async def auto_register_device_api(data: PatTokenRequest):
    """
    PAT 토큰만 받아서 자동으로 에어컨을 찾아 등록합니다.
    """
    try:
        pat_token = data.pat_token.strip()
        user_id = data.user_id or "default"
        
        if not pat_token:
            raise HTTPException(status_code=400, detail="PAT 토큰이 필요합니다.")
        
        if not pat_token.startswith("thinqpat_"):
            raise HTTPException(status_code=400, detail="올바른 PAT 토큰 형식이 아닙니다. 'thinqpat_'로 시작해야 합니다.")
        
        logger.info(f"📱 PAT 토큰으로 디바이스 자동 등록 요청 (사용자: {user_id})")
        logger.info(f"🔑 사용된 PAT 토큰: {pat_token[:20]}... (에어컨 모듈과 독립적으로 동작)")
        logger.info(f"⏱️  요청 시작 시간: {datetime.now().isoformat()}")
        
        # 디바이스 목록 조회 (에어컨 모듈과 독립적으로 동작)
        start_time = time.time()
        devices_result = get_devices_with_pat_token(pat_token)
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️  LG ThinQ API 응답 시간: {elapsed_time:.2f}초")
        
        # 디바이스 목록 추출
        devices = []
        if 'result' in devices_result and 'devices' in devices_result['result']:
            devices = devices_result['result']['devices']
        elif 'response' in devices_result:
            if isinstance(devices_result['response'], list):
                devices = devices_result['response']
            elif isinstance(devices_result['response'], dict) and 'devices' in devices_result['response']:
                devices = devices_result['response']['devices']
        
        if not devices:
            return {
                'success': False,
                'message': '등록된 디바이스가 없습니다. ThinQ 앱에서 디바이스를 등록해주세요.'
            }
        
        # 에어컨만 필터링
        logger.info(f"📋 총 {len(devices)}개의 디바이스 발견, 에어컨 필터링 시작...")
        air_conditioners = []
        for idx, device in enumerate(devices):
            device_info = device.get('deviceInfo', {})
            device_type = device_info.get('type') or device.get('deviceType') or device.get('type', '')
            alias = device_info.get('alias', device.get('alias', ''))
            model_name = device_info.get('modelName', device.get('modelName', ''))
            
            # 디바이스 정보 로깅 (디버깅용)
            logger.info(f"  디바이스 {idx + 1}:")
            logger.info(f"    - deviceId: {device.get('deviceId', 'N/A')[:30]}...")
            logger.info(f"    - alias: {alias}")
            logger.info(f"    - modelName: {model_name}")
            logger.info(f"    - deviceType (deviceInfo.type): {device_info.get('type', 'N/A')}")
            logger.info(f"    - deviceType (root): {device.get('deviceType', 'N/A')}")
            logger.info(f"    - deviceType (root.type): {device.get('type', 'N/A')}")
            logger.info(f"    - 최종 device_type: {device_type}")
            
            # 에어컨 타입 체크 (다양한 형식 지원)
            is_air_conditioner = False
            device_type_upper = device_type.upper() if device_type else ''
            alias_upper = alias.upper() if alias else ''
            model_name_upper = model_name.upper() if model_name else ''
            
            # 1. deviceType으로 확인
            if (device_type == 'DEVICE_AIR_CONDITIONER' or 
                device_type_upper == 'DEVICE_AIR_CONDITIONER' or
                device_type_upper == 'AIR_CONDITIONER' or
                device_type_upper == 'AIRCONDITIONER' or
                ('AIR' in device_type_upper and 'CONDITIONER' in device_type_upper) or
                'AIRCON' in device_type_upper):
                is_air_conditioner = True
                logger.info(f"    ✅ deviceType으로 에어컨 인식됨")
            
            # 2. alias로 확인 (가장 확실한 방법)
            if not is_air_conditioner:
                if any(keyword in alias_upper for keyword in ['에어컨', 'AIR', 'AIRCON', 'AC', 'AIRCONDITIONER']):
                    is_air_conditioner = True
                    logger.info(f"    ✅ alias로 에어컨 인식됨: {alias}")
            
            # 3. modelName으로 확인
            if not is_air_conditioner:
                if any(keyword in model_name_upper for keyword in ['AC', 'AIR', 'AIRCON', '에어컨', 'AIRCONDITIONER']):
                    is_air_conditioner = True
                    logger.info(f"    ✅ modelName으로 에어컨 인식됨: {model_name}")
            
            if is_air_conditioner:
                air_conditioners.append({
                    'deviceId': device.get('deviceId'),
                    'alias': alias,
                    'modelName': model_name,
                    'online': device.get('online', False),
                    'deviceType': device_type
                })
                logger.info(f"    ✅ 에어컨 목록에 추가됨")
            else:
                logger.info(f"    ❌ 에어컨이 아님 (스킵)")
        
        logger.info(f"🔍 에어컨 필터링 결과: {len(air_conditioners)}개의 에어컨 발견")
        
        if len(air_conditioners) == 0:
            return {
                'success': False,
                'message': '등록된 에어컨이 없습니다. ThinQ 앱에서 에어컨을 등록해주세요.'
            }
        elif len(air_conditioners) == 1:
            # 에어컨이 1개면 자동 등록
            device = air_conditioners[0]
            device_id = device['deviceId']
            device_name = device['alias']
            
            logger.info(f"💾 IoT 디바이스 저장 시작: user_id={user_id}, device_id={device_id[:20] if device_id else 'None'}..., device_name={device_name}")
            
            # login 테이블에 해당 user_id가 있는지 확인
            try:
                with engine.connect() as conn:
                    user_check_query = text("""
                        SELECT COUNT(*) as count FROM login WHERE id = :user_id
                    """)
                    user_check_result = conn.execute(user_check_query, {'user_id': user_id})
                    user_exists = user_check_result.fetchone().count > 0
                    
                    if not user_exists:
                        logger.warning(f"⚠️ login 테이블에 user_id={user_id}가 없습니다. IoT 등록을 건너뜁니다.")
                        return {
                            'success': False,
                            'message': f'사용자 {user_id}가 등록되지 않았습니다. 먼저 회원가입을 완료해주세요.'
                        }
                    else:
                        logger.info(f"✅ login 테이블에 user_id={user_id} 존재 확인")
            except Exception as e:
                logger.error(f"❌ 사용자 확인 실패: {str(e)}")
                return {
                    'success': False,
                    'message': '사용자 확인 중 오류가 발생했습니다.'
                }
            
            # 사용자별로 저장 (DB + 메모리 캐시)
            try:
                save_iot_device_to_db(user_id, pat_token, device_id, device_name, device['modelName'])
                logger.info(f"✅ IoT 디바이스 저장 성공: user_id={user_id}")
            except HTTPException as e:
                # 이미 등록된 기기인 경우 에러 메시지 반환
                logger.warning(f"⚠️ IoT 디바이스 저장 실패 (이미 등록됨): user_id={user_id}, error={e.detail}")
                return {
                    'success': False,
                    'message': e.detail,
                    'error': 'DEVICE_ALREADY_REGISTERED'
                }
            except Exception as e:
                logger.error(f"❌ IoT 디바이스 저장 실패: user_id={user_id}, error={str(e)}")
                import traceback
                logger.error(f"❌ 상세 에러: {traceback.format_exc()}")
                return {
                    'success': False,
                    'message': f'디바이스 등록 중 오류가 발생했습니다: {str(e)}'
                }
            # 메모리 캐시는 save_iot_device_to_db() 내부에서 업데이트되므로 여기서는 중복 업데이트하지 않음
            # (save_iot_device_to_db()가 실패한 경우에만 여기서 업데이트)
            if user_id not in user_iot_devices:
                user_iot_devices[user_id] = {
                    'pat_token': pat_token,
                    'device_id': device_id,
                    'device_name': device_name,
                    'model_name': device['modelName']
                }
                logger.info(f"✅ 메모리 캐시 업데이트 완료 (DB 저장 실패 시): user_id={user_id}")
            
            logger.info(f"✅ 에어컨 자동 등록 완료: {device_name} (ID: {device_id[:20]}...)")
            
            return {
                'success': True,
                'deviceId': device_id,
                'deviceName': device_name,
                'modelName': device['modelName'],
                'autoRegistered': True,
                'message': f'{device_name}이(가) 등록되었습니다.'
            }
        else:
            # 에어컨이 여러 개면 목록 반환
            return {
                'success': False,
                'needsSelection': True,
                'devices': air_conditioners,
                'message': '등록된 에어컨이 여러 개입니다. 하나를 선택해주세요.'
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 디바이스 자동 등록 실패: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f'디바이스 등록 실패: {str(e)}')

@app.post("/iot/register-device")
async def register_selected_device_api(data: dict):
    """
    사용자가 선택한 디바이스를 등록합니다.
    """
    try:
        pat_token = data.get('patToken', '').strip()
        device_id = data.get('deviceId', '').strip()
        user_id = data.get('userId', 'default')
        
        if not pat_token or not device_id:
            raise HTTPException(status_code=400, detail="PAT 토큰과 디바이스 ID가 필요합니다.")
        
        # 디바이스 정보 조회
        devices_result = get_devices_with_pat_token(pat_token)
        devices = []
        if 'result' in devices_result and 'devices' in devices_result['result']:
            devices = devices_result['result']['devices']
        elif 'response' in devices_result:
            if isinstance(devices_result['response'], list):
                devices = devices_result['response']
        
        # 선택한 디바이스 찾기
        selected_device = None
        for device in devices:
            if device.get('deviceId') == device_id:
                selected_device = device
                break
        
        if not selected_device:
            raise HTTPException(status_code=404, detail="선택한 디바이스를 찾을 수 없습니다.")
        
        device_info = selected_device.get('deviceInfo', {})
        device_name = device_info.get('alias', '에어컨')
        
        # 저장 (DB + 메모리 캐시)
        try:
            save_iot_device_to_db(user_id, pat_token, device_id, device_name, device_info.get('modelName', ''))
            # 메모리 캐시도 업데이트
            user_iot_devices[user_id] = {
                'pat_token': pat_token,
                'device_id': device_id,
                'device_name': device_name,
                'model_name': device_info.get('modelName', '')
            }
            
            logger.info(f"✅ 디바이스 등록 완료: {device_name} (ID: {device_id[:20]}...)")
            
            return {
                'success': True,
                'deviceId': device_id,
                'deviceName': device_name,
                'message': f'{device_name}이(가) 등록되었습니다.'
            }
        except HTTPException as e:
            # 이미 등록된 기기인 경우 에러 메시지 반환
            logger.warning(f"⚠️ 디바이스 등록 실패 (이미 등록됨): user_id={user_id}, error={e.detail}")
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 디바이스 등록 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'디바이스 등록 실패: {str(e)}')

@app.get("/iot/device-status")
async def get_device_registration_status_api(user_id: Optional[str] = "default"):
    """
    사용자의 디바이스 등록 상태를 조회합니다.
    """
    device_info = user_iot_devices.get(user_id)
    
    if not device_info:
        return {
            'success': False,
            'registered': False,
            'message': '등록된 디바이스가 없습니다.'
        }
    
    return {
        'success': True,
        'registered': True,
        'deviceId': device_info['device_id'],
        'deviceName': device_info['device_name'],
        'modelName': device_info.get('model_name', '')
    }

@app.get("/iot/device-status/db")
async def get_device_registration_status_from_db_api(user_id: Optional[str] = "default"):
    """
    DB에서 사용자의 디바이스 등록 상태를 조회합니다 (디버깅용)
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT user_id, pat_token, device_id, device_name, model_name, created_at, updated_at
                FROM iot_devices
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            result = conn.execute(query, {'user_id': user_id})
            row = result.fetchone()
            
            if not row:
                return {
                    'success': False,
                    'registered': False,
                    'message': 'DB에 등록된 디바이스가 없습니다.',
                    'storage_type': 'database',
                    'memory_cache': user_iot_devices.get(user_id) is not None
                }
            
            return {
                'success': True,
                'registered': True,
                'deviceId': row.device_id,
                'deviceName': row.device_name,
                'modelName': row.model_name or '',
                'createdAt': row.created_at.isoformat() if row.created_at else None,
                'updatedAt': row.updated_at.isoformat() if row.updated_at else None,
                'storage_type': 'database',
                'memory_cache': user_iot_devices.get(user_id) is not None
            }
    except Exception as e:
        logger.error(f"❌ DB에서 디바이스 등록 상태 조회 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'storage_type': 'database',
            'memory_cache': user_iot_devices.get(user_id) is not None
        }

@app.get("/iot/device-status/by-user-no")
async def get_device_registration_status_by_user_no(user_no: int = Depends(verify_token)):
    """
    user_no로 사용자의 디바이스 등록 상태를 조회합니다 (인증 필요)
    """
    try:
        with engine.connect() as conn:
            # user_no로 user_id 조회
            user_query = text("""
                SELECT id FROM login WHERE no = :user_no
            """)
            user_result = conn.execute(user_query, {'user_no': user_no})
            user = user_result.fetchone()
            
            if not user:
                return {
                    'success': False,
                    'registered': False,
                    'message': '사용자를 찾을 수 없습니다.'
                }
            
            user_id = user.id
            
            # user_id로 IoT 디바이스 조회
            device_query = text("""
                SELECT user_id, pat_token, device_id, device_name, model_name, created_at, updated_at
                FROM iot_devices
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            device_result = conn.execute(device_query, {'user_id': user_id})
            device_row = device_result.fetchone()
            
            if not device_row:
                # 메모리 캐시도 확인
                device_info = user_iot_devices.get(user_id)
                if device_info:
                    return {
                        'success': True,
                        'registered': True,
                        'deviceId': device_info['device_id'],
                        'deviceName': device_info['device_name'],
                        'modelName': device_info.get('model_name', ''),
                        'patToken': device_info.get('pat_token', ''),
                        'storage_type': 'memory'
                    }
                
                return {
                    'success': False,
                    'registered': False,
                    'message': '등록된 디바이스가 없습니다.'
                }
            
            # 메모리 캐시도 업데이트
            user_iot_devices[user_id] = {
                'pat_token': device_row.pat_token,
                'device_id': device_row.device_id,
                'device_name': device_row.device_name,
                'model_name': device_row.model_name or ''
            }
            
            return {
                'success': True,
                'registered': True,
                'deviceId': device_row.device_id,
                'deviceName': device_row.device_name,
                'modelName': device_row.model_name or '',
                'patToken': device_row.pat_token or '',
                'createdAt': device_row.created_at.isoformat() if device_row.created_at else None,
                'updatedAt': device_row.updated_at.isoformat() if device_row.updated_at else None,
                'storage_type': 'database'
            }
    except Exception as e:
        logger.error(f"❌ user_no로 디바이스 등록 상태 조회 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'registered': False,
            'message': f'디바이스 등록 상태 조회 실패: {str(e)}'
        }

@app.post("/iot/test-pat-token")
async def test_pat_token_connection(data: PatTokenRequest):
    """
    PAT 토큰 연결 테스트 (타임아웃 전에 빠르게 확인)
    """
    try:
        pat_token = data.pat_token.strip()
        
        if not pat_token:
            raise HTTPException(status_code=400, detail="PAT 토큰이 필요합니다.")
        
        if not pat_token.startswith("thinqpat_"):
            raise HTTPException(status_code=400, detail="올바른 PAT 토큰 형식이 아닙니다.")
        
        logger.info(f"🧪 PAT 토큰 연결 테스트 시작: {pat_token[:20]}...")
        
        # 짧은 타임아웃으로 빠른 테스트 (5초)
        import requests
        THINQ_API_BASE_URL = "https://api-kic.lgthinq.com"
        THINQ_API_KEY = "v6GFvkweNo7DK7yD3ylIZ9w52aKBU0eJ7wLXkSR3"
        CLIENT_ID = "poseul-app"
        import base64
        import uuid
        
        def generate_message_id():
            uuid_v4 = uuid.uuid4()
            uuid_bytes = uuid_v4.bytes
            encoded = base64.urlsafe_b64encode(uuid_bytes).decode('utf-8').rstrip('=')
            return encoded[:22]
        
        url = f"{THINQ_API_BASE_URL}/devices"
        headers = {
            "Authorization": f"Bearer {pat_token}",
            "x-message-id": generate_message_id(),
            "x-country": "KR",
            "x-client-id": CLIENT_ID,
            "x-api-key": THINQ_API_KEY
        }
        
        try:
            logger.info(f"🔍 LG ThinQ API 테스트 호출: {url}")
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            logger.info(f"✅ PAT 토큰 연결 테스트 성공: {response.status_code}")
            
            # 응답 데이터 파싱
            result = response.json()
            device_count = 0
            if 'result' in result and 'devices' in result['result']:
                device_count = len(result['result']['devices'])
            elif 'response' in result:
                if isinstance(result['response'], list):
                    device_count = len(result['response'])
                elif isinstance(result['response'], dict) and 'devices' in result['response']:
                    device_count = len(result['response']['devices'])
            
            return {
                'success': True,
                'connected': True,
                'deviceCount': device_count,
                'message': f'PAT 토큰 연결 성공! 등록된 디바이스: {device_count}개'
            }
        except requests.exceptions.Timeout:
            logger.error(f"❌ PAT 토큰 연결 테스트 타임아웃 (5초 초과)")
            return {
                'success': False,
                'connected': False,
                'error': 'timeout',
                'message': 'LG ThinQ API 응답 시간 초과 (5초). 네트워크 연결을 확인해주세요.'
            }
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 500
            logger.error(f"❌ PAT 토큰 연결 테스트 HTTP 에러: {status_code}")
            error_text = e.response.text[:200] if e.response else str(e)
            return {
                'success': False,
                'connected': False,
                'error': 'http_error',
                'statusCode': status_code,
                'message': f'LG ThinQ API 오류 ({status_code}): {error_text}'
            }
        except Exception as e:
            logger.error(f"❌ PAT 토큰 연결 테스트 실패: {str(e)}")
            return {
                'success': False,
                'connected': False,
                'error': 'unknown',
                'message': f'연결 테스트 실패: {str(e)}'
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PAT 토큰 테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'테스트 실패: {str(e)}')

# ==================== 온도 범위 설정 API ====================

class TemperatureRangeRequest(BaseModel):
    age: int
    bmi: float
    gender: str  # 'M' 또는 'F', 또는 'MALE'/'FEMALE', 또는 0/1
    force_update: Optional[bool] = False  # 강제 업데이트 여부

@app.post("/temperature-range")
async def set_temperature_range(data: TemperatureRangeRequest, user_no: int = Depends(verify_token)):
    """
    사용자 특성(나이, BMI, 성별)에 따라 쾌적 온도 범위를 계산하고 DB에 저장
    (처음 한번만 적용, 이미 설정되어 있으면 기존 값 유지)
    """
    try:
        logger.info(f"🌡️ 온도 범위 설정 요청: 나이={data.age}세, BMI={data.bmi}, 성별={data.gender}, force_update={data.force_update}, user_no={user_no}")
        
        # 온도 범위 초기화
        success, min_temp, max_temp = temperature_control_logic.initialize_user_temperature_range(
            engine=engine,
            age=data.age,
            bmi=data.bmi,
            gender=data.gender,
            air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
            set_temperature_func=set_temperature,
            user_no=user_no,
            force_update=data.force_update
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="온도 범위 설정 실패")
        
        return {
            "success": True,
            "message": "온도 범위 설정 완료",
            "min_temp": min_temp,
            "max_temp": max_temp,
            "target_temp": (min_temp + max_temp) / 2.0,
            "age": data.age,
            "bmi": data.bmi,
            "gender": data.gender
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"온도 범위 설정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 범위 설정 실패: {str(e)}')

@app.get("/temperature-range")
async def get_temperature_range(user_no: int = Depends(verify_token)):
    """
    DB에서 저장된 쾌적 온도 범위 조회 (사용자별 분리)
    """
    try:
        logger.info(f"🌡️ 온도 범위 조회 요청 (user_no={user_no})")
        
        # 1. 먼저 수동 조절 캐시 확인
        is_cached = False
        cached_min_temp = None
        cached_max_temp = None
        try:
            from temperature_threshold_cache import get_temperature_threshold
            cached_threshold = get_temperature_threshold(user_no)
            
            if cached_threshold is not None:
                cached_min_temp = cached_threshold.get("min_temp")
                cached_max_temp = cached_threshold.get("max_temp")
                
                if cached_min_temp is not None and cached_max_temp is not None:
                    is_cached = True
                    logger.info(f"✅ 수동 조절 캐시 발견: {cached_min_temp}~{cached_max_temp}°C (user_no={user_no})")
        except ImportError as e:
            logger.debug(f"temperature_threshold_cache 모듈 없음: {e}")
        except Exception as e:
            logger.debug(f"캐시 조회 중 오류 (무시): {e}")
        
        # 2. 수동 조절 캐시가 있으면 반환
        if is_cached:
            return {
                "success": True,
                "min_temp": float(cached_min_temp),
                "max_temp": float(cached_max_temp),
                "target_temp": (float(cached_min_temp) + float(cached_max_temp)) / 2.0,
                "is_cached": True,
                "is_auto": False
            }
        
        # 3. 캐시가 없으면 DB에서 가져오기 (room_threshold = 자동 조절 범위)
        temperature_range = temperature_control_logic.get_temperature_range_from_db(engine, user_no=user_no)
        
        if temperature_range is not None:
            min_temp, max_temp = temperature_range
            return {
                "success": True,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "target_temp": (min_temp + max_temp) / 2.0,
                "is_cached": False,
                "is_auto": True  # room_threshold에서 가져온 값 = 자동 조절 범위
            }
        
        # 4. DB에도 없으면 predicted_results에서 사용자 정보를 가져와서 자동 조절 범위 계산
        logger.info("📋 room_threshold에 값이 없음. 사용자 정보로 자동 조절 범위 계산 시도...")
        try:
            with engine.connect() as conn:
                # predicted_results 테이블에서 최신 사용자 정보 가져오기 (user_no 필터링)
                query = text("""
                    SELECT age, bmi, gender 
                    FROM predicted_results 
                    WHERE age IS NOT NULL 
                      AND bmi IS NOT NULL 
                      AND gender IS NOT NULL
                      AND user_no = :user_no
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = conn.execute(query, {'user_no': user_no}).fetchone()
                
                if result:
                    age = int(result.age) if result.age else 30
                    bmi = float(result.bmi) if result.bmi else 22.0
                    gender = result.gender
                    
                    # 자동 조절 범위 계산
                    min_temp, max_temp = calculate_comfort_temperature(gender, age, bmi)
                    logger.info(f"🌡️ 자동 조절 범위 계산: {min_temp}~{max_temp}°C (gender: {gender}, age: {age}, bmi: {bmi})")
                    
                    return {
                        "success": True,
                        "min_temp": min_temp,
                        "max_temp": max_temp,
                        "target_temp": (min_temp + max_temp) / 2.0,
                        "is_cached": False,
                        "is_auto": True  # 자동 계산된 값임을 표시
                    }
                else:
                    # 사용자 정보도 없으면 기본값 반환
                    logger.warning("⚠️ 사용자 정보도 없음. 기본값 사용")
                    return {
                        "success": False,
                        "message": "온도 범위가 설정되어 있지 않습니다.",
                        "min_temp": None,
                        "max_temp": None
                    }
        except Exception as e:
            logger.error(f"❌ 자동 조절 범위 계산 실패: {e}")
            return {
                "success": False,
                "message": "온도 범위가 설정되어 있지 않습니다.",
                "min_temp": None,
                "max_temp": None
            }
        
    except Exception as e:
        logger.error(f"온도 범위 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 범위 조회 실패: {str(e)}')

# ==================== 수면 모드 API ====================

class SleepModeRequest(BaseModel):
    duration_hours: float  # 수면 시간 (시간 단위)

@app.post("/sleep-mode/start")
async def start_sleep_mode(data: SleepModeRequest, user_no: int = Depends(verify_token)):
    """
    수면 모드 시작
    설정한 시간 동안만 모델 예측과 온도 조절이 동작
    """
    try:
        from datetime import datetime, timedelta
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=data.duration_hours)
        
        # user_no별로 관리
        global sleep_mode_states
        sleep_mode_states[user_no] = {
            "active": True,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": data.duration_hours
        }
        
        logger.info(f"😴 수면 모드 시작 (user_no: {user_no}): {data.duration_hours}시간 ({start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')})")
        
        return {
            "success": True,
            "message": f"수면 모드가 시작되었습니다. {data.duration_hours}시간 동안 자동 조절이 동작합니다.",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": data.duration_hours
        }
    except Exception as e:
        logger.error(f"❌ 수면 모드 시작 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'수면 모드 시작 실패: {str(e)}')

@app.post("/sleep-mode/stop")
async def stop_sleep_mode(user_no: int = Depends(verify_token)):
    """
    수면 모드 중지
    """
    try:
        # user_no별로 관리
        global sleep_mode_states
        sleep_mode_states[user_no] = {
            "active": False,
            "start_time": None,
            "end_time": None,
            "duration_hours": None
        }
        
        logger.info(f"😴 수면 모드 중지 (user_no: {user_no})")
        
        return {
            "success": True,
            "message": "수면 모드가 중지되었습니다."
        }
    except Exception as e:
        logger.error(f"❌ 수면 모드 중지 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'수면 모드 중지 실패: {str(e)}')

@app.get("/sleep-mode/status")
async def get_sleep_mode_status(user_no: int = Depends(verify_token)):
    """
    수면 모드 상태 조회
    """
    try:
        from datetime import datetime
        
        # user_no별로 관리
        global sleep_mode_states
        sleep_mode_state = sleep_mode_states.get(user_no, {
            "active": False,
            "start_time": None,
            "end_time": None,
            "duration_hours": None
        })
        
        # 수면 모드가 활성화되어 있고 종료 시간이 지났으면 자동으로 비활성화
        if sleep_mode_state["active"] and sleep_mode_state["end_time"]:
            end_time = datetime.fromisoformat(sleep_mode_state["end_time"])
            if datetime.now() >= end_time:
                sleep_mode_state["active"] = False
                sleep_mode_states[user_no] = sleep_mode_state
                logger.info(f"😴 수면 모드 자동 종료 (설정된 시간 경과, user_no: {user_no})")
        
        if sleep_mode_state["active"]:
            end_time = datetime.fromisoformat(sleep_mode_state["end_time"])
            remaining_seconds = (end_time - datetime.now()).total_seconds()
            remaining_hours = remaining_seconds / 3600.0
            
            return {
                "success": True,
                "active": True,
                "start_time": sleep_mode_state["start_time"],
                "end_time": sleep_mode_state["end_time"],
                "duration_hours": sleep_mode_state["duration_hours"],
                "remaining_hours": max(0, remaining_hours),
                "remaining_minutes": max(0, int(remaining_seconds / 60))
            }
        else:
            return {
                "success": True,
                "active": False,
                "start_time": None,
                "end_time": None,
                "duration_hours": None,
                "remaining_hours": 0,
                "remaining_minutes": 0
            }
    except Exception as e:
        logger.error(f"❌ 수면 모드 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'수면 모드 상태 조회 실패: {str(e)}')

# ==================== 기본 API ====================

@app.get("/")
async def root():
    return {"message": "Unified Server is running (Health Data + Model Prediction + IoT Control)"}

def convert_predicted_temp_to_code(predicted_temp, min_threshold, max_threshold):
    """
    예측된 피부 온도를 코드로 변환 (C: 추움, H: 더움, G: 쾌적)
    
    Parameters:
    - predicted_temp: 예측된 피부 온도
    - min_threshold: 최소 임계값
    - max_threshold: 최대 임계값
    
    Returns:
    - 'C' (추움): predicted_temp < min_threshold
    - 'H' (더움): predicted_temp > max_threshold
    - 'G' (쾌적): min_threshold <= predicted_temp <= max_threshold
    """
    if predicted_temp < min_threshold:
        return 'C'
    elif predicted_temp > max_threshold:
        return 'H'
    else:
        return 'G'

@app.post("/temperature_feedback")
async def save_temperature_feedback(data: TemperatureFeedbackRequest, user_no: int = Depends(verify_token)):
    """온도 피드백 저장 API - new_skinthreshold 테이블에 저장하고 예측값과 비교하여 임계값 조정 (사용자별 필터링)"""
    try:
        logger.info(f"📝 온도 피드백 저장 요청: {data.model_dump()}, user_no: {user_no}")
        
        # 피드백 값을 코드로 변환 (C: 추움, H: 더움, G: 쾌적)
        feedback_code = None
        if data.feedback == 'cold':
            feedback_code = 'C'
        elif data.feedback == 'hot':
            feedback_code = 'H'
        elif data.feedback == 'comfortable':
            feedback_code = 'G'
        else:
            logger.warning(f"⚠️ 알 수 없는 피드백 값: {data.feedback}")
            return {
                "success": False,
                "message": f"알 수 없는 피드백 값: {data.feedback}"
            }
        
        # 날짜 처리
        feedback_date = data.date
        if not feedback_date:
            feedback_date = datetime.now().isoformat()
        
        # JSON 파일에 피드백 저장 (user_no 포함, 파일 잠금 사용)
        feedback_file = os.path.join(os.path.dirname(__file__), 'temperature_feedback.json')
        
        try:
            # 기존 피드백 데이터 읽기 (파일 잠금 사용)
            feedbacks = safe_json_read(feedback_file)
            if not isinstance(feedbacks, list):
                feedbacks = []
            
            # 새 피드백 추가 (user_no 포함)
            feedback_entry = {
                'user_no': user_no,
                'feedback': feedback_code,
                'feedback_text': data.feedback,
                'date': feedback_date,
                'timestamp': datetime.now().isoformat()
            }
            feedbacks.append(feedback_entry)
            
            # JSON 파일에 저장 (파일 잠금 사용)
            safe_json_write(feedback_file, feedbacks)
            
            logger.info(f"✅ 피드백 JSON 파일에 저장 완료: {feedback_code} ({data.feedback}), user_no={user_no}")
        except Exception as e:
            logger.error(f"❌ 피드백 JSON 파일 저장 실패: {str(e)}")
        
        with engine.connect() as conn:
            # 피드백과 예측값 비교하여 임계값 조정
            try:
                # 최신 예측값 가져오기 (predicted_results 테이블에서)
                predicted_skin_temp = None
                predicted_skin_code = None
                try:
                    # predicted_results 테이블의 컬럼 구조 확인
                    columns = get_table_columns(conn, "predicted_results")
                    
                    # predicted_results 테이블에서 최신 예측값 가져오기 (ID로 정렬, user_no 필터링 - 해당 사용자만)
                    if user_no is None:
                        logger.warning("⚠️ user_no가 없어 예측값을 조회할 수 없습니다.")
                        latest_prediction = None
                    else:
                        user_filter, query_params = build_user_filter(user_no, allow_null=False)
                        order_by = get_order_by_clause(columns, "predicted_results")
                        
                        latest_prediction_query = text(f"""
                            SELECT predicted_skin_temp
                            FROM predicted_results
                            WHERE predicted_skin_temp IS NOT NULL
                              {user_filter}
                            {order_by}
                            LIMIT 1
                        """)
                        latest_prediction = execute_query_with_params(conn, latest_prediction_query, query_params).fetchone()
                    
                    if latest_prediction:
                        predicted_skin_temp = float(latest_prediction.predicted_skin_temp)
                        logger.info(f"📊 최신 예측 피부 온도: {predicted_skin_temp}°C")
                except Exception as e:
                    logger.warning(f"⚠️ 예측값 조회 실패: {str(e)}")
                
                # 현재 임계값 가져오기 (new_skinthreshold 테이블에서 최신 값 또는 기본값)
                min_threshold = 32.5
                max_threshold = 34.5
                
                try:
                    # new_skinthreshold 테이블 존재 여부 확인
                    if table_exists(conn, "new_skinthreshold"):
                        # 컬럼 확인 및 정렬 컬럼 결정
                        skin_columns = get_table_columns(conn, "new_skinthreshold")
                        skin_order_by = get_order_by_clause(skin_columns, "new_skinthreshold")
                        
                        # 최신 임계값 가져오기 (user_no 필터링)
                        threshold_user_filter, threshold_query_params = build_user_filter(user_no, allow_null=False)
                        if threshold_user_filter:
                            threshold_user_filter = "WHERE 1=1 " + threshold_user_filter
                        
                        latest_threshold_query = text(f"""
                            SELECT min_skinthreshold, max_skinthreshold
                            FROM new_skinthreshold
                            {threshold_user_filter}
                            {skin_order_by}
                            LIMIT 1
                        """)
                        latest_threshold = execute_query_with_params(conn, latest_threshold_query, threshold_query_params).fetchone()
                        
                        if latest_threshold and latest_threshold.min_skinthreshold is not None:
                            min_threshold = float(latest_threshold.min_skinthreshold)
                            max_threshold = float(latest_threshold.max_skinthreshold)
                            logger.info(f"📋 최신 임계값 사용: {min_threshold}~{max_threshold}°C")
                        else:
                            logger.info(f"📋 기본 임계값 사용: {min_threshold}~{max_threshold}°C")
                    else:
                        logger.info(f"📋 기본 임계값 사용 (new_skinthreshold 테이블 없음): {min_threshold}~{max_threshold}°C")
                except Exception as e:
                    logger.warning(f"⚠️ 임계값 조회 실패, 기본값 사용: {str(e)}")
                
                # 예측값을 코드로 변환
                if predicted_skin_temp is not None:
                    predicted_skin_code = convert_predicted_temp_to_code(predicted_skin_temp, min_threshold, max_threshold)
                    logger.info(f"🔮 예측값 코드 변환: {predicted_skin_temp}°C → {predicted_skin_code}")
                
                # 피드백과 예측값 비교하여 임계값 조정
                new_min_threshold = min_threshold
                new_max_threshold = max_threshold
                
                if predicted_skin_code is not None:
                    if feedback_code == predicted_skin_code:
                        # 같으면 기존 값 유지
                        logger.info(f"✅ 피드백과 예측값이 일치: {feedback_code} = {predicted_skin_code}, 임계값 유지")
                    else:
                        # 다르면 피드백에 따라 임계값 조정
                        if feedback_code == 'C':
                            # 추움: 각각 0.5도씩 올림
                            new_min_threshold = min_threshold + 0.5
                            new_max_threshold = max_threshold + 0.5
                            logger.info(f"❄️ 피드백: 추움(C), 임계값 조정: {min_threshold}~{max_threshold}°C → {new_min_threshold}~{new_max_threshold}°C")
                        elif feedback_code == 'H':
                            # 더움: 각각 0.5도씩 내림
                            new_min_threshold = min_threshold - 0.5
                            new_max_threshold = max_threshold - 0.5
                            logger.info(f"🔥 피드백: 더움(H), 임계값 조정: {min_threshold}~{max_threshold}°C → {new_min_threshold}~{new_max_threshold}°C")
                        elif feedback_code == 'G':
                            # 쾌적: 변경 없음
                            logger.info(f"✅ 피드백: 쾌적(G), 임계값 유지")
                else:
                    logger.warning("⚠️ 예측값이 없어 임계값 조정을 건너뜁니다.")
                
                # new_skinthreshold 테이블에 갱신된 임계값 저장
                try:
                    # new_skinthreshold 테이블 존재 여부 확인 및 생성
                    if not table_exists(conn, "new_skinthreshold"):
                        # 테이블이 없으면 생성
                        create_new_table = text("""
                            CREATE TABLE IF NOT EXISTS new_skinthreshold (
                                no INT AUTO_INCREMENT PRIMARY KEY,
                                min_skinthreshold DECIMAL(4,1) NOT NULL,
                                max_skinthreshold DECIMAL(4,1) NOT NULL,
                                feedback VARCHAR(1),
                                predicted_skin VARCHAR(1),
                                user_no INT DEFAULT NULL
                            )
                        """)
                        conn.execute(create_new_table)
                        conn.commit()
                        logger.info("✅ new_skinthreshold 테이블 생성 완료")
                    
                    # user_no 컬럼이 없으면 추가
                    check_and_add_user_no_column(conn, "new_skinthreshold")
                    
                    # 갱신된 임계값 저장 (user_no 포함)
                    insert_new_threshold = text("""
                        INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, feedback, predicted_skin, user_no)
                        VALUES (:min_threshold, :max_threshold, :feedback, :predicted_skin, :user_no)
                    """)
                    conn.execute(insert_new_threshold, {
                        'min_threshold': new_min_threshold,
                        'max_threshold': new_max_threshold,
                        'feedback': feedback_code,
                        'predicted_skin': predicted_skin_code,
                        'user_no': user_no
                    })
                    conn.commit()
                    logger.info(f"✅ new_skinthreshold 테이블에 갱신된 임계값 저장 완료: {new_min_threshold}~{new_max_threshold}°C")
                except Exception as e:
                    logger.error(f"❌ new_skinthreshold 테이블 저장 실패: {str(e)}")
                    
            except Exception as e:
                logger.error(f"❌ 피드백 처리 실패: {str(e)}")
            
            # 피드백 저장 후 자동으로 임계값 조정 처리
            try:
                success, message = feedback_based_adjustment.process_daily_feedback(engine, feedback_code)
                if success:
                    logger.info(f"✅ {message}")
                else:
                    logger.warning(f"⚠️ {message}")
            except Exception as e:
                logger.warning(f"⚠️ 피드백 기반 임계값 조정 실패 (계속 진행): {e}")
        
        return {
            "success": True,
            "message": "피드백이 저장되었습니다.",
            "feedback": data.feedback,
            "feedback_code": feedback_code,
            "predicted_skin_code": predicted_skin_code,
            "threshold_adjusted": predicted_skin_code is not None and feedback_code != predicted_skin_code
        }
    except Exception as e:
        logger.error(f"❌ 온도 피드백 저장 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피드백 저장 실패: {str(e)}"
        }

# ==================== 피드백 기반 조정 API ====================

@app.get("/feedback/count")
async def get_feedback_count(user_no: int = Depends(verify_token)):
    """
    현재 피드백 기간의 피드백 횟수 조회 API (사용자별 필터링)
    """
    try:
        count = feedback_based_adjustment.get_feedback_count(engine, user_no)
        is_within_limit = feedback_based_adjustment.is_within_feedback_limit(engine, user_no)
        return {
            "success": True,
            "count": count,
            "max_count": 7,
            "remaining": max(0, 7 - count),
            "is_within_limit": is_within_limit
        }
    except Exception as e:
        logger.error(f"❌ 피드백 횟수 조회 실패: {str(e)}")
        return {"success": False, "message": f"피드백 횟수 조회 실패: {str(e)}"}

@app.post("/feedback/reset")
async def reset_feedback_period():
    """
    피드백 기반 조정 기간 재시작 API
    (피드백 횟수 리셋, 다시 7번까지 가능)
    """
    try:
        success, message = feedback_based_adjustment.reset_feedback_period(engine)
        
        if success:
            return {
                "success": True,
                "message": message
            }
        else:
            return {
                "success": False,
                "message": message
            }
    except Exception as e:
        logger.error(f"❌ 피드백 기간 재시작 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피드백 기간 재시작 실패: {str(e)}"
        }

@app.get("/feedback/history")
async def get_feedback_history(days: int = 7):
    """
    최근 N일간의 임계값 조정 이력 조회
    
    Args:
        days: 조회할 일수 (기본값: 7)
    """
    try:
        history = feedback_based_adjustment.get_adjustment_history(engine, days)
        return {
            "success": True,
            "days": days,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"❌ 조정 이력 조회 실패: {str(e)}")
        return {
            "success": False,
            "message": f"조정 이력 조회 실패: {str(e)}"
        }

# ==================== 피부온도 분류 기준 관리 API ====================

class ThresholdUpdateRequest(BaseModel):
    """피부온도 분류 기준 업데이트 요청"""
    cold_threshold: float
    hot_threshold: float

@app.post("/threshold/update")
async def update_thresholds_api(data: ThresholdUpdateRequest, user_no: int = Depends(verify_token)):
    """
    피부온도 분류 기준 업데이트 (사용자별 분리, 즉시 적용)
    """
    try:
        old_cold, old_hot = get_user_thresholds(user_no)
        
        set_user_thresholds(user_no, data.cold_threshold, data.hot_threshold)
        
        logger.info(f"🔄 피부온도 분류 기준 업데이트 (user_no={user_no}): COLD={old_cold}°C → {data.cold_threshold}°C, HOT={old_hot}°C → {data.hot_threshold}°C")
        
        # 즉시 적용: 수면 모드가 활성화되어 있으면 제어 로직 실행
        try:
            global sleep_mode_states
            sleep_mode_state = sleep_mode_states.get(user_no, {
                "active": False,
                "start_time": None,
                "end_time": None,
                "duration_hours": None
            })
            sleep_mode_active = sleep_mode_state.get("active", False)
            
            # 종료 시간 확인
            if sleep_mode_active and sleep_mode_state.get("end_time"):
                end_time = datetime.fromisoformat(sleep_mode_state["end_time"])
                if datetime.now() >= end_time:
                    # 수면 모드 자동 종료
                    sleep_mode_states[user_no] = {
                        "active": False,
                        "start_time": None,
                        "end_time": None,
                        "duration_hours": None
                    }
                    sleep_mode_active = False
                    logger.info(f"😴 수면 모드 자동 종료 (user_no: {user_no}, 설정된 시간 경과)")
            
            if sleep_mode_active:
                logger.info(f"🔄 임계값 업데이트 즉시 적용 - 제어 로직 실행 (user_no={user_no})")
                
                # 사용자별 임계값 가져오기 (방금 업데이트한 값)
                cold_threshold, hot_threshold = get_user_thresholds(user_no)
                
                # 콜백 함수 래퍼 (user_no 포함)
                def update_thresholds_wrapper(new_cold: float, new_hot: float):
                    update_thresholds(new_cold, new_hot, user_no)
                
                # 제어 로직 즉시 실행
                air_conditioner_auto_control.adjust_air_conditioner(
                    engine=engine,
                    air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
                    get_air_conditioner_state_func=get_air_conditioner_state,
                    set_temperature_func=set_temperature,
                    cold_threshold=cold_threshold,
                    hot_threshold=hot_threshold,
                    update_threshold_callback=update_thresholds_wrapper,
                    min_interval_minutes=30.0,  # 30분 간격으로 조절
                    user_no=user_no
                )
                logger.info(f"✅ 임계값 업데이트 즉시 적용 완료 (user_no={user_no})")
            else:
                logger.info(f"ℹ️ 수면 모드가 비활성화되어 있어 즉시 적용하지 않습니다. (user_no={user_no})")
        except Exception as apply_error:
            logger.warning(f"⚠️ 임계값 즉시 적용 중 오류 (무시하고 계속 진행): {apply_error}")
        
        return {
            "success": True,
            "message": "피부온도 분류 기준이 업데이트되었습니다.",
            "cold_threshold": data.cold_threshold,
            "hot_threshold": data.hot_threshold
        }
    except Exception as e:
        logger.error(f"❌ 피부온도 분류 기준 업데이트 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피부온도 분류 기준 업데이트 실패: {str(e)}"
        }

@app.get("/threshold")
async def get_thresholds_api(user_no: int = Depends(verify_token)):
    """
    현재 피부온도 분류 기준 조회 (사용자별 분리)
    """
    try:
        cold_threshold, hot_threshold = get_user_thresholds(user_no)
        return {
            "success": True,
            "cold_threshold": cold_threshold,
            "hot_threshold": hot_threshold
        }
    except Exception as e:
        logger.error(f"❌ 피부온도 분류 기준 조회 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피부온도 분류 기준 조회 실패: {str(e)}"
        }

@app.get("/health")
async def health_check(request: Request):
    """서버 상태 확인 (모델, 에어컨, DB 연결 상태 포함)"""
    # 서버의 실제 IP 주소 가져오기
    server_url = None
    try:
        # 요청에서 호스트 정보 가져오기
        host = request.headers.get("host", "localhost:3000")
        # X-Forwarded-Host 헤더 확인 (프록시 환경)
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_host:
            host = forwarded_host
        
        # 프로토콜 확인 (HTTPS 또는 HTTP)
        scheme = 'http'
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            scheme = forwarded_proto
        elif hasattr(request, 'url') and hasattr(request.url, 'scheme'):
            scheme = request.url.scheme
        
        # 서버 URL 구성
        server_url = f"{scheme}://{host}"
    except Exception as e:
        logger.warning(f"서버 URL 구성 실패: {e}")
        # 실패 시 기본값 사용
        try:
            import socket
            # 로컬 IP 주소 가져오기
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            server_url = f"http://{local_ip}:3000"
        except:
            server_url = "http://localhost:3000"
    
    # DB 연결 테스트
    db_connected = False
    db_error = None
    try:
        with engine.connect() as conn:
            # 간단한 쿼리로 연결 테스트
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            db_connected = True
    except Exception as e:
        db_error = str(e)
        logger.error(f"❌ DB 연결 테스트 실패: {db_error}")
    
    # Android 앱 건강 상태 확인
    android_health_status = None
    if android_app_health_logs:
        recent_logs = android_app_health_logs[-10:]  # 최근 10개
        anr_logs = [log for log in recent_logs if log.get("type") == "ANR"]
        recent_metrics = [log for log in recent_logs if log.get("type") != "ANR"]
        
        if recent_metrics:
            cpu_values = [log.get("cpu_usage_percent") for log in recent_metrics if log.get("cpu_usage_percent")]
            memory_values = [log.get("memory_pressure_some") for log in recent_metrics if log.get("memory_pressure_some")]
            
            android_health_status = {
                "has_recent_metrics": True,
                "recent_anr_count": len(anr_logs),
                "avg_cpu_usage": sum(cpu_values) / len(cpu_values) if cpu_values else None,
                "avg_memory_pressure": sum(memory_values) / len(memory_values) if memory_values else None,
                "status": "warning" if (anr_logs or (cpu_values and max(cpu_values) > 30) or (memory_values and max(memory_values) > 40)) else "healthy"
            }
        else:
            android_health_status = {
                "has_recent_metrics": False,
                "status": "unknown"
            }
    else:
        android_health_status = {
            "has_recent_metrics": False,
            "status": "no_data"
        }
    
    # 전체 상태 결정
    overall_status = "healthy"
    if not db_connected or not model_loaded:
        overall_status = "degraded"
    if android_health_status and android_health_status.get("status") == "warning":
        overall_status = "warning"
    
    return {
        "status": overall_status,
        "server_url": server_url,  # 서버 URL 추가
        "model_loaded": model_loaded,
        "air_conditioner_available": AIR_CONDITIONER_AVAILABLE,
        "database_connected": db_connected,
        "database_error": db_error if not db_connected else None,
        "android_app_health": android_health_status
    }

@app.get("/health/db")
async def test_db_connection():
    """DB 연결 테스트 전용 엔드포인트"""
    try:
        with engine.connect() as conn:
            # 간단한 쿼리로 연결 테스트
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            
            # 테이블 존재 여부 확인
            table_check = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'predicted_results'
            """))
            table_exists = table_check.fetchone().count > 0
            
            # 데이터 개수 확인
            data_count = 0
            if table_exists:
                count_result = conn.execute(text("SELECT COUNT(*) as count FROM predicted_results"))
                data_count = count_result.fetchone().count
            
            return {
                "success": True,
                "connected": True,
                "test_query": "SELECT 1",
                "test_result": row.test if row else None,
                "table_exists": table_exists,
                "data_count": data_count,
                "message": "DB 연결 성공"
            }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ DB 연결 테스트 실패: {error_msg}")
        return {
            "success": False,
            "connected": False,
            "error": error_msg,
            "message": "DB 연결 실패"
        }

# ==================== 차트 데이터 API ====================

@app.get("/chart/heartrate")
async def get_heartrate_chart_data(hours: int = 12):
    """
    심박수 차트 데이터 조회 (predicted_results 테이블에서)
    
    Args:
        hours: 조회할 시간 수 (기본값: 12시간)
    """
    try:
        with engine.connect() as conn:
            # 최근 N개 데이터 조회 (no 기준으로 정렬)
            query = text("""
                SELECT 
                    HR_mean as heartRate,
                    no,
                    predicted_skin_temp
                FROM predicted_results
                ORDER BY no DESC
                LIMIT :limit
            """)
            
            result = conn.execute(query, {"limit": hours})
            rows = result.fetchall()
            
            if not rows:
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "message": "데이터가 없습니다."
                }
            
            # 시간 순서대로 정렬 (no 오름차순)
            data = []
            for row in rows:
                data.append({
                    "heartRate": float(row.heartRate) if row.heartRate else 0,
                    "no": int(row.no) if row.no else 0,
                    "predicted_skin_temp": float(row.predicted_skin_temp) if row.predicted_skin_temp else 0
                })
            
            # no 기준 오름차순 정렬
            data.sort(key=lambda x: x["no"])
            
            # 시간 포맷팅 (1시간 간격으로 가정, 현재 시간부터 역산)
            chart_data = []
            now = datetime.now()
            for i, item in enumerate(data):
                # 현재 시간부터 역산하여 시간 계산
                hours_ago = len(data) - 1 - i
                target_time = now - timedelta(hours=hours_ago)
                
                chart_data.append({
                    "timestamp": target_time.isoformat(),
                    "hour": target_time.hour,
                    "minute": target_time.minute,
                    "heartRate": item["heartRate"]
                })
            
            return {
                "success": True,
                "data": chart_data,
                "count": len(chart_data)
            }
    except Exception as e:
        logger.error(f"❌ 심박수 차트 데이터 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"심박수 차트 데이터 조회 실패: {str(e)}")

@app.get("/chart/temperature")
async def get_temperature_chart_data(hours: int = 12):
    """
    온도 차트 데이터 조회 (test_script_logs 테이블에서)
    
    Args:
        hours: 조회할 시간 수 (기본값: 12시간)
    """
    try:
        with engine.connect() as conn:
            # 최근 N시간 데이터 조회 (created_at 기준)
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            query = text("""
                SELECT 
                    classification_results,
                    majority_result,
                    temperature_action,
                    previous_temperature,
                    new_temperature,
                    created_at
                FROM test_script_logs
                WHERE created_at >= :cutoff_time
                ORDER BY created_at ASC
            """)
            
            result = conn.execute(query, {"cutoff_time": cutoff_time})
            rows = result.fetchall()
            
            chart_data = []
            for row in rows:
                # majority_result를 분류로 변환 (H=더움, C=추움, G=적정)
                category_map = {
                    'H': '더움',
                    'C': '추움',
                    'G': '적정'
                }
                category = category_map.get(row.majority_result, '적정')
                
                # created_at에서 시간 추출
                created_at = row.created_at if row.created_at else datetime.now()
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                chart_data.append({
                    "timestamp": created_at.isoformat(),
                    "hour": created_at.hour,
                    "minute": created_at.minute,
                    "predictedTemperature": float(row.new_temperature) if row.new_temperature else 0,
                    "temperatureCategory": category,
                    "currentTemperature": float(row.previous_temperature) if row.previous_temperature else None,
                    "targetTemperature": float(row.new_temperature) if row.new_temperature else None,
                    "classificationResults": row.classification_results,
                    "temperatureAction": row.temperature_action
                })
            
            return {
                "success": True,
                "data": chart_data,
                "count": len(chart_data)
            }
    except Exception as e:
        logger.error(f"❌ 온도 차트 데이터 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"온도 차트 데이터 조회 실패: {str(e)}")

# ==================== Android App Health Monitoring ====================

# android_app_health_logs는 이미 파일 상단에서 초기화됨

@app.post("/android/health/metrics")
async def receive_android_health_metrics(metrics: AndroidAppHealthMetrics):
    """Android 앱 건강 지표 수신 및 로깅"""
    try:
        # 타임스탬프 추가
        if not metrics.timestamp:
            metrics.timestamp = datetime.now().isoformat()
        
        # 로그 저장
        log_entry = {
            "timestamp": metrics.timestamp,
            "package_name": metrics.package_name or "io.ionic.starter",
            "cpu_usage_percent": metrics.cpu_usage_percent,
            "cpu_user_percent": metrics.cpu_user_percent,
            "cpu_kernel_percent": metrics.cpu_kernel_percent,
            "memory_pressure_some": metrics.memory_pressure_some,
            "memory_pressure_full": metrics.memory_pressure_full,
            "io_pressure_some": metrics.io_pressure_some,
            "io_pressure_full": metrics.io_pressure_full,
            "cpu_pressure_some": metrics.cpu_pressure_some,
            "cpu_pressure_full": metrics.cpu_pressure_full,
            "anr_count": metrics.anr_count,
            "connectivity_errors": metrics.connectivity_errors,
            "load_avg_1min": metrics.load_avg_1min,
            "load_avg_5min": metrics.load_avg_5min,
            "load_avg_15min": metrics.load_avg_15min,
            "error_log": metrics.error_log
        }
        
        android_app_health_logs.append(log_entry)
        
        # 최근 1000개만 유지
        if len(android_app_health_logs) > 1000:
            android_app_health_logs.pop(0)
        
        # 경고 조건 확인
        warnings = []
        if metrics.cpu_usage_percent and metrics.cpu_usage_percent > 30:
            warnings.append(f"높은 CPU 사용률: {metrics.cpu_usage_percent:.1f}%")
        if metrics.memory_pressure_some and metrics.memory_pressure_some > 40:
            warnings.append(f"높은 메모리 압력: {metrics.memory_pressure_some:.2f}")
        if metrics.io_pressure_some and metrics.io_pressure_some > 40:
            warnings.append(f"높은 I/O 압력: {metrics.io_pressure_some:.2f}")
        if metrics.cpu_pressure_some and metrics.cpu_pressure_some > 80:
            warnings.append(f"높은 CPU 압력: {metrics.cpu_pressure_some:.2f}")
        if metrics.anr_count and metrics.anr_count > 0:
            warnings.append(f"ANR 발생: {metrics.anr_count}건")
        if metrics.connectivity_errors and metrics.connectivity_errors > 0:
            warnings.append(f"연결 오류: {metrics.connectivity_errors}건")
        
        if warnings:
            logger.warning(f"⚠️ Android 앱 건강 지표 경고: {'; '.join(warnings)}")
        else:
            logger.info(f"✅ Android 앱 건강 지표 수신: CPU={metrics.cpu_usage_percent}%, 메모리 압력={metrics.memory_pressure_some}")
        
        return {
            "success": True,
            "message": "건강 지표 수신 완료",
            "warnings": warnings if warnings else None,
            "timestamp": metrics.timestamp
        }
        
    except Exception as e:
        logger.error(f"❌ Android 앱 건강 지표 수신 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'건강 지표 수신 실패: {str(e)}')

@app.post("/android/health/anr")
async def receive_anr_log(anr_data: dict):
    """ANR 로그 수신 및 분석"""
    try:
        timestamp = datetime.now().isoformat()
        
        # ANR 정보 추출
        package_name = anr_data.get("package_name", "unknown")
        pid = anr_data.get("pid", None)
        reason = anr_data.get("reason", "Unknown")
        error_id = anr_data.get("error_id", None)
        load_avg = anr_data.get("load_avg", {})
        cpu_usage = anr_data.get("cpu_usage", {})
        pressure_stats = anr_data.get("pressure_stats", {})
        full_log = anr_data.get("full_log", "")
        
        log_entry = {
            "timestamp": timestamp,
            "package_name": package_name,
            "pid": pid,
            "reason": reason,
            "error_id": error_id,
            "load_avg": load_avg,
            "cpu_usage": cpu_usage,
            "pressure_stats": pressure_stats,
            "full_log": full_log
        }
        
        android_app_health_logs.append({
            "timestamp": timestamp,
            "type": "ANR",
            "data": log_entry
        })
        
        # 최근 1000개만 유지
        if len(android_app_health_logs) > 1000:
            android_app_health_logs.pop(0)
        
        logger.error(f"🚨 ANR 감지: {package_name} (PID: {pid}) - {reason}")
        logger.error(f"   로드 평균: {load_avg}")
        logger.error(f"   CPU 사용률: {cpu_usage}")
        
        return {
            "success": True,
            "message": "ANR 로그 수신 완료",
            "timestamp": timestamp,
            "error_id": error_id
        }
        
    except Exception as e:
        logger.error(f"❌ ANR 로그 수신 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'ANR 로그 수신 실패: {str(e)}')

@app.get("/android/health/metrics")
async def get_android_health_metrics(limit: int = 100):
    """Android 앱 건강 지표 조회"""
    try:
        # 최근 N개만 반환
        recent_logs = android_app_health_logs[-limit:] if len(android_app_health_logs) > limit else android_app_health_logs
        
        # 통계 계산
        if recent_logs:
            cpu_values = [log.get("cpu_usage_percent") for log in recent_logs if log.get("cpu_usage_percent")]
            memory_values = [log.get("memory_pressure_some") for log in recent_logs if log.get("memory_pressure_some")]
            io_values = [log.get("io_pressure_some") for log in recent_logs if log.get("io_pressure_some")]
            
            stats = {
                "total_logs": len(android_app_health_logs),
                "recent_logs": len(recent_logs),
                "avg_cpu_usage": sum(cpu_values) / len(cpu_values) if cpu_values else None,
                "max_cpu_usage": max(cpu_values) if cpu_values else None,
                "avg_memory_pressure": sum(memory_values) / len(memory_values) if memory_values else None,
                "max_memory_pressure": max(memory_values) if memory_values else None,
                "avg_io_pressure": sum(io_values) / len(io_values) if io_values else None,
                "max_io_pressure": max(io_values) if io_values else None,
            }
        else:
            stats = {
                "total_logs": 0,
                "recent_logs": 0
            }
        
        return {
            "success": True,
            "stats": stats,
            "logs": recent_logs
        }
        
    except Exception as e:
        logger.error(f"❌ Android 앱 건강 지표 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'건강 지표 조회 실패: {str(e)}')

@app.get("/android/health/anr")
async def get_anr_logs(limit: int = 50):
    """ANR 로그 조회"""
    try:
        # ANR 로그만 필터링
        anr_logs = [log for log in android_app_health_logs if log.get("type") == "ANR"]
        
        # 최근 N개만 반환
        recent_anr_logs = anr_logs[-limit:] if len(anr_logs) > limit else anr_logs
        
        return {
            "success": True,
            "total_anr_count": len(anr_logs),
            "recent_anr_count": len(recent_anr_logs),
            "anr_logs": recent_anr_logs
        }
        
    except Exception as e:
        logger.error(f"❌ ANR 로그 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'ANR 로그 조회 실패: {str(e)}')

@app.get("/android/health/connectivity")
async def get_connectivity_errors(limit: int = 50):
    """연결 오류 로그 조회"""
    try:
        global connectivity_error_count, last_connectivity_error
        
        # 연결 오류 로그만 필터링
        connectivity_logs = [log for log in android_app_health_logs if log.get("type") == "connectivity_error"]
        
        # 최근 N개만 반환
        recent_connectivity_logs = connectivity_logs[-limit:] if len(connectivity_logs) > limit else connectivity_logs
        
        return {
            "success": True,
            "total_connectivity_error_count": connectivity_error_count,
            "recent_connectivity_error_count": len(recent_connectivity_logs),
            "last_connectivity_error": last_connectivity_error,
            "connectivity_logs": recent_connectivity_logs
        }
        
    except Exception as e:
        logger.error(f"❌ 연결 오류 로그 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'연결 오류 로그 조회 실패: {str(e)}')

# ==================== 에어컨 자동 온도 조절 시스템 ====================

# 스케줄러 초기화
scheduler = BackgroundScheduler()

def update_thresholds(new_cold: float, new_hot: float, user_no: Optional[int] = None):
    """
    사용자별 피부온도 분류 기준 갱신 콜백 함수
    
    Args:
        new_cold: 새로운 추움 분류 기준
        new_hot: 새로운 더움 분류 기준
        user_no: 사용자 번호 (선택사항, None이면 갱신하지 않음)
    """
    if user_no is None:
        logger.warning("⚠️ user_no가 없어 임계값을 갱신할 수 없습니다.")
        return
    
    set_user_thresholds(user_no, new_cold, new_hot)
    logger.info(f"🔄 사용자별 피부온도 분류 기준 갱신 (user_no={user_no}): COLD={new_cold}°C, HOT={new_hot}°C")

def adjust_air_conditioner_wrapper():
    """스케줄러에서 호출할 래퍼 함수 (모든 활성 사용자에 대해 실행)"""
    from datetime import datetime
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 수면 모드 확인 (모든 사용자)
    global sleep_mode_states
    
    # 활성 수면 모드가 있는 사용자 찾기
    active_users = []
    for user_no, state in sleep_mode_states.items():
        if state.get("active", False):
            # 종료 시간 확인
            if state.get("end_time"):
                end_time = datetime.fromisoformat(state["end_time"])
                if datetime.now() >= end_time:
                    # 수면 모드 자동 종료
                    sleep_mode_states[user_no] = {
                        "active": False,
                        "start_time": None,
                        "end_time": None,
                        "duration_hours": None
                    }
                    logger.info(f"😴 수면 모드 자동 종료 (user_no: {user_no}, 설정된 시간 경과)")
                    continue
            active_users.append(user_no)
    
    if not active_users:
        # 활성 수면 모드가 없으면 실행하지 않음
        logger.debug(f"⏸️ [{current_time}] 활성 수면 모드 없음 - 에어컨 자동 조절 건너뜀")
        return
    
    logger.info(f"😴 [{current_time}] 활성 수면 모드 사용자: {active_users} - 에어컨 자동 조절 실행")
    
    # 각 활성 사용자에 대해 에어컨 조절 실행
    for user_no in active_users:
        try:
            print("\n" + "=" * 80)
            print(f"⏰ [{current_time}] 스케줄러 실행: 에어컨 자동 조절 시작 (user_no: {user_no}, 30분 주기, 백업용)")
            print("=" * 80)
            logger.info(f"⏰ [{current_time}] 스케줄러 실행: 에어컨 자동 조절 시작 (user_no: {user_no}, 30분 주기, 백업용)")
            
            # 사용자별 임계값 가져오기
            cold_threshold, hot_threshold = get_user_thresholds(user_no)
            
            # 콜백 함수 래퍼 (user_no 포함)
            def update_thresholds_wrapper(new_cold: float, new_hot: float):
                update_thresholds(new_cold, new_hot, user_no)
            
            # user_no를 사용하여 사용자별 PAT 토큰과 device_id를 가져오는 래퍼 함수 생성
            def get_air_conditioner_state_with_user():
                try:
                    # user_no로 user_id 조회 (login 테이블 사용)
                    with engine.connect() as conn:
                        user_query = text("SELECT id FROM login WHERE no = :user_no")
                        user_result = conn.execute(user_query, {'user_no': user_no})
                        user_row = user_result.fetchone()
                        if not user_row:
                            logger.warning(f"⚠️ user_no={user_no}에 해당하는 사용자를 찾을 수 없습니다.")
                            return None
                        user_id = user_row.id
                    
                    # user_id로 PAT 토큰과 device_id 조회
                    with engine.connect() as conn:
                        device_query = text("""
                            SELECT pat_token, device_id
                            FROM iot_devices
                            WHERE user_id = :user_id
                            ORDER BY updated_at DESC
                            LIMIT 1
                        """)
                        device_result = conn.execute(device_query, {'user_id': user_id})
                        device_row = device_result.fetchone()
                        if not device_row:
                            logger.warning(f"⚠️ user_id={user_id}에 등록된 디바이스가 없습니다.")
                            return None
                        pat_token = device_row.pat_token
                        device_id = device_row.device_id
                    
                    # PAT 토큰으로 상태 조회
                    return get_device_state_with_pat_token(pat_token, device_id)
                except Exception as e:
                    logger.error(f"❌ 사용자별 에어컨 상태 조회 실패 (user_no={user_no}): {e}")
                    return None
            
            air_conditioner_auto_control.adjust_air_conditioner(
                engine=engine,
                air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
                get_air_conditioner_state_func=get_air_conditioner_state_with_user,
                set_temperature_func=set_temperature,
                cold_threshold=cold_threshold,
                hot_threshold=hot_threshold,
                update_threshold_callback=update_thresholds_wrapper,
                min_interval_minutes=30.0,  # 30분 간격으로 조절
                user_no=user_no
            )
            print(f"✅ [{current_time}] 스케줄러 실행 완료: 에어컨 자동 조절 종료 (user_no: {user_no})")
            print("=" * 80 + "\n")
            logger.info(f"✅ [{current_time}] 스케줄러 실행 완료: 에어컨 자동 조절 종료 (user_no: {user_no})")
        except Exception as e:
            print(f"\n❌ [{current_time}] 스케줄러 실행 중 오류 (user_no: {user_no}): {e}")
            print("=" * 80 + "\n")
            logger.error(f"❌ [{current_time}] 스케줄러 실행 중 오류 (user_no: {user_no}): {e}")
            import traceback
            logger.error(f"❌ 스케줄러 오류 상세 (user_no: {user_no}): {traceback.format_exc()}")

scheduler.add_job(
    adjust_air_conditioner_wrapper,
    trigger=IntervalTrigger(minutes=30),  # 30분마다 백업용 실행 (실제 제어는 실시간 데이터 수신 시 10분 간격으로 실행)
    id='air_conditioner_adjustment',
    name='에어컨 자동 온도 조절 (백업)',
    replace_existing=True
)

# 온도 임계값 캐시 만료 체크 (1시간마다)
scheduler.add_job(
    check_and_cleanup_expired_cache,
    trigger=IntervalTrigger(hours=1),
    id='temperature_threshold_cache_cleanup',
    name='온도 임계값 캐시 만료 체크',
    replace_existing=True
)

# 서버 시작 시 초기 세팅 및 스케줄러 시작
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기 세팅 및 스케줄러 시작"""
    logger.info("🚀 서버 시작 중...")
    
    # IoT 디바이스 테이블 초기화 (없으면 생성)
    init_iot_devices_table()
    
    # IoT 디바이스 등록 정보 초기화 (서버 재시작 시마다 매번 새로 등록하도록)
    load_iot_devices_from_db()  # 이 함수는 이제 등록 정보를 초기화만 함
    
    air_conditioner_auto_control.initialize_air_conditioner_settings(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature
    )
    scheduler.start()
    logger.info("✅ 스케줄러 시작 완료 (30분마다 백업용 자동 조절, 실제 제어는 실시간 데이터 수신 시 10분 간격으로 실행)")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 스케줄러 종료"""
    logger.info("🛑 서버 종료 중...")
    scheduler.shutdown()
    logger.info("✅ 스케줄러 종료 완료")

if __name__ == "__main__":
    import uvicorn
    import os
    
    # SSL 인증서 파일 경로
    SSL_KEYFILE = os.path.join(os.path.dirname(__file__), "server.key")
    SSL_CERTFILE = os.path.join(os.path.dirname(__file__), "server.crt")
    
    # SSL 인증서가 있으면 HTTPS로 실행, 없으면 HTTP로 실행
    if os.path.exists(SSL_KEYFILE) and os.path.exists(SSL_CERTFILE):
        # logger.info("🔒 HTTPS 모드로 서버 시작 (SSL 인증서 사용)")
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=3000,
            ssl_keyfile=SSL_KEYFILE,
            ssl_certfile=SSL_CERTFILE,
            access_log=False  # HTTP 요청 로그 비활성화
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=3000, access_log=False)  # HTTP 요청 로그 비활성화
