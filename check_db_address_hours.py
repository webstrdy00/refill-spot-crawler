"""
데이터베이스에 저장된 주소와 영업시간 정보 확인
"""
import psycopg2
import psycopg2.extras
from config.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def check_address_hours():
    """주소와 영업시간 정보 확인"""
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 통계 쿼리
        print("=== 주소 및 영업시간 수집 통계 ===")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_stores,
                COUNT(CASE WHEN address IS NOT NULL AND address != '' THEN 1 END) as stores_with_address,
                COUNT(CASE WHEN open_hours IS NOT NULL AND open_hours != '' THEN 1 END) as stores_with_hours,
                COUNT(CASE WHEN holiday IS NOT NULL AND holiday != '' THEN 1 END) as stores_with_holiday,
                COUNT(CASE WHEN holiday LIKE '%요일%' THEN 1 END) as stores_with_weekday_holiday,
                COUNT(CASE WHEN open_hours LIKE '%요일%' THEN 1 END) as stores_with_weekday_hours
            FROM stores
        """)
        
        stats = cursor.fetchone()
        print(f"전체 가게 수: {stats['total_stores']}")
        print(f"주소 있는 가게: {stats['stores_with_address']} ({stats['stores_with_address']/stats['total_stores']*100:.1f}%)")
        print(f"영업시간 있는 가게: {stats['stores_with_hours']} ({stats['stores_with_hours']/stats['total_stores']*100:.1f}%)")
        print(f"휴무일 있는 가게: {stats['stores_with_holiday']} ({stats['stores_with_holiday']/stats['total_stores']*100:.1f}%)")
        print(f"요일별 휴무일: {stats['stores_with_weekday_holiday']} ({stats['stores_with_weekday_holiday']/stats['total_stores']*100:.1f}%)")
        print(f"요일별 영업시간: {stats['stores_with_weekday_hours']} ({stats['stores_with_weekday_hours']/stats['total_stores']*100:.1f}%)")
        
        # 샘플 데이터 확인
        print("\n=== 최근 저장된 가게 샘플 (5개) ===")
        cursor.execute("""
            SELECT 
                name,
                address,
                open_hours,
                holiday,
                break_time,
                last_order,
                created_at
            FROM stores
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        samples = cursor.fetchall()
        for i, store in enumerate(samples, 1):
            print(f"\n[{i}] {store['name']}")
            print(f"  주소: {store['address'] or 'N/A'}")
            print(f"  영업시간: {store['open_hours'] or 'N/A'}")
            print(f"  휴무일: {store['holiday'] or 'N/A'}")
            print(f"  브레이크타임: {store['break_time'] or 'N/A'}")
            print(f"  라스트오더: {store['last_order'] or 'N/A'}")
            print(f"  저장일시: {store['created_at']}")
        
        # 문제가 있는 데이터 확인
        print("\n=== 문제가 있는 데이터 샘플 ===")
        
        # 주소가 없는 가게
        cursor.execute("""
            SELECT name, diningcode_place_id
            FROM stores
            WHERE address IS NULL OR address = ''
            LIMIT 3
        """)
        no_address = cursor.fetchall()
        if no_address:
            print("\n주소가 없는 가게:")
            for store in no_address:
                print(f"  - {store['name']} (ID: {store['diningcode_place_id']})")
        
        # 날짜별 영업시간을 가진 가게 (개선 필요)
        cursor.execute("""
            SELECT name, open_hours
            FROM stores
            WHERE open_hours LIKE '%월%일%'
            LIMIT 3
        """)
        date_hours = cursor.fetchall()
        if date_hours:
            print("\n날짜별 영업시간 (개선 필요):")
            for store in date_hours:
                print(f"  - {store['name']}")
                print(f"    영업시간: {store['open_hours'][:100]}...")
        
        # 구체적이지 않은 휴무일
        cursor.execute("""
            SELECT name, holiday
            FROM stores
            WHERE holiday IN ('휴무일', '정기휴일')
            LIMIT 3
        """)
        vague_holiday = cursor.fetchall()
        if vague_holiday:
            print("\n구체적이지 않은 휴무일:")
            for store in vague_holiday:
                print(f"  - {store['name']}: {store['holiday']}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_address_hours() 