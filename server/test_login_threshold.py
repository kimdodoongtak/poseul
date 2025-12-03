#!/usr/bin/env python3
"""
로그인 후 new_skinthreshold 테이블에 기본값이 저장되었는지 확인하는 테스트 스크립트
"""
from sqlalchemy import create_engine, text

DB_URL = 'mysql+pymysql://iriskimhs:dyvVyn-kihxe0-parxes@aiservice.cd0you2cyo60.ap-northeast-2.rds.amazonaws.com:3306/main'

def check_new_skinthreshold():
    """new_skinthreshold 테이블 상태 확인"""
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # new_skinthreshold 테이블 확인
            result = conn.execute(text('''
                SELECT user_no, min_skinthreshold, max_skinthreshold, no 
                FROM new_skinthreshold 
                ORDER BY no DESC 
                LIMIT 10
            '''))
            rows = result.fetchall()
            
            print('=' * 60)
            print('new_skinthreshold 테이블 상태')
            print('=' * 60)
            if rows:
                for row in rows:
                    print(f'no={row.no}, user_no={row.user_no}, min={row.min_skinthreshold}, max={row.max_skinthreshold}')
            else:
                print('레코드 없음 (아직 로그인하지 않았거나 저장되지 않음)')
            print()
            
            # login 테이블에서 사용자 확인
            result2 = conn.execute(text('SELECT no, id FROM login ORDER BY no DESC LIMIT 5'))
            rows2 = result2.fetchall()
            print('=' * 60)
            print('login 테이블 사용자 목록')
            print('=' * 60)
            for row in rows2:
                print(f'no={row.no}, id={row.id}')
            
    except Exception as e:
        print(f'오류: {e}')

if __name__ == '__main__':
    check_new_skinthreshold()




