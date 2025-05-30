"""
다이닝코드 무한리필 가게 크롤링 메인 스크립트
1단계: MVP 테스트용
"""

import logging
import pandas as pd
from typing import List, Dict
import config
from crawler import DiningCodeCrawler
from database import DatabaseManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('refill_spot_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

"""
다이닝코드 무한리필 가게 크롤링 메인 스크립트
1단계: MVP 테스트용 (PostGIS 지원 버전)
"""

import logging
import pandas as pd
from typing import List, Dict
from collections import Counter
import config
from crawler import DiningCodeCrawler
from database import DatabaseManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('refill_spot_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process_crawled_data(stores_data: List[Dict]) -> List[Dict]:
    """크롤링된 데이터 정제 및 처리 (새 스키마 반영)"""
    processed_stores = []
    
    for store in stores_data:
        # 필수 필드 검증
        if not store.get('diningcode_place_id') or not store.get('name'):
            logger.warning(f"필수 필드 누락: {store}")
            continue
        
        # 무한리필 관련 키워드 확인
        is_refill = False
        refill_keywords = ['무한리필', '뷔페', '무제한', '리필']
        
        # 이름에서 확인
        for keyword in refill_keywords:
            if keyword in store.get('name', ''):
                is_refill = True
                break
        
        # 카테고리에서 확인
        categories = store.get('raw_categories_diningcode', [])
        for category in categories:
            for keyword in refill_keywords:
                if keyword in category:
                    is_refill = True
                    break
        
        # 검색 키워드 기반 확인
        search_keyword = store.get('keyword', '')
        if '무한리필' in search_keyword:
            is_refill = True
        
        if not is_refill:
            logger.warning(f"무한리필 관련성 없음: {store.get('name')}")
            continue
        
        # 좌표 유효성 검증 (필수 필드)
        lat = store.get('position_lat')
        lng = store.get('position_lng')
        
        if not lat or not lng:
            logger.warning(f"좌표 정보 없음: {store.get('name')}")
            continue
        
        try:
            lat = float(lat)
            lng = float(lng)
            # 한국 좌표 범위 확인 (대략적)
            if not (33 <= lat <= 39 and 124 <= lng <= 132):
                logger.warning(f"좌표 범위 벗어남: {store.get('name')} ({lat}, {lng})")
                continue
        except (ValueError, TypeError):
            logger.warning(f"좌표 변환 실패: {store.get('name')}")
            continue
        
        # 평점 처리 (diningcode_rating 필드 사용)
        rating = store.get('diningcode_rating')
        if rating:
            try:
                rating = float(rating)
                if not (0 <= rating <= 5):
                    rating = None
            except (ValueError, TypeError):
                rating = None
        
        # 정제된 데이터 구성 (새 스키마에 맞춤)
        processed_store = {
            'name': store.get('name', '').strip(),
            'address': store.get('address', '').strip(),
            'description': store.get('description', '').strip(),
            'position_lat': lat,
            'position_lng': lng,
            'position_x': None,  # 카카오맵 좌표 (나중에 추가)
            'position_y': None,  # 카카오맵 좌표 (나중에 추가)
            'naver_rating': None,  # 네이버 평점 (나중에 추가)
            'kakao_rating': None,  # 카카오 평점 (나중에 추가)
            'diningcode_rating': rating,
            'open_hours': store.get('open_hours', ''),
            'open_hours_raw': store.get('open_hours_raw', ''),
            'price': store.get('price'),
            'refill_items': store.get('refill_items', []),
            'image_urls': store.get('image_urls', []),
            'phone_number': store.get('phone_number', '').strip(),
            'diningcode_place_id': store.get('diningcode_place_id'),
            'raw_categories_diningcode': categories,
            'status': '운영중'
        }
        
        processed_stores.append(processed_store)
    
    logger.info(f"데이터 정제 완료: {len(stores_data)} -> {len(processed_stores)}")
    return processed_stores

def run_mvp_crawling():
    """MVP 크롤링 실행 (PostGIS 버전)"""
    crawler = None
    db = None
    
    try:
        logger.info("=== Refill Spot 크롤링 시작 (MVP - PostGIS) ===")
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        
        # 데이터베이스 초기화
        db = DatabaseManager()
        if not db.test_connection():
            logger.error("데이터베이스 연결 실패")
            return
        
        db.create_tables()
        
        all_stores = []
        
        # 기본 키워드로 크롤링
        for keyword in config.KEYWORDS[:2]:  # MVP에서는 처음 2개만
            logger.info(f"키워드 '{keyword}' 크롤링 시작")
            
            # 목록 수집
            stores = crawler.get_store_list(keyword, config.TEST_RECT)
            logger.info(f"키워드 '{keyword}': {len(stores)}개 가게 발견")
            
            if not stores:
                continue
            
            # 상세 정보 수집 (MVP에서는 처음 5개만)
            detailed_stores = []
            for i, store in enumerate(stores[:5]):  
                try:
                    logger.info(f"상세 정보 수집 {i+1}/{min(5, len(stores))}: {store.get('name')}")
                    detailed_store = crawler.get_store_detail(store)
                    detailed_stores.append(detailed_store)
                    
                except Exception as e:
                    logger.error(f"상세 정보 수집 실패: {store.get('name')} - {e}")
                    continue
            
            all_stores.extend(detailed_stores)
        
        if not all_stores:
            logger.warning("수집된 데이터가 없습니다")
            return
        
        # 데이터 정제
        processed_stores = process_crawled_data(all_stores)
        
        if not processed_stores:
            logger.warning("정제 후 유효한 데이터가 없습니다")
            return
        
        # CSV 저장
        df = pd.DataFrame(processed_stores)
        df.to_csv('mvp_crawling_result.csv', index=False, encoding='utf-8-sig')
        logger.info(f"CSV 저장 완료: mvp_crawling_result.csv ({len(processed_stores)}개 가게)")
        
        # 데이터베이스 저장 (키워드와 rect 정보 포함)
        db.save_crawled_data(processed_stores, keyword="무한리필", rect_area=config.TEST_RECT)
        logger.info("데이터베이스 저장 완료")
        
        # 결과 요약
        logger.info("=== 크롤링 결과 요약 ===")
        logger.info(f"총 수집 가게 수: {len(processed_stores)}")
        logger.info(f"좌표 있는 가게: {sum(1 for s in processed_stores if s['position_lat'])}")
        logger.info(f"전화번호 있는 가게: {sum(1 for s in processed_stores if s['phone_number'])}")
        logger.info(f"다이닝코드 평점 있는 가게: {sum(1 for s in processed_stores if s['diningcode_rating'])}")
        
        # 평점 통계
        ratings = [s['diningcode_rating'] for s in processed_stores if s['diningcode_rating']]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            logger.info(f"평균 다이닝코드 평점: {avg_rating:.2f}")
        
        # 카테고리 분포
        all_categories = []
        for store in processed_stores:
            all_categories.extend(store.get('raw_categories_diningcode', []))
        
        category_count = Counter(all_categories)
        logger.info("주요 카테고리:")
        for category, count in category_count.most_common(10):
            logger.info(f"  {category}: {count}개")
        
        # 데이터베이스 통계
        stats = db.get_crawling_stats()
        logger.info("=== 데이터베이스 전체 통계 ===")
        for key, value in stats.items():
            logger.info(f"{key}: {value}")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}")
        raise
        
    finally:
        if crawler:
            crawler.close()
        if db:
            db.close()
        logger.info("=== 크롤링 완료 ===")

def test_single_store():
    """단일 가게 테스트"""
    crawler = None
    
    try:
        logger.info("=== 단일 가게 테스트 ===")
        crawler = DiningCodeCrawler()
        
        # 목록에서 첫 번째 가게만
        stores = crawler.get_store_list("무한리필", config.TEST_RECT)
        if stores:
            first_store = stores[0]
            detailed_store = crawler.get_store_detail(first_store)
            
            logger.info("=== 테스트 결과 ===")
            for key, value in detailed_store.items():
                logger.info(f"{key}: {value}")
                
            # 정제 테스트
            processed = process_crawled_data([detailed_store])
            if processed:
                logger.info("=== 정제된 데이터 ===")
                for key, value in processed[0].items():
                    logger.info(f"{key}: {value}")
                    
    except Exception as e:
        logger.error(f"단일 가게 테스트 실패: {e}")
    finally:
        if crawler:
            crawler.close()

def test_database_only():
    """데이터베이스 기능만 테스트"""
    try:
        logger.info("=== 데이터베이스 전용 테스트 ===")
        
        db = DatabaseManager()
        
        # 연결 및 테이블 확인
        if not db.test_connection():
            return
        
        db.create_tables()
        
        # 통계 조회
        stats = db.get_crawling_stats()
        logger.info("현재 데이터베이스 통계:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        # 테스트 데이터 삽입
        test_data = [{
            'name': 'MVP 테스트 무한리필 가게',
            'address': '서울특별시 강남구 테스트동 123',
            'description': 'MVP 테스트용 가게입니다',
            'position_lat': 37.5665,
            'position_lng': 126.9780,
            'phone_number': '02-1234-5678',
            'diningcode_place_id': 'mvp_test_001',
            'diningcode_rating': 4.5,
            'raw_categories_diningcode': ['무한리필', '한식', '고기'],
            'status': '운영중'
        }]
        
        db.save_crawled_data(test_data, 'test', 'mvp_test')
        logger.info("테스트 데이터 저장 완료")
        
        # 업데이트된 통계
        stats = db.get_crawling_stats()
        logger.info("업데이트된 통계:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"데이터베이스 테스트 실패: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_single_store()
        elif sys.argv[1] == "db":
            test_database_only()
        elif sys.argv[1] == "full":
            run_mvp_crawling()
        else:
            print("사용법: python main.py [test|db|full]")
            print("  test: 단일 가게 크롤링 테스트")
            print("  db: 데이터베이스 기능 테스트")  
            print("  full: 전체 MVP 크롤링 실행")
    else:
        run_mvp_crawling()

def run_mvp_crawling():
    """MVP 크롤링 실행"""
    crawler = None
    db = None
    
    try:
        logger.info("=== Refill Spot 크롤링 시작 (MVP) ===")
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        
        # 데이터베이스 초기화
        db = DatabaseManager()
        db.create_tables()
        
        all_stores = []
        
        # 기본 키워드로 크롤링
        for keyword in config.KEYWORDS[:2]:  # MVP에서는 처음 2개만
            logger.info(f"키워드 '{keyword}' 크롤링 시작")
            
            # 목록 수집
            stores = crawler.get_store_list(keyword, config.TEST_RECT)
            logger.info(f"키워드 '{keyword}': {len(stores)}개 가게 발견")
            
            if not stores:
                continue
            
            # 상세 정보 수집 (MVP에서는 처음 5개만)
            detailed_stores = []
            for i, store in enumerate(stores[:5]):  
                try:
                    logger.info(f"상세 정보 수집 {i+1}/{min(5, len(stores))}: {store.get('name')}")
                    detailed_store = crawler.get_store_detail(store)
                    detailed_stores.append(detailed_store)
                    
                except Exception as e:
                    logger.error(f"상세 정보 수집 실패: {store.get('name')} - {e}")
                    continue
            
            all_stores.extend(detailed_stores)
        
        if not all_stores:
            logger.warning("수집된 데이터가 없습니다")
            return
        
        # 데이터 정제
        processed_stores = process_crawled_data(all_stores)
        
        if not processed_stores:
            logger.warning("정제 후 유효한 데이터가 없습니다")
            return
        
        # CSV 저장
        df = pd.DataFrame(processed_stores)
        df.to_csv('mvp_crawling_result.csv', index=False, encoding='utf-8-sig')
        logger.info(f"CSV 저장 완료: mvp_crawling_result.csv ({len(processed_stores)}개 가게)")
        
        # 데이터베이스 저장
        db.save_crawled_data(processed_stores)
        logger.info("데이터베이스 저장 완료")
        
        # 결과 요약
        logger.info("=== 크롤링 결과 요약 ===")
        logger.info(f"총 수집 가게 수: {len(processed_stores)}")
        logger.info(f"좌표 있는 가게: {sum(1 for s in processed_stores if s['position_lat'])}")
        logger.info(f"전화번호 있는 가게: {sum(1 for s in processed_stores if s['phone_number'])}")
        logger.info(f"평점 있는 가게: {sum(1 for s in processed_stores if s['diningcode_rating'])}")
        
        # 카테고리 분포
        all_categories = []
        for store in processed_stores:
            all_categories.extend(store.get('raw_categories_diningcode', []))
        
        from collections import Counter
        category_count = Counter(all_categories)
        logger.info("주요 카테고리:")
        for category, count in category_count.most_common(10):
            logger.info(f"  {category}: {count}개")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}")
        raise
        
    finally:
        if crawler:
            crawler.close()
        if db:
            db.close()
        logger.info("=== 크롤링 완료 ===")

def test_single_store():
    """단일 가게 테스트"""
    crawler = None
    
    try:
        logger.info("=== 단일 가게 테스트 ===")
        crawler = DiningCodeCrawler()
        
        # 목록에서 첫 번째 가게만
        stores = crawler.get_store_list("무한리필", config.TEST_RECT)
        if stores:
            first_store = stores[0]
            detailed_store = crawler.get_store_detail(first_store)
            
            logger.info("=== 테스트 결과 ===")
            for key, value in detailed_store.items():
                logger.info(f"{key}: {value}")
                
    except Exception as e:
        logger.error(f"단일 가게 테스트 실패: {e}")
    finally:
        if crawler:
            crawler.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_single_store()
    else:
        run_mvp_crawling()