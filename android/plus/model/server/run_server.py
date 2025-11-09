#!/usr/bin/env python3
"""
AI 체온 예측 서버 실행 스크립트
"""

import sys
import os
import subprocess

def install_requirements():
    """필요한 패키지 설치"""
    print("📦 필요한 패키지를 설치합니다...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 패키지 설치 완료")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 패키지 설치 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 AI 체온 예측 서버를 시작합니다...")
    print("=" * 50)
    
    # 현재 디렉토리를 server 폴더로 변경
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 패키지 설치
    if not install_requirements():
        return
    
    # 서버 실행
    print("\n🌐 서버를 시작합니다...")
    print("서버 주소: http://localhost:5000")
    print("API 문서:")
    print("  - GET  /health      : 서버 상태 확인")
    print("  - POST /predict     : 체온 예측")
    print("  - GET  /model_info  : 모델 정보")
    print("\n종료하려면 Ctrl+C를 누르세요.")
    print("=" * 50)
    
    try:
        from app import app, load_model
        if load_model():
            app.run(host='0.0.0.0', port=5000, debug=True)
        else:
            print("❌ 모델 로드 실패로 서버를 시작할 수 없습니다.")
    except KeyboardInterrupt:
        print("\n👋 서버를 종료합니다.")
    except Exception as e:
        print(f"❌ 서버 실행 실패: {e}")

if __name__ == "__main__":
    main()
