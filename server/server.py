from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from datetime import datetime, timedelta
import logging
import os
import sys
import numpy as np
import pandas as pd
import joblib
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import air_conditioner_auto_control
import temperature_control_logic

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

# 모델 로드
# 서버 디렉토리 기준으로 모델 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, 'ai_thermal_model_final.pkl')

model = None
model_loaded = False

def load_model():
    """모델 로드"""
    global model, model_loaded
    if model is not None:
        model_loaded = True
        return model
    
    if not os.path.exists(MODEL_FILE):
        logger.warning(f"⚠️ 모델 파일을 찾을 수 없습니다: {MODEL_FILE}")
        return None
    
    try:
        model = joblib.load(MODEL_FILE)
        model_loaded = True
        logger.info("✅ 모델 로드 성공! (joblib)")
        return model
    except Exception as e1:
        logger.error(f"❌ joblib 로드 실패: {e1}")
        try:
            import pickle
            with open(MODEL_FILE, 'rb') as f:
                model = pickle.load(f)
            model_loaded = True
            logger.info("✅ 모델 로드 성공! (pickle)")
            return model
        except Exception as e2:
            logger.error(f"❌ pickle 로드 실패: {e2}")
            return None

# 서버 시작 시 모델 로드
model = load_model()

# ==================== 피부온도 분류 기준 설정 ====================
# 갱신 가능하도록 전역 변수로 관리
COLD_THRESHOLD = 34.5  # 추움 분류 기준 (갱신 가능)
HOT_THRESHOLD = 35.6    # 더움 분류 기준 (갱신 가능)

# 에어컨 제어 모듈 import
# IoT 폴더의 모듈 import를 위한 경로 추가
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # server 디렉토리의 상위 디렉토리 (프로젝트 루트)
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
    AIR_CONDITIONER_AVAILABLE = True
    logger.info("✅ 에어컨 모듈 로드 성공")
except ImportError as e:
    logger.warning(f"⚠️  에어컨 모듈을 불러올 수 없습니다: {e}")
    AIR_CONDITIONER_AVAILABLE = False

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
    if bmi < 18.5:
        delta_bmi = 1.0
    elif 18.5 <= bmi < 25:
        delta_bmi = 0.0
    elif 25 <= bmi < 30:
        delta_bmi = -0.5
    else:  # bmi >= 30
        delta_bmi = -1.0
    
    # 최종 온도 계산
    min_temp = base_min + delta_gender + delta_age + delta_bmi
    max_temp = base_max + delta_gender + delta_age + delta_bmi
    
    return round(min_temp, 1), round(max_temp, 1)

# ==================== 모델 예측 함수 ====================

def predict_temperature_with_model(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
    """
    체온 예측 함수 (pandas DataFrame 기반)
    
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

class TemperatureRangeRequest(BaseModel):
    age: int
    bmi: float
    gender: str  # 'M' 또는 'F', 또는 'MALE'/'FEMALE', 또는 0/1
    force_update: Optional[bool] = False  # 강제 업데이트 여부

class ThresholdUpdateRequest(BaseModel):
    cold_threshold: Optional[float] = None
    hot_threshold: Optional[float] = None

# ==================== Health Data API ====================

@app.post("/healthdata")
async def receive_health_data(data: HealthData):
    """
    HealthKit 데이터를 받아서 DB에 저장하고 모델로 예측
    """
    try:
        logger.info(f"💌 받은 데이터: {data.dict()}")
        
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
            # 기존 사용자 정보 확인 (나이, BMI, 성별이 있는지)
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
            except Exception as e:
                logger.warning(f"테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                order_by = "ORDER BY 1 DESC"
            
            # predicted_results에서 기존 사용자 정보 확인 (나이, BMI, 성별만)
            check_query = text(f"""
                SELECT age, bmi, gender
                FROM predicted_results
                WHERE age IS NOT NULL 
                  AND bmi IS NOT NULL 
                  AND gender IS NOT NULL
                {order_by}
                LIMIT 1
            """)
            
            existing_user = conn.execute(check_query).fetchone()
            
            # room_threshold 테이블에서 기존 쾌적 온도 범위 확인
            try:
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # room_threshold에서 기존 임계값 확인
                    threshold_query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                    threshold_result = conn.execute(threshold_query).fetchone()
                    
                    # 기존 사용자 정보가 있고, 나이/BMI/성별이 동일하고, room_threshold에 값이 있으면 사용
                    if existing_user and existing_user.age == age and existing_user.bmi == bmi and existing_user.gender == gender:
                        if threshold_result and threshold_result.min_temp is not None and threshold_result.max_temp is not None:
                            comfort_min = float(threshold_result.min_temp)
                            comfort_max = float(threshold_result.max_temp)
                            logger.info(f"📋 기존 쾌적 온도 범위 사용 (room_threshold): {comfort_min}~{comfort_max}°C")
            except Exception as e:
                logger.warning(f"room_threshold 확인 실패: {e}")
            
            # 쾌적 온도 범위가 없으면 계산 (처음 입력이거나 정보가 변경된 경우)
            if comfort_min is None or comfort_max is None:
                comfort_min, comfort_max = calculate_comfort_temperature(gender, int(age), bmi)
                logger.info(f"🌡️ 쾌적 온도 범위 계산 (새로 계산): {comfort_min}~{comfort_max}°C (gender: {gender}, age: {int(age)}, bmi: {bmi})")
            
            # room_threshold 테이블에 임계값 저장 (처음 한 번만)
            try:
                # room_threshold 테이블 존재 여부 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # 테이블이 있으면 레코드가 있는지 확인
                    check_threshold = text("SELECT COUNT(*) as count FROM room_threshold")
                    threshold_count = conn.execute(check_threshold).fetchone().count
                    
                    # 레코드가 없을 때만 삽입 (처음 한 번만)
                    if threshold_count == 0:
                        try:
                            insert_threshold = text("""
                                INSERT INTO room_threshold (min_temp, max_temp)
                                VALUES (:min_temp, :max_temp)
                            """)
                            conn.execute(insert_threshold, {
                                'min_temp': comfort_min,
                                'max_temp': comfort_max
                            })
                            logger.info(f"✅ room_threshold 테이블에 임계값 저장 (처음 저장): {comfort_min}~{comfort_max}°C")
                        except Exception as e:
                            logger.warning(f"room_threshold 저장 실패: {e}")
                    else:
                        logger.info(f"📋 room_threshold 테이블에 이미 임계값이 저장되어 있습니다. (건너뜀)")
                else:
                    logger.warning("⚠️ room_threshold 테이블이 존재하지 않습니다.")
            except Exception as e:
                logger.warning(f"room_threshold 테이블 처리 중 오류: {e}")
            
            # predicted_results 테이블에 데이터 삽입 (쾌적 온도 범위는 저장하지 않음)
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
            
            conn.commit()
        
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
async def get_latest_health_data():
    """서버에 저장된 최신 건강 데이터 조회 (안드로이드에서 호출)"""
    try:
        logger.info("📱 최신 건강 데이터 조회 요청")
        
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
                    
                    # predicted_results 테이블에서 최신 데이터 조회
                    query = text(f"""
                        SELECT 
                            {select_columns}
                        FROM predicted_results
                        {order_by}
                        LIMIT 1
                    """)
                except Exception as e:
                    logger.warning(f"테이블 구조 확인 실패, 기본 쿼리 사용: {e}")
                    # 기본 쿼리 (created_at 없이)
                    query = text("""
                        SELECT 
                            HR_mean as heartRate,
                            HRV_SDNN as hrv,
                            mean_sa02 as oxygenSaturation,
                            bmi,
                            age,
                            gender
                        FROM predicted_results
                        LIMIT 1
                    """)
                
                result = conn.execute(query)
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
        
        logger.info(f"📱 앱에서 예측 요청 받음: {data.dict()}")
        
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
            'input_data': data.dict()
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

@app.get("/air_conditioner/state")
async def get_air_conditioner_state_api():
    """에어컨 상태 조회 API"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="에어컨 모듈을 사용할 수 없습니다.")
    
    try:
        logger.info("📱 앱에서 에어컨 상태 조회 요청")
        state_response = get_air_conditioner_state()
        
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
                'device_id': AIR_CONDITIONER_DEVICE_ID,
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
async def control_air_conditioner_api(data: AirConditionerControlRequest):
    """에어컨 제어 API"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="에어컨 모듈을 사용할 수 없습니다.")
    
    try:
        logger.info(f"📱 앱에서 에어컨 제어 요청: {data.dict()}")
        
        if not data.action:
            raise HTTPException(status_code=400, detail="action 파라미터가 필요합니다.")
        
        result = None
        
        if data.action == 'set_temperature':
            if data.target_temperature is None:
                raise HTTPException(status_code=400, detail="target_temperature 파라미터가 필요합니다.")
            result = set_temperature(target_temp=float(data.target_temperature), unit=data.unit or 'C')
            
        elif data.action == 'set_mode':
            if not data.mode:
                raise HTTPException(status_code=400, detail="mode 파라미터가 필요합니다.")
            result = set_job_mode(mode=data.mode)
            
        elif data.action == 'set_wind_strength':
            if not data.strength:
                raise HTTPException(status_code=400, detail="strength 파라미터가 필요합니다.")
            result = set_wind_strength(strength=data.strength)
            
        elif data.action == 'set_power':
            result = set_power(power_on=bool(data.power_on))
            
        else:
            raise HTTPException(status_code=400, detail=f'지원하지 않는 action: {data.action}')
        
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

# ==================== 온도 범위 설정 API ====================

@app.post("/temperature-range")
async def set_temperature_range(data: TemperatureRangeRequest):
    """
    사용자 특성(나이, BMI, 성별)에 따라 쾌적 온도 범위를 계산하고 DB에 저장
    (처음 한번만 적용, 이미 설정되어 있으면 기존 값 유지)
    """
    try:
        logger.info(f"🌡️ 온도 범위 설정 요청: 나이={data.age}세, BMI={data.bmi}, 성별={data.gender}, force_update={data.force_update}")
        
        # 온도 범위 초기화
        success, min_temp, max_temp = temperature_control_logic.initialize_user_temperature_range(
            engine=engine,
            age=data.age,
            bmi=data.bmi,
            gender=data.gender,
            air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
            set_temperature_func=set_temperature,
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
async def get_temperature_range():
    """
    DB에서 저장된 쾌적 온도 범위 조회
    """
    try:
        logger.info("🌡️ 온도 범위 조회 요청")
        
        temperature_range = temperature_control_logic.get_temperature_range_from_db(engine)
        
        if temperature_range is None:
            return {
                "success": False,
                "message": "온도 범위가 설정되지 않았습니다",
                "min_temp": None,
                "max_temp": None
            }
        
        min_temp, max_temp = temperature_range
        
        # DB에서 사용자 정보도 함께 조회
        with engine.connect() as conn:
            query = text("SELECT age, bmi, gender FROM room_threshold LIMIT 1")
            result = conn.execute(query).fetchone()
            
            user_info = None
            if result:
                user_info = {
                    "age": result.age,
                    "bmi": float(result.bmi) if result.bmi else None,
                    "gender": result.gender
                }
        
        return {
            "success": True,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "target_temp": (min_temp + max_temp) / 2.0,
            "user_info": user_info
        }
        
    except Exception as e:
        logger.error(f"온도 범위 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 범위 조회 실패: {str(e)}')

# ==================== 기본 API ====================

@app.get("/")
async def root():
    return {"message": "Unified Server is running (Health Data + Model Prediction + IoT Control)"}

@app.post("/temperature_feedback")
async def save_temperature_feedback(data: TemperatureFeedbackRequest):
    """온도 피드백 저장 API"""
    try:
        logger.info(f"📝 온도 피드백 저장 요청: {data.dict()}")
        
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
            from datetime import datetime
            feedback_date = datetime.now().isoformat()
        
        with engine.connect() as conn:
            # room_threshold 테이블에 feedback 저장
            try:
                # room_threshold 테이블 존재 여부 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # feedback 컬럼 존재 여부 확인
                    columns_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'room_threshold'
                        AND COLUMN_NAME = 'feedback'
                    """)
                    has_feedback_column = conn.execute(columns_check).fetchone() is not None
                    
                    if has_feedback_column:
                        # feedback 컬럼이 있으면 업데이트
                        # id 컬럼이 있는지 확인
                        id_check = text("""
                            SELECT COLUMN_NAME 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'main' 
                            AND TABLE_NAME = 'room_threshold'
                            AND COLUMN_NAME = 'id'
                        """)
                        has_id = conn.execute(id_check).fetchone() is not None
                        
                        if has_id:
                            # id가 있으면 첫 번째 레코드 업데이트
                            update_query = text("""
                                UPDATE room_threshold 
                                SET feedback = :feedback
                                WHERE id = (SELECT id FROM (SELECT id FROM room_threshold LIMIT 1) AS t)
                            """)
                        else:
                            # id가 없으면 모든 레코드 업데이트 (단일 레코드 가정)
                            update_query = text("""
                                UPDATE room_threshold 
                                SET feedback = :feedback
                            """)
                        
                        conn.execute(update_query, {
                            'feedback': feedback_code
                        })
                        conn.commit()
                        logger.info(f"✅ room_threshold 테이블에 피드백 저장 완료: {feedback_code} ({data.feedback})")
                    else:
                        logger.warning("⚠️ room_threshold 테이블에 feedback 컬럼이 존재하지 않습니다.")
                else:
                    logger.warning("⚠️ room_threshold 테이블이 존재하지 않습니다.")
            except Exception as e:
                logger.error(f"❌ room_threshold 피드백 저장 실패: {str(e)}")
            
            # temperature_feedback 테이블에도 저장 (선택적)
            try:
                # temperature_feedback 테이블 존재 여부 확인
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'temperature_feedback'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # 테이블이 있으면 저장
                    insert_query = text("""
                        INSERT INTO temperature_feedback (feedback, feedback_date, created_at)
                        VALUES (:feedback, :feedback_date, NOW())
                    """)
                    conn.execute(insert_query, {
                        'feedback': data.feedback,
                        'feedback_date': feedback_date
                    })
                    conn.commit()
                    logger.info(f"✅ temperature_feedback 테이블에 피드백 저장 완료: {data.feedback}")
            except Exception as e:
                logger.warning(f"temperature_feedback 테이블 저장 실패 (선택적): {str(e)}")
        
        return {
            "success": True,
            "message": "피드백이 저장되었습니다.",
            "feedback": data.feedback,
            "feedback_code": feedback_code
        }
    except Exception as e:
        logger.error(f"❌ 온도 피드백 저장 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피드백 저장 실패: {str(e)}"
        }

@app.post("/threshold/update")
async def update_threshold(data: ThresholdUpdateRequest):
    """
    피부온도 분류 기준 갱신 API
    
    Args:
        cold_threshold: 추움 분류 기준 (선택)
        hot_threshold: 더움 분류 기준 (선택)
    """
    global COLD_THRESHOLD, HOT_THRESHOLD
    
    try:
        updated = []
        
        if data.cold_threshold is not None:
            if data.cold_threshold < 0 or data.cold_threshold > 50:
                raise HTTPException(status_code=400, detail="cold_threshold는 0~50 사이의 값이어야 합니다.")
            COLD_THRESHOLD = data.cold_threshold
            updated.append(f"cold_threshold={COLD_THRESHOLD}")
            logger.info(f"✅ COLD_THRESHOLD 갱신: {COLD_THRESHOLD}°C")
        
        if data.hot_threshold is not None:
            if data.hot_threshold < 0 or data.hot_threshold > 50:
                raise HTTPException(status_code=400, detail="hot_threshold는 0~50 사이의 값이어야 합니다.")
            HOT_THRESHOLD = data.hot_threshold
            updated.append(f"hot_threshold={HOT_THRESHOLD}")
            logger.info(f"✅ HOT_THRESHOLD 갱신: {HOT_THRESHOLD}°C")
        
        if not updated:
            raise HTTPException(status_code=400, detail="cold_threshold 또는 hot_threshold 중 하나 이상을 제공해야 합니다.")
        
        return {
            "success": True,
            "message": "분류 기준 갱신 완료",
            "cold_threshold": COLD_THRESHOLD,
            "hot_threshold": HOT_THRESHOLD,
            "updated": updated
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 분류 기준 갱신 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'분류 기준 갱신 실패: {str(e)}')

@app.get("/threshold")
async def get_threshold():
    """현재 피부온도 분류 기준 조회"""
    return {
        "success": True,
        "cold_threshold": COLD_THRESHOLD,
        "hot_threshold": HOT_THRESHOLD
    }

@app.get("/health")
async def health_check():
    """서버 상태 확인 (모델, 에어컨, DB 연결 상태 포함)"""
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
    
    return {
        "status": "healthy",
        "model_loaded": model_loaded,
        "air_conditioner_available": AIR_CONDITIONER_AVAILABLE,
        "database_connected": db_connected,
        "database_error": db_error if not db_connected else None
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

# ==================== 에어컨 자동 온도 조절 시스템 ====================

# 스케줄러 초기화
scheduler = BackgroundScheduler()

def adjust_air_conditioner_wrapper():
    """스케줄러에서 호출할 래퍼 함수 (전역 변수 사용)"""
    global COLD_THRESHOLD, HOT_THRESHOLD
    
    def update_thresholds(new_cold: float, new_hot: float):
        """전역 변수 갱신 콜백 함수"""
        global COLD_THRESHOLD, HOT_THRESHOLD
        COLD_THRESHOLD = new_cold
        HOT_THRESHOLD = new_hot
    
    # 전역 변수에서 최신 값 가져오기 (런타임에 갱신 가능)
    air_conditioner_auto_control.adjust_air_conditioner(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature,
        cold_threshold=COLD_THRESHOLD,  # 전역 변수에서 가져옴 (갱신 가능)
        hot_threshold=HOT_THRESHOLD,    # 전역 변수에서 가져옴 (갱신 가능)
        update_threshold_callback=update_thresholds  # DB 값 변경 시 전역 변수 갱신 콜백
    )

scheduler.add_job(
    adjust_air_conditioner_wrapper,
    trigger=IntervalTrigger(minutes=30),
    id='air_conditioner_adjustment',
    name='에어컨 자동 온도 조절',
    replace_existing=True
)

# 서버 시작 시 초기 세팅 및 스케줄러 시작
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기 세팅 및 스케줄러 시작"""
    logger.info("🚀 서버 시작 중...")
    air_conditioner_auto_control.initialize_air_conditioner_settings(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature
    )
    scheduler.start()
    logger.info("✅ 스케줄러 시작 완료 (30분마다 자동 조절)")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 스케줄러 종료"""
    logger.info("🛑 서버 종료 중...")
    scheduler.shutdown()
    logger.info("✅ 스케줄러 종료 완료")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
