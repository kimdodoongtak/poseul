import pandas as pd
from sqlalchemy import text
from model_utils import prepare_batch_features_for_prediction, get_db_engine, load_model, predict_with_model, MODEL_FILE

# DB 연결 (공통 함수 사용)
engine = get_db_engine()

# 테이블 목록 확인
tables = pd.read_sql('SHOW TABLES', engine)
print("데이터베이스의 테이블 목록:")
print(tables)

# 테이블 불러오기 (predicted_results 테이블 사용)
df = pd.read_sql('SELECT * FROM predicted_results', engine)
print("\npredicted_results 테이블 전체 데이터:")
print(df.head())
print(f"\n전체 데이터 형태: {df.shape}")

# 예측이 필요한 데이터만 필터링 (predicted_skin_temp가 NULL이거나 NaN이거나 0인 경우)
# 0.0도 예측이 실패한 것으로 간주하고 다시 예측
df_to_predict = df[(df['predicted_skin_temp'].isna()) | (df['predicted_skin_temp'] == 0.0)].copy()
print(f"\n예측 필요한 데이터: {len(df_to_predict)}개 (NULL 또는 0.0인 데이터)")

# 데이터가 있는지 확인
if len(df_to_predict) == 0:
    print("예측할 데이터가 없습니다. 모든 데이터에 예측 값이 이미 존재합니다.")
else:
    print("\n예측 대상 데이터:")
    print(df_to_predict[['no', 'HR_mean', 'HRV_SDNN', 'gender', 'bmi', 'age', 'mean_sa02']])
    
    # 공통 함수를 사용하여 배치 피처 준비
    X = prepare_batch_features_for_prediction(df_to_predict)
    
    print("\n생성된 피처들:")
    print(X.columns.tolist())
    print(f"피처 데이터 형태: {X.shape}")
    print(f"피처 데이터 타입:")
    print(X.dtypes)
    print(f"\n피처 데이터 샘플:")
    print(X.head())
    
    # 모델 로드 (공통 함수 사용)
    model = load_model(MODEL_FILE)
    
    if model is None:
        print(f"경고: {MODEL_FILE} 파일을 찾을 수 없거나 로드할 수 없습니다.")
        print("모델 파일을 현재 디렉토리에 추가해주세요.")
        exit()
    
    # 예측 실행 (공통 함수 사용)
    preds = predict_with_model(model, X)
    
    print(f"\n예측 결과: {preds}")
    
    # 각 레코드별로 UPDATE 실행 (중복 방지)
    with engine.connect() as conn:
        for i, (idx, row) in enumerate(df_to_predict.iterrows()):
            update_query = text("""
                UPDATE predicted_results 
                SET predicted_skin_temp = :pred_temp 
                WHERE no = :no
            """)
            conn.execute(update_query, {'pred_temp': float(preds[i]), 'no': int(row['no'])})
        conn.commit()
    
    print(f"\n예측 완료! {len(df_to_predict)}개의 레코드가 predicted_results 테이블에 업데이트되었습니다.")

