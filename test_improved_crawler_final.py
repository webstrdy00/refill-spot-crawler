"""
개선된 크롤러 최종 테스트
- 주소 추출 개선
- 요일별 영업시간 추출
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.crawler import DiningCodeCrawler
from src.core.database import DatabaseManager
import time
import json

def test_improved_crawler():
    """개선된 크롤러 테스트"""
    print("=== 개선된 크롤러 테스트 시작 ===")
    
    # 데이터베이스 초기화
    db = DatabaseManager()
    
    # 기존 데이터 삭제
    print("\n1. 기존 데이터 삭제 중...")
    try:
        cursor = db.pg_conn.cursor()
        cursor.execute("DELETE FROM stores")
        db.pg_conn.commit()
        cursor.close()
        print("기존 데이터 삭제 완료")
    except Exception as e:
        print(f"데이터 삭제 중 오류: {e}")
    
    # 크롤러 초기화
    crawler = DiningCodeCrawler()
    
    # 테스트할 가게 URL들 (다양한 형태의 가게)
    test_stores = [
        {"diningcode_place_id": "TjHHaWq8Ylqt", "name": "우래옥 본점"},  # 평양냉면
        {"diningcode_place_id": "yJWYroWneBZz", "name": "농민백암순대 본점"},  # 순대국밥
        {"diningcode_place_id": "wJpwvXzEFYVj", "name": "오레노라멘 본점"},  # 라멘
    ]
    
    results = []
    
    print("\n2. 개별 가게 크롤링 시작...")
    for i, store in enumerate(test_stores, 1):
        print(f"\n가게 {i} 크롤링: {store['diningcode_place_id']}")
        try:
            data = crawler._extract_store_detail(store)
            if data:
                results.append(data)
                print(f"✓ 수집 성공")
                print(f"  - 이름: {data.get('name', 'N/A')}")
                print(f"  - 주소: {data.get('address', 'N/A')}")
                print(f"  - 영업시간: {data.get('open_hours', 'N/A')}")
                print(f"  - 휴무일: {data.get('holiday', 'N/A')}")
                
                # 데이터베이스에 저장
                db.insert_stores_batch([data])
                print(f"  - DB 저장 완료")
            else:
                print(f"✗ 수집 실패")
        except Exception as e:
            print(f"✗ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(2)  # 요청 간격
    
    # 크롤러 종료
    crawler.close()
    
    # 결과 저장
    with open('test_improved_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n3. 크롤링 완료: {len(results)}개 가게 수집")
    
    # 데이터베이스에서 확인
    print("\n4. 데이터베이스 확인...")
    try:
        cursor = db.pg_conn.cursor()
        
        # 전체 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores")
        total = cursor.fetchone()[0]
        print(f"총 가게 수: {total}")
        
        # 주소가 있는 가게
        cursor.execute("SELECT COUNT(*) FROM stores WHERE address IS NOT NULL AND address != ''")
        with_address = cursor.fetchone()[0]
        print(f"주소 있는 가게: {with_address} ({with_address/total*100:.1f}%)")
        
        # 요일별 영업시간이 있는 가게
        cursor.execute("""
            SELECT COUNT(*) FROM stores 
            WHERE open_hours IS NOT NULL 
            AND open_hours != ''
            AND (open_hours LIKE '%월요일%' OR open_hours LIKE '%화요일%' 
                 OR open_hours LIKE '%수요일%' OR open_hours LIKE '%목요일%'
                 OR open_hours LIKE '%금요일%' OR open_hours LIKE '%토요일%'
                 OR open_hours LIKE '%일요일%')
        """)
        with_weekday_hours = cursor.fetchone()[0]
        print(f"요일별 영업시간 있는 가게: {with_weekday_hours} ({with_weekday_hours/total*100:.1f}%)")
        
        # 상세 데이터 출력
        print("\n5. 수집된 데이터 상세:")
        cursor.execute("""
            SELECT name, address, open_hours, holiday 
            FROM stores 
            ORDER BY created_at DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"\n가게명: {row[0]}")
            print(f"주소: {row[1]}")
            print(f"영업시간: {row[2][:100]}..." if row[2] and len(row[2]) > 100 else f"영업시간: {row[2]}")
            print(f"휴무일: {row[3]}")
        
        cursor.close()
        
    except Exception as e:
        print(f"데이터베이스 확인 중 오류: {e}")
    
    db.close()
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_improved_crawler() 