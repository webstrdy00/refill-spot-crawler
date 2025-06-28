#!/usr/bin/env python3
"""
안전한 마이그레이션: 크롤링 DB → 메인 프로젝트 DB
크롤링 DB 스키마 변경 없이 메인 프로젝트 스키마에 맞게 데이터 변환
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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('safe_migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SafeMigration:
    """안전한 데이터 마이그레이션 클래스"""
    
    def __init__(self, main_project_db_url: str = None, crawler_db_url: str = None):
        # 크롤링 DB 연결 (기존 그대로)
        self.crawler_db_url = crawler_db_url or 'postgresql://postgres:12345@localhost:5432/refill_spot'
        
        # 메인 프로젝트 DB 연결 (Supabase 또는 별도 DB)
        self.main_project_db_url = os.getenv('PROJECT_DATABASE_URL')
        
        # 크롤링 DB 연결
        self.crawler_conn = self._create_connection(self.crawler_db_url)
        logger.info("크롤링 DB 연결 완료")
        
        # 메인 프로젝트 스키마 정의 (변경하지 않을 원본 스키마)
        self.main_schema = {
            'required_fields': ['name', 'address', 'position_lat', 'position_lng', 'position_x', 'position_y'],
            'optional_fields': ['description', 'naver_rating', 'kakao_rating', 'open_hours', 'price', 'refill_items', 'image_urls'],
            'data_types': {
                'name': 'text',
                'address': 'text', 
                'description': 'text',
                'position_lat': 'double precision',
                'position_lng': 'double precision',
                'position_x': 'double precision',
                'position_y': 'double precision',
                'naver_rating': 'double precision',
                'kakao_rating': 'double precision',
                'open_hours': 'text',
                'price': 'text',
                'refill_items': 'text[]',
                'image_urls': 'text[]'
            }
        }
    
    def _create_connection(self, db_url: str):
        """DB 연결 생성"""
        try:
            parsed = urlparse(db_url)
            config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:] if parsed.path else 'postgres',
                'user': parsed.username,
                'password': parsed.password
            }
            return psycopg2.connect(**config)
        except Exception as e:
            logger.error(f"DB 연결 실패 ({db_url}): {e}")
            raise
    
    def get_crawler_stores(self, limit: Optional[int] = None) -> List[Dict]:
        """크롤링 DB에서 데이터 조회 (기존 크롤링 스키마 그대로 사용)"""
        try:
            cursor = self.crawler_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 크롤링 DB의 실제 스키마에 맞는 쿼리
            query = """
                SELECT 
                    s.*
                FROM stores s
                WHERE s.name IS NOT NULL 
                AND s.name != ''
                ORDER BY s.created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            stores = cursor.fetchall()
            
            logger.info(f"크롤링 DB에서 {len(stores)}개 가게 조회 완료")
            return [dict(store) for store in stores]
            
        except Exception as e:
            logger.error(f"크롤링 데이터 조회 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def convert_to_main_schema(self, crawler_store: Dict) -> Dict:
        """크롤링 데이터를 메인 프로젝트 스키마에 맞게 안전하게 변환"""
        try:
            converted = {}
            
            # 1. 필수 필드 처리 (메인 프로젝트 NOT NULL 필드들)
            converted['name'] = self._safe_text(crawler_store.get('name'), '무한리필 가게')
            converted['address'] = self._safe_text(crawler_store.get('address'), '주소 정보 없음')
            
            # 2. 위치 정보 처리 (메인 프로젝트 NOT NULL)
            converted['position_lat'] = self._safe_coordinate(crawler_store.get('position_lat'), 37.5665)  # 서울시청
            converted['position_lng'] = self._safe_coordinate(crawler_store.get('position_lng'), 126.9780)
            converted['position_x'] = self._safe_coordinate(crawler_store.get('position_x'), converted['position_lng'])
            converted['position_y'] = self._safe_coordinate(crawler_store.get('position_y'), converted['position_lat'])
            
            # 3. 선택적 필드 처리
            converted['description'] = self._generate_description(crawler_store)
            converted['naver_rating'] = self._safe_float(crawler_store.get('naver_rating'))
            converted['kakao_rating'] = self._safe_float(crawler_store.get('kakao_rating'))
            converted['open_hours'] = self._process_open_hours(crawler_store)
            converted['price'] = self._process_price(crawler_store)
            converted['refill_items'] = self._process_refill_items(crawler_store)
            converted['image_urls'] = self._process_image_urls(crawler_store)
            
            # 4. 데이터 검증
            self._validate_converted_data(converted)
            
            return converted
            
        except Exception as e:
            logger.error(f"데이터 변환 실패 ({crawler_store.get('name', 'Unknown')}): {e}")
            raise
    
    def _safe_text(self, value, default: str = '') -> str:
        """안전한 텍스트 변환"""
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default
    
    def _safe_coordinate(self, value, default: float) -> float:
        """안전한 좌표 변환"""
        if value is None:
            return default
        try:
            coord = float(value)
            # 서울시 범위 검증
            if 37.4 <= coord <= 37.7 or 126.8 <= coord <= 127.2:
                return coord
            return default
        except (ValueError, TypeError):
            return default
    
    def _safe_float(self, value) -> Optional[float]:
        """안전한 float 변환"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _generate_description(self, store: Dict) -> Optional[str]:
        """설명 생성 (크롤링 데이터의 풍부한 정보를 요약)"""
        parts = []
        
        # 기본 설명
        if store.get('description'):
            parts.append(str(store['description']))
        
        # 무한리필 정보
        if store.get('refill_type'):
            parts.append(f"{store['refill_type']} 전문점")
        
        # 분위기 정보
        if store.get('atmosphere'):
            parts.append(f"분위기: {store['atmosphere']}")
        
        # 키워드 정보
        if store.get('keywords') and isinstance(store['keywords'], list):
            keywords = [str(k) for k in store['keywords'][:3]]  # 상위 3개만
            if keywords:
                parts.append(f"특징: {', '.join(keywords)}")
        
        result = ' | '.join(filter(None, parts))
        return result[:500] if result else None
    
    def _process_open_hours(self, store: Dict) -> Optional[str]:
        """영업시간 정보 통합"""
        hours_info = []
        
        if store.get('open_hours'):
            hours_info.append(str(store['open_hours']))
        elif store.get('open_hours_raw'):
            hours_info.append(str(store['open_hours_raw']))
        
        if store.get('break_time'):
            hours_info.append(f"브레이크타임: {store['break_time']}")
        
        if store.get('holiday'):
            hours_info.append(f"휴무: {store['holiday']}")
        
        return ' / '.join(hours_info) if hours_info else None
    
    def _process_price(self, store: Dict) -> Optional[str]:
        """가격 정보 처리 (메인 프로젝트는 text 타입)"""
        # 크롤링 DB의 다양한 가격 필드에서 정보 수집
        price_sources = [
            store.get('price'),
            store.get('average_price'),
            store.get('price_range')
        ]
        
        for price in price_sources:
            if price:
                return str(price).strip()
        
        # price_details 배열에서 추출
        if store.get('price_details') and isinstance(store['price_details'], list):
            details = [str(p) for p in store['price_details'] if p]
            if details:
                return ', '.join(details[:3])  # 상위 3개만
        
        return None
    
    def _process_refill_items(self, store: Dict) -> List[str]:
        """무한리필 아이템 처리"""
        items = set()
        
        # 기존 refill_items 필드
        if store.get('refill_items'):
            if isinstance(store['refill_items'], list):
                items.update([str(item) for item in store['refill_items'] if item])
            elif isinstance(store['refill_items'], str):
                items.add(store['refill_items'])
        
        # refill_type에서 추출
        if store.get('refill_type'):
            refill_type = str(store['refill_type'])
            # "소고기 무한리필" -> "소고기" 추출
            match = re.search(r'(.+?)\s*무한리필', refill_type)
            if match:
                item = match.group(1).strip()
                if item:
                    items.add(item)
        
        # 정리 및 필터링
        filtered_items = []
        for item in items:
            if item and len(str(item).strip()) > 0:
                filtered_items.append(str(item).strip())
        
        return filtered_items[:10]  # 최대 10개로 제한
    
    def _process_image_urls(self, store: Dict) -> List[str]:
        """이미지 URL 처리"""
        urls = set()
        
        # 다양한 이미지 필드에서 수집
        image_fields = ['main_image', 'image_urls', 'menu_images', 'interior_images']
        
        for field in image_fields:
            value = store.get(field)
            if value:
                if isinstance(value, list):
                    urls.update([str(url) for url in value if url])
                elif isinstance(value, str):
                    urls.add(value)
        
        # URL 검증 및 필터링
        valid_urls = []
        for url in urls:
            if url and str(url).startswith(('http://', 'https://')):
                valid_urls.append(str(url))
        
        return valid_urls[:5]  # 최대 5개로 제한
    
    def _validate_converted_data(self, data: Dict):
        """변환된 데이터 검증"""
        # 필수 필드 검증
        for field in self.main_schema['required_fields']:
            if field not in data or data[field] is None:
                raise ValueError(f"필수 필드 누락: {field}")
        
        # 위치 좌표 유효성 검증
        lat, lng = data['position_lat'], data['position_lng']
        if not (37.0 <= lat <= 38.0 and 126.0 <= lng <= 128.0):
            logger.warning(f"좌표 범위 이상: lat={lat}, lng={lng}")
    
    def generate_migration_sql(self, limit: Optional[int] = None) -> List[str]:
        """메인 프로젝트용 마이그레이션 SQL 생성"""
        try:
            stores = self.get_crawler_stores(limit)
            sql_statements = []
            
            logger.info(f"총 {len(stores)}개 가게 마이그레이션 시작")
            
            for i, store in enumerate(stores, 1):
                try:
                    # 안전한 데이터 변환
                    converted = self.convert_to_main_schema(store)
                    
                    # SQL 생성 (메인 프로젝트 스키마에 맞게)
                    refill_items_sql = self._array_to_sql(converted['refill_items'])
                    image_urls_sql = self._array_to_sql(converted['image_urls'])
                    
                    sql = f"""
INSERT INTO stores (
    name, address, description,
    position_lat, position_lng, position_x, position_y,
    naver_rating, kakao_rating, open_hours, price,
    refill_items, image_urls
) VALUES (
    {self._escape_sql_string(converted['name'])},
    {self._escape_sql_string(converted['address'])},
    {self._escape_sql_string(converted['description'])},
    {converted['position_lat']},
    {converted['position_lng']},
    {converted['position_x']},
    {converted['position_y']},
    {converted['naver_rating'] if converted['naver_rating'] else 'NULL'},
    {converted['kakao_rating'] if converted['kakao_rating'] else 'NULL'},
    {self._escape_sql_string(converted['open_hours'])},
    {self._escape_sql_string(converted['price'])},
    {refill_items_sql},
    {image_urls_sql}
);"""
                    
                    sql_statements.append(sql.strip())
                    
                    if i % 10 == 0:
                        logger.info(f"진행률: {i}/{len(stores)} ({i/len(stores)*100:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"가게 '{store.get('name', 'Unknown')}' 마이그레이션 실패: {e}")
                    continue
            
            logger.info(f"마이그레이션 SQL 생성 완료: {len(sql_statements)}개")
            return sql_statements
            
        except Exception as e:
            logger.error(f"마이그레이션 SQL 생성 실패: {e}")
            raise
    
    def _escape_sql_string(self, value) -> str:
        """SQL 문자열 이스케이프"""
        if value is None:
            return 'NULL'
        return f"'{str(value).replace(chr(39), chr(39)*2)}'"  # 작은따옴표 이스케이프
    
    def _array_to_sql(self, arr: List[str]) -> str:
        """배열을 SQL 형식으로 변환"""
        if not arr:
            return 'ARRAY[]::text[]'
        escaped_items = [f"'{item.replace(chr(39), chr(39)*2)}'" for item in arr]
        return f"ARRAY[{','.join(escaped_items)}]"
    
    def close(self):
        """연결 종료"""
        if self.crawler_conn:
            self.crawler_conn.close()

def main():
    """메인 실행 함수"""
    print("🔄 안전한 마이그레이션 시작")
    print("=" * 50)
    
    migration = SafeMigration()
    
    try:
        # 1. 미리보기
        print("👀 데이터 미리보기...")
        stores = migration.get_crawler_stores(limit=3)
        
        if not stores:
            print("❌ 크롤링 데이터가 없습니다.")
            return
        
        print(f"📊 총 {len(stores)}개 샘플 데이터 확인")
        for i, store in enumerate(stores, 1):
            converted = migration.convert_to_main_schema(store)
            print(f"{i}. {converted['name']}")
            print(f"   주소: {converted['address']}")
            print(f"   리필아이템: {', '.join(converted['refill_items'][:3])}")
            print()
        
        # 2. 전체 마이그레이션 SQL 생성
        print("📝 마이그레이션 SQL 생성 중...")
        sql_statements = migration.generate_migration_sql(limit=100)  # 테스트용 100개
        
        # 3. SQL 파일 저장
        output_file = "safe_migration.sql"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- 안전한 마이그레이션 SQL\n")
            f.write(f"-- 생성일: {datetime.now()}\n")
            f.write("-- 크롤링 DB → 메인 프로젝트 DB\n\n")
            f.write("\n\n".join(sql_statements))
        
        print(f"✅ 마이그레이션 SQL 생성 완료: {output_file}")
        print(f"📄 총 {len(sql_statements)}개 가게 데이터 준비됨")
        
        print("\n🔧 다음 단계:")
        print("1. safe_migration.sql 파일을 확인하세요")
        print("2. 메인 프로젝트 DB에서 실행하세요")
        print("3. 데이터 무결성을 검증하세요")
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        logger.error(f"마이그레이션 실패: {e}")
    finally:
        migration.close()
        print("\n🔚 마이그레이션 완료")

if __name__ == "__main__":
    main()