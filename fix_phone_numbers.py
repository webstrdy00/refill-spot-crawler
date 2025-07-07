#!/usr/bin/env python3
"""
크롤링 DB에서 07-****-**** 형태의 전화번호를 0507-****-****로 수정하는 스크립트
"""
import psycopg2
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def fix_phone_numbers(dry_run=True):
    """
    07-****-**** 형태의 전화번호를 0507-****-****로 수정
    
    Args:
        dry_run (bool): True면 실제 수정하지 않고 미리보기만, False면 실제 수정
    """
    print("📞 전화번호 수정 스크립트")
    print("=" * 50)
    
    # 크롤링 DB 연결
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:12345@localhost:5432/refill_spot_crawler')
    parsed = urlparse(db_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password
    )
    
    cursor = conn.cursor()
    
    try:
        # 1. 수정 대상 확인
        print("🔍 수정 대상 확인 중...")
        cursor.execute("""
            SELECT id, name, phone_number 
            FROM stores 
            WHERE phone_number LIKE '07-%'
            ORDER BY name
        """)
        
        stores_to_fix = cursor.fetchall()
        print(f"📊 수정 대상: {len(stores_to_fix)}개 가게")
        
        if len(stores_to_fix) == 0:
            print("✅ 수정할 전화번호가 없습니다.")
            return
        
        # 2. 샘플 미리보기
        print("\n📋 수정 미리보기 (처음 10개):")
        print("-" * 60)
        for i, (store_id, name, phone) in enumerate(stores_to_fix[:10], 1):
            new_phone = phone.replace('07-', '0507-', 1)  # 첫 번째 07-만 교체
            print(f"{i:2d}. {name}")
            print(f"    변경 전: {phone}")
            print(f"    변경 후: {new_phone}")
            print()
        
        if len(stores_to_fix) > 10:
            print(f"... 외 {len(stores_to_fix) - 10}개 더")
        
        # 3. 실제 수정 또는 드라이런
        if dry_run:
            print("\n🔍 DRY RUN 모드 - 실제로 수정하지 않습니다.")
            print("실제 수정하려면 --execute 옵션을 사용하세요.")
        else:
            print(f"\n🔧 실제 수정을 시작합니다... ({len(stores_to_fix)}개)")
            
            success_count = 0
            for store_id, name, phone in stores_to_fix:
                try:
                    new_phone = phone.replace('07-', '0507-', 1)
                    
                    cursor.execute("""
                        UPDATE stores 
                        SET phone_number = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (new_phone, store_id))
                    
                    success_count += 1
                    if success_count % 50 == 0:  # 50개마다 진행상황 출력
                        print(f"  진행: {success_count}/{len(stores_to_fix)}개 완료")
                        
                except Exception as e:
                    print(f"❌ 수정 실패 ({name}): {e}")
                    continue
            
            # 커밋
            conn.commit()
            print(f"\n✅ 수정 완료: {success_count}/{len(stores_to_fix)}개 성공")
            
            # 4. 결과 확인
            print("\n🔍 수정 결과 확인...")
            cursor.execute("""
                SELECT COUNT(*) 
                FROM stores 
                WHERE phone_number LIKE '07-%'
            """)
            remaining = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM stores 
                WHERE phone_number LIKE '0507-%'
            """)
            fixed_count = cursor.fetchone()[0]
            
            print(f"📊 남은 07- 전화번호: {remaining}개")
            print(f"📊 0507- 전화번호: {fixed_count}개")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()
        conn.close()

def validate_phone_format():
    """전화번호 형식 검증"""
    print("\n🔍 전화번호 형식 검증")
    print("=" * 30)
    
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:12345@localhost:5432/refill_spot_crawler')
    parsed = urlparse(db_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password
    )
    
    cursor = conn.cursor()
    
    try:
        # 다양한 전화번호 패턴 확인
        patterns = [
            ("07-로 시작", "phone_number LIKE '07-%'"),
            ("0507-로 시작", "phone_number LIKE '0507-%'"),
            ("02-로 시작", "phone_number LIKE '02-%'"),
            ("031-로 시작", "phone_number LIKE '031-%'"),
            ("기타 패턴", "phone_number NOT LIKE '07-%' AND phone_number NOT LIKE '0507-%' AND phone_number NOT LIKE '02-%' AND phone_number NOT LIKE '031-%' AND phone_number IS NOT NULL")
        ]
        
        for pattern_name, condition in patterns:
            cursor.execute(f"SELECT COUNT(*) FROM stores WHERE {condition}")
            count = cursor.fetchone()[0]
            print(f"{pattern_name}: {count}개")
            
            # 샘플 보기
            if count > 0 and count <= 5:
                cursor.execute(f"SELECT name, phone_number FROM stores WHERE {condition} LIMIT 5")
                samples = cursor.fetchall()
                for name, phone in samples:
                    print(f"  - {name}: {phone}")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='전화번호 수정 스크립트')
    parser.add_argument('--execute', action='store_true', help='실제로 수정 실행 (기본값: dry-run)')
    parser.add_argument('--validate', action='store_true', help='전화번호 형식 검증만 실행')
    
    args = parser.parse_args()
    
    if args.validate:
        validate_phone_format()
    else:
        fix_phone_numbers(dry_run=not args.execute) 