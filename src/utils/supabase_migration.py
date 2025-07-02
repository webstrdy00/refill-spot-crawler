"""
Supabase를 위한 크롤링 데이터 마이그레이션 시스템
"""
import psycopg2
import psycopg2.extras
import logging
import json
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Union
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import datetime

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supabase_migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SupabaseMigration:
    """Supabase를 위한 데이터 마이그레이션 클래스"""
    
    def __init__(self, supabase_project_id: str = None, crawler_db_config: Union[Dict, str] = None):
        self.supabase_project_id = supabase_project_id or "ykztepbfcocxmtotrdbk"
        
        # 크롤러 DB 연결 설정
        if crawler_db_config is None:
            crawler_db_config = os.getenv('DATABASE_URL', 
                                         'postgresql://postgres:12345@localhost:5432/refill_spot_crawler')
        
        # 크롤러 DB 연결
        self.crawler_conn = self._create_crawler_connection(crawler_db_config)
        
        logger.info(f"Supabase 마이그레이션 시스템 초기화 완료 (프로젝트 ID: {self.supabase_project_id})")
    
    def _create_crawler_connection(self, db_config: Union[Dict, str]):
        """크롤러 DB 연결 생성"""
        try:
            if isinstance(db_config, str):
                parsed = urlparse(db_config)
                config = {
                    'host': parsed.hostname,
                    'port': parsed.port or 5432,
                    'database': parsed.path[1:] if parsed.path else 'postgres',
                    'user': parsed.username,
                    'password': parsed.password
                }
            else:
                config = db_config
            
            return psycopg2.connect(**config)
            
        except Exception as e:
            logger.error(f"크롤러 DB 연결 실패: {e}")
            raise
    
    def get_crawler_stores(self, limit: Optional[int] = None) -> List[Dict]:
        """크롤러 DB에서 가게 데이터 조회"""
        try:
            cursor = self.crawler_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            query = """
                SELECT 
                    s.*,
                    s.raw_categories_diningcode as category_names
                FROM stores s
                WHERE (s.status = 'open' OR s.status = '운영중')
                AND s.position_lat IS NOT NULL 
                AND s.position_lng IS NOT NULL
                AND s.position_lat BETWEEN 37.4 AND 37.7
                AND s.position_lng BETWEEN 126.8 AND 127.2
                ORDER BY s.created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            stores = cursor.fetchall()
            
            logger.info(f"크롤러 DB에서 {len(stores)}개 가게 조회 완료")
            return [dict(store) for store in stores]
            
        except Exception as e:
            logger.error(f"크롤러 데이터 조회 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def process_store_data(self, store: Dict) -> Dict:
        """크롤러 데이터를 Supabase 형식으로 가공"""
        try:
            # 기본 정보 검증
            name = store.get('name', '').strip()
            address = store.get('address', '').strip()
            
            if not name or not address:
                raise ValueError("가게명 또는 주소가 없습니다")
            
            # 위치 정보 처리
            position_lat = float(store['position_lat'])
            position_lng = float(store['position_lng'])
            position_x = float(store.get('position_x', position_lng))
            position_y = float(store.get('position_y', position_lat))
            
            # 서울시 범위 검증
            if not (37.4 <= position_lat <= 37.7 and 126.8 <= position_lng <= 127.2):
                raise ValueError("서울시 범위를 벗어난 좌표입니다")
            
            return {
                'name': name,
                'address': address,
                'description': self._generate_description(store),
                'position_lat': position_lat,
                'position_lng': position_lng,
                'position_x': position_x,
                'position_y': position_y,
                'naver_rating': self._safe_float(store.get('naver_rating')),
                'kakao_rating': self._safe_float(store.get('kakao_rating')),
                'open_hours': self._process_open_hours(store),
                'price': self._process_price(store),
                'refill_items': self._process_refill_items(store),
                'image_urls': self._process_image_urls(store),
                'categories': self._map_categories(store.get('category_names', []))
            }
            
        except Exception as e:
            logger.error(f"데이터 가공 실패 ({store.get('name', 'Unknown')}): {e}")
            raise
    
    def _safe_float(self, value) -> Optional[float]:
        """안전한 float 변환"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _process_price(self, store: Dict) -> Optional[str]:
        """가격 정보 가공"""
        price_fields = ['price', 'average_price', 'price_range']
        
        for field in price_fields:
            value = store.get(field)
            if value:
                return str(value).strip()
        
        return None
    
    def _process_refill_items(self, store: Dict) -> List[str]:
        """무한리필 아이템 가공"""
        items = set()
        
        # 기존 refill_items 필드
        if store.get('refill_items'):
            if isinstance(store['refill_items'], list):
                items.update(store['refill_items'])
            elif isinstance(store['refill_items'], str):
                items.add(store['refill_items'])
        
        # refill_type에서 추출
        if store.get('refill_type'):
            refill_type = store['refill_type']
            match = re.search(r'(.+?)\s*무한리필', refill_type)
            if match:
                item = match.group(1).strip()
                if item:
                    items.add(item)
        
        # 정리 및 필터링
        filtered_items = []
        for item in items:
            if item and len(item.strip()) > 0:
                filtered_items.append(item.strip())
        
        return filtered_items[:10]
    
    def _process_image_urls(self, store: Dict) -> List[str]:
        """이미지 URL 검증 및 필터링 (대표 이미지만)"""
        urls = []
        
        # 로컬 대표 이미지 우선 사용
        if store.get('main_image_local'):
            urls.append(store['main_image_local'])
            logger.info(f"로컬 대표 이미지 사용: {os.path.basename(store['main_image_local'])}")
        elif store.get('main_image'):
            urls.append(store['main_image'])
            logger.info("원본 대표 이미지 URL 사용")
        
        # URL 검증 및 중복 제거
        valid_urls = []
        seen = set()
        
        for url in urls:
            if url and url not in seen:
                # 로컬 파일 경로이거나 기본적인 URL 검증
                if (url.startswith(('data/', 'data\\', '/')) or 
                    url.startswith(('http://', 'https://', '//'))):
                    valid_urls.append(url)
                    seen.add(url)
        
        return valid_urls[:1]  # 대표 이미지 1개만
    
    def _process_open_hours(self, store: Dict) -> Optional[str]:
        """영업시간 정보 정리"""
        open_hours = store.get('open_hours') or store.get('open_hours_raw')
        
        if not open_hours:
            return None
        
        # 라스트오더는 이미 open_hours에 포함되어 있으므로 중복 추가하지 않음
        parts = [str(open_hours)]
        
        if store.get('break_time'):
            parts.append(f"브레이크타임: {store['break_time']}")
        
        if store.get('holiday'):
            parts.append(f"휴무: {store['holiday']}")
        
        return ' / '.join(parts)
    
    def _generate_description(self, store: Dict) -> str:
        """가게 설명 생성"""
        parts = []
        
        if store.get('description'):
            parts.append(str(store['description']))
        
        if store.get('refill_type'):
            parts.append(f"{store['refill_type']} 전문점")
        
        result = ' | '.join(filter(None, parts))
        return result[:500] if result else f"{store.get('name', '')} 무한리필 전문점"
    
    def _map_categories(self, crawler_categories: List[str]) -> List[str]:
        """크롤러 카테고리를 표준 카테고리로 매핑"""
        if not crawler_categories:
            return ['무한리필']
        
        category_mapping = {
            '무한리필': '무한리필',
            '고기무한리필': '고기',
            '소고기무한리필': '고기', 
            '삼겹살무한리필': '고기',
            '삼겹살': '고기',
            '갈비': '고기',
            '뷔페': '뷔페',
            '초밥뷔페': '일식',
            '해산물무한리필': '해산물',
            '한식': '한식',
            '일식': '일식',
            '중식': '중식',
            '양식': '양식',
            '피자': '피자',
            '치킨': '치킨'
        }
        
        mapped_categories = set()
        
        for cat in crawler_categories:
            if not cat:
                continue
                
            cat = str(cat).strip()
            
            if cat in category_mapping:
                mapped_categories.add(category_mapping[cat])
            else:
                for key, value in category_mapping.items():
                    if key in cat or cat in key:
                        mapped_categories.add(value)
                        break
        
        # 무한리필 관련 카테고리 보장
        if any('무한' in str(cat) or '리필' in str(cat) for cat in crawler_categories):
            mapped_categories.add('무한리필')
        
        if not mapped_categories:
            mapped_categories.add('무한리필')
        
        return list(mapped_categories)
    
    def generate_sql_statements(self, limit: Optional[int] = None) -> List[str]:
        """Supabase 삽입용 SQL 문 생성"""
        try:
            stores = self.get_crawler_stores(limit)
            sql_statements = []
            
            for store in stores:
                try:
                    processed_data = self.process_store_data(store)
                    
                    # 카테고리 삽입 SQL
                    for category in processed_data['categories']:
                        category_sql = f"""
INSERT INTO categories (name) VALUES ('{category}') ON CONFLICT (name) DO NOTHING;"""
                        sql_statements.append(category_sql)
                    
                    # 가게 삽입 SQL
                    refill_items_array = "ARRAY[" + ",".join([f"'{item.replace("'", "''")}'" for item in processed_data['refill_items']]) + "]"
                    image_urls_array = "ARRAY[" + ",".join([f"'{url.replace("'", "''")}'" for url in processed_data['image_urls']]) + "]"
                    
                    store_sql = f"""
INSERT INTO stores (
    name, address, description, 
    position_lat, position_lng, position_x, position_y,
    naver_rating, kakao_rating, open_hours, 
    price, refill_items, image_urls
) VALUES (
    '{processed_data['name'].replace("'", "''")}',
    '{processed_data['address'].replace("'", "''")}',
    '{processed_data['description'].replace("'", "''")}',
    {processed_data['position_lat']},
    {processed_data['position_lng']},
    {processed_data['position_x']},
    {processed_data['position_y']},
    {processed_data['naver_rating'] if processed_data['naver_rating'] else 'NULL'},
    {processed_data['kakao_rating'] if processed_data['kakao_rating'] else 'NULL'},
    {f"'{processed_data['open_hours'].replace("'", "''")}'" if processed_data['open_hours'] else 'NULL'},
    {f"'{processed_data['price'].replace("'", "''")}'" if processed_data['price'] else 'NULL'},
    {refill_items_array},
    {image_urls_array}
);"""
                    sql_statements.append(store_sql)
                    
                except Exception as e:
                    logger.error(f"SQL 생성 실패 ({store.get('name', 'Unknown')}): {e}")
                    continue
            
            logger.info(f"총 {len(sql_statements)}개 SQL 문 생성 완료")
            return sql_statements
            
        except Exception as e:
            logger.error(f"SQL 생성 실패: {e}")
            raise
    
    def close(self):
        """연결 종료"""
        if self.crawler_conn:
            self.crawler_conn.close()


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Supabase 데이터 마이그레이션')
    parser.add_argument('--limit', type=int, help='마이그레이션할 가게 수 제한')
    parser.add_argument('--generate-sql', action='store_true', help='SQL 문만 생성')
    parser.add_argument('--output', help='SQL 출력 파일명')
    
    args = parser.parse_args()
    
    migration = SupabaseMigration()
    
    try:
        if args.generate_sql:
            sql_statements = migration.generate_sql_statements(args.limit)
            
            output_file = args.output or 'supabase_migration.sql'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("-- Supabase 마이그레이션 SQL\n")
                f.write(f"-- 생성일: {datetime.now()}\n\n")
                f.write("\n".join(sql_statements))
            
            logger.info(f"SQL 파일 생성 완료: {output_file}")
        else:
            logger.info("일반 마이그레이션 모드는 추후 구현 예정")
            
    except Exception as e:
        logger.error(f"실행 실패: {e}")
        raise
    finally:
        migration.close()


if __name__ == "__main__":
    main() 