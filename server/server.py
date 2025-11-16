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

# ë¡œê¹… ?¤ì •
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS ?¤ì • (ëª¨ë“  origin ?ˆìš©)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< HEAD
# ?°ê²° ?¤ë¥˜ ì¶”ì 
connectivity_error_count = 0
last_connectivity_error = None

# Android ??ê±´ê°• ë¡œê·¸ ?€?¥ì†Œ (ë¯¸ë“¤?¨ì–´?ì„œ ?¬ìš©?˜ê¸° ?„í•´ ?¬ê¸°??ì´ˆê¸°??
android_app_health_logs = []

# ?¨ë„ ?„ê³„ê°?ìºì‹œ ëª¨ë“ˆ import
from temperature_threshold_cache import save_temperature_threshold as save_threshold, get_temperature_threshold as get_threshold

@app.middleware("http")
async def track_connectivity_errors(request: Request, call_next):
    """?°ê²° ?¤ë¥˜ ì¶”ì  ë¯¸ë“¤?¨ì–´"""
    global connectivity_error_count, last_connectivity_error, android_app_health_logs
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # ?‘ë‹µ ?œê°„???ˆë¬´ ê¸¸ë©´ ê²½ê³ 
        if process_time > 5.0:
            logger.warning(f"? ï¸ ?ë¦° ?‘ë‹µ ?œê°„: {request.url.path} - {process_time:.2f}ì´?)
        
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
        
        logger.error(f"???°ê²° ?¤ë¥˜ ë°œìƒ: {request.url.path} - {error_msg}")
        
        # Android ??ê±´ê°• ë¡œê·¸???°ê²° ?¤ë¥˜ ê¸°ë¡
        android_app_health_logs.append({
            "timestamp": datetime.now().isoformat(),
            "type": "connectivity_error",
            "path": str(request.url.path),
            "method": request.method,
            "error": error_msg
        })
        # ìµœê·¼ 1000ê°œë§Œ ? ì?
        if len(android_app_health_logs) > 1000:
            android_app_health_logs.pop(0)
        
        raise
# DB ?°ê²° ?¤ì •
# DBeaver ?°ê²° ?•ë³´??ë§ê²Œ ?˜ì •:
# Host: aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com
# Username: iriskimhs
# Port: 3306
# Database: main (URL?ì„œ ?•ì¸)
# Password: dyvVyn-kihxe0-parxes
DB_URL = "mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main"
# ?°ê²° ?µì…˜ ì¶”ê? (SSL, ?€?„ì•„????
# pymysql??SSL ?¤ì •: ssl_disabled=Trueë¡?ë¹„í™œ?±í™”?˜ê±°?? ssl_ca ?¸ì¦??ê²½ë¡œ ì§€??
# DBeaver?ì„œ ?°ê²°???˜ë©´ SSL ?†ì´???°ê²° ê°€?¥í•  ???ˆìŒ
import sqlalchemy
engine = sqlalchemy.create_engine(
    DB_URL,
    connect_args={
        "ssl_disabled": True,  # SSL ë¹„í™œ?±í™” (DBeaver?€ ?™ì¼???¤ì •)
        "connect_timeout": 10,  # ?°ê²° ?€?„ì•„??10ì´?
        "read_timeout": 10,  # ?½ê¸° ?€?„ì•„??10ì´?
        "write_timeout": 10,  # ?°ê¸° ?€?„ì•„??10ì´?
    },
    pool_pre_ping=True,  # ?°ê²° ? íš¨???¬ì „ ?•ì¸
    pool_recycle=3600,  # 1?œê°„ë§ˆë‹¤ ?°ê²° ?¬ì‚¬??
    echo=False  # SQL ì¿¼ë¦¬ ë¡œê¹… (?”ë²„ê¹???Trueë¡?ë³€ê²?
)

# ëª¨ë¸ ë¡œë“œ
# ?œë²„ ?”ë ‰? ë¦¬ ê¸°ì??¼ë¡œ ëª¨ë¸ ?Œì¼ ê²½ë¡œ ?¤ì •
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, 'ai_thermal_model_final.pkl')

model = None
model_loaded = False

def load_model():
    """ëª¨ë¸ ë¡œë“œ"""
    global model, model_loaded
    if model is not None:
        model_loaded = True
        return model
    
    if not os.path.exists(MODEL_FILE):
        logger.warning(f"? ï¸ ëª¨ë¸ ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤: {MODEL_FILE}")
        return None
    
    try:
        model = joblib.load(MODEL_FILE)
        model_loaded = True
        logger.info("??ëª¨ë¸ ë¡œë“œ ?±ê³µ! (joblib)")
        return model
    except Exception as e1:
        logger.error(f"??joblib ë¡œë“œ ?¤íŒ¨: {e1}")
        try:
            import pickle
            with open(MODEL_FILE, 'rb') as f:
                model = pickle.load(f)
            model_loaded = True
            logger.info("??ëª¨ë¸ ë¡œë“œ ?±ê³µ! (pickle)")
            return model
        except Exception as e2:
            logger.error(f"??pickle ë¡œë“œ ?¤íŒ¨: {e2}")
            return None

# ?œë²„ ?œì‘ ??ëª¨ë¸ ë¡œë“œ
model = load_model()

# ==================== ?¼ë??¨ë„ ë¶„ë¥˜ ê¸°ì? ?¤ì • ====================
# ê°±ì‹  ê°€?¥í•˜?„ë¡ ?„ì—­ ë³€?˜ë¡œ ê´€ë¦?
COLD_THRESHOLD = 34.5  # ì¶”ì? ë¶„ë¥˜ ê¸°ì? (ê°±ì‹  ê°€??
HOT_THRESHOLD = 35.6    # ?”ì? ë¶„ë¥˜ ê¸°ì? (ê°±ì‹  ê°€??

# ?ì–´ì»??œì–´ ëª¨ë“ˆ import
# IoT ?´ë”??ëª¨ë“ˆ importë¥??„í•œ ê²½ë¡œ ì¶”ê?
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # server ?”ë ‰? ë¦¬???ìœ„ ?”ë ‰? ë¦¬ (?„ë¡œ?íŠ¸ ë£¨íŠ¸)
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
    logger.info("???ì–´ì»?ëª¨ë“ˆ ë¡œë“œ ?±ê³µ")
except ImportError as e:
    logger.warning(f"? ï¸  ?ì–´ì»?ëª¨ë“ˆ??ë¶ˆëŸ¬?????†ìŠµ?ˆë‹¤: {e}")
    AIR_CONDITIONER_AVAILABLE = False

# ==================== ì¾Œì  ?¨ë„ ê³„ì‚° ?¨ìˆ˜ ====================

def calculate_comfort_temperature(gender: str, age: int, bmi: float) -> tuple[float, float]:
    """
    ?±ë³„, ?˜ì´, BMI ê¸°ë°˜ ?¤ë‚´ ì¾Œì  ?¨ë„ ë²”ìœ„ ê³„ì‚°
    
    Args:
        gender: ?±ë³„ ('F': ?¬ì„±, 'M': ?¨ì„±)
        age: ?˜ì´
        bmi: ì²´ì§ˆ?‰ì???
    
    Returns:
        (min_temp, max_temp): ì¾Œì  ?¨ë„ ë²”ìœ„ (ìµœì†Œ ?¨ë„, ìµœë? ?¨ë„)
    """
    # ê¸°ë³¸ ?¨ë„ ë²”ìœ„
    base_min, base_max = 19.0, 21.0
    
    # 1ï¸âƒ£ ?±ë³„ ì¡°ì •
    if gender.upper() == 'F':  # ?¬ì„±
        delta_gender = 1.0
    else:  # ?¨ì„± ('M')
        delta_gender = 0.0
    
    # 2ï¸âƒ£ ?˜ì´ ì¡°ì •
    if 60 <= age < 70:
        delta_age = 0.5
    elif 70 <= age <= 80:
        delta_age = 1.0
    else:
        delta_age = 0.0
    
    # 3ï¸âƒ£ BMI ì¡°ì •
    if bmi < 18.5:
        delta_bmi = 1.0
    elif 18.5 <= bmi < 25:
        delta_bmi = 0.0
    elif 25 <= bmi < 30:
        delta_bmi = -0.5
    else:  # bmi >= 30
        delta_bmi = -1.0
    
    # ìµœì¢… ?¨ë„ ê³„ì‚°
    min_temp = base_min + delta_gender + delta_age + delta_bmi
    max_temp = base_max + delta_gender + delta_age + delta_bmi
    
    return round(min_temp, 1), round(max_temp, 1)

# ==================== ëª¨ë¸ ?ˆì¸¡ ?¨ìˆ˜ ====================

def predict_temperature_with_model(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
    """
    ì²´ì˜¨ ?ˆì¸¡ ?¨ìˆ˜ (pandas DataFrame ê¸°ë°˜)
    
    Parameters:
    - hr_mean: ?‰ê·  ?¬ë°•??
    - hrv_sdnn: ?¬ë°•ë³€?´ë„ (SDNN)
    - bmi: ì²´ì§ˆ?‰ì???
    - mean_sa02: ?‰ê·  ?°ì†Œ?¬í™”??
    - gender: ?±ë³„ (0: ?¬ì„±, 1: ?¨ì„± ?ëŠ” 'F': ?¬ì„±, 'M': ?¨ì„±)
    - age: ?˜ì´
    
    Returns:
    - ?ˆì¸¡??ì²´ì˜¨ (Â°C)
    """
    if not model_loaded or model is None:
        raise ValueError("ëª¨ë¸??ë¡œë“œ?˜ì? ?Šì•˜?µë‹ˆ??")
    
    # ?±ë³„ ë³€??(0/1 -> F/M ?ëŠ” ê·¸ë?ë¡?
    if isinstance(gender, (int, float)):
        gender_str = 'F' if gender == 0 else 'M'
    else:
        gender_str = str(gender)
    
    # ?Œìƒ ?¼ì²˜ ê³„ì‚°
    hrv_hr_ratio = hrv_sdnn / hr_mean if hr_mean > 0 else 0
    bmi_hr_interaction = bmi * hr_mean
    age_bmi_interaction = age * bmi
    age_hrv_ratio = age / (hrv_sdnn + 1) if hrv_sdnn > 0 else 0  # 0?¼ë¡œ ?˜ëˆ„ê¸?ë°©ì?
    
    # pandas DataFrame?¼ë¡œ ?°ì´??ì¤€ë¹?(Flask ?œë²„?€ ?™ì¼???•ì‹)
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
        
        # ?ˆì¸¡
        temp_pred = model.predict(data)[0]
        return float(temp_pred)
    except Exception as e:
        logger.error(f"pandas DataFrame ?ˆì¸¡ ?¤íŒ¨, numpy ë°°ì—´ë¡??¬ì‹œ?? {e}")
        # pandas ?¤íŒ¨ ??numpy ë°°ì—´ë¡??¬ì‹œ??(ê¸°ì¡´ server.py ë°©ì‹)
        age_hrv_ratio = age / (hrv_sdnn + 1e-8) if hrv_sdnn > 0 else 0
        age_bmi_interaction = age * bmi
        bmi_hr_interaction = bmi * hr_mean
        hrv_hr_ratio = hrv_sdnn / (hr_mean + 1e-8) if hr_mean > 0 else 0
        
        # ?±ë³„???«ìë¡?ë³€??(0: ?¬ì„±, 1: ?¨ì„±)
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

# ==================== Pydantic ëª¨ë¸ ====================

class HealthData(BaseModel):
    heartRate: Optional[float] = None
    HRV: Optional[float] = None
    oxygenSaturation: Optional[float] = None
    bmi: Optional[float] = None
    age: Optional[float] = None
    gender: Optional[float] = None  # 0: ?¬ì„±, 1: ?¨ì„±

class PredictRequest(BaseModel):
    hr_mean: float
    hrv_sdnn: float
    bmi: float
    mean_sa02: float
    gender: str  # 'M' ?ëŠ” 'F'
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
    gender: str  # 'M' ?ëŠ” 'F', ?ëŠ” 'MALE'/'FEMALE', ?ëŠ” 0/1
    force_update: Optional[bool] = False  # ê°•ì œ ?…ë°?´íŠ¸ ?¬ë?

class ThresholdUpdateRequest(BaseModel):
    cold_threshold: Optional[float] = None
    hot_threshold: Optional[float] = None

# ==================== Health Data API ====================

@app.post("/healthdata")
async def receive_health_data(data: HealthData):
    """
    HealthKit ?°ì´?°ë? ë°›ì•„??DB???€?¥í•˜ê³?ëª¨ë¸ë¡??ˆì¸¡
    """
    try:
        logger.info(f"?’Œ ë°›ì? ?°ì´?? {data.dict()}")
        
        # ?„ìˆ˜ ?°ì´???•ì¸
        if data.heartRate is None or data.HRV is None or data.oxygenSaturation is None:
            raise HTTPException(status_code=400, detail="heartRate, HRV, oxygenSaturation?€ ?„ìˆ˜?…ë‹ˆ??")
        
        # ê¸°ë³¸ê°??¤ì •
        # gender: 0.0 ?ëŠ” 1.0??'F' ?ëŠ” 'M'?¼ë¡œ ë³€??
        gender_value = data.gender if data.gender is not None else 0.0  # ê¸°ë³¸ê°? ?¬ì„±
        gender = 'F' if gender_value == 0.0 else 'M'  # 0.0: ?¬ì„±(F), 1.0: ?¨ì„±(M)
        bmi = data.bmi if data.bmi is not None else 0.0
        age = data.age if data.age is not None else 0.0
        
        logger.info(f"?“Š ì²˜ë¦¬???°ì´??- gender: {gender} (?ë³¸: {gender_value}), bmi: {bmi}, age: {age}")
        
        # ëª¨ë¸ë¡??ˆì¸¡
        predicted_skin_temp = 0.0  # ê¸°ë³¸ê°??¤ì • (?°ì´?°ë² ?´ìŠ¤ NOT NULL ?œì•½ ì¡°ê±´ ?€??
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
                logger.info(f"?”® ?ˆì¸¡ ê²°ê³¼: {predicted_skin_temp}")
            except Exception as e:
                logger.error(f"???ˆì¸¡ ?¤íŒ¨: {str(e)}")
                logger.error(f"???ˆì¸¡ ?¤íŒ¨ ?ì„¸ - ?…ë ¥ ?¼ì²˜ ?? 9, ëª¨ë¸ ê¸°ë?: 9")
                # ?ˆì¸¡ ?¤íŒ¨ ??ê¸°ë³¸ê°?? ì? (0.0)
        
        # DB???°ì´???€??
        comfort_min = None
        comfort_max = None
        
        with engine.connect() as conn:
            # ê¸°ì¡´ ?¬ìš©???•ë³´ ?•ì¸ (?˜ì´, BMI, ?±ë³„???ˆëŠ”ì§€)
            # ë¨¼ì? ?Œì´ë¸?êµ¬ì¡° ?•ì¸
            try:
                columns_query = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'predicted_results'
                """)
                columns_result = conn.execute(columns_query)
                columns = [row.COLUMN_NAME for row in columns_result]
                
                # ? ì§œ ì»¬ëŸ¼ ì°¾ê¸°
                date_column = None
                for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                    if col in columns or col.lower() in [c.lower() for c in columns]:
                        date_column = col
                        break
                
                # ORDER BY ???ì„±
                if date_column:
                    order_by = f"ORDER BY {date_column} DESC"
                else:
                    order_by = "ORDER BY 1 DESC"
            except Exception as e:
                logger.warning(f"?Œì´ë¸?êµ¬ì¡° ?•ì¸ ?¤íŒ¨, ê¸°ë³¸ ì¿¼ë¦¬ ?¬ìš©: {e}")
                order_by = "ORDER BY 1 DESC"
            
            # predicted_results?ì„œ ê¸°ì¡´ ?¬ìš©???•ë³´ ?•ì¸ (?˜ì´, BMI, ?±ë³„ë§?
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
            
            # room_threshold ?Œì´ë¸”ì—??ê¸°ì¡´ ì¾Œì  ?¨ë„ ë²”ìœ„ ?•ì¸
            try:
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # room_threshold?ì„œ ê¸°ì¡´ ?„ê³„ê°??•ì¸
                    threshold_query = text("SELECT min_temp, max_temp FROM room_threshold LIMIT 1")
                    threshold_result = conn.execute(threshold_query).fetchone()
                    
                    # ê¸°ì¡´ ?¬ìš©???•ë³´ê°€ ?ˆê³ , ?˜ì´/BMI/?±ë³„???™ì¼?˜ê³ , room_threshold??ê°’ì´ ?ˆìœ¼ë©??¬ìš©
                    if existing_user and existing_user.age == age and existing_user.bmi == bmi and existing_user.gender == gender:
                        if threshold_result and threshold_result.min_temp is not None and threshold_result.max_temp is not None:
                            comfort_min = float(threshold_result.min_temp)
                            comfort_max = float(threshold_result.max_temp)
                            logger.info(f"?“‹ ê¸°ì¡´ ì¾Œì  ?¨ë„ ë²”ìœ„ ?¬ìš© (room_threshold): {comfort_min}~{comfort_max}Â°C")
            except Exception as e:
                logger.warning(f"room_threshold ?•ì¸ ?¤íŒ¨: {e}")
            
            # ì¾Œì  ?¨ë„ ë²”ìœ„ê°€ ?†ìœ¼ë©?ê³„ì‚° (ì²˜ìŒ ?…ë ¥?´ê±°???•ë³´ê°€ ë³€ê²½ëœ ê²½ìš°)
            if comfort_min is None or comfort_max is None:
                comfort_min, comfort_max = calculate_comfort_temperature(gender, int(age), bmi)
                logger.info(f"?Œ¡ï¸?ì¾Œì  ?¨ë„ ë²”ìœ„ ê³„ì‚° (?ˆë¡œ ê³„ì‚°): {comfort_min}~{comfort_max}Â°C (gender: {gender}, age: {int(age)}, bmi: {bmi})")
            
            # room_threshold ?Œì´ë¸”ì— ?„ê³„ê°??€??(ì²˜ìŒ ??ë²ˆë§Œ)
            try:
                # room_threshold ?Œì´ë¸?ì¡´ì¬ ?¬ë? ?•ì¸
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # ?Œì´ë¸”ì´ ?ˆìœ¼ë©??ˆì½”?œê? ?ˆëŠ”ì§€ ?•ì¸
                    check_threshold = text("SELECT COUNT(*) as count FROM room_threshold")
                    threshold_count = conn.execute(check_threshold).fetchone().count
                    
                    # ?ˆì½”?œê? ?†ì„ ?Œë§Œ ?½ì… (ì²˜ìŒ ??ë²ˆë§Œ)
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
                            logger.info(f"??room_threshold ?Œì´ë¸”ì— ?„ê³„ê°??€??(ì²˜ìŒ ?€??: {comfort_min}~{comfort_max}Â°C")
                        except Exception as e:
                            logger.warning(f"room_threshold ?€???¤íŒ¨: {e}")
                    else:
                        logger.info(f"?“‹ room_threshold ?Œì´ë¸”ì— ?´ë? ?„ê³„ê°’ì´ ?€?¥ë˜???ˆìŠµ?ˆë‹¤. (ê±´ë„ˆ?€)")
                else:
                    logger.warning("? ï¸ room_threshold ?Œì´ë¸”ì´ ì¡´ì¬?˜ì? ?ŠìŠµ?ˆë‹¤.")
            except Exception as e:
                logger.warning(f"room_threshold ?Œì´ë¸?ì²˜ë¦¬ ì¤??¤ë¥˜: {e}")
            
            # predicted_results ?Œì´ë¸”ì— ?°ì´???½ì… (ì¾Œì  ?¨ë„ ë²”ìœ„???€?¥í•˜ì§€ ?ŠìŒ)
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
        
        logger.info(f"???°ì´?°ê? DB???€?¥ë˜?ˆìŠµ?ˆë‹¤. (gender: {gender}, bmi: {bmi}, age: {age}, predicted_skin_temp: {predicted_skin_temp})")
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
        logger.error(f"???°ì´???€???¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/healthdata/latest")
async def get_latest_health_data():
    """?œë²„???€?¥ëœ ìµœì‹  ê±´ê°• ?°ì´??ì¡°íšŒ (?ˆë“œë¡œì´?œì—???¸ì¶œ)"""
    try:
        logger.info("?“± ìµœì‹  ê±´ê°• ?°ì´??ì¡°íšŒ ?”ì²­")
        
        try:
            with engine.connect() as conn:
                # ë¨¼ì? ?Œì´ë¸?êµ¬ì¡° ?•ì¸ (created_at ì»¬ëŸ¼ ì¡´ì¬ ?¬ë?)
                try:
                    # ?Œì´ë¸?ì»¬ëŸ¼ ?•ë³´ ì¡°íšŒ
                    columns_query = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'predicted_results'
                    """)
                    columns_result = conn.execute(columns_query)
                    columns = [row.COLUMN_NAME for row in columns_result]
                    
                    # ? ì§œ ì»¬ëŸ¼ ì°¾ê¸° (created_at, timestamp, date ??
                    date_column = None
                    for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                        if col in columns or col.lower() in [c.lower() for c in columns]:
                            date_column = col
                            break
                    
                    # ORDER BY ???ì„± (? ì§œ ì»¬ëŸ¼???ˆìœ¼ë©??¬ìš©, ?†ìœ¼ë©?ID ?¬ìš©)
                    order_by = f"ORDER BY {date_column} DESC" if date_column else "ORDER BY 1 DESC"  # 1?€ ì²?ë²ˆì§¸ ì»¬ëŸ¼
                    
                    # SELECT ???ì„± (created_at???ˆìœ¼ë©??¬í•¨, ?†ìœ¼ë©??œì™¸)
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
                    
                    # predicted_results ?Œì´ë¸”ì—??ìµœì‹  ?°ì´??ì¡°íšŒ
                    query = text(f"""
                        SELECT 
                            {select_columns}
                        FROM predicted_results
                        {order_by}
                        LIMIT 1
                    """)
                except Exception as e:
                    logger.warning(f"?Œì´ë¸?êµ¬ì¡° ?•ì¸ ?¤íŒ¨, ê¸°ë³¸ ì¿¼ë¦¬ ?¬ìš©: {e}")
                    # ê¸°ë³¸ ì¿¼ë¦¬ (created_at ?†ì´)
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
                    logger.info("?“Š ?€?¥ëœ ê±´ê°• ?°ì´?°ê? ?†ìŠµ?ˆë‹¤.")
                    return {
                        "success": True,
                        "data": {},
                        "message": "?€?¥ëœ ê±´ê°• ?°ì´?°ê? ?†ìŠµ?ˆë‹¤."
                    }
                
                # ?°ì´??ë³€??
                health_data = {
                    "heartRate": float(row.heartRate) if row.heartRate else None,
                    "hrv": float(row.hrv) if row.hrv else None,
                    "oxygenSaturation": float(row.oxygenSaturation) if row.oxygenSaturation else None,
                }
                
                # ? ì§œ ?¬ë§·??(created_at ì»¬ëŸ¼???ˆìœ¼ë©??¬ìš©, ?†ìœ¼ë©??„ì¬ ?œê°„ ?¬ìš©)
                try:
                    created_at = getattr(row, 'created_at', None)
                    if created_at is None:
                        # created_at ì»¬ëŸ¼???†ìœ¼ë©??„ì¬ ?œê°„ ?¬ìš©
                        created_at = datetime.now()
                        date_str = created_at.isoformat()
                    elif isinstance(created_at, datetime):
                        date_str = created_at.isoformat()
                    else:
                        date_str = str(created_at)
                except AttributeError:
                    # created_at ?ì„±???†ìœ¼ë©??„ì¬ ?œê°„ ?¬ìš©
                    created_at = datetime.now()
                    date_str = created_at.isoformat()
                
                logger.info(f"??ìµœì‹  ê±´ê°• ?°ì´??ì¡°íšŒ ?±ê³µ: {health_data}")
                
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
            logger.error(f"??DB ì¡°íšŒ ?¤íŒ¨: {str(db_error)}")
            # DB ?¤ë¥˜ ??ë¹??°ì´??ë°˜í™˜ (?œë²„???•ìƒ ?‘ë‹µ)
            return {
                "success": True,
                "data": {},
                "message": f"?°ì´??ì¡°íšŒ ?¤íŒ¨: {str(db_error)}"
            }
    
    except Exception as e:
        logger.error(f"??ìµœì‹  ê±´ê°• ?°ì´??ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        # ?ëŸ¬ ë°œìƒ ?œì—??ë¹??°ì´??ë°˜í™˜ (500 ?ëŸ¬ ë°©ì?)
        return {
            "success": True,
            "data": {},
            "message": f"?°ì´??ì¡°íšŒ ?¤íŒ¨: {str(e)}"
        }

# ==================== ëª¨ë¸ ?ˆì¸¡ API ====================

@app.post("/predict")
async def predict(data: PredictRequest):
    """ì²´ì˜¨ ?ˆì¸¡ API"""
    try:
        if not model_loaded:
            raise HTTPException(status_code=500, detail="ëª¨ë¸??ë¡œë“œ?˜ì? ?Šì•˜?µë‹ˆ??")
        
        logger.info(f"?“± ?±ì—???ˆì¸¡ ?”ì²­ ë°›ìŒ: {data.dict()}")
        
        # ?ˆì¸¡ ?˜í–‰
        predicted_temp = predict_temperature_with_model(
            hr_mean=data.hr_mean,
            hrv_sdnn=data.hrv_sdnn,
            bmi=data.bmi,
            mean_sa02=data.mean_sa02,
            gender=data.gender,
            age=data.age
        )
        
        # ?¨ë„ ë¶„ë¥˜ (?±ê³¼ ?™ì¼??ê¸°ì?: 34.5?„ë???35.6?„ê¹Œì§€ ì¾Œì  ë²”ìœ„???¬í•¨)
        def classify_temperature(temp, cold_threshold=34.5, hot_threshold=35.6):
            if temp < 34.5:
                return "ì¶”ì?"
            elif temp > 35.6:
                return "?”ì?"
            else:
                # 34.5 <= temp <= 35.6: ì¾Œì ??(ê²½ê³„ê°??¬í•¨)
                return "?ì •"
        
        temperature_category = classify_temperature(predicted_temp)
        
        result = {
            'success': True,
            'predicted_temperature': predicted_temp,
            'temperature_category': temperature_category,
            'input_data': data.dict()
        }
        logger.info(f"???ˆì¸¡ ?„ë£Œ: {predicted_temp:.2f}Â°C ({temperature_category})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"?ˆì¸¡ ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?ˆì¸¡ ?¤íŒ¨: {str(e)}')

@app.get("/model_info")
async def model_info():
    """ëª¨ë¸ ?•ë³´ ë°˜í™˜"""
    if not model_loaded:
        raise HTTPException(status_code=500, detail="ëª¨ë¸??ë¡œë“œ?˜ì? ?Šì•˜?µë‹ˆ??")
    
    return {
        'model_type': '?™ìƒë¸?ëª¨ë¸ (RandomForest + ExtraTrees + GradientBoosting) - ?˜ì´ ?¬í•¨',
        'features': ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio', 'gender'],
        'target': 'TEMP_median (ì²´ì˜¨)',
        'model_loaded': model_loaded
    }

@app.get("/comfort_temperature")
async def get_comfort_temperature():
    """DB?ì„œ ?€?¥ëœ ì¾Œì  ?¨ë„ ë²”ìœ„ ì¡°íšŒ (ê³„ì‚°?˜ì? ?Šê³  ?€?¥ëœ ê°??¬ìš©)"""
    try:
        logger.info("?Œ¡ï¸?ì¾Œì  ?¨ë„ ë²”ìœ„ ì¡°íšŒ ?”ì²­")
        
        with engine.connect() as conn:
            # ë¨¼ì? ?Œì´ë¸?êµ¬ì¡° ?•ì¸
            try:
                columns_query = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'main' 
                    AND TABLE_NAME = 'predicted_results'
                """)
                columns_result = conn.execute(columns_query)
                columns = [row.COLUMN_NAME for row in columns_result]
                
                # ? ì§œ ì»¬ëŸ¼ ì°¾ê¸°
                date_column = None
                for col in ['created_at', 'timestamp', 'date', 'datetime', 'createdAt']:
                    if col in columns or col.lower() in [c.lower() for c in columns]:
                        date_column = col
                        break
                
                # ORDER BY ???ì„±
                if date_column:
                    order_by = f"ORDER BY {date_column} DESC"
                else:
                    order_by = "ORDER BY 1 DESC"
                
                # ì¾Œì  ?¨ë„ ì»¬ëŸ¼ ì¡´ì¬ ?¬ë? ?•ì¸
                has_comfort_columns = 'comfort_min_temp' in columns or 'comfort_min_temp'.lower() in [c.lower() for c in columns]
                
            except Exception as e:
                logger.warning(f"?Œì´ë¸?êµ¬ì¡° ?•ì¸ ?¤íŒ¨, ê¸°ë³¸ ì¿¼ë¦¬ ?¬ìš©: {e}")
                order_by = "ORDER BY 1 DESC"
                has_comfort_columns = False
            
            # ?€?¥ëœ ì¾Œì  ?¨ë„ ë²”ìœ„ê°€ ?ˆìœ¼ë©??¬ìš©
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
                # ì¾Œì  ?¨ë„ ì»¬ëŸ¼???†ìœ¼ë©??¬ìš©???•ë³´ë§?ì¡°íšŒ
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
                logger.warning("? ï¸ ?¬ìš©???•ë³´ê°€ ?†ìŠµ?ˆë‹¤.")
                return {
                    "success": False,
                    "message": "?¬ìš©???•ë³´ê°€ ?†ìŠµ?ˆë‹¤. ë¨¼ì? ê±´ê°• ?°ì´?°ë? ?€?¥í•´ì£¼ì„¸??",
                    "comfort_temperature_range": None
                }
            
            # ?€?¥ëœ ì¾Œì  ?¨ë„ ë²”ìœ„ê°€ ?ˆìœ¼ë©??¬ìš©
            if has_comfort_columns and row.comfort_min_temp is not None and row.comfort_max_temp is not None:
                comfort_min = float(row.comfort_min_temp)
                comfort_max = float(row.comfort_max_temp)
                logger.info(f"?“‹ ?€?¥ëœ ì¾Œì  ?¨ë„ ë²”ìœ„ ?¬ìš©: {comfort_min}~{comfort_max}Â°C")
            else:
                # ?€?¥ëœ ê°’ì´ ?†ìœ¼ë©?ê³„ì‚° (?˜ì?ë§???ê²½ìš°??ê±°ì˜ ë°œìƒ?˜ì? ?Šì•„????
                gender = row.gender
                age = int(row.age) if row.age else 0
                bmi = float(row.bmi) if row.bmi else 0.0
                comfort_min, comfort_max = calculate_comfort_temperature(gender, age, bmi)
                logger.info(f"?Œ¡ï¸?ì¾Œì  ?¨ë„ ë²”ìœ„ ê³„ì‚° (?€?¥ëœ ê°??†ìŒ): {comfort_min}~{comfort_max}Â°C")
            
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
        logger.error(f"??ì¾Œì  ?¨ë„ ë²”ìœ„ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return {
            "success": False,
            "message": f"ì¾Œì  ?¨ë„ ë²”ìœ„ ì¡°íšŒ ?¤íŒ¨: {str(e)}",
            "comfort_temperature_range": None
        }

# ==================== ?ì–´ì»??œì–´ API ====================

@app.get("/air_conditioner/state")
async def get_air_conditioner_state_api():
    """?ì–´ì»??íƒœ ì¡°íšŒ API"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="?ì–´ì»?ëª¨ë“ˆ???¬ìš©?????†ìŠµ?ˆë‹¤.")
    
    try:
        logger.info("?“± ?±ì—???ì–´ì»??íƒœ ì¡°íšŒ ?”ì²­")
        state_response = get_air_conditioner_state()
        
        # ?‘ë‹µ êµ¬ì¡° ë¶„ì„ ë°??íƒœ ?•ë³´ ì¶”ì¶œ
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
            # ?íƒœ ?•ë³´ë¥??±ì—???¬ìš©?˜ê¸° ?¬ìš´ ?•íƒœë¡?ë³€??
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
                    'raw_state': state  # ?„ì²´ ?íƒœ ?•ë³´???¬í•¨
                }
            }
            logger.info(f"???ì–´ì»??íƒœ ì¡°íšŒ ?±ê³µ")
            return result
        else:
            raise HTTPException(status_code=500, detail="?íƒœ ?•ë³´ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"?ì–´ì»??íƒœ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?ì–´ì»??íƒœ ì¡°íšŒ ?¤íŒ¨: {str(e)}')

@app.post("/air_conditioner/control")
async def control_air_conditioner_api(data: AirConditionerControlRequest):
    """?ì–´ì»??œì–´ API"""
    if not AIR_CONDITIONER_AVAILABLE:
        raise HTTPException(status_code=500, detail="?ì–´ì»?ëª¨ë“ˆ???¬ìš©?????†ìŠµ?ˆë‹¤.")
    
    try:
        logger.info(f"?“± ?±ì—???ì–´ì»??œì–´ ?”ì²­: {data.dict()}")
        
        if not data.action:
            raise HTTPException(status_code=400, detail="action ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??")
        
        result = None
        
        if data.action == 'set_temperature':
            if data.target_temperature is None:
                raise HTTPException(status_code=400, detail="target_temperature ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??")
            result = set_temperature(target_temp=float(data.target_temperature), unit=data.unit or 'C')
            
        elif data.action == 'set_mode':
            if not data.mode:
                raise HTTPException(status_code=400, detail="mode ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??")
            result = set_job_mode(mode=data.mode)
            
        elif data.action == 'set_wind_strength':
            if not data.strength:
                raise HTTPException(status_code=400, detail="strength ?Œë¼ë¯¸í„°ê°€ ?„ìš”?©ë‹ˆ??")
            result = set_wind_strength(strength=data.strength)
            
        elif data.action == 'set_power':
            result = set_power(power_on=bool(data.power_on))
            
        else:
            raise HTTPException(status_code=400, detail=f'ì§€?í•˜ì§€ ?ŠëŠ” action: {data.action}')
        
        logger.info(f"???ì–´ì»??œì–´ ?±ê³µ: {data.action}")
        
        # ?¡ì…˜ë³?ë©”ì‹œì§€ ?ì„±
        messages = {
            'set_power': f"?„ì› {'ì¼œê¸°' if data.power_on else '?„ê¸°'} ?±ê³µ",
            'set_temperature': f"ëª©í‘œ ?¨ë„ {data.target_temperature}Â°C ?¤ì • ?±ê³µ",
            'set_mode': f"ëª¨ë“œ {data.mode} ?¤ì • ?±ê³µ",
            'set_wind_strength': f"?ëŸ‰ {data.strength} ?¤ì • ?±ê³µ",
        }
        
        return {
            'success': True,
            'action': data.action,
            'message': messages.get(data.action, '?œì–´ ?±ê³µ'),
            'result': result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"?ì–´ì»??œì–´ ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?ì–´ì»??œì–´ ?¤íŒ¨: {str(e)}')

<<<<<<< HEAD
class TemperatureThresholdRequest(BaseModel):
    """?¨ë„ ?„ê³„ê°??€???”ì²­"""
    target_temperature: float  # ?¬ìš©?ê? ?¤ì •???¨ë„ (?? 24??

@app.post("/air_conditioner/temperature_threshold")
async def save_temperature_threshold_api(data: TemperatureThresholdRequest):
    """?ì–´ì»??¨ë„ ?„ê³„ê°’ì„ ìºì‹œ???€??(12?œê°„ ? íš¨)"""
    try:
        threshold = save_threshold(data.target_temperature)
        
        return {
            "success": True,
            "message": "?¨ë„ ?„ê³„ê°’ì´ ?€?¥ë˜?ˆìŠµ?ˆë‹¤.",
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"???¨ë„ ?„ê³„ê°??€???¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?¨ë„ ?„ê³„ê°??€???¤íŒ¨: {str(e)}')

@app.get("/air_conditioner/temperature_threshold")
async def get_temperature_threshold_api():
    """?„ì¬ ?€?¥ëœ ?¨ë„ ?„ê³„ê°?ì¡°íšŒ (ë§Œë£Œ?˜ì? ?Šì? ê²½ìš°ë§?"""
    try:
        threshold = get_threshold()
        
        if threshold is None:
            return {
                "success": True,
                "has_threshold": False,
                "message": "?€?¥ëœ ?„ê³„ê°’ì´ ?†ìŠµ?ˆë‹¤."
            }
        
        return {
            "success": True,
            "has_threshold": True,
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"???¨ë„ ?„ê³„ê°?ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?¨ë„ ?„ê³„ê°?ì¡°íšŒ ?¤íŒ¨: {str(e)}')
# ==================== ?¨ë„ ë²”ìœ„ ?¤ì • API ====================

@app.post("/temperature-range")
async def set_temperature_range(data: TemperatureRangeRequest):
    """
    ?¬ìš©???¹ì„±(?˜ì´, BMI, ?±ë³„)???°ë¼ ì¾Œì  ?¨ë„ ë²”ìœ„ë¥?ê³„ì‚°?˜ê³  DB???€??
    (ì²˜ìŒ ?œë²ˆë§??ìš©, ?´ë? ?¤ì •?˜ì–´ ?ˆìœ¼ë©?ê¸°ì¡´ ê°?? ì?)
    """
    try:
        logger.info(f"?Œ¡ï¸??¨ë„ ë²”ìœ„ ?¤ì • ?”ì²­: ?˜ì´={data.age}?? BMI={data.bmi}, ?±ë³„={data.gender}, force_update={data.force_update}")
        
        # ?¨ë„ ë²”ìœ„ ì´ˆê¸°??
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
            raise HTTPException(status_code=500, detail="?¨ë„ ë²”ìœ„ ?¤ì • ?¤íŒ¨")
        
        return {
            "success": True,
            "message": "?¨ë„ ë²”ìœ„ ?¤ì • ?„ë£Œ",
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
        logger.error(f"?¨ë„ ë²”ìœ„ ?¤ì • ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?¨ë„ ë²”ìœ„ ?¤ì • ?¤íŒ¨: {str(e)}')

@app.get("/temperature-range")
async def get_temperature_range():
    """
    DB?ì„œ ?€?¥ëœ ì¾Œì  ?¨ë„ ë²”ìœ„ ì¡°íšŒ
    """
    try:
        logger.info("?Œ¡ï¸??¨ë„ ë²”ìœ„ ì¡°íšŒ ?”ì²­")
        
        temperature_range = temperature_control_logic.get_temperature_range_from_db(engine)
        
        if temperature_range is None:
            return {
                "success": False,
                "message": "?¨ë„ ë²”ìœ„ê°€ ?¤ì •?˜ì? ?Šì•˜?µë‹ˆ??,
                "min_temp": None,
                "max_temp": None
            }
        
        min_temp, max_temp = temperature_range
        
        # DB?ì„œ ?¬ìš©???•ë³´???¨ê»˜ ì¡°íšŒ
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
        logger.error(f"?¨ë„ ë²”ìœ„ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'?¨ë„ ë²”ìœ„ ì¡°íšŒ ?¤íŒ¨: {str(e)}')
>>>>>>> 849157b2f84eeecf85c280df228b6557b6ccf58b

# ==================== ê¸°ë³¸ API ====================

@app.get("/")
async def root():
    return {"message": "Unified Server is running (Health Data + Model Prediction + IoT Control)"}

@app.post("/temperature_feedback")
async def save_temperature_feedback(data: TemperatureFeedbackRequest):
    """?¨ë„ ?¼ë“œë°??€??API"""
    try:
        logger.info(f"?“ ?¨ë„ ?¼ë“œë°??€???”ì²­: {data.dict()}")
        
        # ?¼ë“œë°?ê°’ì„ ì½”ë“œë¡?ë³€??(C: ì¶”ì?, H: ?”ì?, G: ì¾Œì )
        feedback_code = None
        if data.feedback == 'cold':
            feedback_code = 'C'
        elif data.feedback == 'hot':
            feedback_code = 'H'
        elif data.feedback == 'comfortable':
            feedback_code = 'G'
        else:
            logger.warning(f"? ï¸ ?????†ëŠ” ?¼ë“œë°?ê°? {data.feedback}")
            return {
                "success": False,
                "message": f"?????†ëŠ” ?¼ë“œë°?ê°? {data.feedback}"
            }
        
        # ? ì§œ ì²˜ë¦¬
        feedback_date = data.date
        if not feedback_date:
            from datetime import datetime
            feedback_date = datetime.now().isoformat()
        
        with engine.connect() as conn:
            # room_threshold ?Œì´ë¸”ì— feedback ?€??
            try:
                # room_threshold ?Œì´ë¸?ì¡´ì¬ ?¬ë? ?•ì¸
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'room_threshold'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # feedback ì»¬ëŸ¼ ì¡´ì¬ ?¬ë? ?•ì¸
                    columns_check = text("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'main' 
                        AND TABLE_NAME = 'room_threshold'
                        AND COLUMN_NAME = 'feedback'
                    """)
                    has_feedback_column = conn.execute(columns_check).fetchone() is not None
                    
                    if has_feedback_column:
                        # feedback ì»¬ëŸ¼???ˆìœ¼ë©??…ë°?´íŠ¸
                        # id ì»¬ëŸ¼???ˆëŠ”ì§€ ?•ì¸
                        id_check = text("""
                            SELECT COLUMN_NAME 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'main' 
                            AND TABLE_NAME = 'room_threshold'
                            AND COLUMN_NAME = 'id'
                        """)
                        has_id = conn.execute(id_check).fetchone() is not None
                        
                        if has_id:
                            # idê°€ ?ˆìœ¼ë©?ì²?ë²ˆì§¸ ?ˆì½”???…ë°?´íŠ¸
                            update_query = text("""
                                UPDATE room_threshold 
                                SET feedback = :feedback
                                WHERE id = (SELECT id FROM (SELECT id FROM room_threshold LIMIT 1) AS t)
                            """)
                        else:
                            # idê°€ ?†ìœ¼ë©?ëª¨ë“  ?ˆì½”???…ë°?´íŠ¸ (?¨ì¼ ?ˆì½”??ê°€??
                            update_query = text("""
                                UPDATE room_threshold 
                                SET feedback = :feedback
                            """)
                        
                        conn.execute(update_query, {
                            'feedback': feedback_code
                        })
                        conn.commit()
                        logger.info(f"??room_threshold ?Œì´ë¸”ì— ?¼ë“œë°??€???„ë£Œ: {feedback_code} ({data.feedback})")
                    else:
                        logger.warning("? ï¸ room_threshold ?Œì´ë¸”ì— feedback ì»¬ëŸ¼??ì¡´ì¬?˜ì? ?ŠìŠµ?ˆë‹¤.")
                else:
                    logger.warning("? ï¸ room_threshold ?Œì´ë¸”ì´ ì¡´ì¬?˜ì? ?ŠìŠµ?ˆë‹¤.")
            except Exception as e:
                logger.error(f"??room_threshold ?¼ë“œë°??€???¤íŒ¨: {str(e)}")
            
            # temperature_feedback ?Œì´ë¸”ì—???€??(? íƒ??
            try:
                # temperature_feedback ?Œì´ë¸?ì¡´ì¬ ?¬ë? ?•ì¸
                table_check = text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_name = 'temperature_feedback'
                """)
                table_exists = conn.execute(table_check).fetchone().count > 0
                
                if table_exists:
                    # ?Œì´ë¸”ì´ ?ˆìœ¼ë©??€??
                    insert_query = text("""
                        INSERT INTO temperature_feedback (feedback, feedback_date, created_at)
                        VALUES (:feedback, :feedback_date, NOW())
                    """)
                    conn.execute(insert_query, {
                        'feedback': data.feedback,
                        'feedback_date': feedback_date
                    })
                    conn.commit()
                    logger.info(f"??temperature_feedback ?Œì´ë¸”ì— ?¼ë“œë°??€???„ë£Œ: {data.feedback}")
            except Exception as e:
                logger.warning(f"temperature_feedback ?Œì´ë¸??€???¤íŒ¨ (? íƒ??: {str(e)}")
        
        return {
            "success": True,
            "message": "?¼ë“œë°±ì´ ?€?¥ë˜?ˆìŠµ?ˆë‹¤.",
            "feedback": data.feedback,
            "feedback_code": feedback_code
        }
    except Exception as e:
        logger.error(f"???¨ë„ ?¼ë“œë°??€???¤íŒ¨: {str(e)}")
        return {
            "success": False,
            "message": f"?¼ë“œë°??€???¤íŒ¨: {str(e)}"
        }

@app.post("/threshold/update")
async def update_threshold(data: ThresholdUpdateRequest):
    """
    ?¼ë??¨ë„ ë¶„ë¥˜ ê¸°ì? ê°±ì‹  API
    
    Args:
        cold_threshold: ì¶”ì? ë¶„ë¥˜ ê¸°ì? (? íƒ)
        hot_threshold: ?”ì? ë¶„ë¥˜ ê¸°ì? (? íƒ)
    """
    global COLD_THRESHOLD, HOT_THRESHOLD
    
    try:
        updated = []
        
        if data.cold_threshold is not None:
            if data.cold_threshold < 0 or data.cold_threshold > 50:
                raise HTTPException(status_code=400, detail="cold_threshold??0~50 ?¬ì´??ê°’ì´?´ì•¼ ?©ë‹ˆ??")
            COLD_THRESHOLD = data.cold_threshold
            updated.append(f"cold_threshold={COLD_THRESHOLD}")
            logger.info(f"??COLD_THRESHOLD ê°±ì‹ : {COLD_THRESHOLD}Â°C")
        
        if data.hot_threshold is not None:
            if data.hot_threshold < 0 or data.hot_threshold > 50:
                raise HTTPException(status_code=400, detail="hot_threshold??0~50 ?¬ì´??ê°’ì´?´ì•¼ ?©ë‹ˆ??")
            HOT_THRESHOLD = data.hot_threshold
            updated.append(f"hot_threshold={HOT_THRESHOLD}")
            logger.info(f"??HOT_THRESHOLD ê°±ì‹ : {HOT_THRESHOLD}Â°C")
        
        if not updated:
            raise HTTPException(status_code=400, detail="cold_threshold ?ëŠ” hot_threshold ì¤??˜ë‚˜ ?´ìƒ???œê³µ?´ì•¼ ?©ë‹ˆ??")
        
        return {
            "success": True,
            "message": "ë¶„ë¥˜ ê¸°ì? ê°±ì‹  ?„ë£Œ",
            "cold_threshold": COLD_THRESHOLD,
            "hot_threshold": HOT_THRESHOLD,
            "updated": updated
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"??ë¶„ë¥˜ ê¸°ì? ê°±ì‹  ?¤íŒ¨: {str(e)}")
        raise HTTPException(status_code=500, detail=f'ë¶„ë¥˜ ê¸°ì? ê°±ì‹  ?¤íŒ¨: {str(e)}')

@app.get("/threshold")
async def get_threshold():
    """?„ì¬ ?¼ë??¨ë„ ë¶„ë¥˜ ê¸°ì? ì¡°íšŒ"""
    return {
        "success": True,
        "cold_threshold": COLD_THRESHOLD,
        "hot_threshold": HOT_THRESHOLD
    }

@app.get("/health")
async def health_check():
    """?œë²„ ?íƒœ ?•ì¸ (ëª¨ë¸, ?ì–´ì»? DB ?°ê²° ?íƒœ ?¬í•¨)"""
    # DB ?°ê²° ?ŒìŠ¤??
    db_connected = False
    db_error = None
    try:
        with engine.connect() as conn:
            # ê°„ë‹¨??ì¿¼ë¦¬ë¡??°ê²° ?ŒìŠ¤??
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            db_connected = True
    except Exception as e:
        db_error = str(e)
        logger.error(f"??DB ?°ê²° ?ŒìŠ¤???¤íŒ¨: {db_error}")
    
    return {
        "status": "healthy",
        "model_loaded": model_loaded,
        "air_conditioner_available": AIR_CONDITIONER_AVAILABLE,
        "database_connected": db_connected,
        "database_error": db_error if not db_connected else None
    }

@app.get("/health/db")
async def test_db_connection():
    """DB ?°ê²° ?ŒìŠ¤???„ìš© ?”ë“œ?¬ì¸??""
    try:
        with engine.connect() as conn:
            # ê°„ë‹¨??ì¿¼ë¦¬ë¡??°ê²° ?ŒìŠ¤??
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            
            # ?Œì´ë¸?ì¡´ì¬ ?¬ë? ?•ì¸
            table_check = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = 'main' 
                AND table_name = 'predicted_results'
            """))
            table_exists = table_check.fetchone().count > 0
            
            # ?°ì´??ê°œìˆ˜ ?•ì¸
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
                "message": "DB ?°ê²° ?±ê³µ"
            }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"??DB ?°ê²° ?ŒìŠ¤???¤íŒ¨: {error_msg}")
        return {
            "success": False,
            "connected": False,
            "error": error_msg,
            "message": "DB ?°ê²° ?¤íŒ¨"
        }

# ==================== ?ì–´ì»??ë™ ?¨ë„ ì¡°ì ˆ ?œìŠ¤??====================

# ?¤ì?ì¤„ëŸ¬ ì´ˆê¸°??
scheduler = BackgroundScheduler()

def adjust_air_conditioner_wrapper():
    """?¤ì?ì¤„ëŸ¬?ì„œ ?¸ì¶œ???˜í¼ ?¨ìˆ˜ (?„ì—­ ë³€???¬ìš©)"""
    global COLD_THRESHOLD, HOT_THRESHOLD
    
    def update_thresholds(new_cold: float, new_hot: float):
        """?„ì—­ ë³€??ê°±ì‹  ì½œë°± ?¨ìˆ˜"""
        global COLD_THRESHOLD, HOT_THRESHOLD
        COLD_THRESHOLD = new_cold
        HOT_THRESHOLD = new_hot
    
    # ?„ì—­ ë³€?˜ì—??ìµœì‹  ê°?ê°€?¸ì˜¤ê¸?(?°í??„ì— ê°±ì‹  ê°€??
    air_conditioner_auto_control.adjust_air_conditioner(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature,
        cold_threshold=COLD_THRESHOLD,  # ?„ì—­ ë³€?˜ì—??ê°€?¸ì˜´ (ê°±ì‹  ê°€??
        hot_threshold=HOT_THRESHOLD,    # ?„ì—­ ë³€?˜ì—??ê°€?¸ì˜´ (ê°±ì‹  ê°€??
        update_threshold_callback=update_thresholds  # DB ê°?ë³€ê²????„ì—­ ë³€??ê°±ì‹  ì½œë°±
    )

scheduler.add_job(
    adjust_air_conditioner_wrapper,
    trigger=IntervalTrigger(minutes=30),
    id='air_conditioner_adjustment',
    name='?ì–´ì»??ë™ ?¨ë„ ì¡°ì ˆ',
    replace_existing=True
)

# ?œë²„ ?œì‘ ??ì´ˆê¸° ?¸íŒ… ë°??¤ì?ì¤„ëŸ¬ ?œì‘
@app.on_event("startup")
async def startup_event():
    """?œë²„ ?œì‘ ??ì´ˆê¸° ?¸íŒ… ë°??¤ì?ì¤„ëŸ¬ ?œì‘"""
    logger.info("?? ?œë²„ ?œì‘ ì¤?..")
    air_conditioner_auto_control.initialize_air_conditioner_settings(
        engine=engine,
        air_conditioner_available=AIR_CONDITIONER_AVAILABLE,
        get_air_conditioner_state_func=get_air_conditioner_state,
        set_temperature_func=set_temperature
    )
    scheduler.start()
    logger.info("???¤ì?ì¤„ëŸ¬ ?œì‘ ?„ë£Œ (30ë¶„ë§ˆ???ë™ ì¡°ì ˆ)")

@app.on_event("shutdown")
async def shutdown_event():
    """?œë²„ ì¢…ë£Œ ???¤ì?ì¤„ëŸ¬ ì¢…ë£Œ"""
    logger.info("?›‘ ?œë²„ ì¢…ë£Œ ì¤?..")
    scheduler.shutdown()
    logger.info("???¤ì?ì¤„ëŸ¬ ì¢…ë£Œ ?„ë£Œ")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
