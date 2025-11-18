import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score, classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support, mean_absolute_percentage_error, max_error
from sklearn.model_selection import cross_val_score
import joblib
import pickle
import warnings
import time
warnings.filterwarnings('ignore')

print("🚀 AI 서비스용 체온 예측 모델 학습 (나이 피처 포함, GradientBoosting)")
print("=" * 60)

# 전체 실행 시간 측정 시작
start_time = time.time()

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

# 2️⃣ 필수 피처 정의 (나이 포함)
print("\n🎯 필수 피처 정의 (나이 포함)")

# 필수 피처 정의
essential_features = ['bmi', 'mean_sa02', 'HRV_SDNN', 'HR_mean', 'age']
cat_features = ['gender']

# 파생 피처 계산
df['hrv_hr_ratio'] = df['HRV_SDNN'] / df['HR_mean']
df['bmi_hr_interaction'] = df['bmi'] * df['HR_mean']
df['age_bmi_interaction'] = df['age'] * df['bmi']
df['age_hrv_ratio'] = df['age'] / (df['HRV_SDNN'] + 1)

# 최종 필수 피처 정의
final_features = ['bmi', 'mean_sa02', 'HRV_SDNN', 'hrv_hr_ratio', 'bmi_hr_interaction', 'age', 'age_bmi_interaction', 'age_hrv_ratio']
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
transformers = []
if final_features:
    transformers.append(("num", StandardScaler(), final_features))
if cat_features:
    transformers.append(("cat", OneHotEncoder(drop='first', handle_unknown='ignore'), cat_features))

if not transformers:
    print("❌ 사용할 수 있는 특성이 없습니다!")
    exit(1)

preprocessor = ColumnTransformer(transformers=transformers)

# 5️⃣ 모델 구성
print("\n🔧 GradientBoosting 모델 구성 중...")

# GradientBoosting 파이프라인
model = Pipeline([
    ("preprocess", preprocessor),
    ("model", GradientBoostingRegressor(
        n_estimators=1000, 
        learning_rate=0.01, 
        max_depth=6, 
        subsample=0.9, 
        random_state=42
    ))
])

# 온도 분류 함수 정의 (모델 평가 전에 정의)
def classify_temperature(temp, cold_threshold=33.0, hot_threshold=35.0):
    if temp < cold_threshold:
        return "냉기"
    elif temp > hot_threshold:
        return "더위"
    else:
        return "적정"

# 6️⃣ 모델 학습 및 성능 평가
print("\n🔍 GradientBoosting 모델 학습 및 평가 중...")
print("=" * 60)

# 모델 학습 시간 측정
train_start = time.time()
model.fit(X_train, y_train)
train_time = time.time() - train_start

# 전체 검증 세트 예측
y_pred = model.predict(X_valid)

# 단일 샘플 예측 시간 측정 (여러 번 반복하여 평균 계산)
single_pred_times = []
sample_idx = 0  # 첫 번째 샘플 사용
sample_data = X_valid.iloc[[sample_idx]]

# 워밍업 (첫 예측은 보통 느림)
_ = model.predict(sample_data)

# 100번 반복하여 평균 계산
for _ in range(100):
    single_pred_start = time.time()
    _ = model.predict(sample_data)
    single_pred_times.append(time.time() - single_pred_start)

single_pred_time = np.mean(single_pred_times) * 1000  # 밀리초로 변환

# 회귀 성능 지표 계산
r2 = r2_score(y_valid, y_pred)
mse = mean_squared_error(y_valid, y_pred)
rmse = np.sqrt(mse)
mae = np.mean(np.abs(y_valid - y_pred))

# 추가 회귀 지표
try:
    mape = mean_absolute_percentage_error(y_valid, y_pred) * 100
except:
    mape = np.nan

max_err = max_error(y_valid, y_pred)
median_ae = np.median(np.abs(y_valid - y_pred))

# 교차 검증
cv_start = time.time()
cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
cv_time = time.time() - cv_start
cv_r2_mean = cv_scores.mean()
cv_r2_std = cv_scores.std() * 2

# 분류 성능 평가
y_valid_class = [classify_temperature(temp) for temp in y_valid]
y_pred_class = [classify_temperature(temp) for temp in y_pred]

accuracy = accuracy_score(y_valid_class, y_pred_class)
precision, recall, f1, support = precision_recall_fscore_support(
    y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"], zero_division=0
)
precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
    y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"], average='weighted', zero_division=0
)

# 회귀 성능 지표 출력
print(f"\n⏱️  실행 시간:")
print(f"  학습 시간: {train_time:.2f}초")
print(f"  단일 샘플 예측 시간: {single_pred_time:.4f}ms (평균, 100회 반복)")
print(f"  교차 검증 시간: {cv_time:.2f}초")

print(f"\n📈 회귀 성능 지표:")
print(f"  R² Score: {r2:.4f}")
print(f"  MSE: {mse:.4f}")
print(f"  RMSE: {rmse:.4f}°C")
print(f"  MAE: {mae:.4f}°C")
if not np.isnan(mape):
    print(f"  MAPE: {mape:.2f}%")
print(f"  Median AE: {median_ae:.4f}°C")
print(f"  Max Error: {max_err:.4f}°C")
print(f"  CV R²: {cv_r2_mean:.4f} (+/- {cv_r2_std:.4f})")

# 분류 성능 지표 출력
print(f"\n🎯 분류 성능 지표:")
print(f"  Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
print(f"  Weighted Precision: {precision_weighted:.4f}")
print(f"  Weighted Recall: {recall_weighted:.4f}")
print(f"  Weighted F1-Score: {f1_weighted:.4f}")
print(f"  Macro F1-Score: {f1.mean():.4f}")

# 클래스별 성능
print(f"\n📊 클래스별 성능:")
print(f"  {'클래스':<10} {'Precision':<12} {'Recall':<12} {'F1-Score':<12} {'Support':<10}")
print(f"  {'-'*60}")
for i, label in enumerate(["냉기", "적정", "더위"]):
    print(f"  {label:<10} {precision[i]:<12.4f} {recall[i]:<12.4f} {f1[i]:<12.4f} {support[i]:<10}")

# 혼동 행렬
cm = confusion_matrix(y_valid_class, y_pred_class, labels=["냉기", "적정", "더위"])
print(f"\n📋 혼동 행렬:")
print(f"        예측")
print(f"실제   {'냉기':<8} {'적정':<8} {'더위':<8}")
for i, label in enumerate(["냉기", "적정", "더위"]):
    print(f"{label:4} {cm[i]}")

# 7️⃣ 모델 저장
model_path = '/Users/Iris/인공지능서비스개발2/model/ai_thermal_model_with_age_single.pkl'
joblib.dump(model, model_path)
print(f"\n✅ GradientBoosting 모델 저장 완료: {model_path}")

# 8️⃣ 예측 함수 정의 및 저장
def create_predict_function(trained_model):
    """
    예측 함수 생성 (모델을 클로저로 포함)
    """
    def predict_temperature_with_age(hr_mean, hrv_sdnn, bmi, mean_sa02, gender, age):
        """
        체온 예측 함수 (나이 포함, GradientBoosting 모델 사용)
        
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
        
        # 예측 (GradientBoosting 모델 사용)
        temp_pred = trained_model.predict(data)[0]
        return temp_pred
    
    return predict_temperature_with_age

predict_temperature_with_age = create_predict_function(model)

# 예측 함수 저장
predict_function_path = '/Users/Iris/인공지능서비스개발2/model/predict_function_with_age_single.pkl'
with open(predict_function_path, 'wb') as f:
    pickle.dump(predict_temperature_with_age, f)
print(f"✅ 예측 함수 저장 완료: {predict_function_path}")

# 9️⃣ 나이별 성능 분석
print("\n" + "=" * 60)
print("📊 나이별 성능 분석")
print("=" * 60)

df_valid_with_age = df.loc[valid_indices].copy()
df_valid_with_age['pred_temp'] = y_pred
df_valid_with_age['temp_error'] = abs(df_valid_with_age['TEMP_median'] - df_valid_with_age['pred_temp'])

df_valid_with_age['age_group'] = pd.cut(df_valid_with_age['age'], 
                                       bins=[0, 30, 50, 70, 100], 
                                       labels=['청년(30세미만)', '중년(30-50세)', '장년(50-70세)', '노년(70세이상)'])

age_performance = df_valid_with_age.groupby('age_group').agg({
    'temp_error': ['mean', 'std', 'count'],
    'TEMP_median': ['mean', 'std'],
    'pred_temp': ['mean', 'std']
}).round(3)

print("\n📊 나이 그룹별 성능:")
print(age_performance)

# 🔟 최종 요약
total_execution_time = time.time() - start_time

print("\n" + "=" * 80)
print("AI 서비스 모델 학습 완료 (나이 피처 포함, GradientBoosting)")
print("=" * 80)
print(f"📊 모델 정보: GradientBoosting, 피처 {len(final_features)}개, R² {r2:.4f}, RMSE {rmse:.4f}°C")
print(f"⏱️  전체 실행 시간: {total_execution_time:.2f}초 ({total_execution_time/60:.2f}분)")
print(f"⚡ 단일 샘플 예측 시간: {single_pred_time:.4f}ms")
print(f"🔥 주요 특징: GradientBoosting 모델, 나이별 맞춤형 예측, 실시간 최적화")
print(f"📁 저장 파일: ai_thermal_model_with_age_single.pkl, predict_function_with_age_single.pkl")
print("🏆 AI 서비스용 체온 예측 모델 완성! 🎉")

