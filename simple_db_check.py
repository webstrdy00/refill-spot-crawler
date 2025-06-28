"""
간단한 데이터베이스 확인 스크립트
"""
import psycopg2
import psycopg2.extras
from config.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def simple_check():
    """간단한 데이터베이스 확인"""
    try:
        print("데이터베이스 연결 중...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("연결 성공!")
        
        cursor = conn.cursor()
        
        # 전체 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores")
        total = cursor.fetchone()[0]
        print(f"전체 가게 수: {total}")
        
        # 주소가 있는 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores WHERE address IS NOT NULL AND address != ''")
        with_address = cursor.fetchone()[0]
        print(f"주소가 있는 가게: {with_address} ({with_address/total*100:.1f}%)")
        
        # 영업시간이 있는 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores WHERE open_hours IS NOT NULL AND open_hours != ''")
        with_hours = cursor.fetchone()[0]
        print(f"영업시간이 있는 가게: {with_hours} ({with_hours/total*100:.1f}%)")
        
        # 라스트오더가 있는 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores WHERE last_order IS NOT NULL AND last_order != ''")
        with_last_order = cursor.fetchone()[0]
        print(f"라스트오더가 있는 가게: {with_last_order} ({with_last_order/total*100:.1f}%)")
        
        # 휴무일이 있는 가게 수
        cursor.execute("SELECT COUNT(*) FROM stores WHERE holiday IS NOT NULL AND holiday != ''")
        with_holiday = cursor.fetchone()[0]
        print(f"휴무일이 있는 가게: {with_holiday} ({with_holiday/total*100:.1f}%)")
        
        # 최근 저장된 가게 3개
        print("\n=== 최근 저장된 가게 3개 ===")
        cursor.execute("""
            SELECT name, address, open_hours, last_order, holiday, created_at
            FROM stores
            ORDER BY created_at DESC
            LIMIT 3
        """)
        
        for i, row in enumerate(cursor.fetchall(), 1):
            name, address, hours, last_order, holiday, created = row
            print(f"\n[{i}] {name}")
            print(f"  주소: {address[:50] if address else 'N/A'}")
            print(f"  영업시간: {hours[:50] if hours else 'N/A'}")
            print(f"  라스트오더: {last_order if last_order else 'N/A'}")
            print(f"  휴무일: {holiday if holiday else 'N/A'}")
            print(f"  저장일시: {created}")
        
        cursor.close()
        conn.close()
        print("\n✅ 확인 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_check() 