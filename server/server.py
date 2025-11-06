from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlalchemy
from sqlalchemy import text
from datetime import datetime
import logging
import pickle
import os
import numpy as np

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
DB_URL = "mysql+pymysql://jiwooyoon:dbswldnwldn0121@aiservice.ctcekecusqi9.ap-northeast-2.rds.amazonaws.com:3306/main"
engine = sqlalchemy.create_engine(DB_URL)

# 모델 로드
MODEL_FILE = os.path.join(os.path.dirname(__file__), 'ai_thermal_model_with_age.pkl')
model = None

def load_model():
    """모델 로드"""
    global model
    if model is not None:
        return model
    
    if not os.path.exists(MODEL_FILE):
        logger.warning(f"⚠️ 모델 파일을 찾을 수 없습니다: {MODEL_FILE}")
        return None
    
    try:
        with open(MODEL_FILE, 'rb') as f:
            model = pickle.load(f)
        logger.info("✅ 모델 로드 성공!")
        return model
    except Exception as e1:
        logger.error(f"❌ pickle 로드 실패: {e1}")
        try:
            import joblib
            model = joblib.load(MODEL_FILE)
            logger.info("✅ joblib로 모델 로드 성공!")
            return model
        except Exception as e2:
            logger.error(f"❌ joblib 로드 실패: {e2}")
            return None

# 서버 시작 시 모델 로드
model = load_model()

# HealthKit 데이터 모델
class HealthData(BaseModel):
    heartRate: Optional[float] = None
    HRV: Optional[float] = None
    oxygenSaturation: Optional[float] = None
    bmi: Optional[float] = None
    age: Optional[float] = None
    gender: Optional[float] = None  # 0: 여성, 1: 남성

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
        gender = data.gender if data.gender is not None else 0.0  # 기본값: 여성
        bmi = data.bmi if data.bmi is not None else 0.0
        age = data.age if data.age is not None else 0.0
        
        # 모델로 예측
        predicted_skin_temp = None
        if model is not None:
            try:
                # 피처 준비
                features = {
                    'HR_mean': data.heartRate,
                    'HRV_SDNN': data.HRV,
                    'gender': gender,
                    'bmi': bmi,
                    'age': age,
                    'mean_sa02': data.oxygenSaturation
                }
                
                # 파생 변수 생성
                age_hrv_ratio = age / (data.HRV + 1e-8) if data.HRV > 0 else 0
                age_bmi_interaction = age * bmi
                bmi_hr_interaction = bmi * data.heartRate
                hrv_hr_ratio = data.HRV / (data.heartRate + 1e-8) if data.heartRate > 0 else 0
                
                # 모델 입력 형식에 맞게 변환
                X = np.array([[
                    features['HR_mean'],
                    features['HRV_SDNN'],
                    features['gender'],
                    features['bmi'],
                    features['age'],
                    features['mean_sa02'],
                    age_hrv_ratio,
                    age_bmi_interaction,
                    bmi_hr_interaction,
                    hrv_hr_ratio
                ]])
                
                # 예측 실행
                predicted_skin_temp = float(model.predict(X)[0])
                logger.info(f"🔮 예측 결과: {predicted_skin_temp}")
            except Exception as e:
                logger.error(f"❌ 예측 실패: {str(e)}")
                # 예측 실패해도 데이터는 저장
        
        # DB에 데이터 저장
        with engine.connect() as conn:
            # predicted_results 테이블에 데이터 삽입
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
                'created_at': datetime.now()
            })
            conn.commit()
        
        logger.info("✅ 데이터가 DB에 저장되었습니다.")
        return {
            "status": "ok", 
            "message": "Data saved successfully",
            "predicted_skin_temp": predicted_skin_temp
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 데이터 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Health Data Server is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

