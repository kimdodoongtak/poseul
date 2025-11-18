from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
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
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
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

# 모델 로드
# 서버 디렉토리 기준으로 모델 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # server 디렉토리의 상위 디렉토리 (프로젝트 루트)
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
# 나중에 경로로 설정 가능하도록 변수로 관리
COLD_THRESHOLD = 34.5  # 추움 분류 기준 (나중에 경로로 설정 가능)
HOT_THRESHOLD = 35.6    # 더움 분류 기준 (나중에 경로로 설정 가능)

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
            # predicted_skin 컬럼이 있는지 확인
            predicted_skin_code = None
            try:
                # predicted_skin 컬럼 존재 여부 확인
                columns_check = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'predicted_results'
                    AND COLUMN_NAME = 'predicted_skin'
                """)
                has_predicted_skin_column = conn.execute(columns_check).fetchone() is not None
                
                # 예측값을 코드로 변환 (임계값 사용)
                if predicted_skin_temp > 0 and has_predicted_skin_column:
                    # 임계값 가져오기 (new_skinthreshold 테이블에서 최신 값 또는 기본값)
                    temp_min_threshold = 32.5
                    temp_max_threshold = 34.5
                    
                    try:
                        # new_skinthreshold 테이블 존재 여부 확인
                        new_table_check = text("""
                            SELECT COUNT(*) as count
                            FROM information_schema.tables 
                            WHERE table_schema = 'main' 
                            AND table_name = 'new_skinthreshold'
                        """)
                        new_table_exists = conn.execute(new_table_check).fetchone().count > 0
                        
                        if new_table_exists:
                            # 최신 임계값 가져오기
                            latest_threshold_query = text("""
                                SELECT min_skinthreshold, max_skinthreshold
                                FROM new_skinthreshold
                                ORDER BY id DESC
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
                
                data_inserted = False
                if has_predicted_skin_column and predicted_skin_code is not None:
                    # predicted_skin 컬럼이 있으면 함께 저장
                    insert_query = text("""
                        INSERT INTO predicted_results 
                        (HR_mean, HRV_SDNN, mean_sa02, bmi, age, gender, predicted_skin_temp, predicted_skin)
                        VALUES 
                        (:heart_rate, :hrv, :oxygen_sat, :bmi, :age, :gender, :predicted_temp, :predicted_skin)
                    """)
                    conn.execute(insert_query, {
                        'heart_rate': data.heartRate,
                        'hrv': data.HRV,
                        'oxygen_sat': data.oxygenSaturation,
                        'bmi': bmi,
                        'age': age,
                        'gender': gender,
                        'predicted_temp': predicted_skin_temp,
                        'predicted_skin': predicted_skin_code
                    })
                    data_inserted = True
                else:
                    # predicted_skin 컬럼이 없으면 기존 방식으로 저장
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
                    data_inserted = True
            except Exception as e:
                logger.warning(f"⚠️ predicted_skin 컬럼 확인 실패, 기존 방식으로 저장: {str(e)}")
                # 예외 발생 시에만 기존 방식으로 저장 (중복 방지)
                if not data_inserted:
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
            
            # 온도 조절은 스케줄러가 2분마다 자동으로 처리합니다 (최근 3개 데이터 확인)
        
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

class TemperatureThresholdRequest(BaseModel):
    """온도 임계값 저장 요청"""
    target_temperature: float  # 사용자가 설정한 온도 (예: 24도)

@app.post("/air_conditioner/temperature_threshold")
async def save_temperature_threshold_api(data: TemperatureThresholdRequest):
    """에어컨 온도 임계값을 캐시에 저장 (유효)"""
    try:
        threshold = save_threshold(data.target_temperature)
        
        return {
            "success": True,
            "message": "온도 임계값이 저장되었습니다.",
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"❌ 온도 임계값 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 임계값 저장 실패: {str(e)}')

@app.get("/air_conditioner/temperature_threshold")
async def get_temperature_threshold_api():
    """현재 저장된 온도 임계값 조회 (만료되지 않은 경우만)"""
    try:
        threshold = get_threshold()
        
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

# ==================== 온도 범위 설정 API ====================

class TemperatureRangeRequest(BaseModel):
    age: int
    bmi: float
    gender: str  # 'M' 또는 'F', 또는 'MALE'/'FEMALE', 또는 0/1
    force_update: Optional[bool] = False  # 강제 업데이트 여부

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
    - 현재 사용 중인 값 (수동 조절 캐시 우선)
    - 원래 설정된 값 (DB에서 직접)
    """
    try:
        logger.info("🌡️ 온도 범위 조회 요청")
        
        # 현재 사용 중인 온도 범위 (캐시 우선, 없으면 DB)
        temperature_range = temperature_control_logic.get_temperature_range_from_db(engine)
        
        # 원래 설정된 온도 범위 (DB에서 직접 가져오기 - room_threshold 테이블의 min_temp, max_temp 컬럼)
        original_min_temp = None
        original_max_temp = None
        try:
            with engine.connect() as conn:
                query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                result = conn.execute(query).fetchone()
                if result and result.min_temp is not None and result.max_temp is not None:
                    original_min_temp = float(result.min_temp)
                    original_max_temp = float(result.max_temp)
        except Exception as e:
            logger.warning(f"원래 온도 범위 조회 실패: {e}")
        
        if temperature_range is None:
            return {
                "success": False,
                "message": "온도 범위가 설정되어 있지 않습니다.",
                "min_temp": None,
                "max_temp": None,
                "original_min_temp": original_min_temp,
                "original_max_temp": original_max_temp
            }
        
        min_temp, max_temp = temperature_range
        
        return {
            "success": True,
            "min_temp": min_temp,  # 현재 사용 중인 값 (수동 조절 캐시 우선)
            "max_temp": max_temp,  # 현재 사용 중인 값
            "original_min_temp": original_min_temp,  # 원래 설정된 값 (room_threshold 테이블의 min_temp)
            "original_max_temp": original_max_temp,  # 원래 설정된 값 (room_threshold 테이블의 max_temp)
            "target_temp": (min_temp + max_temp) / 2.0
        }
        
    except Exception as e:
        logger.error(f"온도 범위 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f'온도 범위 조회 실패: {str(e)}')

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
async def save_temperature_feedback(data: TemperatureFeedbackRequest):
    """온도 피드백 저장 API - new_skinthreshold 테이블에 저장하고 예측값과 비교하여 임계값 조정"""
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
            feedback_date = datetime.now().isoformat()
        
        # JSON 파일에 피드백 저장
        feedback_file = os.path.join(os.path.dirname(__file__), 'temperature_feedback.json')
        
        try:
            # 기존 피드백 데이터 읽기
            feedbacks = []
            if os.path.exists(feedback_file):
                try:
                    with open(feedback_file, 'r', encoding='utf-8') as f:
                        feedbacks = json.load(f)
                except (json.JSONDecodeError, IOError):
                    feedbacks = []
            
            # 새 피드백 추가
            feedback_entry = {
                'feedback': feedback_code,
                'feedback_text': data.feedback,
                'date': feedback_date,
                'timestamp': datetime.now().isoformat()
            }
            feedbacks.append(feedback_entry)
            
            # JSON 파일에 저장
            with open(feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedbacks, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 피드백 JSON 파일에 저장 완료: {feedback_code} ({data.feedback})")
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
                    columns_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns = [row.COLUMN_NAME for row in conn.execute(columns_check).fetchall()]
                    
                    # predicted_results 테이블에서 최신 예측값 가져오기 (ID로 정렬)
                    if 'id' in columns:
                        latest_prediction_query = text("""
                            SELECT predicted_skin_temp
                            FROM predicted_results
                            WHERE predicted_skin_temp IS NOT NULL
                            ORDER BY id DESC
                            LIMIT 1
                        """)
                    else:
                        # ID도 없으면 그냥 최신 하나 가져오기
                        latest_prediction_query = text("""
                            SELECT predicted_skin_temp
                            FROM predicted_results
                            WHERE predicted_skin_temp IS NOT NULL
                            LIMIT 1
                        """)
                    
                    latest_prediction = conn.execute(latest_prediction_query).fetchone()
                    
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
                    new_table_check = text("""
                        SELECT COUNT(*) as count
                        FROM information_schema.tables 
                        WHERE table_schema = 'main' 
                        AND table_name = 'new_skinthreshold'
                    """)
                    new_table_exists = conn.execute(new_table_check).fetchone().count > 0
                    
                    if new_table_exists:
                        # 최신 임계값 가져오기 (ID로 정렬)
                        latest_threshold_query = text("""
                            SELECT min_skinthreshold, max_skinthreshold
                            FROM new_skinthreshold
                            ORDER BY id DESC
                            LIMIT 1
                        """)
                        latest_threshold = conn.execute(latest_threshold_query).fetchone()
                        
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
                    new_table_check = text("""
                        SELECT COUNT(*) as count
                        FROM information_schema.tables 
                        WHERE table_schema = 'main' 
                        AND table_name = 'new_skinthreshold'
                    """)
                    new_table_exists = conn.execute(new_table_check).fetchone().count > 0
                    
                    if not new_table_exists:
                        # 테이블이 없으면 생성
                        create_new_table = text("""
                            CREATE TABLE IF NOT EXISTS new_skinthreshold (
                                no INT AUTO_INCREMENT PRIMARY KEY,
                                min_skinthreshold DECIMAL(4,1) NOT NULL,
                                max_skinthreshold DECIMAL(4,1) NOT NULL,
                                feedback VARCHAR(1),
                                predicted_skin VARCHAR(1)
                            )
                        """)
                        conn.execute(create_new_table)
                        conn.commit()
                        logger.info("✅ new_skinthreshold 테이블 생성 완료")
                    
                    # 갱신된 임계값 저장
                    insert_new_threshold = text("""
                        INSERT INTO new_skinthreshold (min_skinthreshold, max_skinthreshold, feedback, predicted_skin)
                        VALUES (:min_threshold, :max_threshold, :feedback, :predicted_skin)
                    """)
                    conn.execute(insert_new_threshold, {
                        'min_threshold': new_min_threshold,
                        'max_threshold': new_max_threshold,
                        'feedback': feedback_code,
                        'predicted_skin': predicted_skin_code
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
async def get_feedback_count():
    """
    현재 피드백 기간의 피드백 횟수 조회 API
    """
    try:
        count = feedback_based_adjustment.get_feedback_count(engine)
        is_within_limit = feedback_based_adjustment.is_within_feedback_limit(engine)
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
async def update_thresholds_api(data: ThresholdUpdateRequest):
    """
    피부온도 분류 기준(COLD_THRESHOLD, HOT_THRESHOLD) 전역 변수 업데이트
    """
    try:
        global COLD_THRESHOLD, HOT_THRESHOLD
        old_cold = COLD_THRESHOLD
        old_hot = HOT_THRESHOLD
        
        COLD_THRESHOLD = data.cold_threshold
        HOT_THRESHOLD = data.hot_threshold
        
        logger.info(f"🔄 피부온도 분류 기준 업데이트: COLD={old_cold}°C → {COLD_THRESHOLD}°C, HOT={old_hot}°C → {HOT_THRESHOLD}°C")
        
        return {
            "success": True,
            "message": "피부온도 분류 기준이 업데이트되었습니다.",
            "cold_threshold": COLD_THRESHOLD,
            "hot_threshold": HOT_THRESHOLD
        }
    except Exception as e:
        logger.error(f"❌ 피부온도 분류 기준 업데이트 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피부온도 분류 기준 업데이트 실패: {str(e)}"
        }

@app.get("/threshold")
async def get_thresholds_api():
    """
    현재 피부온도 분류 기준(COLD_THRESHOLD, HOT_THRESHOLD) 조회
    """
    try:
        return {
            "success": True,
            "cold_threshold": COLD_THRESHOLD,
            "hot_threshold": HOT_THRESHOLD
        }
    except Exception as e:
        logger.error(f"❌ 피부온도 분류 기준 조회 실패: {str(e)}")
        return {
            "success": False,
            "message": f"피부온도 분류 기준 조회 실패: {str(e)}"
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

def update_thresholds(new_cold: float, new_hot: float):
    """전역 변수 갱신 콜백 함수"""
    global COLD_THRESHOLD, HOT_THRESHOLD
    COLD_THRESHOLD = new_cold
    HOT_THRESHOLD = new_hot
    logger.info(f"🔄 전역 변수 갱신: COLD_THRESHOLD={COLD_THRESHOLD}°C, HOT_THRESHOLD={HOT_THRESHOLD}°C")

def adjust_air_conditioner_wrapper():
    """스케줄러에서 호출할 래퍼 함수"""
    from datetime import datetime
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        print("\n" + "=" * 80)
        print(f"⏰ [{current_time}] 스케줄러 실행: 에어컨 자동 조절 시작 (2분 주기)")
        print("=" * 80)
        logger.info(f"⏰ [{current_time}] 스케줄러 실행: 에어컨 자동 조절 시작 (2분 주기)")
        air_conditioner_auto_control.adjust_air_conditioner(
            engine=engine,
            air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
            get_air_conditioner_state_func=get_air_conditioner_state,
            set_temperature_func=set_temperature,
            cold_threshold=COLD_THRESHOLD,
            hot_threshold=HOT_THRESHOLD,
            update_threshold_callback=update_thresholds
        )
        print(f"✅ [{current_time}] 스케줄러 실행 완료: 에어컨 자동 조절 종료")
        print("=" * 80 + "\n")
        logger.info(f"✅ [{current_time}] 스케줄러 실행 완료: 에어컨 자동 조절 종료")
    except Exception as e:
        print(f"\n❌ [{current_time}] 스케줄러 실행 중 오류: {e}")
        print("=" * 80 + "\n")
        logger.error(f"❌ [{current_time}] 스케줄러 실행 중 오류: {e}")
        import traceback
        logger.error(f"❌ 스케줄러 오류 상세: {traceback.format_exc()}")

scheduler.add_job(
    adjust_air_conditioner_wrapper,
    trigger=IntervalTrigger(minutes=2),  # 테스트용: 2분으로 변경
    id='air_conditioner_adjustment',
    name='에어컨 자동 온도 조절',
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
    air_conditioner_auto_control.initialize_air_conditioner_settings(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature
    )
    scheduler.start()
    logger.info("✅ 스케줄러 시작 완료 (2분마다 자동 조절 - 테스트 모드)")

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
