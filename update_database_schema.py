#!/usr/bin/env python3
"""
데이터베이스 스키마 업데이트 스크립트
- description, price_range, average_price 필드 제거
- 카테고리를 7개로 제한
"""

import psycopg2
import logging
from config.config import DATABASE_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_database_schema():
    """데이터베이스 스키마 업데이트"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        logger.info("데이터베이스 스키마 업데이트 시작...")
        
        # 1. stores 테이블에서 불필요한 필드 제거
        logger.info("1. 불필요한 필드 제거 중...")
        
        try:
            cursor.execute("ALTER TABLE stores DROP COLUMN IF EXISTS description;")
            logger.info("   - description 필드 제거 완료")
        except Exception as e:
            logger.warning(f"   - description 필드 제거 실패: {e}")
        
        try:
            cursor.execute("ALTER TABLE stores DROP COLUMN IF EXISTS price_range;")
            logger.info("   - price_range 필드 제거 완료")
        except Exception as e:
            logger.warning(f"   - price_range 필드 제거 실패: {e}")
        
        try:
            cursor.execute("ALTER TABLE stores DROP COLUMN IF EXISTS average_price;")
            logger.info("   - average_price 필드 제거 완료")
        except Exception as e:
            logger.warning(f"   - average_price 필드 제거 실패: {e}")
        
        # 2. 기존 카테고리 데이터 정리
        logger.info("2. 카테고리 데이터 정리 중...")
        
        # 먼저 사용되지 않는 카테고리와의 연결 제거
        cursor.execute("""
            DELETE FROM store_categories 
            WHERE category_id IN (
                SELECT id FROM categories 
                WHERE name NOT IN ('고기', '해산물', '양식', '한식', '중식', '일식', '디저트')
            );
        """)
        deleted_links = cursor.rowcount
        logger.info(f"   - 불필요한 카테고리 연결 {deleted_links}개 제거")
        
        # 사용되지 않는 카테고리 제거
        cursor.execute("""
            DELETE FROM categories 
            WHERE name NOT IN ('고기', '해산물', '양식', '한식', '중식', '일식', '디저트');
        """)
        deleted_categories = cursor.rowcount
        logger.info(f"   - 불필요한 카테고리 {deleted_categories}개 제거")
        
        # 3. 표준 카테고리 추가
        logger.info("3. 표준 카테고리 추가 중...")
        
        standard_categories = ['고기', '해산물', '양식', '한식', '중식', '일식', '디저트']
        for category in standard_categories:
            cursor.execute("""
                INSERT INTO categories (name) VALUES (%s) 
                ON CONFLICT (name) DO NOTHING
            """, (category,))
        
        logger.info(f"   - 표준 카테고리 {len(standard_categories)}개 확인/추가 완료")
        
        # 4. 카테고리가 없는 가게들에게 기본 카테고리(한식) 할당
        logger.info("4. 기본 카테고리 할당 중...")
        
        cursor.execute("""
            INSERT INTO store_categories (store_id, category_id)
            SELECT s.id, c.id
            FROM stores s
            CROSS JOIN categories c
            WHERE c.name = '한식'
            AND NOT EXISTS (
                SELECT 1 FROM store_categories sc 
                WHERE sc.store_id = s.id
            );
        """)
        assigned_count = cursor.rowcount
        logger.info(f"   - {assigned_count}개 가게에 기본 카테고리(한식) 할당")
        
        # 변경사항 커밋
        conn.commit()
        logger.info("모든 변경사항 커밋 완료!")
        
        # 5. 결과 확인
        logger.info("5. 결과 확인...")
        
        cursor.execute("SELECT COUNT(*) FROM categories;")
        categories_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM stores;")
        stores_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM store_categories;")
        links_count = cursor.fetchone()[0]
        
        logger.info(f"   - 카테고리 수: {categories_count}")
        logger.info(f"   - 가게 수: {stores_count}")
        logger.info(f"   - 카테고리-가게 연결 수: {links_count}")
        
        # 카테고리별 가게 수
        cursor.execute("""
            SELECT c.name, COUNT(sc.store_id) as store_count
            FROM categories c
            LEFT JOIN store_categories sc ON c.id = sc.category_id
            GROUP BY c.name
            ORDER BY store_count DESC;
        """)
        
        category_stats = cursor.fetchall()
        logger.info("   - 카테고리별 가게 수:")
        for name, count in category_stats:
            logger.info(f"     * {name}: {count}개")
        
        cursor.close()
        conn.close()
        
        logger.info("데이터베이스 스키마 업데이트 완료!")
        
    except Exception as e:
        logger.error(f"데이터베이스 스키마 업데이트 실패: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    update_database_schema() 