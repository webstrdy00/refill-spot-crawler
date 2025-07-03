"""
간단한 데이터베이스 확인 스크립트
"""
import psycopg2
import json
from config.config import DATABASE_URL

def check_data():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 테이블 구조 확인
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'stores'
            ORDER BY ordinal_position
        """)
        
        print('🗄️ stores 테이블 구조:')
        columns = cursor.fetchall()
        for row in columns:
            print(f'  - {row[0]}: {row[1]}')
        
        # 최근 저장된 데이터 확인
        cursor.execute("""
            SELECT name, address, phone_number, diningcode_rating, price, raw_categories_diningcode, refill_items
            FROM stores 
            WHERE name LIKE '%강남 돼지상회%' 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if result:
            print(f'\n🏪 가게명: {result[0]}')
            print(f'📍 주소: {result[1]}')
            print(f'📞 전화번호: {result[2]}')
            print(f'⭐ 평점: {result[3]}')
            print(f'💰 가격: {result[4]}')
            print(f'🏷️ 카테고리: {result[5]}')
            print(f'🔄 무한리필 아이템: {result[6]}')
        else:
            print('데이터를 찾을 수 없습니다.')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f'오류 발생: {e}')

if __name__ == "__main__":
    check_data() 