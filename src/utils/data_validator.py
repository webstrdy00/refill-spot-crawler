"""
크롤링 데이터 검증 스크립트
마이그레이션 전에 데이터 품질을 확인
"""
import psycopg2
import psycopg2.extras
import logging
from typing import Dict, List
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidator:
    def __init__(self, db_config: Dict):
        self.conn = psycopg2.connect(**db_config)
        
    def validate_all(self):
        """모든 검증 수행"""
        logger.info("=== 크롤링 데이터 검증 시작 ===")
        
        # 1. 기본 통계
        self.check_basic_stats()
        
        # 2. 데이터 품질 검증
        self.check_data_quality()
        
        # 3. 무한리필 관련 검증
        self.check_refill_data()
        
        # 4. 위치 정보 검증
        self.check_location_data()
        
        # 5. 중복 데이터 검증
        self.check_duplicates()
        
        logger.info("=== 검증 완료 ===")
    
    def check_basic_stats(self):
        """기본 통계 확인"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 전체 가게 수
            cursor.execute("SELECT COUNT(*) as total FROM stores")
            total = cursor.fetchone()['total']
            logger.info(f"\n총 가게 수: {total}")
            
            # 상태별 통계
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM stores 
                GROUP BY status
            """)
            logger.info("\n상태별 통계:")
            for row in cursor.fetchall():
                logger.info(f"  - {row['status']}: {row['count']}개")
            
            # 카테고리 통계
            cursor.execute("""
                SELECT c.name, COUNT(DISTINCT sc.store_id) as store_count
                FROM categories c
                LEFT JOIN store_categories sc ON c.id = sc.category_id
                GROUP BY c.name
                ORDER BY store_count DESC
                LIMIT 20
            """)
            logger.info("\n상위 20개 카테고리:")
            for row in cursor.fetchall():
                logger.info(f"  - {row['name']}: {row['store_count']}개 가게")
                
        finally:
            cursor.close()
    
    def check_data_quality(self):
        """데이터 품질 검증"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 필수 필드 누락 확인
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN name IS NULL OR name = '' THEN 1 END) as no_name,
                    COUNT(CASE WHEN address IS NULL OR address = '' THEN 1 END) as no_address,
                    COUNT(CASE WHEN position_lat IS NULL OR position_lng IS NULL THEN 1 END) as no_location,
                    COUNT(CASE WHEN phone_number IS NULL OR phone_number = '' THEN 1 END) as no_phone,
                    COUNT(CASE WHEN open_hours IS NULL AND open_hours_raw IS NULL THEN 1 END) as no_hours,
                    COUNT(CASE WHEN price IS NULL AND average_price IS NULL AND price_range IS NULL THEN 1 END) as no_price
                FROM stores
                WHERE status = '운영중'
            """)
            
            result = cursor.fetchone()
            logger.info("\n데이터 품질 검증:")
            logger.info(f"  - 이름 없음: {result['no_name']}개 ({result['no_name']/result['total']*100:.1f}%)")
            logger.info(f"  - 주소 없음: {result['no_address']}개 ({result['no_address']/result['total']*100:.1f}%)")
            logger.info(f"  - 위치 정보 없음: {result['no_location']}개 ({result['no_location']/result['total']*100:.1f}%)")
            logger.info(f"  - 전화번호 없음: {result['no_phone']}개 ({result['no_phone']/result['total']*100:.1f}%)")
            logger.info(f"  - 영업시간 없음: {result['no_hours']}개 ({result['no_hours']/result['total']*100:.1f}%)")
            logger.info(f"  - 가격 정보 없음: {result['no_price']}개 ({result['no_price']/result['total']*100:.1f}%)")
            
            # 이미지 정보
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN array_length(image_urls, 1) > 0 THEN 1 END) as with_images,
                    AVG(CASE WHEN image_urls IS NOT NULL THEN array_length(image_urls, 1) ELSE 0 END) as avg_images
                FROM stores
                WHERE status = '운영중'
            """)
            
            result = cursor.fetchone()
            logger.info(f"\n이미지 정보:")
            logger.info(f"  - 이미지 있는 가게: {result['with_images']}개 ({result['with_images']/result['total']*100:.1f}%)")
            logger.info(f"  - 평균 이미지 수: {result['avg_images']:.1f}개")
            
        finally:
            cursor.close()
    
    def check_refill_data(self):
        """무한리필 관련 데이터 검증"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 무한리필 확인 상태
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_confirmed_refill = true THEN 1 END) as confirmed,
                    COUNT(CASE WHEN refill_type IS NOT NULL AND refill_type != '' THEN 1 END) as has_type,
                    COUNT(CASE WHEN array_length(refill_items, 1) > 0 THEN 1 END) as has_items
                FROM stores
                WHERE status = '운영중'
            """)
            
            result = cursor.fetchone()
            logger.info("\n무한리필 데이터:")
            logger.info(f"  - 무한리필 확인됨: {result['confirmed']}개 ({result['confirmed']/result['total']*100:.1f}%)")
            logger.info(f"  - 리필 타입 있음: {result['has_type']}개 ({result['has_type']/result['total']*100:.1f}%)")
            logger.info(f"  - 리필 아이템 있음: {result['has_items']}개 ({result['has_items']/result['total']*100:.1f}%)")
            
            # 리필 타입별 통계
            cursor.execute("""
                SELECT refill_type, COUNT(*) as count
                FROM stores
                WHERE refill_type IS NOT NULL AND refill_type != ''
                GROUP BY refill_type
                ORDER BY count DESC
                LIMIT 10
            """)
            
            logger.info("\n상위 10개 리필 타입:")
            for row in cursor.fetchall():
                logger.info(f"  - {row['refill_type']}: {row['count']}개")
                
        finally:
            cursor.close()
    
    def check_location_data(self):
        """위치 정보 검증"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 서울 지역 범위 확인 (대략적인 서울 경계)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE 
                        WHEN position_lat BETWEEN 37.4 AND 37.7 
                        AND position_lng BETWEEN 126.8 AND 127.2 
                        THEN 1 
                    END) as in_seoul
                FROM stores
                WHERE position_lat IS NOT NULL AND position_lng IS NOT NULL
            """)
            
            result = cursor.fetchone()
            logger.info(f"\n위치 정보:")
            logger.info(f"  - 서울 지역 가게: {result['in_seoul']}개 ({result['in_seoul']/result['total']*100:.1f}%)")
            
            # 이상한 좌표 확인
            cursor.execute("""
                SELECT name, address, position_lat, position_lng
                FROM stores
                WHERE position_lat IS NOT NULL AND position_lng IS NOT NULL
                AND (
                    position_lat NOT BETWEEN 33 AND 43  -- 한국 위도 범위
                    OR position_lng NOT BETWEEN 124 AND 132  -- 한국 경도 범위
                )
                LIMIT 10
            """)
            
            invalid_coords = cursor.fetchall()
            if invalid_coords:
                logger.warning(f"\n잘못된 좌표를 가진 가게 {len(invalid_coords)}개 발견:")
                for store in invalid_coords[:5]:
                    logger.warning(f"  - {store['name']} ({store['position_lat']}, {store['position_lng']})")
                    
        finally:
            cursor.close()
    
    def check_duplicates(self):
        """중복 데이터 검증"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 이름과 주소가 같은 중복 가게
            cursor.execute("""
                SELECT name, address, COUNT(*) as count
                FROM stores
                WHERE status = '운영중'
                GROUP BY name, address
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                LIMIT 10
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                logger.warning(f"\n중복 가게 발견:")
                for dup in duplicates:
                    logger.warning(f"  - {dup['name']} ({dup['address']}): {dup['count']}개")
            else:
                logger.info("\n중복 가게 없음")
            
            # 같은 위치에 여러 가게
            cursor.execute("""
                SELECT position_lat, position_lng, COUNT(*) as count,
                       array_agg(name) as store_names
                FROM stores
                WHERE position_lat IS NOT NULL AND position_lng IS NOT NULL
                AND status = '운영중'
                GROUP BY position_lat, position_lng
                HAVING COUNT(*) > 2
                ORDER BY count DESC
                LIMIT 10
            """)
            
            same_location = cursor.fetchall()
            if same_location:
                logger.info(f"\n같은 위치에 여러 가게:")
                for loc in same_location[:5]:
                    logger.info(f"  - 위치 ({loc['position_lat']}, {loc['position_lng']}): {loc['count']}개")
                    logger.info(f"    가게들: {', '.join(loc['store_names'][:3])}...")
                    
        finally:
            cursor.close()
    
    def close(self):
        """연결 종료"""
        self.conn.close()


# 사용 예시
if __name__ == "__main__":
    # 크롤러 DB 연결 정보
    db_config = {
        'host': 'localhost',
        'port': 5433,
        'database': 'refill_spot_crawler',
        'user': 'crawler_user',
        'password': 'crawler_password'
    }
    
    validator = DataValidator(db_config)
    
    try:
        validator.validate_all()
    finally:
        validator.close() 