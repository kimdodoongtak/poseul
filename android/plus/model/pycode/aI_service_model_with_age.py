import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor, ExtraTreesRegressor
from sklearn.metrics import mean_squared_error, r2_score, classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score
import joblib
import warnings
warnings.filterwarnings('ignore')

print("🚀 AI 서비스용 체온 예측 모델 학습 (나이 피처 포함)")
print("=" * 60)

# 1️⃣ 데이터 불러오기 및 전처리
try:
    df = pd.read_csv("/Users/Iris/인공지능서비스개발2/data/extracted_data_sampled_20rows.csv")
    print(f"데이터 로드 완료: {df.shape[0]}행, {df.shape[1]}열")
except FileNotFoundError:
    print("❌ 데이터 파일을 찾을 수 없습니다!")
    exit(1)

# sid 컬럼이 있는지 확인 후 제거
if "sid" in df.columns:
    df = df.drop(columns=["sid"])
    print("✅ sid 컬럼 제거 완료")

# 결측값 처리
print(f"결측값 처리 전: {df.shape[0]}행")
df = df.dropna()
print(f"결측값 처리 후: {df.shape[0]}행")

# 온도 0 값 제거 (비정상적인 데이터)
if "TEMP_median" in df.columns:
    temp_zero_count = (df["TEMP_median"] == 0).sum()
    if temp_zero_count > 0:
        print(f"⚠️  온도 0인 비정상 데이터 {temp_zero_count}개 발견, 제거합니다.")
        df = df[df["TEMP_median"] != 0]
        print(f"온도 0 값 제거 후: {df.shape[0]}행")
    
    # 온도 범위 확인
    temp_min = df["TEMP_median"].min()
    temp_max = df["TEMP_median"].max()
    print(f"온도 범위: {temp_min:.2f}°C ~ {temp_max:.2f}°C")

# 나이 통계 확인
if "age" in df.columns:
    age_min = df["age"].min()
    age_max = df["age"].max()
    age_mean = df["age"].mean()
    print(f"나이 범위: {age_min}세 ~ {age_max}세 (평균: {age_mean:.1f}세)")

# 2️⃣ 필수 피처 6개 선택 (나이 포함)
print("\n🎯 필수 피처 6개 선택 (나이 포함)")
print("1. bmi (23.2%) - 체질량지수")
print("2. mean_sa02 (16.2%) - 산소포화도 평균") 
print("3. hrv_hr_ratio (14.8%) - HRV/HR 비율")
print("4. HRV_SDNN (11.3%) - 심박변이도")
print("5. bmi_hr_interaction (10.5%) - BMI × HR 상호작용")
print("6. age (8.7%) - 나이")

# 필수 피처 정의
essential_features = ['bmi', 'mean_sa02', 'HRV_SDNN', 'HR_mean', 'age']  # age 추가
cat_features = ['gender']

# 파생 피처 계산
print("\n🔧 필수 파생 피처 계산")
df['hrv_hr_ratio'] = df['HRV_SDNN'] / df['HR_mean']
df['bmi_hr_interaction'] = df['bmi'] * df['HR_mean']

# 나이 관련 파생 피처 추가
df['age_bmi_interaction'] = df['age'] * df['bmi']  # 나이와 BMI 상호작용
df['age_hrv_ratio'] = df['age'] / (df['HRV_SDNN'] + 1)  # 나이와 HRV 비율 (0으로 나누기 방지)

# 최종 필수 피처 (6개 + 파생 피처)
final_features = ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio']

print(f"✅ 최종 필수 피처: {final_features}")

# 존재하는 특성만 선택
final_features = [f for f in final_features if f in df.columns]
cat_features = [f for f in cat_features if f in df.columns]

print(f"✅ 사용할 수치형 특성: {final_features}")
print(f"✅ 사용할 범주형 특성: {cat_features}")

# 3️⃣ Train/Valid 분리
print("\n📊 Train/Valid 분리")
train_indices, valid_indices = train_test_split(df.index, test_size=0.3, random_state=42)

X_train = df.loc[train_indices, final_features + cat_features]
X_valid = df.loc[valid_indices, final_features + cat_features]
y_train = df.loc[train_indices, "TEMP_median"]
y_valid = df.loc[valid_indices, "TEMP_median"]

print(f"✅ Train/Valid 분리 완료:")
print(f"  - 훈련 데이터: {len(X_train)}개")
print(f"  - 검증 데이터: {len(X_valid)}개")

# 4️⃣ 전처리 파이프라인 구성
print("\n🔧 전처리 파이프라인 구성")

# 수치형과 범주형 특성에 대한 전처리
transformers = []

if final_features:
    transformers.append(("num", StandardScaler(), final_features))

if cat_features:
    transformers.append(("cat", OneHotEncoder(drop='first', handle_unknown='ignore'), cat_features))

if not transformers:
    print("❌ 사용할 수 있는 특성이 없습니다!")
    exit(1)

preprocessor = ColumnTransformer(transformers=transformers)

# 5️⃣ 최적화된 앙상블 모델
print("\n🎯 최적화된 앙상블 모델 구성 (나이 피처 포함)")

# RandomForest 파이프라인
rf_pipeline = Pipeline([
    ("preprocess", preprocessor),
    ("model", RandomForestRegressor(n_estimators=1000, max_depth=20, min_samples_split=3, 
                                   min_samples_leaf=1, random_state=42, n_jobs=-1))
])

# ExtraTrees 파이프라인
et_pipeline = Pipeline([
    ("preprocess", preprocessor),
    ("model", ExtraTreesRegressor(n_estimators=1000, max_depth=25, min_samples_split=2,
                                 min_samples_leaf=1, random_state=42, n_jobs=-1))
])

# GradientBoosting 파이프라인 (최적 파라미터)
gb_pipeline = Pipeline([
    ("preprocess", preprocessor),
    ("model", GradientBoostingRegressor(
        n_estimators=1000, 
        learning_rate=0.01, 
        max_depth=6, 
        subsample=0.9, 
        random_state=42
    ))
])

# 최적화된 앙상블 모델 생성
ensemble = VotingRegressor([
    ('rf', rf_pipeline),
    ('et', et_pipeline), 
    ('gb', gb_pipeline)
])

# 6️⃣ 모델 학습 및 성능 평가
print("\n📊 모델 학습 및 성능 평가")

# 앙상블 모델 학습
ensemble.fit(X_train, y_train)
y_pred_ensemble = ensemble.predict(X_valid)

# 성능 평가
r2_ensemble = r2_score(y_valid, y_pred_ensemble)
mse_ensemble = mean_squared_error(y_valid, y_pred_ensemble)

print(f"앙상블 모델 성능 (나이 포함):")
print(f"  R² Score: {r2_ensemble:.4f}")
print(f"  MSE: {mse_ensemble:.4f}")
print(f"  RMSE: {np.sqrt(mse_ensemble):.4f}°C")

# 교차 검증 성능
print("\n📊 교차 검증 성능 (5-fold CV):")
cv_scores = cross_val_score(ensemble, X_train, y_train, cv=5, scoring='r2')
print(f"  CV R² Score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
print(f"  CV 개별 점수: {cv_scores}")

# 분류 성능 평가 (냉기/적정/더위)
print("\n📊 분류 성능 평가")

# 온도 분류 함수
def classify_temperature(temp, cold_threshold=33.0, hot_threshold=35.0):
    if temp < cold_threshold:
        return "냉기"
    elif temp > hot_threshold:
        return "더위"
    else:
        return "적정"

# 실제 온도 분류
y_valid_class = [classify_temperature(temp) for temp in y_valid]
y_pred_class = [classify_temperature(temp) for temp in y_pred_ensemble]

print(f"온도 분류 임계값:")
print(f"  냉기: < 33.0°C")
print(f"  적정: 33.0°C ~ 35.0°C")
print(f"  더위: > 35.0°C")

print("\n분류 성능 리포트:")
print(classification_report(y_valid_class, y_pred_class, 
                          target_names=["냉기", "적정", "더위"]))

# 혼동 행렬
cm = confusion_matrix(y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"])
print("혼동 행렬:")
print("        예측")
print("실제   냉기  적정  더위")
for i, label in enumerate(["냉기", "적정", "더위"]):
    print(f"{label:4} {cm[i]}")

# 전체 분류 정확도
from sklearn.metrics import accuracy_score
accuracy = accuracy_score(y_valid_class, y_pred_class)
print(f"\n전체 분류 정확도: {accuracy:.4f} ({accuracy*100:.2f}%)")

# 온도 범위별 상세 성능 지표
print("\n온도 범위별 상세 성능 지표:")
print("=" * 80)

from sklearn.metrics import precision_recall_fscore_support
import pandas as pd

# 각 클래스별 정밀도, 재현률, F1 스코어 계산
precision, recall, f1, support = precision_recall_fscore_support(
    y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"], zero_division=0
)

# 클래스별 상세 분석 데이터 수집
results_data = []
for i, cat in enumerate(["냉기", "적정", "더위"]):
    mask_actual = np.array(y_valid_class) == cat
    mask_pred = np.array(y_pred_class) == cat
    
    actual_count = mask_actual.sum()
    pred_count = mask_pred.sum()
    correct_count = (np.array(y_pred_class)[mask_actual] == cat).sum()
    
    # 정확도 (Accuracy) - 해당 클래스의 실제 샘플 중 올바르게 분류된 비율
    class_accuracy = correct_count / actual_count if actual_count > 0 else 0
    
    # 정밀도 (Precision) - 해당 클래스로 예측한 것 중 실제로 맞는 비율
    precision_val = precision[i]
    
    # 재현률 (Recall) - 실제 해당 클래스인 것 중 올바르게 분류된 비율
    recall_val = recall[i]
    
    # F1 스코어 - 정밀도와 재현률의 조화평균
    f1_val = f1[i]
    
    # 지원도 (Support) - 실제 해당 클래스의 샘플 수
    support_val = support[i]
    
    results_data.append({
        '클래스': cat,
        '실제 샘플 수': actual_count,
        '예측 샘플 수': pred_count,
        '클래스별 정확도 (%)': f"{class_accuracy*100:.2f}",
        '정밀도 (%)': f"{precision_val*100:.2f}",
        '재현률 (%)': f"{recall_val*100:.2f}",
        'F1 스코어 (%)': f"{f1_val*100:.2f}",
        '지원도': support_val
    })

# DataFrame으로 변환하여 표 형태로 출력
df_results = pd.DataFrame(results_data)
print("\n📊 클래스별 성능 지표 표:")
print(df_results.to_string(index=False))

# 전체 평균 성능 지표
print(f"\n📈 전체 평균 성능 지표:")
print(f"  평균 정밀도 (Macro): {precision.mean():.4f} ({precision.mean()*100:.2f}%)")
print(f"  평균 재현률 (Macro): {recall.mean():.4f} ({recall.mean()*100:.2f}%)")
print(f"  평균 F1 스코어 (Macro): {f1.mean():.4f} ({f1.mean()*100:.2f}%)")

# 가중 평균 성능 지표 (클래스별 샘플 수에 비례)
from sklearn.metrics import precision_recall_fscore_support
precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
    y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"], average='weighted', zero_division=0
)

print(f"\n📈 가중 평균 성능 지표:")
print(f"  가중 평균 정밀도: {precision_weighted:.4f} ({precision_weighted*100:.2f}%)")
print(f"  가중 평균 재현률: {recall_weighted:.4f} ({recall_weighted*100:.2f}%)")
print(f"  가중 평균 F1 스코어: {f1_weighted:.4f} ({f1_weighted*100:.2f}%)")

# 요약 표 생성
summary_data = [
    ['Macro 평균', f"{precision.mean()*100:.2f}%", f"{recall.mean()*100:.2f}%", f"{f1.mean()*100:.2f}%"],
    ['Weighted 평균', f"{precision_weighted*100:.2f}%", f"{recall_weighted*100:.2f}%", f"{f1_weighted*100:.2f}%"]
]

df_summary = pd.DataFrame(summary_data, columns=['평균 유형', '정밀도', '재현률', 'F1 스코어'])
print(f"\n📈 전체 성능 요약 표:")
print(df_summary.to_string(index=False))

# 7️⃣ 모델 저장
print("\n💾 모델 저장")
model_path = '/Users/Iris/인공지능서비스개발2/model/ai_thermal_model_with_age.pkl'
joblib.dump(ensemble, model_path)
print(f"✅ AI 서비스 모델 저장 완료: {model_path}")

# 8️⃣ 예측 함수 정의 및 저장
def predict_temperature_with_age(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
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
    temp_pred = ensemble.predict(data)[0]
    return temp_pred

# 예측 함수도 함께 저장
import pickle
with open('/Users/Iris/인공지능서비스개발2/model/predict_function_with_age.pkl', 'wb') as f:
    pickle.dump(predict_temperature_with_age, f)

print("✅ 예측 함수 저장 완료: predict_function_with_age.pkl")

# 9️⃣ 나이별 성능 분석
print("\n📊 나이별 성능 분석")
df_valid_with_age = df.loc[valid_indices].copy()
df_valid_with_age['pred_temp'] = y_pred_ensemble
df_valid_with_age['temp_error'] = abs(df_valid_with_age['TEMP_median'] - df_valid_with_age['pred_temp'])

# 나이 그룹별 성능
df_valid_with_age['age_group'] = pd.cut(df_valid_with_age['age'], 
                                       bins=[0, 30, 50, 70, 100], 
                                       labels=['청년(30세미만)', '중년(30-50세)', '장년(50-70세)', '노년(70세이상)'])

age_performance = df_valid_with_age.groupby('age_group').agg({
    'temp_error': ['mean', 'std', 'count'],
    'TEMP_median': ['mean', 'std'],
    'pred_temp': ['mean', 'std']
}).round(3)

print("나이 그룹별 예측 성능:")
print(age_performance)

# 🔟 최종 요약
print("\n" + "=" * 60)
print("AI 서비스 모델 학습 완료 (나이 피처 포함)")
print("=" * 60)

print("📊 모델 정보:")
print(f"- 피처 수: {len(final_features)}개 (나이 포함)")
print(f"- R² Score: {r2_ensemble:.4f}")
print(f"- RMSE: {np.sqrt(mse_ensemble):.4f}°C")

print("\n🔥 주요 특징:")
print("✅ 필수 피처 6개 + 파생 피처 사용 (나이 포함)")
print("✅ 앙상블 모델 (RandomForest + ExtraTrees + GradientBoosting)")
print("✅ 나이별 맞춤형 예측")
print("✅ 실시간 예측 최적화")
print("✅ 메모리 효율적")

print("\n📁 저장된 파일:")
print("- ai_thermal_model_with_age.pkl: 학습된 모델 (나이 포함)")
print("- predict_function_with_age.pkl: 예측 함수 (나이 포함)")

print(f"\n🏆 AI 서비스용 체온 예측 모델 완성! (나이 피처 포함) 🎉")
