"""
크롤링 데이터를 프로젝트 DB로 마이그레이션하는 스크립트
"""
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Optional, Union
import json
import re
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataMigration:
    def __init__(self, crawler_db_config: Union[Dict, str] = None, project_db_config: Union[Dict, str] = None):
        """
        Args:
            crawler_db_config: 크롤러 DB 연결 정보 (dict 또는 DATABASE_URL 문자열)
            project_db_config: 프로젝트 DB 연결 정보 (dict 또는 DATABASE_URL 문자열)
        """
        # 크롤러 DB 연결 설정 (기존 DATABASE_URL 사용)
        if crawler_db_config is None:
            crawler_db_config = os.getenv('DATABASE_URL', 
                                         'postgresql://postgres:12345@localhost:5432/refill_spot_crawler')
        
        # 프로젝트 DB 연결 설정 (새로운 PROJECT_DATABASE_URL 사용)
        if project_db_config is None:
            project_db_config = os.getenv('PROJECT_DATABASE_URL',
                                         'postgresql://postgres:your_password@localhost:5432/refill_spot')
        
        # 연결 정보 파싱 및 연결
        self.crawler_conn = self._create_connection(crawler_db_config, "크롤러 DB")
        self.project_conn = self._create_connection(project_db_config, "프로젝트 DB")
    
    def _create_connection(self, db_config: Union[Dict, str], db_name: str):
        """DB 연결 생성"""
        try:
            if isinstance(db_config, str):
                # DATABASE_URL 형식 파싱
                parsed = urlparse(db_config)
                config = {
                    'host': parsed.hostname,
                    'port': parsed.port or 5432,
                    'database': parsed.path[1:] if parsed.path else 'postgres',
                    'user': parsed.username,
                    'password': parsed.password
                }
                logger.info(f"{db_name} 연결: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
            else:
                # Dictionary 형식
                config = db_config
                logger.info(f"{db_name} 연결: {config.get('user')}@{config.get('host')}:{config.get('port')}/{config.get('database')}")
            
            return psycopg2.connect(**config)
            
        except Exception as e:
            logger.error(f"{db_name} 연결 실패: {e}")
            raise
        
    def migrate_stores(self, limit: Optional[int] = None):
        """크롤러 DB에서 프로젝트 DB로 가게 정보 마이그레이션"""
        try:
            # 1. 크롤러 DB에서 데이터 조회
            crawler_cursor = self.crawler_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            query = """
                SELECT 
                    s.*,
                    array_agg(DISTINCT c.name) as category_names
                FROM stores s
                LEFT JOIN store_categories sc ON s.id = sc.store_id
                LEFT JOIN categories c ON sc.category_id = c.id
                WHERE s.status = '운영중'
                AND s.position_lat IS NOT NULL 
                AND s.position_lng IS NOT NULL
                AND s.position_lat != 0
                AND s.position_lng != 0
                GROUP BY s.id
                ORDER BY s.created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            crawler_cursor.execute(query)
            stores = crawler_cursor.fetchall()
            
            logger.info(f"크롤러 DB에서 {len(stores)}개 가게 조회 완료")
            
            # 2. 데이터 가공 및 프로젝트 DB에 삽입
            project_cursor = self.project_conn.cursor()
            
            success_count = 0
            for store in stores:
                try:
                    # 데이터 가공
                    processed_data = self._process_store_data(store)
                    
                    # 프로젝트 DB에 삽입
                    self._insert_to_project_db(project_cursor, processed_data)
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"가게 마이그레이션 실패 ({store['name']}): {e}")
                    continue
            
            self.project_conn.commit()
            logger.info(f"마이그레이션 완료: {success_count}/{len(stores)}개 성공")
            
        except Exception as e:
            logger.error(f"마이그레이션 실패: {e}")
            self.project_conn.rollback()
            raise
            
        finally:
            crawler_cursor.close()
            project_cursor.close()
    
    def _process_store_data(self, store: Dict) -> Dict:
        """크롤러 데이터를 프로젝트 DB 형식으로 가공"""
        
        # 1. 가격 정보 가공
        price = self._process_price(store)
        
        # 2. 무한리필 아이템 가공
        refill_items = self._process_refill_items(store)
        
        # 3. 이미지 URL 검증 및 필터링
        image_urls = self._process_image_urls(store)
        
        # 4. 영업시간 정보 정리
        open_hours = self._process_open_hours(store)
        
        # 5. 평점 정보 통합
        naver_rating = store.get('naver_rating')
        kakao_rating = store.get('kakao_rating')
        diningcode_rating = store.get('diningcode_rating')
        
        # 6. 카테고리 매핑
        category_names = store.get('category_names') or []
        # None 값이나 [None] 배열 처리
        if category_names and category_names[0] is None:
            category_names = []
        categories = self._map_categories(category_names)
        
        # 좌표 검증 및 변환
        try:
            position_lat = float(store['position_lat']) if store.get('position_lat') else None
            position_lng = float(store['position_lng']) if store.get('position_lng') else None
            
            if position_lat is None or position_lng is None:
                raise ValueError("좌표 정보가 없습니다")
                
            # position_x, position_y가 None인 경우 lat/lng 값을 사용
            position_x = float(store['position_x']) if store.get('position_x') is not None else position_lng
            position_y = float(store['position_y']) if store.get('position_y') is not None else position_lat
            
        except (ValueError, TypeError) as e:
            raise ValueError(f"좌표 변환 실패: {e}")
        
        return {
            'name': store['name'],
            'address': store.get('address', ''),
            'description': self._generate_description(store),
            'position_lat': position_lat,
            'position_lng': position_lng,
            'position_x': position_x,
            'position_y': position_y,
            'naver_rating': float(naver_rating) if naver_rating else None,
            'kakao_rating': float(kakao_rating) if kakao_rating else None,
            'open_hours': open_hours,
            'price': price,
            'refill_items': refill_items,
            'image_urls': image_urls,
            'categories': categories
        }
    
    def _process_price(self, store: Dict) -> Optional[str]:
        """가격 정보 가공"""
        # 우선순위: price > average_price > price_range
        if store.get('price'):
            return str(store['price'])
        elif store.get('average_price'):
            return store['average_price']
        elif store.get('price_range'):
            return store['price_range']
        elif store.get('price_details'):
            # price_details 배열에서 첫 번째 가격 정보 추출
            details = store['price_details']
            if isinstance(details, list) and len(details) > 0:
                return details[0]
        return None
    
    def _process_refill_items(self, store: Dict) -> List[str]:
        """무한리필 아이템 가공"""
        items = []
        
        # refill_items 필드
        if store.get('refill_items'):
            items.extend(store['refill_items'])
        
        # refill_type에서 추가 정보 추출
        if store.get('refill_type'):
            refill_type = store['refill_type']
            # "고기 무한리필", "삼겹살 무한리필" 등에서 아이템 추출
            match = re.search(r'(.+?)\s*무한리필', refill_type)
            if match:
                item = match.group(1).strip()
                if item and item not in items:
                    items.append(item)
        
        # 메뉴에서 무한리필 관련 아이템 추출
        if store.get('menu_items'):
            try:
                menu_items = store['menu_items']
                if isinstance(menu_items, str):
                    menu_items = json.loads(menu_items)
                
                for item in menu_items:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        if '무한' in name or '리필' in name:
                            items.append(name)
            except:
                pass
        
        # 중복 제거 및 정리
        return list(set(filter(None, items)))[:10]  # 최대 10개까지
    
    def _process_image_urls(self, store: Dict) -> List[str]:
        """이미지 URL 검증 및 필터링"""
        urls = []
        
        # main_image
        if store.get('main_image'):
            urls.append(store['main_image'])
        
        # image_urls
        if store.get('image_urls'):
            urls.extend(store['image_urls'])
        
        # menu_images
        if store.get('menu_images'):
            urls.extend(store['menu_images'])
        
        # interior_images (최대 2개만)
        if store.get('interior_images'):
            urls.extend(store['interior_images'][:2])
        
        # URL 검증 및 중복 제거
        valid_urls = []
        seen = set()
        
        for url in urls:
            if url and url not in seen:
                # 기본적인 URL 검증
                if url.startswith(('http://', 'https://', '//')):
                    valid_urls.append(url)
                    seen.add(url)
        
        return valid_urls[:5]  # 최대 5개까지
    
    def _process_open_hours(self, store: Dict) -> Optional[str]:
        """영업시간 정보 정리"""
        # 우선순위: open_hours > open_hours_raw
        open_hours = store.get('open_hours') or store.get('open_hours_raw')
        
        if not open_hours:
            return None
        
        # 추가 정보 포함 (라스트오더는 크롤링 단계에서 이미 포함되어 있으므로 제외)
        parts = [open_hours]
        
        if store.get('break_time'):
            parts.append(f"브레이크타임: {store['break_time']}")
        
        # 라스트오더는 이미 open_hours에 포함되어 있으므로 중복 추가하지 않음
        # if store.get('last_order'):
        #     parts.append(f"라스트오더: {store['last_order']}")
        
        if store.get('holiday'):
            parts.append(f"휴무: {store['holiday']}")
        
        return ' / '.join(parts)
    
    def _generate_description(self, store: Dict) -> str:
        """가게 설명 생성"""
        parts = []
        
        # 기본 설명
        if store.get('description'):
            parts.append(store['description'])
        
        # 무한리필 정보
        if store.get('refill_type'):
            parts.append(f"{store['refill_type']} 전문점")
        
        if store.get('refill_conditions'):
            parts.append(f"리필 조건: {store['refill_conditions']}")
        
        # 분위기
        if store.get('atmosphere'):
            parts.append(f"분위기: {store['atmosphere']}")
        
        # 리뷰 요약
        if store.get('review_summary'):
            parts.append(store['review_summary'])
        
        # 키워드
        if store.get('keywords'):
            keywords = store['keywords'][:5]  # 최대 5개
            parts.append(f"키워드: {', '.join(keywords)}")
        
        return ' | '.join(parts)[:500]  # 최대 500자
    
    def _map_categories(self, crawler_categories: List[str]) -> List[str]:
        """크롤러 카테고리를 프로젝트 카테고리로 매핑"""
        # None 값 처리
        if not crawler_categories:
            return ['무한리필']  # 기본 카테고리
        
        # 카테고리 매핑 테이블
        category_mapping = {
            '무한리필': '무한리필',
            '고기무한리필': '고기',
            '소고기무한리필': '고기',
            '삼겹살무한리필': '고기',
            '삼겹살': '고기',
            '갈비': '고기',
            '뷔페': '뷔페',
            '초밥뷔페': '일식',
            '초밥': '일식',
            '해산물무한리필': '해산물',
            '해산물': '해산물',
            '한식': '한식',
            '일식': '일식',
            '중식': '중식',
            '양식': '양식',
            '피자': '피자',
            '치킨': '치킨',
            '족발': '족발',
            '곱창': '곱창',
            '스테이크': '스테이크',
            '파스타': '파스타',
            '디저트': '디저트',
            '카페': '카페',
            '브런치': '브런치',
            '샐러드': '샐러드',
            '분식': '분식',
            '찜닭': '찜닭',
            '버거': '버거'
        }
        
        mapped_categories = set()
        
        for cat in crawler_categories:
            if cat and cat is not None:  # None 체크 추가
                # 정확한 매칭
                if cat in category_mapping:
                    mapped_categories.add(category_mapping[cat])
                # 부분 매칭
                else:
                    for key, value in category_mapping.items():
                        if key in cat or cat in key:
                            mapped_categories.add(value)
                            break
        
        # 무한리필 관련 카테고리가 있으면 '무한리필' 추가
        if any('무한' in str(cat) or '리필' in str(cat) for cat in crawler_categories if cat):
            mapped_categories.add('무한리필')
        
        # 카테고리가 없으면 기본 카테고리 추가
        if not mapped_categories:
            mapped_categories.add('무한리필')
        
        return list(mapped_categories)
    
    def _insert_to_project_db(self, cursor, data: Dict):
        """프로젝트 DB에 데이터 삽입"""
        # 1. 카테고리 확인 및 생성
        category_ids = []
        for category_name in data['categories']:
            cursor.execute(
                "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (category_name,)
            )
            cursor.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
            result = cursor.fetchone()
            if result:
                category_ids.append(result[0])
        
        # 2. 가게 정보 삽입
        cursor.execute("""
            INSERT INTO stores (
                name, address, description, 
                position_lat, position_lng, position_x, position_y,
                naver_rating, kakao_rating, open_hours, 
                price, refill_items, image_urls, geom
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            ) RETURNING id
        """, (
            data['name'], data['address'], data['description'],
            data['position_lat'], data['position_lng'], 
            data['position_x'], data['position_y'],
            data['naver_rating'], data['kakao_rating'], data['open_hours'],
            data['price'], data['refill_items'], data['image_urls'],
            data['position_lng'], data['position_lat']  # geom 필드를 위한 좌표
        ))
        
        store_id = cursor.fetchone()[0]
        
        # 3. 가게-카테고리 연결
        for category_id in category_ids:
            cursor.execute(
                "INSERT INTO store_categories (store_id, category_id) VALUES (%s, %s)",
                (store_id, category_id)
            )
        
        logger.info(f"가게 삽입 완료: {data['name']} (ID: {store_id})")
    
    def close(self):
        """연결 종료"""
        self.crawler_conn.close()
        self.project_conn.close()


def create_migration_from_env():
    """환경변수에서 마이그레이션 객체 생성"""
    return DataMigration()

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='크롤링 데이터 마이그레이션')
    parser.add_argument('--limit', type=int, help='마이그레이션할 가게 수 제한')
    parser.add_argument('--test', action='store_true', help='테스트 모드 (10개만 마이그레이션)')
    parser.add_argument('--crawler-db', help='크롤러 DB URL (기본값: 환경변수 DATABASE_URL)')
    parser.add_argument('--project-db', help='프로젝트 DB URL (기본값: 환경변수 PROJECT_DATABASE_URL)')
    
    args = parser.parse_args()
    
    # 마이그레이션 객체 생성
    migration = DataMigration(
        crawler_db_config=args.crawler_db,
        project_db_config=args.project_db
    )
    
    try:
        if args.test:
            logger.info("🧪 테스트 모드: 10개 가게만 마이그레이션")
            migration.migrate_stores(limit=10)
        elif args.limit:
            logger.info(f"📊 제한 모드: {args.limit}개 가게 마이그레이션")
            migration.migrate_stores(limit=args.limit)
        else:
            logger.info("🚀 전체 마이그레이션 시작")
            migration.migrate_stores()
            
    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}")
        raise
    finally:
        migration.close()

# 사용 예시
if __name__ == "__main__":
    main() 