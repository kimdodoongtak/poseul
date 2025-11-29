"""
모델 예측 관련 공통 유틸리티 함수
"""
import pandas as pd
import sqlalchemy
import logging
import pickle
import os
import joblib

logger = logging.getLogger(__name__)

# DB 연결 설정 (공통)
DB_URL = "mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main"

# 모델 파일 경로 (공통)
# ai_thermal_model_final.pkl 파일 경로 (프로젝트 루트에 있음)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # server 디렉토리
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # 프로젝트 루트
MODEL_FILE = os.path.join(PROJECT_ROOT, 'ai_thermal_model_final.pkl')

def get_db_engine():
    """
    DB 연결 엔진을 반환합니다.
    
    Returns:
        sqlalchemy.engine.Engine: DB 연결 엔진
    """
    return sqlalchemy.create_engine(DB_URL)


def load_model(model_file: str = None):
    """
    모델을 로드합니다.
    
    Args:
        model_file: 모델 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        로드된 모델 또는 None
    """
    if model_file is None:
        # 기본 경로 사용 (ai_thermal_model_final.pkl)
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        PROJECT_ROOT = os.path.dirname(BASE_DIR)
        model_file = os.path.join(PROJECT_ROOT, 'ai_thermal_model_final.pkl')
    
    if not os.path.exists(model_file):
        logger.warning(f"⚠️ 모델 파일을 찾을 수 없습니다: {model_file}")
        return None
    
    # joblib을 먼저 시도 (더 안전하고 호환성이 좋음)
    try:
        model = joblib.load(model_file)
        logger.info(f"✅ joblib로 모델 로드 성공: {model_file}")
        return model
    except Exception as e2:
        logger.warning(f"⚠️ joblib 로드 실패: {e2}")
        # pickle로 시도
        try:
            with open(model_file, 'rb') as f:
                model = pickle.load(f)
            logger.info(f"✅ pickle로 모델 로드 성공: {model_file}")
            return model
        except Exception as e1:
            logger.error(f"❌ pickle 로드 실패: {e1}")
            return None

def prepare_features_for_prediction(
    heart_rate: float,
    hrv: float,
    oxygen_saturation: float,
    bmi: float,
    age: float,
    gender_value: float  # 0.0: 여성, 1.0: 남성
) -> pd.DataFrame:
    """
    모델 예측을 위한 피처를 준비합니다.
    
    Args:
        heart_rate: 심박수 (HR_mean)
        hrv: 심박변이 (HRV_SDNN)
        oxygen_saturation: 산소포화도 (mean_sa02)
        bmi: BMI
        age: 나이
        gender_value: 성별 (0.0: 여성, 1.0: 남성)
    
    Returns:
        모델이 기대하는 형식의 pandas DataFrame (9개 피처)
    """
    # 파생 변수 생성
    age_hrv_ratio = age / (hrv + 1e-8) if hrv > 0 else 0
    age_bmi_interaction = age * bmi
    bmi_hr_interaction = bmi * heart_rate
    hrv_hr_ratio = hrv / (heart_rate + 1e-8) if heart_rate > 0 else 0
    
    # gender를 문자열로 변환 (OneHotEncoder가 기대하는 형식)
    gender_str = 'F' if gender_value == 0.0 else 'M'
    
    # 모델이 기대하는 피처 순서로 DataFrame 생성
    # 모델이 기대하는 피처: ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio', 'gender']
    X = pd.DataFrame([{
        'bmi': float(bmi),
        'mean_sa02': float(oxygen_saturation),
        'HRV_SDNN': float(hrv),
        'hrv_hr_ratio': float(hrv_hr_ratio),
        'bmi_hr_interaction': float(bmi_hr_interaction),
        'age': float(age),
        'age_bmi_interaction': float(age_bmi_interaction),
        'age_hrv_ratio': float(age_hrv_ratio),
        'gender': gender_str  # 문자열로 변환 (OneHotEncoder가 기대하는 형식)
    }])
    
    return X


def prepare_batch_features_for_prediction(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    배치 예측을 위한 피처를 준비합니다.
    
    Args:
        df: DB에서 가져온 DataFrame (컬럼: HR_mean, HRV_SDNN, gender, bmi, age, mean_sa02)
    
    Returns:
        모델이 기대하는 형식의 pandas DataFrame (9개 피처)
    """
    # 기본 피처 복사
    X = df[['HR_mean', 'HRV_SDNN', 'gender', 'bmi', 'age', 'mean_sa02']].copy()
    
    # gender를 문자열로 변환 (OneHotEncoder가 기대하는 형식)
    # F -> 'F', M -> 'M', 0 -> 'F', 1 -> 'M'
    X['gender'] = X['gender'].map({
        'F': 'F', 'M': 'M',
        '0': 'F', '1': 'M',
        0: 'F', 1: 'M',
        0.0: 'F', 1.0: 'M'
    }).fillna('F')
    X['gender'] = X['gender'].astype('object')  # 문자열로 유지
    
    # 모든 숫자 값을 float64로 명시적으로 변환
    X['HR_mean'] = X['HR_mean'].astype('float64')
    X['HRV_SDNN'] = X['HRV_SDNN'].astype('float64')
    X['bmi'] = X['bmi'].astype('float64')
    X['age'] = X['age'].astype('float64')
    X['mean_sa02'] = X['mean_sa02'].astype('float64')
    
    # 모델이 요구하는 파생 변수들 생성
    X['age_hrv_ratio'] = (X['age'] / (X['HRV_SDNN'] + 1e-8)).astype('float64')  # 0으로 나누기 방지
    X['age_bmi_interaction'] = (X['age'] * X['bmi']).astype('float64')
    X['bmi_hr_interaction'] = (X['bmi'] * df['HR_mean'].values).astype('float64')
    X['hrv_hr_ratio'] = (X['HRV_SDNN'] / (df['HR_mean'].values + 1e-8)).astype('float64')  # 0으로 나누기 방지
    
    # 모델이 기대하는 피처 순서로 재정렬
    # HR_mean은 모델이 기대하지 않으므로 제거
    X = X[['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio', 'gender']]
    
    return X


def predict_with_model(model, X: pd.DataFrame):
    """
    모델을 사용하여 예측을 실행합니다.
    
    Args:
        model: 로드된 모델
        X: 예측할 데이터 (pandas DataFrame)
    
    Returns:
        예측 결과 (단일 값 또는 배열)
    """
    if model is None:
        raise ValueError("모델이 None입니다. 모델을 먼저 로드해주세요.")
    
    return model.predict(X)

