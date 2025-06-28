#!/usr/bin/env python3
"""
크롤러 데이터베이스 테이블 구조 확인
"""
import psycopg2
import psycopg2.extras

def check_database():
    """데이터베이스 테이블 구조 확인"""
    try:
        # 크롤러 DB 연결
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='refill_spot_crawler',
            user='postgres',
            password='12345'
        )
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. 테이블 목록 조회
        print("📋 테이블 목록:")
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table['tablename']}")
        
        # 2. stores 테이블 구조 확인
        if any(t['tablename'] == 'stores' for t in tables):
            print("\n🏪 stores 테이블 구조:")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'stores'
                ORDER BY ordinal_position;
            """)
            
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        # 3. stores 테이블 데이터 개수 확인
        if any(t['tablename'] == 'stores' for t in tables):
            cursor.execute("SELECT COUNT(*) as count FROM stores;")
            count = cursor.fetchone()
            print(f"\n📊 stores 테이블 데이터: {count['count']}개")
            
            # 샘플 데이터 조회
            cursor.execute("""
                SELECT name, address, status, created_at
                FROM stores 
                ORDER BY created_at DESC 
                LIMIT 3;
            """)
            
            samples = cursor.fetchall()
            print("\n🔍 샘플 데이터:")
            for i, sample in enumerate(samples, 1):
                print(f"  {i}. {sample['name']} - {sample['address']} ({sample.get('status', 'N/A')})")
        
        cursor.close()
        conn.close()
        
        print("\n✅ 데이터베이스 확인 완료")
        
    except Exception as e:
        print(f"❌ 데이터베이스 확인 실패: {e}")

if __name__ == "__main__":
    check_database() 