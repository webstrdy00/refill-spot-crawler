import psycopg2
import psycopg2.extras
import pandas as pd
import logging
from typing import List, Dict, Optional
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pg_conn = None
        self.setup_connection()
    
    def setup_connection(self):
        """PostgreSQL 연결 설정"""
        try:
            # PostgreSQL 직접 연결
            self.pg_conn = psycopg2.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            self.pg_conn.autocommit = True
            logger.info("PostgreSQL 연결 성공")
            
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise
    
import psycopg2
import psycopg2.extras
import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pg_conn = None
        self.setup_connection()
    
    def setup_connection(self):
        """PostgreSQL 연결 설정 (DATABASE_URL 또는 개별 파라미터)"""
        try:
            # DATABASE_URL이 있으면 직접 사용, 없으면 개별 파라미터 조합
            if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL:
                logger.info(f"DATABASE_URL로 연결 시도: {config.DATABASE_URL.replace(config.DB_PASSWORD, '***')}")
                self.pg_conn = psycopg2.connect(config.DATABASE_URL)
            else:
                # 개별 파라미터로 연결
                logger.info(f"개별 파라미터로 연결 시도: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
                self.pg_conn = psycopg2.connect(
                    host=config.DB_HOST,
                    port=config.DB_PORT,
                    database=config.DB_NAME,
                    user=config.DB_USER,
                    password=config.DB_PASSWORD
                )
            
            self.pg_conn.autocommit = True
            logger.info("PostgreSQL 연결 성공")
            
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            logger.info("연결 정보:")
            logger.info(f"  Host: {config.DB_HOST}")
            logger.info(f"  Port: {config.DB_PORT}")
            logger.info(f"  Database: {config.DB_NAME}")
            logger.info(f"  User: {config.DB_USER}")
            raise
    
    def test_connection(self):
        """연결 테스트"""
        cursor = self.pg_conn.cursor()
        try:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"PostgreSQL 버전: {version[0]}")
            
            # 현재 데이터베이스 정보 확인
            cursor.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port();")
            db_info = cursor.fetchone()
            logger.info(f"연결된 DB: {db_info[0]}, 사용자: {db_info[1]}, 서버: {db_info[2]}:{db_info[3]}")
            
            # PostGIS 확장 확인
            try:
                cursor.execute("SELECT PostGIS_Version();")
                postgis_version = cursor.fetchone()
                if postgis_version:
                    logger.info(f"PostGIS 버전: {postgis_version[0]}")
            except:
                logger.warning("PostGIS 확장이 설치되지 않았습니다. init.sql이 실행되지 않았을 수 있습니다.")
            
            return True
        except Exception as e:
            logger.error(f"연결 테스트 실패: {e}")
            return False
        finally:
            cursor.close()
    
    def create_tables(self):
        """테이블 생성 (init.sql이 이미 실행되었다고 가정)"""
        cursor = self.pg_conn.cursor()
        
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('stores', 'categories', 'store_categories')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['stores', 'categories', 'store_categories']
            missing_tables = [t for t in required_tables if t not in existing_tables]
            
            if missing_tables:
                logger.warning(f"누락된 테이블: {missing_tables}")
                logger.info("docker-compose up 실행 시 init.sql이 자동으로 테이블을 생성합니다.")
            else:
                logger.info("모든 필수 테이블이 존재합니다.")
            
        except Exception as e:
            logger.error(f"테이블 확인 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def insert_categories(self, categories: List[str]) -> Dict[str, int]:
        """카테고리 삽입 및 ID 매핑 반환"""
        cursor = self.pg_conn.cursor()
        category_map = {}
        
        try:
            for category in categories:
                cursor.execute("""
                    INSERT INTO categories (name) 
                    VALUES (%s) 
                    ON CONFLICT (name) DO NOTHING
                """, (category,))
            
            # ID 매핑 조회
            placeholders = ','.join(['%s'] * len(categories))
            cursor.execute(f"""
                SELECT name, id FROM categories 
                WHERE name IN ({placeholders})
            """, categories)
            
            category_map = dict(cursor.fetchall())
            logger.info(f"카테고리 처리 완료: {len(category_map)}개")
            
        except Exception as e:
            logger.error(f"카테고리 삽입 실패: {e}")
            raise
        finally:
            cursor.close()
            
        return category_map
    
    def insert_stores_batch(self, stores_data: List[Dict]) -> List[int]:
        """가게 정보 배치 삽입 (새로운 스키마 반영)"""
        cursor = self.pg_conn.cursor()
        store_ids = []
        
        try:
            # stores 테이블 삽입용 데이터 준비
            store_values = []
            for store in stores_data:
                values = (
                    store.get('name'),
                    store.get('address'),
                    store.get('description'),
                    store.get('position_lat'),
                    store.get('position_lng'),
                    store.get('position_x'),  # 카카오맵 좌표 (옵션)
                    store.get('position_y'),  # 카카오맵 좌표 (옵션)
                    store.get('naver_rating'),
                    store.get('kakao_rating'),
                    store.get('diningcode_rating'),
                    store.get('open_hours'),
                    store.get('open_hours_raw'),
                    store.get('price'),
                    store.get('refill_items', []),
                    store.get('image_urls', []),
                    store.get('phone_number'),
                    store.get('diningcode_place_id'),
                    store.get('raw_categories_diningcode', []),
                    store.get('status', '운영중')
                )
                store_values.append(values)
            
            # 배치 삽입
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO stores (
                    name, address, description,
                    position_lat, position_lng, position_x, position_y,
                    naver_rating, kakao_rating, diningcode_rating,
                    open_hours, open_hours_raw, price, refill_items, image_urls,
                    phone_number, diningcode_place_id, raw_categories_diningcode, status
                ) VALUES %s
                ON CONFLICT (diningcode_place_id) 
                DO UPDATE SET
                    name = EXCLUDED.name,
                    address = EXCLUDED.address,
                    description = EXCLUDED.description,
                    position_lat = EXCLUDED.position_lat,
                    position_lng = EXCLUDED.position_lng,
                    naver_rating = EXCLUDED.naver_rating,
                    kakao_rating = EXCLUDED.kakao_rating,
                    diningcode_rating = EXCLUDED.diningcode_rating,
                    open_hours = EXCLUDED.open_hours,
                    open_hours_raw = EXCLUDED.open_hours_raw,
                    price = EXCLUDED.price,
                    refill_items = EXCLUDED.refill_items,
                    image_urls = EXCLUDED.image_urls,
                    phone_number = EXCLUDED.phone_number,
                    raw_categories_diningcode = EXCLUDED.raw_categories_diningcode,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                RETURNING id
                """,
                store_values
            )
            
            store_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"가게 {len(store_ids)}개 삽입/업데이트 완료")
            
        except Exception as e:
            logger.error(f"가게 배치 삽입 실패: {e}")
            raise
        finally:
            cursor.close()
            
        return store_ids
    
    def link_store_categories(self, store_id: int, category_ids: List[int]):
        """가게-카테고리 연결"""
        if not category_ids:
            return
            
        cursor = self.pg_conn.cursor()
        
        try:
            # 기존 연결 삭제
            cursor.execute("DELETE FROM store_categories WHERE store_id = %s", (store_id,))
            
            # 새 연결 삽입
            category_values = [(store_id, cat_id) for cat_id in category_ids]
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO store_categories (store_id, category_id) VALUES %s",
                category_values
            )
            
        except Exception as e:
            logger.error(f"가게-카테고리 연결 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def log_crawling_session(self, keyword: str, rect_area: str) -> int:
        """크롤링 세션 로그 시작"""
        cursor = self.pg_conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO crawling_logs (keyword, rect_area, started_at, status)
                VALUES (%s, %s, %s, 'running')
                RETURNING id
            """, (keyword, rect_area, datetime.now()))
            
            log_id = cursor.fetchone()[0]
            logger.info(f"크롤링 세션 시작: {log_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"크롤링 로그 생성 실패: {e}")
            return None
        finally:
            cursor.close()
    
    def update_crawling_log(self, log_id: int, stores_found: int, stores_processed: int, 
                           errors: int = 0, status: str = 'completed', error_message: str = None):
        """크롤링 세션 로그 업데이트"""
        if not log_id:
            return
            
        cursor = self.pg_conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE crawling_logs 
                SET stores_found = %s, stores_processed = %s, errors = %s,
                    completed_at = %s, status = %s, error_message = %s
                WHERE id = %s
            """, (stores_found, stores_processed, errors, datetime.now(), status, error_message, log_id))
            
        except Exception as e:
            logger.error(f"크롤링 로그 업데이트 실패: {e}")
        finally:
            cursor.close()
    
    def get_crawling_stats(self) -> Dict:
        """크롤링 통계 조회"""
        cursor = self.pg_conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM get_crawling_stats()")
            result = cursor.fetchone()
            
            if result:
                return {
                    'total_stores': result[0],
                    'stores_with_coordinates': result[1],
                    'stores_with_phone': result[2],
                    'stores_with_rating': result[3],
                    'avg_rating': float(result[4]) if result[4] else 0,
                    'categories_count': result[5],
                    'last_crawled': result[6]
                }
            return {}
            
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def save_crawled_data(self, stores_data: List[Dict], keyword: str = '', rect_area: str = ''):
        """크롤링된 데이터 저장 (개선된 버전)"""
        if not stores_data:
            logger.warning("저장할 데이터가 없습니다")
            return
        
        # 크롤링 로그 시작
        log_id = self.log_crawling_session(keyword, rect_area)
        
        try:
            # 모든 카테고리 수집
            all_categories = set()
            for store in stores_data:
                categories = store.get('raw_categories_diningcode', [])
                all_categories.update(categories)
                # 무한리필 카테고리는 필수로 추가
                all_categories.add('무한리필')
            
            # 카테고리 삽입
            category_map = self.insert_categories(list(all_categories))
            
            # 가게 데이터 삽입
            store_ids = self.insert_stores_batch(stores_data)
            
            # 가게-카테고리 연결
            processed_count = 0
            for i, store in enumerate(stores_data):
                if i < len(store_ids):
                    store_categories = store.get('raw_categories_diningcode', [])
                    store_categories.append('무한리필')  # 필수 카테고리
                    
                    category_ids = [category_map[cat] for cat in store_categories if cat in category_map]
                    self.link_store_categories(store_ids[i], category_ids)
                    processed_count += 1
            
            # 크롤링 로그 완료
            self.update_crawling_log(log_id, len(stores_data), processed_count)
            
            logger.info(f"총 {len(stores_data)}개 가게 데이터 저장 완료")
            
            # 통계 출력
            stats = self.get_crawling_stats()
            logger.info(f"현재 데이터베이스 통계: {stats}")
            
        except Exception as e:
            # 크롤링 로그 실패 처리
            self.update_crawling_log(log_id, len(stores_data), 0, 1, 'failed', str(e))
            logger.error(f"데이터 저장 실패: {e}")
            raise
    
    def close(self):
        """연결 종료"""
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("PostgreSQL 연결 종료")

# 테스트 함수
def test_database():
    """데이터베이스 연결 및 기능 테스트"""
    db = DatabaseManager()
    
    try:
        # 연결 테스트
        if not db.test_connection():
            return
        
        # 테이블 확인
        db.create_tables()
        
        # 통계 조회 테스트
        stats = db.get_crawling_stats()
        logger.info(f"현재 통계: {stats}")
        
        logger.info("데이터베이스 테스트 완료")
        
    except Exception as e:
        logger.error(f"데이터베이스 테스트 실패: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_database()
    
    def create_tables(self):
        """테이블 생성 (없는 경우)"""
        cursor = self.pg_conn.cursor()
        
        try:
            # categories 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # stores 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    id SERIAL PRIMARY KEY,
                    diningcode_place_id VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    address TEXT,
                    description TEXT,
                    position_lat DECIMAL(10, 8),
                    position_lng DECIMAL(11, 8),
                    open_hours TEXT,
                    open_hours_raw TEXT,
                    price INTEGER,
                    refill_items TEXT[],
                    image_urls TEXT[],
                    phone_number VARCHAR(20),
                    diningcode_rating DECIMAL(3, 2),
                    raw_categories_diningcode TEXT[],
                    status VARCHAR(20) DEFAULT '운영중',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # store_categories 연결 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS store_categories (
                    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
                    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                    PRIMARY KEY (store_id, category_id)
                )
            """)
            
            # 인덱스 생성
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stores_diningcode_id 
                ON stores(diningcode_place_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stores_position 
                ON stores(position_lat, position_lng)
            """)
            
            logger.info("테이블 생성 완료")
            
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def insert_categories(self, categories: List[str]) -> Dict[str, int]:
        """카테고리 삽입 및 ID 매핑 반환"""
        cursor = self.pg_conn.cursor()
        category_map = {}
        
        try:
            for category in categories:
                cursor.execute("""
                    INSERT INTO categories (name) 
                    VALUES (%s) 
                    ON CONFLICT (name) DO NOTHING
                """, (category,))
            
            # ID 매핑 조회
            placeholders = ','.join(['%s'] * len(categories))
            cursor.execute(f"""
                SELECT name, id FROM categories 
                WHERE name IN ({placeholders})
            """, categories)
            
            category_map = dict(cursor.fetchall())
            logger.info(f"카테고리 처리 완료: {len(category_map)}개")
            
        except Exception as e:
            logger.error(f"카테고리 삽입 실패: {e}")
            raise
        finally:
            cursor.close()
            
        return category_map
    
    def insert_stores_batch(self, stores_data: List[Dict]) -> List[int]:
        """가게 정보 배치 삽입"""
        cursor = self.pg_conn.cursor()
        store_ids = []
        
        try:
            # stores 테이블 삽입용 데이터 준비
            store_values = []
            for store in stores_data:
                values = (
                    store.get('diningcode_place_id'),
                    store.get('name'),
                    store.get('address'),
                    store.get('description'),
                    store.get('position_lat'),
                    store.get('position_lng'),
                    store.get('open_hours'),
                    store.get('open_hours_raw'),
                    store.get('price'),
                    store.get('refill_items', []),
                    store.get('image_urls', []),
                    store.get('phone_number'),
                    store.get('diningcode_rating'),
                    store.get('raw_categories_diningcode', []),
                    store.get('status', '운영중')
                )
                store_values.append(values)
            
            # 배치 삽입
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO stores (
                    diningcode_place_id, name, address, description,
                    position_lat, position_lng, open_hours, open_hours_raw,
                    price, refill_items, image_urls, phone_number,
                    diningcode_rating, raw_categories_diningcode, status
                ) VALUES %s
                ON CONFLICT (diningcode_place_id) 
                DO UPDATE SET
                    name = EXCLUDED.name,
                    address = EXCLUDED.address,
                    description = EXCLUDED.description,
                    position_lat = EXCLUDED.position_lat,
                    position_lng = EXCLUDED.position_lng,
                    open_hours = EXCLUDED.open_hours,
                    open_hours_raw = EXCLUDED.open_hours_raw,
                    price = EXCLUDED.price,
                    refill_items = EXCLUDED.refill_items,
                    image_urls = EXCLUDED.image_urls,
                    phone_number = EXCLUDED.phone_number,
                    diningcode_rating = EXCLUDED.diningcode_rating,
                    raw_categories_diningcode = EXCLUDED.raw_categories_diningcode,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                store_values
            )
            
            store_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"가게 {len(store_ids)}개 삽입/업데이트 완료")
            
        except Exception as e:
            logger.error(f"가게 배치 삽입 실패: {e}")
            raise
        finally:
            cursor.close()
            
        return store_ids
    
    def link_store_categories(self, store_id: int, category_ids: List[int]):
        """가게-카테고리 연결"""
        if not category_ids:
            return
            
        cursor = self.pg_conn.cursor()
        
        try:
            # 기존 연결 삭제
            cursor.execute("DELETE FROM store_categories WHERE store_id = %s", (store_id,))
            
            # 새 연결 삽입
            category_values = [(store_id, cat_id) for cat_id in category_ids]
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO store_categories (store_id, category_id) VALUES %s",
                category_values
            )
            
        except Exception as e:
            logger.error(f"가게-카테고리 연결 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def save_crawled_data(self, stores_data: List[Dict]):
        """크롤링된 데이터 저장"""
        if not stores_data:
            logger.warning("저장할 데이터가 없습니다")
            return
        
        try:
            # 모든 카테고리 수집
            all_categories = set()
            for store in stores_data:
                categories = store.get('raw_categories_diningcode', [])
                all_categories.update(categories)
                # 무한리필 카테고리는 필수로 추가
                all_categories.add('무한리필')
            
            # 카테고리 삽입
            category_map = self.insert_categories(list(all_categories))
            
            # 가게 데이터 삽입
            store_ids = self.insert_stores_batch(stores_data)
            
            # 가게-카테고리 연결
            for i, store in enumerate(stores_data):
                if i < len(store_ids):
                    store_categories = store.get('raw_categories_diningcode', [])
                    store_categories.append('무한리필')  # 필수 카테고리
                    
                    category_ids = [category_map[cat] for cat in store_categories if cat in category_map]
                    self.link_store_categories(store_ids[i], category_ids)
            
            logger.info(f"총 {len(stores_data)}개 가게 데이터 저장 완료")
            
        except Exception as e:
            logger.error(f"데이터 저장 실패: {e}")
            raise
    
    def close(self):
        """연결 종료"""
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("PostgreSQL 연결 종료")

# 테스트 함수
def test_database():
    """데이터베이스 연결 및 테이블 생성 테스트"""
    db = DatabaseManager()
    
    try:
        # 테이블 생성
        db.create_tables()
        
        # 테스트 데이터
        test_data = [{
            'diningcode_place_id': 'test_001',
            'name': '테스트 무한리필 가게',
            'address': '서울특별시 강남구 테스트동 123',
            'description': '테스트용 가게입니다',
            'position_lat': 37.5665,
            'position_lng': 126.9780,
            'phone_number': '02-1234-5678',
            'raw_categories_diningcode': ['무한리필', '한식', '고기'],
            'diningcode_rating': 4.5
        }]
        
        # 데이터 저장 테스트
        db.save_crawled_data(test_data)
        logger.info("데이터베이스 테스트 완료")
        
    except Exception as e:
        logger.error(f"데이터베이스 테스트 실패: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_database()