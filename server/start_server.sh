#!/bin/bash

# 서버 디렉토리로 이동
cd "$(dirname "$0")"

# Python 가상환경 활성화 (있는 경우)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 서버 실행
python3 server.py

