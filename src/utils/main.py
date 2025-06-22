"""
다이닝코드 무한리필 가게 크롤링 메인 스크립트
3단계: 데이터 품질 고도화 버전 (지오코딩, 가격정규화, 카테고리매핑, 중복제거)
"""

import logging
import pandas as pd
import time
import json
from typing import List, Dict
from collections import Counter
from datetime import datetime
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

import config
from crawler import DiningCodeCrawler
from database import DatabaseManager
from data_enhancement import DataEnhancer  # 3단계 고도화 모듈

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

class CrawlingProgressMonitor:
    """크롤링 진행상황 모니터링 클래스"""
    
    def __init__(self):
        self.start_time = None
        self.total_keywords = 0
        self.completed_keywords = 0
        self.total_stores = 0
        self.processed_stores = 0
        self.failed_stores = 0
        self.current_keyword = ""
        
    def start_session(self, total_keywords: int):
        """크롤링 세션 시작"""
        self.start_time = datetime.now()
        self.total_keywords = total_keywords
        self.completed_keywords = 0
        self.total_stores = 0
        self.processed_stores = 0
        self.failed_stores = 0
        logger.info(f"=== 크롤링 세션 시작: {total_keywords}개 키워드 ===")
        
    def start_keyword(self, keyword: str):
        """키워드 처리 시작"""
        self.current_keyword = keyword
        logger.info(f"키워드 '{keyword}' 처리 시작 ({self.completed_keywords + 1}/{self.total_keywords})")
        
    def update_stores_found(self, count: int):
        """발견된 가게 수 업데이트"""
        self.total_stores += count
        logger.info(f"키워드 '{self.current_keyword}': {count}개 가게 발견")
        
    def update_store_processed(self, success: bool = True):
        """가게 처리 완료 업데이트"""
        if success:
            self.processed_stores += 1
        else:
            self.failed_stores += 1
            
    def complete_keyword(self):
        """키워드 처리 완료"""
        self.completed_keywords += 1
        elapsed = datetime.now() - self.start_time
        avg_time_per_keyword = elapsed.total_seconds() / self.completed_keywords
        remaining_keywords = self.total_keywords - self.completed_keywords
        estimated_remaining = remaining_keywords * avg_time_per_keyword
        
        logger.info(f"키워드 '{self.current_keyword}' 완료")
        logger.info(f"진행률: {self.completed_keywords}/{self.total_keywords} ({self.completed_keywords/self.total_keywords*100:.1f}%)")
        logger.info(f"예상 남은 시간: {estimated_remaining/60:.1f}분")
        
    def get_summary(self) -> Dict:
        """세션 요약 정보 반환"""
        elapsed = datetime.now() - self.start_time if self.start_time else None
        return {
            'total_keywords': self.total_keywords,
            'completed_keywords': self.completed_keywords,
            'total_stores_found': self.total_stores,
            'processed_stores': self.processed_stores,
            'failed_stores': self.failed_stores,
            'success_rate': self.processed_stores / max(self.total_stores, 1) * 100,
            'elapsed_time_minutes': elapsed.total_seconds() / 60 if elapsed else 0
        }

def process_crawled_data_enhanced(stores_data: List[Dict]) -> List[Dict]:
    """크롤링된 데이터 정제 및 처리 (강화된 버전)"""
    processed_stores = []
    
    for store in stores_data:
        # 필수 필드 검증
        if not store.get('diningcode_place_id') or not store.get('name'):
            logger.warning(f"필수 필드 누락: {store}")
            continue
        
        # 무한리필 관련성 검증 (강화)
        is_refill = validate_refill_relevance(store)
        if not is_refill:
            logger.warning(f"무한리필 관련성 없음: {store.get('name')}")
            continue
        
        # 좌표 유효성 검증
        lat, lng = validate_coordinates(store)
        if not lat or not lng:
            logger.warning(f"좌표 정보 없음: {store.get('name')}")
            continue
        
        # 평점 정보 정규화
        rating = normalize_rating(store.get('diningcode_rating'))
        
        # 가격 정보 정규화
        price_info = normalize_price_info(store)
        
        # 정제된 데이터 구성 (강화된 스키마)
        processed_store = {
            # 기본 정보
            'name': store.get('name', '').strip(),
            'address': store.get('address', '').strip(),
            'description': store.get('description', '').strip(),
            
            # 위치 정보
            'position_lat': lat,
            'position_lng': lng,
            'position_x': None,
            'position_y': None,
            
            # 평점 정보
            'naver_rating': None,
            'kakao_rating': None,
            'diningcode_rating': rating,
            
            # 영업시간 정보 (강화)
            'open_hours': store.get('open_hours', ''),
            'open_hours_raw': store.get('open_hours_raw', ''),
            'break_time': store.get('break_time', ''),
            'last_order': store.get('last_order', ''),
            'holiday': store.get('holiday', ''),
            
            # 가격 정보 (강화)
            'price': price_info.get('price'),
            'price_range': store.get('price_range', ''),
            'average_price': store.get('average_price', ''),
            'price_details': store.get('price_details', []),
            
            # 무한리필 정보 (강화)
            'refill_items': store.get('refill_items', []),
            'refill_type': store.get('refill_type', ''),
            'refill_conditions': store.get('refill_conditions', ''),
            'is_confirmed_refill': store.get('is_confirmed_refill', False),
            
            # 이미지 정보 (강화)
            'image_urls': store.get('image_urls', []),
            'main_image': store.get('main_image', ''),
            'menu_images': store.get('menu_images', []),
            'interior_images': store.get('interior_images', []),
            
            # 메뉴 정보 (강화)
            'menu_items': store.get('menu_items', []),
            'menu_categories': store.get('menu_categories', []),
            'signature_menu': store.get('signature_menu', []),
            
            # 리뷰 및 설명 정보 (강화)
            'review_summary': store.get('review_summary', ''),
            'keywords': store.get('keywords', []),
            'atmosphere': store.get('atmosphere', ''),
            
            # 연락처 정보 (강화)
            'phone_number': store.get('phone_number', '').strip(),
            'website': store.get('website', ''),
            'social_media': store.get('social_media', []),
            
            # 기존 필드
            'diningcode_place_id': store.get('diningcode_place_id'),
            'raw_categories_diningcode': store.get('raw_categories_diningcode', []),
            'status': '운영중'
        }
        
        processed_stores.append(processed_store)
    
    logger.info(f"데이터 정제 완료: {len(stores_data)} -> {len(processed_stores)}")
    return processed_stores

def validate_refill_relevance(store: Dict) -> bool:
    """무한리필 관련성 검증 (강화)"""
    refill_keywords = ['무한리필', '뷔페', '무제한', '리필', '셀프바', '무료리필']
    
    # 이름에서 확인
    name = store.get('name', '').lower()
    for keyword in refill_keywords:
        if keyword in name:
            return True
    
    # 카테고리에서 확인
    categories = store.get('raw_categories_diningcode', [])
    for category in categories:
        for keyword in refill_keywords:
            if keyword in category.lower():
                return True
    
    # 무한리필 확정 필드 확인
    if store.get('is_confirmed_refill'):
        return True
    
    # 리필 아이템이 있는 경우
    if store.get('refill_items') and len(store.get('refill_items', [])) > 0:
        return True
    
    # 키워드에서 확인
    keywords = store.get('keywords', [])
    for keyword in keywords:
        for refill_kw in refill_keywords:
            if refill_kw in keyword.lower():
                return True
    
    return False

def validate_coordinates(store: Dict) -> tuple:
    """좌표 유효성 검증"""
    lat = store.get('position_lat')
    lng = store.get('position_lng')
    
    if not lat or not lng:
        return None, None
    
    try:
        lat = float(lat)
        lng = float(lng)
        # 한국 좌표 범위 확인
        if not (33 <= lat <= 39 and 124 <= lng <= 132):
            return None, None
        return lat, lng
    except (ValueError, TypeError):
        return None, None

def normalize_rating(rating) -> float:
    """평점 정규화"""
    if not rating:
        return None
    try:
        rating = float(rating)
        if 0 <= rating <= 5:
            return rating
    except (ValueError, TypeError):
        pass
    return None

def normalize_price_info(store: Dict) -> Dict:
    """가격 정보 정규화"""
    price_info = {'price': None}
    
    # 기존 price 필드 처리
    price = store.get('price')
    if price:
        try:
            if isinstance(price, str):
                # 문자열에서 숫자 추출
                import re
                numbers = re.findall(r'\d+', price.replace(',', ''))
                if numbers:
                    price_info['price'] = int(numbers[0])
            else:
                price_info['price'] = int(price)
        except (ValueError, TypeError):
            pass
    
    # average_price에서 추출 시도
    if not price_info['price']:
        avg_price = store.get('average_price', '')
        if avg_price:
            try:
                import re
                numbers = re.findall(r'\d+', avg_price.replace(',', ''))
                if numbers:
                    price_info['price'] = int(numbers[0])
            except:
                pass
    
    return price_info

def run_enhanced_crawling():
    """강화된 크롤링 실행 (3단계: 데이터 품질 고도화 포함)"""
    crawler = None
    db = None
    monitor = CrawlingProgressMonitor()
    
    try:
        logger.info("=== Refill Spot 크롤링 시작 (3단계 고도화 버전) ===")
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        
        # 데이터베이스 초기화
        db = DatabaseManager()
        if not db.test_connection():
            logger.error("데이터베이스 연결 실패")
            return
        
        db.create_tables()
        
        # 크롤링 설정
        region_name = config.REGIONS[config.TEST_REGION]["name"]
        keywords = config.TEST_KEYWORDS
        rect = config.TEST_RECT
        
        logger.info(f"=== {region_name} 지역 크롤링 시작 ===")
        logger.info(f"사용할 키워드: {keywords}")
        logger.info(f"검색 영역: {rect}")
        
        # 진행상황 모니터링 시작
        monitor.start_session(len(keywords))
        
        all_stores = []
        
        # 각 키워드별로 크롤링
        for keyword in keywords:
            monitor.start_keyword(keyword)
            
            try:
                # 목록 수집
                stores = crawler.get_store_list(keyword, rect)
                monitor.update_stores_found(len(stores))
                
                if not stores:
                    logger.warning(f"키워드 '{keyword}'로 검색된 가게가 없습니다.")
                    monitor.complete_keyword()
                    continue
                
                # 상세 정보 수집 (배치 처리)
                detailed_stores = process_stores_batch(crawler, stores, monitor)
                all_stores.extend(detailed_stores)
                
                monitor.complete_keyword()
                
                # 키워드 간 휴식 시간
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"키워드 '{keyword}' 처리 중 오류: {e}")
                monitor.complete_keyword()
                continue
        
        # 3단계 고도화: 데이터 품질 강화
        if all_stores:
            logger.info("=== 3단계 데이터 품질 강화 시작 ===")
            
            # 데이터 강화 실행
            enhancer = DataEnhancer()
            enhanced_stores, enhancement_stats = enhancer.enhance_stores_data(all_stores)
            
            # 강화 결과 로깅
            logger.info("=== 데이터 강화 완료 ===")
            logger.info(f"원본 가게 수: {enhancement_stats.total_stores}")
            logger.info(f"최종 가게 수: {len(enhanced_stores)}")
            logger.info(f"지오코딩 성공: {enhancement_stats.geocoding_success}/{enhancement_stats.total_stores}")
            logger.info(f"가격 정규화: {enhancement_stats.price_normalized}/{enhancement_stats.total_stores}")
            logger.info(f"카테고리 매핑: {enhancement_stats.categories_mapped}/{enhancement_stats.total_stores}")
            logger.info(f"중복 제거: {enhancement_stats.duplicates_removed}개")
            logger.info(f"강화 처리 시간: {enhancement_stats.processing_time:.2f}초")
            
            # 강화된 데이터 저장
            if enhanced_stores:
                processed_data = process_crawled_data_enhanced(enhanced_stores)
                if processed_data:
                    db.save_crawled_data(processed_data, "enhanced_crawling", rect)
                    logger.info(f"강화된 데이터 저장 완료: {len(processed_data)}개")
            
            # 강화 통계 상세 정보
            enhancement_summary = enhancer.get_enhancement_summary()
            logger.info("=== 강화 통계 상세 ===")
            logger.info(f"좌표 완성도: {enhancement_summary.get('geocoding_rate', 0):.1f}%")
            logger.info(f"가격 정규화율: {enhancement_summary.get('price_normalization_rate', 0):.1f}%")
            logger.info(f"카테고리 매핑율: {enhancement_summary.get('category_mapping_rate', 0):.1f}%")
            logger.info(f"중복 제거율: {enhancement_summary.get('duplicate_removal_rate', 0):.1f}%")
            
            # 지오코딩 상세 통계
            geocoding_stats = enhancement_summary.get('geocoding_stats', {})
            if geocoding_stats:
                logger.info("=== 지오코딩 통계 ===")
                logger.info(f"카카오 API 성공률: {geocoding_stats.get('kakao_rate', 0):.1f}%")
                logger.info(f"네이버 API 성공률: {geocoding_stats.get('naver_rate', 0):.1f}%")
                logger.info(f"전체 성공률: {geocoding_stats.get('success_rate', 0):.1f}%")
            
            # 가격 정규화 상세 통계
            price_stats = enhancement_summary.get('price_stats', {})
            if price_stats:
                logger.info("=== 가격 정규화 통계 ===")
                logger.info(f"단일 가격: {price_stats.get('single_price', 0)}개")
                logger.info(f"범위 가격: {price_stats.get('range_price', 0)}개")
                logger.info(f"시간대별 가격: {price_stats.get('time_based_price', 0)}개")
                logger.info(f"조건부 가격: {price_stats.get('conditional_price', 0)}개")
                logger.info(f"가격 문의: {price_stats.get('inquiry_price', 0)}개")
                logger.info(f"정규화 성공률: {price_stats.get('success_rate', 0):.1f}%")
        
        # 최종 결과 요약
        summary = monitor.get_summary()
        logger.info("=== 크롤링 완료 ===")
        logger.info(f"총 키워드: {summary['total_keywords']}개")
        logger.info(f"총 발견 가게: {summary['total_stores_found']}개")
        logger.info(f"성공 처리: {summary['processed_stores']}개")
        logger.info(f"실패: {summary['failed_stores']}개")
        logger.info(f"성공률: {summary['success_rate']:.1f}%")
        logger.info(f"소요 시간: {summary['elapsed_time_minutes']:.1f}분")
        
        # 강화된 통계 조회
        stats = db.get_enhanced_crawling_stats()
        if stats:
            logger.info("=== 데이터베이스 통계 ===")
            basic = stats.get('basic_stats', {})
            logger.info(f"총 가게 수: {basic.get('total_stores', 0)}개")
            logger.info(f"무한리필 확정: {basic.get('confirmed_refill_stores', 0)}개")
            logger.info(f"메뉴 정보 보유: {basic.get('stores_with_menu', 0)}개")
            logger.info(f"이미지 보유: {basic.get('stores_with_images', 0)}개")
            logger.info(f"가격 정보 보유: {basic.get('stores_with_price', 0)}개")
            logger.info(f"평균 평점: {basic.get('avg_rating', 0):.2f}")
        
        return enhanced_stores if 'enhanced_stores' in locals() else all_stores
        
    except Exception as e:
        logger.error(f"크롤링 실행 중 오류: {e}")
        return []
        
    finally:
        if crawler:
            crawler.close()
        if db:
            db.close()

def process_stores_batch(crawler: DiningCodeCrawler, stores: List[Dict], monitor: CrawlingProgressMonitor, batch_size: int = 5) -> List[Dict]:
    """가게 상세 정보 배치 처리"""
    detailed_stores = []
    
    for i in range(0, len(stores), batch_size):
        batch = stores[i:i + batch_size]
        logger.info(f"배치 처리 {i//batch_size + 1}: {len(batch)}개 가게")
        
        for store in batch:
            try:
                logger.info(f"상세 정보 수집: {store.get('name')}")
                detailed_store = crawler.get_store_detail(store)
                detailed_stores.append(detailed_store)
                monitor.update_store_processed(True)
                
                # 가게 간 휴식 시간
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"상세 정보 수집 실패: {store.get('name')} - {e}")
                monitor.update_store_processed(False)
                continue
        
        # 배치 간 휴식 시간
        if i + batch_size < len(stores):
            logger.info(f"배치 완료. 3초 휴식...")
            time.sleep(3)
    
    return detailed_stores

def run_region_expansion():
    """지역 확장 크롤링"""
    logger.info("=== 지역 확장 크롤링 시작 ===")
    
    # 모든 지역에 대해 크롤링 실행
    for region_key, region_info in config.REGIONS.items():
        logger.info(f"=== {region_info['name']} 지역 크롤링 ===")
        
        # 임시로 설정 변경
        original_region = config.TEST_REGION
        original_rect = config.TEST_RECT
        original_keywords = config.TEST_KEYWORDS
        
        try:
            config.TEST_REGION = region_key
            config.TEST_RECT = region_info["rect"]
            config.TEST_KEYWORDS = region_info["keywords"]
            
            # 해당 지역 크롤링 실행
            run_enhanced_crawling()
            
        finally:
            # 설정 복원
            config.TEST_REGION = original_region
            config.TEST_RECT = original_rect
            config.TEST_KEYWORDS = original_keywords
        
        # 지역 간 휴식 시간
        logger.info("지역 완료. 10초 휴식...")
        time.sleep(10)

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
    """MVP 크롤링 실행 (지역별 키워드 사용)"""
    crawler = None
    db = None
    
    try:
        logger.info("=== Refill Spot 크롤링 시작 (MVP - 지역별 키워드) ===")
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        
        # 데이터베이스 초기화
        db = DatabaseManager()
        if not db.test_connection():
            logger.error("데이터베이스 연결 실패")
            return
        
        db.create_tables()
        
        all_stores = []
        
        # 지역별 키워드로 크롤링
        region_name = config.REGIONS[config.TEST_REGION]["name"]
        keywords = config.TEST_KEYWORDS
        rect = config.TEST_RECT
        
        logger.info(f"=== {region_name} 지역 크롤링 시작 ===")
        logger.info(f"사용할 키워드: {keywords}")
        logger.info(f"검색 영역: {rect}")
        
        # 각 키워드별로 크롤링 (MVP에서는 처음 2개만)
        for keyword in keywords[:2]:  # MVP에서는 처음 2개 키워드만
            logger.info(f"키워드 '{keyword}' 크롤링 시작")
            
            # 목록 수집
            stores = crawler.get_store_list(keyword, rect)
            logger.info(f"키워드 '{keyword}': {len(stores)}개 가게 발견")
            
            if not stores:
                logger.warning(f"키워드 '{keyword}'로 검색된 가게가 없습니다. 다른 키워드를 시도해보세요.")
                continue
            
            # 상세 정보 수집 (MVP에서는 처음 3개만)
            detailed_stores = []
            for i, store in enumerate(stores[:3]):  
                try:
                    logger.info(f"상세 정보 수집 {i+1}/{min(3, len(stores))}: {store.get('name')}")
                    detailed_store = crawler.get_store_detail(store)
                    detailed_stores.append(detailed_store)
                    
                except Exception as e:
                    logger.error(f"상세 정보 수집 실패: {store.get('name')} - {e}")
                    continue
            
            all_stores.extend(detailed_stores)
            
            # 키워드별 결과 요약
            logger.info(f"키워드 '{keyword}' 완료: {len(detailed_stores)}개 가게 상세 정보 수집")
        
        if not all_stores:
            logger.warning("수집된 데이터가 없습니다")
            logger.info("다음을 확인해보세요:")
            logger.info("1. 다이닝코드 사이트 접속 가능 여부")
            logger.info("2. ChromeDriver 정상 동작 여부") 
            logger.info("3. 네트워크 연결 상태")
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
        
        # 데이터베이스 저장 (지역명과 rect 정보 포함)
        db.save_crawled_data(processed_stores, keyword=region_name, rect_area=rect)
        logger.info("데이터베이스 저장 완료")
        
        # 결과 요약
        logger.info("=== 크롤링 결과 요약 ===")
        logger.info(f"검색 지역: {region_name}")
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

def test_single_store_enhanced():
    """단일 가게 테스트 (강화된 버전)"""
    crawler = None
    
    try:
        logger.info("=== 단일 가게 테스트 (강화된 버전) ===")
        crawler = DiningCodeCrawler()
        
        # 지역명을 포함한 키워드로 검색
        region_name = config.REGIONS[config.TEST_REGION]["name"]
        test_keyword = f"{region_name} 무한리필"
        logger.info(f"테스트 키워드: {test_keyword}")
        
        # 목록에서 첫 번째 가게만
        stores = crawler.get_store_list(test_keyword, config.TEST_RECT)
        
        if not stores:
            # 백업 키워드로 재시도
            backup_keyword = "강남 고기무한리필"
            logger.info(f"백업 키워드로 재시도: {backup_keyword}")
            stores = crawler.get_store_list(backup_keyword, config.TEST_RECT)
        
        if stores:
            first_store = stores[0]
            logger.info(f"테스트 대상: {first_store.get('name')}")
            logger.info(f"가게 ID: {first_store.get('diningcode_place_id')}")
            
            detailed_store = crawler.get_store_detail(first_store)
            
            logger.info("=== 강화된 테스트 결과 ===")
            
            # 기본 정보
            logger.info("📍 기본 정보:")
            logger.info(f"  이름: {detailed_store.get('name')}")
            logger.info(f"  주소: {detailed_store.get('address')}")
            logger.info(f"  전화번호: {detailed_store.get('phone_number')}")
            logger.info(f"  평점: {detailed_store.get('diningcode_rating')}")
            
            # 무한리필 정보
            logger.info("🍽️ 무한리필 정보:")
            logger.info(f"  확정 여부: {detailed_store.get('is_confirmed_refill')}")
            logger.info(f"  리필 타입: {detailed_store.get('refill_type')}")
            logger.info(f"  리필 아이템: {detailed_store.get('refill_items', [])}")
            
            # 메뉴 정보
            menu_items = detailed_store.get('menu_items', [])
            signature_menu = detailed_store.get('signature_menu', [])
            logger.info("🍴 메뉴 정보:")
            logger.info(f"  메뉴 개수: {len(menu_items)}")
            logger.info(f"  대표 메뉴: {signature_menu}")
            
            # 가격 정보
            logger.info("💰 가격 정보:")
            logger.info(f"  가격 범위: {detailed_store.get('price_range')}")
            logger.info(f"  평균 가격: {detailed_store.get('average_price')}")
            
            # 영업시간 정보
            logger.info("🕐 영업시간 정보:")
            logger.info(f"  영업시간: {detailed_store.get('open_hours')}")
            logger.info(f"  브레이크타임: {detailed_store.get('break_time')}")
            logger.info(f"  휴무일: {detailed_store.get('holiday')}")
            
            # 이미지 정보
            image_urls = detailed_store.get('image_urls', [])
            menu_images = detailed_store.get('menu_images', [])
            logger.info("📸 이미지 정보:")
            logger.info(f"  총 이미지: {len(image_urls)}개")
            logger.info(f"  메뉴 이미지: {len(menu_images)}개")
            
            # 키워드 정보
            keywords = detailed_store.get('keywords', [])
            logger.info("🏷️ 키워드:")
            logger.info(f"  {keywords}")
            
        else:
            logger.warning("테스트할 가게를 찾을 수 없습니다.")
            logger.info("다음을 확인해보세요:")
            logger.info("1. 네트워크 연결 상태")
            logger.info("2. 다이닝코드 사이트 접근 가능 여부")
            logger.info("3. 검색 키워드 및 지역 설정")
            
    except Exception as e:
        logger.error(f"단일 가게 테스트 실패: {e}")
    finally:
        if crawler:
            crawler.close()

def show_database_stats():
    """데이터베이스 통계 조회 및 출력"""
    db = None
    
    try:
        logger.info("=== 데이터베이스 통계 조회 ===")
        db = DatabaseManager()
        
        if not db.test_connection():
            logger.error("데이터베이스 연결 실패")
            return
        
        stats = db.get_enhanced_crawling_stats()
        
        if not stats:
            logger.warning("통계 데이터가 없습니다.")
            return
        
        # 기본 통계
        basic = stats.get('basic_stats', {})
        logger.info("📊 기본 통계:")
        logger.info(f"  총 가게 수: {basic.get('total_stores', 0):,}개")
        logger.info(f"  무한리필 확정: {basic.get('confirmed_refill_stores', 0):,}개")
        logger.info(f"  메뉴 정보 보유: {basic.get('stores_with_menu', 0):,}개")
        logger.info(f"  이미지 보유: {basic.get('stores_with_images', 0):,}개")
        logger.info(f"  가격 정보 보유: {basic.get('stores_with_price', 0):,}개")
        logger.info(f"  평균 평점: {basic.get('avg_rating', 0):.2f}/5.0")
        
        # 리필 타입별 통계
        refill_types = stats.get('refill_type_stats', [])
        if refill_types:
            logger.info("🍽️ 리필 타입별 통계:")
            for item in refill_types[:5]:  # 상위 5개만
                logger.info(f"  {item['refill_type']}: {item['count']}개")
        
        # 지역별 통계
        regions = stats.get('region_stats', [])
        if regions:
            logger.info("📍 지역별 통계:")
            for item in regions:
                logger.info(f"  {item['region']}: {item['count']}개")
        
        # 최근 크롤링 세션
        recent = stats.get('recent_sessions', [])
        if recent:
            logger.info("📅 최근 크롤링 세션:")
            for session in recent[:3]:  # 최근 3개만
                created_at = session['created_at'].strftime('%Y-%m-%d %H:%M')
                logger.info(f"  {created_at} | {session['keyword']} | {session['stores_processed']}개 처리")
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
    finally:
        if db:
            db.close()

def test_stage3_enhancement():
    """3단계 고도화 기능 테스트"""
    logger.info("=== 3단계 고도화 기능 테스트 시작 ===")
    
    try:
        # 테스트용 샘플 데이터 생성
        test_stores = [
            {
                'name': '맛있는 삼겹살집',
                'address': '서울 강남구 테헤란로 123',
                'price': '1만5천원',
                'raw_categories_diningcode': ['#삼겹살무한리필', '#고기', '#강남맛집'],
                'diningcode_place_id': 'test1',
                'menu_items': ['삼겹살', '목살', '갈비살']
            },
            {
                'name': '맛있는삼겹살집',  # 중복 (띄어쓰기 차이)
                'address': '서울 강남구 테헤란로 125',
                'price': '15000원',
                'raw_categories_diningcode': ['#무한리필', '#삼겹살'],
                'diningcode_place_id': 'test2',
                'phone_number': '02-123-4567'
            },
            {
                'name': '초밥뷔페 스시로',
                'address': '서울 강남구 역삼동',  # 좌표 없음
                'price': '런치 2만원, 디너 3만원',
                'raw_categories_diningcode': ['#초밥뷔페', '#일식', '#뷔페'],
                'diningcode_place_id': 'test3',
                'menu_items': ['초밥', '사시미', '우동']
            },
            {
                'name': '고기천국',
                'address': '서울 강남구 논현동',
                'price': '2만원대',
                'raw_categories_diningcode': ['#소고기무한리필', '#한우', '#구이'],
                'diningcode_place_id': 'test4',
                'position_lat': 37.5129,
                'position_lng': 127.0426
            }
        ]
        
        # 데이터 강화 실행
        from data_enhancement import DataEnhancer
        enhancer = DataEnhancer()
        
        logger.info(f"테스트 데이터: {len(test_stores)}개 가게")
        
        enhanced_stores, stats = enhancer.enhance_stores_data(test_stores)
        
        # 결과 출력
        logger.info("=== 강화 결과 ===")
        logger.info(f"원본 가게 수: {stats.total_stores}")
        logger.info(f"최종 가게 수: {len(enhanced_stores)}")
        logger.info(f"지오코딩 성공: {stats.geocoding_success}")
        logger.info(f"가격 정규화: {stats.price_normalized}")
        logger.info(f"카테고리 매핑: {stats.categories_mapped}")
        logger.info(f"중복 제거: {stats.duplicates_removed}")
        
        # 개별 가게 결과 확인
        for i, store in enumerate(enhanced_stores):
            logger.info(f"\n=== 가게 {i+1}: {store.get('name')} ===")
            logger.info(f"주소: {store.get('address')}")
            logger.info(f"좌표: {store.get('position_lat')}, {store.get('position_lng')}")
            
            # 지오코딩 정보
            if store.get('geocoding_source'):
                logger.info(f"지오코딩 소스: {store.get('geocoding_source')}")
                logger.info(f"지오코딩 신뢰도: {store.get('geocoding_confidence', 0):.2f}")
            
            # 정규화된 가격 정보
            norm_price = store.get('normalized_price', {})
            if norm_price:
                logger.info(f"가격 타입: {norm_price.get('price_type')}")
                logger.info(f"가격 범위: {norm_price.get('min_price')} ~ {norm_price.get('max_price')}")
                logger.info(f"가격 신뢰도: {norm_price.get('confidence', 0):.2f}")
                if norm_price.get('time_based'):
                    logger.info(f"시간대별 가격: {norm_price.get('time_based')}")
                if norm_price.get('conditions'):
                    logger.info(f"가격 조건: {norm_price.get('conditions')}")
            
            # 표준 카테고리
            std_categories = store.get('standard_categories', [])
            if std_categories:
                logger.info(f"표준 카테고리: {std_categories}")
        
        # 강화 통계 상세 정보
        summary = enhancer.get_enhancement_summary()
        logger.info("\n=== 강화 통계 상세 ===")
        logger.info(f"좌표 완성도: {summary.get('geocoding_rate', 0):.1f}%")
        logger.info(f"가격 정규화율: {summary.get('price_normalization_rate', 0):.1f}%")
        logger.info(f"카테고리 매핑율: {summary.get('category_mapping_rate', 0):.1f}%")
        logger.info(f"중복 제거율: {summary.get('duplicate_removal_rate', 0):.1f}%")
        
        logger.info("=== 3단계 고도화 기능 테스트 완료 ===")
        return enhanced_stores
        
    except Exception as e:
        logger.error(f"3단계 고도화 테스트 중 오류: {e}")
        return []

def run_stage3_crawling():
    """3단계 고도화 크롤링 실행 (카카오 API 사용)"""
    logger.info("=== 3단계 고도화 크롤링 실행 ===")
    
    # API 키 확인
    if not config.KAKAO_API_KEY:
        logger.warning("카카오 지오코딩 API 키가 설정되지 않았습니다.")
        logger.info("카카오 API 키를 config.py에 설정해주세요.")
        logger.info("API 키 없이도 가격 정규화, 카테고리 매핑, 중복 제거는 동작합니다.")
    
    # 강화된 크롤링 실행
    return run_enhanced_crawling()

def run_stage4_seoul_coverage():
    """4단계: 서울 25개 구 완전 커버리지 크롤링"""
    logger.info("=== 4단계: 서울 완전 커버리지 크롤링 시작 ===")
    
    try:
        from seoul_districts import SeoulDistrictManager
        from seoul_scheduler import SeoulCrawlingScheduler
        
        # 서울 구 관리자 초기화
        district_manager = SeoulDistrictManager()
        
        # 서울 커버리지 현황 확인
        stats = district_manager.get_seoul_coverage_stats()
        logger.info(f"서울 커버리지 현황:")
        logger.info(f"  총 구 수: {stats['total_districts']}")
        logger.info(f"  완료율: {stats['completion_rate']:.1f}%")
        logger.info(f"  예상 총 가게 수: {stats['total_expected_stores']:,}개")
        
        # 미완료 구 목록
        incomplete_districts = district_manager.get_incomplete_districts()
        logger.info(f"미완료 구: {len(incomplete_districts)}개")
        
        if not incomplete_districts:
            logger.info("모든 구의 크롤링이 완료되었습니다!")
            return
        
        # 우선순위별 처리
        for priority in range(1, 6):
            priority_districts = [d for d in incomplete_districts if d.priority == priority]
            if not priority_districts:
                continue
                
            logger.info(f"=== Tier {priority} 구 처리 시작 ===")
            
            for district in priority_districts:
                logger.info(f"{district.name} 크롤링 시작...")
                
                # 구별 크롤링 실행
                result = run_district_crawling(district)
                
                if result['success']:
                    district_manager.update_district_status(
                        district.name, "완료", result['stores_processed']
                    )
                    logger.info(f"{district.name} 완료: {result['stores_processed']}개 가게")
                else:
                    district_manager.update_district_status(district.name, "오류")
                    logger.error(f"{district.name} 실패: {result['error']}")
                
                # 구간 휴식 (API 부하 방지)
                time.sleep(30)
        
        # 최종 통계
        final_stats = district_manager.get_seoul_coverage_stats()
        logger.info(f"=== 4단계 크롤링 완료 ===")
        logger.info(f"최종 완료율: {final_stats['completion_rate']:.1f}%")
        logger.info(f"총 처리 가게: {final_stats['total_expected_stores']:,}개")
        
    except Exception as e:
        logger.error(f"4단계 크롤링 오류: {e}")
        raise

def run_district_crawling(district_info) -> Dict:
    """개별 구 크롤링 실행"""
    try:
        # 기존 설정 백업
        original_region = getattr(config, 'TEST_REGION', None)
        original_rect = getattr(config, 'TEST_RECT', None)
        original_keywords = getattr(config, 'TEST_KEYWORDS', None)
        
        # 구별 설정으로 변경
        config.TEST_REGION = district_info.name
        config.TEST_RECT = district_info.rect
        config.TEST_KEYWORDS = district_info.keywords
        
        logger.info(f"{district_info.name} 설정:")
        logger.info(f"  검색 영역: {district_info.rect}")
        logger.info(f"  키워드 수: {len(district_info.keywords)}")
        logger.info(f"  예상 가게: {district_info.expected_stores}개")
        
        # 크롤링 실행
        stores = run_enhanced_crawling()
        
        return {
            'success': True,
            'stores_found': len(stores) if stores else 0,
            'stores_processed': len(stores) if stores else 0,
            'district': district_info.name
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'district': district_info.name
        }
        
    finally:
        # 설정 복원
        if original_region:
            config.TEST_REGION = original_region
        if original_rect:
            config.TEST_RECT = original_rect
        if original_keywords:
            config.TEST_KEYWORDS = original_keywords

def start_seoul_scheduler():
    """서울 자동 스케줄러 시작"""
    logger.info("=== 서울 자동 스케줄러 시작 ===")
    
    try:
        from seoul_districts import SeoulDistrictManager
        from seoul_scheduler import SeoulCrawlingScheduler
        
        # 구 관리자 및 스케줄러 초기화
        district_manager = SeoulDistrictManager()
        scheduler = SeoulCrawlingScheduler(district_manager)
        
        # 스케줄러 시작 (무한 루프)
        scheduler.start_scheduler()
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 스케줄러가 중지되었습니다.")
    except Exception as e:
        logger.error(f"스케줄러 오류: {e}")
        raise

def test_stage4_system():
    """4단계 시스템 테스트"""
    logger.info("=== 4단계 시스템 테스트 ===")
    
    try:
        from seoul_districts import SeoulDistrictManager, test_seoul_district_system
        from seoul_scheduler import test_seoul_scheduler
        
        # 1. 서울 구 시스템 테스트
        logger.info("1. 서울 구 시스템 테스트")
        test_seoul_district_system()
        
        # 2. 스케줄러 시스템 테스트
        logger.info("2. 스케줄러 시스템 테스트")
        test_seoul_scheduler()
        
        # 3. 단일 구 크롤링 테스트
        logger.info("3. 단일 구 크롤링 테스트")
        district_manager = SeoulDistrictManager()
        test_district = district_manager.get_district_info("강남구")
        
        if test_district:
            result = run_district_crawling(test_district)
            logger.info(f"테스트 결과: {result}")
        
        logger.info("4단계 시스템 테스트 완료")
        
    except Exception as e:
        logger.error(f"4단계 테스트 오류: {e}")

def show_seoul_coverage_dashboard():
    """서울 커버리지 대시보드 표시"""
    try:
        from seoul_districts import SeoulDistrictManager
        
        district_manager = SeoulDistrictManager()
        stats = district_manager.get_seoul_coverage_stats()
        
        print("\n" + "="*60)
        print("🗺️  서울 25개 구 커버리지 대시보드")
        print("="*60)
        
        print(f"📊 전체 현황:")
        print(f"   총 구 수: {stats['total_districts']}개")
        print(f"   완료: {stats['completed']}개")
        print(f"   진행중: {stats['in_progress']}개")
        print(f"   대기: {stats['pending']}개")
        print(f"   오류: {stats['error']}개")
        print(f"   완료율: {stats['completion_rate']:.1f}%")
        print(f"   예상 총 가게: {stats['total_expected_stores']:,}개")
        
        print(f"\n🏆 티어별 현황:")
        for tier, info in stats['tier_breakdown'].items():
            tier_num = tier.split('_')[1]
            print(f"   Tier {tier_num}: {info['completed']}/{info['count']}개 완료, 예상 {info['expected_stores']}개 가게")
            print(f"     구 목록: {', '.join(info['districts'])}")
        
        # 미완료 구 목록
        incomplete = district_manager.get_incomplete_districts()
        if incomplete:
            print(f"\n⏳ 미완료 구 ({len(incomplete)}개):")
            for district in incomplete[:10]:  # 최대 10개만
                print(f"   {district.name}: {district.status}, 예상 {district.expected_stores}개")
        
        print("="*60)
        
    except Exception as e:
        logger.error(f"대시보드 표시 오류: {e}")

def main():
    """메인 크롤링 함수"""
    logger.info("=== 리필스팟 크롤러 시작 ===")
    try:
        # 기본적으로 서울 전체 크롤링 실행
        return run_stage4_seoul_coverage()
    except Exception as e:
        logger.error(f"크롤링 실행 오류: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "mvp":
            run_mvp_crawling()
        elif command == "enhanced":
            run_enhanced_crawling()
        elif command == "expansion":
            run_region_expansion()
        elif command == "stage3":
            run_stage3_crawling()
        elif command == "stage4":
            run_stage4_seoul_coverage()
        elif command == "seoul-scheduler":
            start_seoul_scheduler()
        elif command == "test-stage4":
            test_stage4_system()
        elif command == "seoul-dashboard":
            show_seoul_coverage_dashboard()
        elif command == "stats":
            show_database_stats()
        elif command == "test-single":
            test_single_store_enhanced()
        elif command == "test-stage3":
            test_stage3_enhancement()
        else:
            print("사용법:")
            print("  python main.py mvp              # MVP 크롤링")
            print("  python main.py enhanced         # 강화된 크롤링")
            print("  python main.py expansion        # 지역 확장 크롤링")
            print("  python main.py stage3           # 3단계 고도화 크롤링")
            print("  python main.py stage4           # 4단계 서울 완전 커버리지")
            print("  python main.py seoul-scheduler  # 서울 자동 스케줄러 시작")
            print("  python main.py test-stage4      # 4단계 시스템 테스트")
            print("  python main.py seoul-dashboard  # 서울 커버리지 대시보드")
            print("  python main.py stats            # 데이터베이스 통계")
            print("  python main.py test-single      # 단일 가게 테스트")
            print("  python main.py test-stage3      # 3단계 기능 테스트")
    else:
        # 기본 실행: 강화된 크롤링
        run_enhanced_crawling()