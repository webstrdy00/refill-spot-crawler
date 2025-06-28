"""
직접 데이터베이스 연결 테스트
"""
import psycopg2

def test_direct_connection():
    """직접 연결 테스트"""
    try:
        print("직접 연결 시도...")
        
        # 기본 설정으로 연결
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='refill_spot',
            user='postgres',
            password='password123'
        )
        
        print("✅ 연결 성공!")
        
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("SELECT COUNT(*) FROM stores")
        count = cursor.fetchone()[0]
        print(f"stores 테이블의 레코드 수: {count}")
        
        # 최근 추가된 데이터 확인
        cursor.execute("""
            SELECT name, address, open_hours, last_order, holiday 
            FROM stores 
            ORDER BY id DESC 
            LIMIT 5
        """)
        
        print("\n=== 최근 추가된 가게 5개 ===")
        for i, row in enumerate(cursor.fetchall(), 1):
            name, address, hours, last_order, holiday = row
            print(f"\n[{i}] {name}")
            print(f"  주소: {address[:50] if address else 'N/A'}")
            print(f"  영업시간: {hours[:50] if hours else 'N/A'}")
            print(f"  라스트오더: {last_order if last_order else 'N/A'}")
            print(f"  휴무일: {holiday if holiday else 'N/A'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        
        # Supabase 연결 시도
        print("\nSupabase 연결 시도...")
        try:
            conn = psycopg2.connect(
                host='aws-0-ap-northeast-2.pooler.supabase.com',
                port=6543,
                database='postgres',
                user='postgres.mhpjvwgkpjjzfqizyxap',
                password='refillspot123!'
            )
            
            print("✅ Supabase 연결 성공!")
            
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stores")
            count = cursor.fetchone()[0]
            print(f"Supabase stores 테이블의 레코드 수: {count}")
            
            cursor.close()
            conn.close()
            
        except Exception as e2:
            print(f"❌ Supabase 연결도 실패: {e2}")

if __name__ == "__main__":
    test_direct_connection() 