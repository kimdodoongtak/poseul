"""
AI 체온 예측 서버
앙상블 모델을 사용하여 체온을 예측하는 Flask API 서버
에어컨 제어 API 포함
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import pandas as pd
import numpy as np
import os
import sys
import zipfile
import tempfile
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# IoT 폴더의 모듈 import를 위한 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../IoT'))
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

app = Flask(__name__)
CORS(app)  # CORS 허용

# 전역 변수
model = None
model_loaded = False

# 건강 데이터 저장소 (실제 운영 환경에서는 데이터베이스 사용 권장)
health_data_store = {
    'heartRate': None,
    'hrv': None,
    'oxygenSaturation': None,
    'lastUpdated': None
}

def load_model():
    """앙상블 모델 로드"""
    global model, model_loaded
    
    try:
        # 모델 파일 경로 (final 모델)
        model_path = '../pycode/ai_thermal_model_final.pkl'
        
        if not os.path.exists(model_path):
            logger.error(f"모델 파일을 찾을 수 없습니다: {model_path}")
            return False
        
        # 모델 로드
        model = joblib.load(model_path)
        
        if model is None:
            logger.error("모델을 로드할 수 없습니다.")
            return False
            
        model_loaded = True
        logger.info("앙상블 모델 로드 완료")
        return True
        
    except Exception as e:
        logger.error(f"모델 로드 실패: {str(e)}")
        return False

def predict_temperature(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
    """
    체온 예측 함수 (나이 포함)
    
    Parameters:
    - hr_mean: 평균 심박수
    - hrv_sdnn: 심박변이도 (SDNN)
    - bmi: 체질량지수
    - mean_sa02: 평균 산소포화도
    - gender: 성별 ('M' 또는 'F')
    - age: 나이
    
    Returns:
    - 예측된 체온 (°C)
    """
    if not model_loaded:
        raise ValueError("모델이 로드되지 않았습니다.")
    
    # 파생 피처 계산
    hrv_hr_ratio = hrv_sdnn / hr_mean
    bmi_hr_interaction = bmi * hr_mean
    age_bmi_interaction = age * bmi
    age_hrv_ratio = age / (hrv_sdnn + 1)  # 0으로 나누기 방지
    
    # 데이터 준비
    data = pd.DataFrame({
        'bmi': [bmi],
        'mean_sa02': [mean_sa02], 
        'HRV_SDNN': [hrv_sdnn],
        'hrv_hr_ratio': [hrv_hr_ratio],
        'bmi_hr_interaction': [bmi_hr_interaction],
        'age': [age],
        'age_bmi_interaction': [age_bmi_interaction],
        'age_hrv_ratio': [age_hrv_ratio],
        'gender': [gender]
    })
    
    # 예측
    temp_pred = model.predict(data)[0]
    return float(temp_pred)

@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model_loaded
    })

@app.route('/predict', methods=['POST'])
def predict():
    """체온 예측 API"""
    try:
        if not model_loaded:
            return jsonify({
                'error': '모델이 로드되지 않았습니다.'
            }), 500
        
        # 요청 데이터 파싱
        data = request.get_json()
        logger.info(f"📱 앱에서 예측 요청 받음: {data}")
        
        # 필수 파라미터 확인
        required_params = ['hr_mean', 'hrv_sdnn', 'bmi', 'mean_sa02', 'gender', 'age']
        for param in required_params:
            if param not in data:
                return jsonify({
                    'error': f'필수 파라미터가 누락되었습니다: {param}'
                }), 400
        
        # 예측 수행
        predicted_temp = predict_temperature(
            hr_mean=float(data['hr_mean']),
            hrv_sdnn=float(data['hrv_sdnn']),
            bmi=float(data['bmi']),
            mean_sa02=float(data['mean_sa02']),
            gender=str(data['gender']),
            age=int(data['age'])
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
            'input_data': data
        }
        logger.info(f"✅ 예측 완료: {predicted_temp:.2f}°C ({temperature_category})")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"예측 실패: {str(e)}")
        return jsonify({
            'error': f'예측 실패: {str(e)}'
        }), 500

@app.route('/model_info', methods=['GET'])
def model_info():
    """모델 정보 반환"""
    if not model_loaded:
        return jsonify({
            'error': '모델이 로드되지 않았습니다.'
        }), 500
    
    return jsonify({
        'model_type': '앙상블 모델 (RandomForest + ExtraTrees + GradientBoosting) - 나이 포함',
        'features': ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio', 'gender'],
        'target': 'TEMP_median (체온)',
        'model_loaded': model_loaded
    })

# ==================== 에어컨 제어 API ====================

@app.route('/air_conditioner/state', methods=['GET'])
def get_air_conditioner_state_api():
    """에어컨 상태 조회 API"""
    if not AIR_CONDITIONER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '에어컨 모듈을 사용할 수 없습니다.'
        }), 500
    
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
                    'power_on': state.get('operation', {}).get('airConOperationMode') == 'POWER_ON',
                    'current_temperature': state.get('temperature', {}).get('currentTemperature'),
                    'target_temperature': state.get('temperature', {}).get('targetTemperature'),
                    'temperature_unit': state.get('temperature', {}).get('unit', 'C'),
                    'job_mode': state.get('airConJobMode', {}).get('currentJobMode'),
                    'wind_strength': state.get('airFlow', {}).get('windStrength'),
                    'air_quality': {
                        'pm1': state.get('airQualitySensor', {}).get('PM1'),
                        'pm2': state.get('airQualitySensor', {}).get('PM2'),
                        'pm10': state.get('airQualitySensor', {}).get('PM10'),
                        'humidity': state.get('airQualitySensor', {}).get('humidity')
                    },
                    'filter_percent': state.get('filterInfo', {}).get('filterRemainPercent'),
                    'raw_state': state  # 전체 상태 정보도 포함
                }
            }
            logger.info(f"✅ 에어컨 상태 조회 성공")
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'error': '상태 정보를 찾을 수 없습니다.',
                'raw_response': state_response
            }), 500
            
    except Exception as e:
        logger.error(f"에어컨 상태 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'에어컨 상태 조회 실패: {str(e)}'
        }), 500


@app.route('/air_conditioner/control', methods=['POST'])
def control_air_conditioner_api():
    """에어컨 제어 API"""
    if not AIR_CONDITIONER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '에어컨 모듈을 사용할 수 없습니다.'
        }), 500
    
    try:
        data = request.get_json()
        logger.info(f"📱 앱에서 에어컨 제어 요청: {data}")
        
        action = data.get('action')
        if not action:
            return jsonify({
                'success': False,
                'error': 'action 파라미터가 필요합니다.'
            }), 400
        
        result = None
        
        if action == 'set_temperature':
            target_temp = data.get('target_temperature')
            unit = data.get('unit', 'C')
            if target_temp is None:
                return jsonify({
                    'success': False,
                    'error': 'target_temperature 파라미터가 필요합니다.'
                }), 400
            result = set_temperature(target_temp=float(target_temp), unit=unit)
            
        elif action == 'set_mode':
            mode = data.get('mode')
            if not mode:
                return jsonify({
                    'success': False,
                    'error': 'mode 파라미터가 필요합니다.'
                }), 400
            result = set_job_mode(mode=mode)
            
        elif action == 'set_wind_strength':
            strength = data.get('strength')
            if not strength:
                return jsonify({
                    'success': False,
                    'error': 'strength 파라미터가 필요합니다.'
                }), 400
            result = set_wind_strength(strength=strength)
            
        elif action == 'set_power':
            power_on = data.get('power_on', True)
            result = set_power(power_on=bool(power_on))
            
        else:
            return jsonify({
                'success': False,
                'error': f'지원하지 않는 action: {action}'
            }), 400
        
        logger.info(f"✅ 에어컨 제어 성공: {action}")
        
        # 액션별 메시지 생성
        messages = {
            'set_power': f"전원 {'켜기' if data.get('power_on', True) else '끄기'} 성공",
            'set_temperature': f"목표 온도 {data.get('target_temperature')}°C 설정 성공",
            'set_mode': f"모드 {data.get('mode')} 설정 성공",
            'set_wind_strength': f"풍량 {data.get('strength')} 설정 성공",
        }
        
        return jsonify({
            'success': True,
            'action': action,
            'message': messages.get(action, '제어 성공'),
            'result': result
        })
        
    except Exception as e:
        logger.error(f"에어컨 제어 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'에어컨 제어 실패: {str(e)}'
        }), 500

@app.route('/health_data/save', methods=['POST'])
def save_health_data():
    """iOS에서 받은 건강 데이터를 서버에 저장"""
    try:
        data = request.get_json()
        logger.info(f"📱 건강 데이터 저장 요청: {data}")
        
        global health_data_store
        
        # 데이터 저장
        if data.get('heartRate'):
            health_data_store['heartRate'] = data['heartRate']
        if data.get('hrv'):
            health_data_store['hrv'] = data['hrv']
        if data.get('oxygenSaturation'):
            health_data_store['oxygenSaturation'] = data['oxygenSaturation']
        
        health_data_store['lastUpdated'] = pd.Timestamp.now().isoformat()
        
        logger.info(f"✅ 건강 데이터 저장 완료: {health_data_store}")
        
        return jsonify({
            'success': True,
            'message': '건강 데이터 저장 성공',
            'data': health_data_store
        })
        
    except Exception as e:
        logger.error(f"건강 데이터 저장 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'건강 데이터 저장 실패: {str(e)}'
        }), 500

@app.route('/health_data/latest', methods=['GET'])
def get_latest_health_data():
    """서버에 저장된 최신 건강 데이터 조회 (안드로이드에서 호출)"""
    try:
        global health_data_store
        
        logger.info(f"📱 건강 데이터 조회 요청")
        logger.info(f"📊 저장된 데이터: {health_data_store}")
        
        # 데이터가 없으면 빈 응답
        if not health_data_store.get('heartRate') and not health_data_store.get('hrv') and not health_data_store.get('oxygenSaturation'):
            return jsonify({
                'success': True,
                'data': {},
                'message': '저장된 건강 데이터가 없습니다.'
            })
        
        return jsonify({
            'success': True,
            'data': {
                'heartRate': health_data_store.get('heartRate'),
                'hrv': health_data_store.get('hrv'),
                'oxygenSaturation': health_data_store.get('oxygenSaturation'),
            },
            'lastUpdated': health_data_store.get('lastUpdated')
        })
        
    except Exception as e:
        logger.error(f"건강 데이터 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'건강 데이터 조회 실패: {str(e)}'
        }), 500

if __name__ == '__main__':
    # 서버 시작 시 모델 로드
    if load_model():
        logger.info("서버 시작 중...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        logger.error("모델 로드 실패로 서버를 시작할 수 없습니다.")
