import psycopg2
import psycopg2.extras
import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
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
    
    def execute_query(self, query: str, params=None):
        """일반적인 쿼리 실행"""
        cursor = self.pg_conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # SELECT 쿼리인 경우 결과 반환
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"쿼리 실행 실패: {e}")
            raise
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
        """가게 정보 배치 삽입/업데이트 (UPSERT 방식)"""
        cursor = self.pg_conn.cursor()
        store_ids = []
        
        try:
            # 개별 UPSERT 처리 (PostgreSQL ON CONFLICT 사용)
            for store in stores_data:
                cursor.execute("""
                    INSERT INTO stores (
                        name, address, description, position_lat, position_lng, 
                        position_x, position_y, naver_rating, kakao_rating, diningcode_rating,
                        open_hours, open_hours_raw, price, refill_items, image_urls,
                        phone_number, diningcode_place_id, raw_categories_diningcode, status,
                        menu_items, menu_categories, signature_menu, price_range, average_price,
                        price_details, break_time, last_order, holiday, main_image,
                        menu_images, interior_images, review_summary, keywords, atmosphere,
                        website, social_media, refill_type, refill_conditions, is_confirmed_refill
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (diningcode_place_id) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        address = COALESCE(EXCLUDED.address, stores.address),
                        description = COALESCE(EXCLUDED.description, stores.description),
                        position_lat = COALESCE(EXCLUDED.position_lat, stores.position_lat),
                        position_lng = COALESCE(EXCLUDED.position_lng, stores.position_lng),
                        position_x = COALESCE(EXCLUDED.position_x, stores.position_x),
                        position_y = COALESCE(EXCLUDED.position_y, stores.position_y),
                        naver_rating = COALESCE(EXCLUDED.naver_rating, stores.naver_rating),
                        kakao_rating = COALESCE(EXCLUDED.kakao_rating, stores.kakao_rating),
                        diningcode_rating = COALESCE(EXCLUDED.diningcode_rating, stores.diningcode_rating),
                        open_hours = COALESCE(EXCLUDED.open_hours, stores.open_hours),
                        open_hours_raw = COALESCE(EXCLUDED.open_hours_raw, stores.open_hours_raw),
                        price = COALESCE(EXCLUDED.price, stores.price),
                        refill_items = COALESCE(EXCLUDED.refill_items, stores.refill_items),
                        image_urls = COALESCE(EXCLUDED.image_urls, stores.image_urls),
                        phone_number = COALESCE(EXCLUDED.phone_number, stores.phone_number),
                        raw_categories_diningcode = COALESCE(EXCLUDED.raw_categories_diningcode, stores.raw_categories_diningcode),
                        status = EXCLUDED.status,
                        menu_items = COALESCE(EXCLUDED.menu_items, stores.menu_items),
                        menu_categories = COALESCE(EXCLUDED.menu_categories, stores.menu_categories),
                        signature_menu = COALESCE(EXCLUDED.signature_menu, stores.signature_menu),
                        price_range = COALESCE(EXCLUDED.price_range, stores.price_range),
                        average_price = COALESCE(EXCLUDED.average_price, stores.average_price),
                        price_details = COALESCE(EXCLUDED.price_details, stores.price_details),
                        break_time = COALESCE(EXCLUDED.break_time, stores.break_time),
                        last_order = COALESCE(EXCLUDED.last_order, stores.last_order),
                        holiday = COALESCE(EXCLUDED.holiday, stores.holiday),
                        main_image = COALESCE(EXCLUDED.main_image, stores.main_image),
                        menu_images = COALESCE(EXCLUDED.menu_images, stores.menu_images),
                        interior_images = COALESCE(EXCLUDED.interior_images, stores.interior_images),
                        review_summary = COALESCE(EXCLUDED.review_summary, stores.review_summary),
                        keywords = COALESCE(EXCLUDED.keywords, stores.keywords),
                        atmosphere = COALESCE(EXCLUDED.atmosphere, stores.atmosphere),
                        website = COALESCE(EXCLUDED.website, stores.website),
                        social_media = COALESCE(EXCLUDED.social_media, stores.social_media),
                        refill_type = COALESCE(EXCLUDED.refill_type, stores.refill_type),
                        refill_conditions = COALESCE(EXCLUDED.refill_conditions, stores.refill_conditions),
                        is_confirmed_refill = EXCLUDED.is_confirmed_refill,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (
                    store.get('name'),
                    store.get('address'),
                    store.get('description'),
                    store.get('position_lat'),
                    store.get('position_lng'),
                    store.get('position_x'),
                    store.get('position_y'),
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
                    store.get('status', '운영중'),
                    store.get('menu_items', []),
                    store.get('menu_categories', []),
                    store.get('signature_menu', []),
                    store.get('price_range', ''),
                    store.get('average_price', ''),
                    store.get('price_details', []),
                    store.get('break_time', ''),
                    store.get('last_order', ''),
                    store.get('holiday', ''),
                    store.get('main_image', ''),
                    store.get('menu_images', []),
                    store.get('interior_images', []),
                    store.get('review_summary', ''),
                    store.get('keywords', []),
                    store.get('atmosphere', ''),
                    store.get('website', ''),
                    store.get('social_media', []),
                    store.get('refill_type', ''),
                    store.get('refill_conditions', ''),
                    store.get('is_confirmed_refill', False)
                ))
                
                # 삽입/업데이트된 ID 수집
                result = cursor.fetchone()
                if result:
                    store_ids.append(result[0])
            
            logger.info(f"가게 정보 UPSERT 완료: {len(store_ids)}개 (신규 삽입 또는 업데이트)")
            
        except Exception as e:
            logger.error(f"가게 정보 UPSERT 실패: {e}")
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
        """크롤링된 데이터 저장 (강화된 정보 포함)"""
        if not stores_data:
            logger.warning("저장할 데이터가 없습니다.")
            return
        
        try:
            # 크롤링 세션 로그 시작
            log_id = self.log_crawling_session(keyword, rect_area)
            
            # 모든 카테고리 수집
            all_categories = set()
            for store in stores_data:
                categories = store.get('raw_categories_diningcode', [])
                all_categories.update(categories)
                
                # 메뉴 카테고리도 추가
                menu_categories = store.get('menu_categories', [])
                all_categories.update(menu_categories)
                
                # 키워드도 카테고리로 추가
                keywords = store.get('keywords', [])
                all_categories.update(keywords)
            
            # 카테고리 삽입
            if all_categories:
                category_map = self.insert_categories(list(all_categories))
            else:
                category_map = {}
            
            # 가게 정보 삽입
            store_ids = self.insert_stores_batch(stores_data)
            
            # 가게-카테고리 연결
            for i, store in enumerate(stores_data):
                if i < len(store_ids):
                    store_id = store_ids[i]
                    
                    # 기본 카테고리 연결
                    categories = store.get('raw_categories_diningcode', [])
                    category_ids = [category_map[cat] for cat in categories if cat in category_map]
                    
                    # 메뉴 카테고리 연결
                    menu_categories = store.get('menu_categories', [])
                    menu_category_ids = [category_map[cat] for cat in menu_categories if cat in category_map]
                    category_ids.extend(menu_category_ids)
                    
                    # 키워드 카테고리 연결
                    keywords = store.get('keywords', [])
                    keyword_ids = [category_map[kw] for kw in keywords if kw in category_map]
                    category_ids.extend(keyword_ids)
                    
                    if category_ids:
                        self.link_store_categories(store_id, list(set(category_ids)))
            
            # 크롤링 로그 업데이트
            self.update_crawling_log(
                log_id, 
                stores_found=len(stores_data), 
                stores_processed=len(store_ids),
                status='completed'
            )
            
            logger.info(f"데이터 저장 완료: {len(store_ids)}개 가게, {len(all_categories)}개 카테고리")
            
        except Exception as e:
            logger.error(f"데이터 저장 실패: {e}")
            if 'log_id' in locals():
                self.update_crawling_log(
                    log_id, 
                    stores_found=len(stores_data), 
                    stores_processed=0,
                    errors=1,
                    status='failed',
                    error_message=str(e)
                )
            raise
    
    def get_enhanced_crawling_stats(self) -> Dict:
        """강화된 크롤링 통계 조회"""
        cursor = self.pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 기본 통계
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_stores,
                    COUNT(CASE WHEN is_confirmed_refill = true THEN 1 END) as confirmed_refill_stores,
                    COUNT(CASE WHEN menu_items IS NOT NULL AND array_length(menu_items, 1) > 0 THEN 1 END) as stores_with_menu,
                    COUNT(CASE WHEN image_urls IS NOT NULL AND array_length(image_urls, 1) > 0 THEN 1 END) as stores_with_images,
                    COUNT(CASE WHEN price_range != '' THEN 1 END) as stores_with_price,
                    AVG(CASE WHEN diningcode_rating IS NOT NULL THEN diningcode_rating END) as avg_rating
                FROM stores
            """)
            basic_stats = cursor.fetchone()
            
            # 리필 타입별 통계
            cursor.execute("""
                SELECT refill_type, COUNT(*) as count
                FROM stores 
                WHERE refill_type != ''
                GROUP BY refill_type
                ORDER BY count DESC
            """)
            refill_type_stats = cursor.fetchall()
            
            # 지역별 통계 (주소 기반)
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN address LIKE '%강남%' THEN '강남'
                        WHEN address LIKE '%홍대%' OR address LIKE '%마포%' THEN '홍대/마포'
                        WHEN address LIKE '%강북%' THEN '강북'
                        WHEN address LIKE '%서울%' THEN '기타 서울'
                        ELSE '기타'
                    END as region,
                    COUNT(*) as count
                FROM stores
                GROUP BY region
                ORDER BY count DESC
            """)
            region_stats = cursor.fetchall()
            
            # 최근 크롤링 세션 통계
            cursor.execute("""
                SELECT 
                    keyword,
                    rect_area,
                    stores_found,
                    stores_processed,
                    created_at
                FROM crawling_logs
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_sessions = cursor.fetchall()
            
            stats = {
                'basic_stats': dict(basic_stats),
                'refill_type_stats': [dict(row) for row in refill_type_stats],
                'region_stats': [dict(row) for row in region_stats],
                'recent_sessions': [dict(row) for row in recent_sessions]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
        finally:
            cursor.close()
    
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