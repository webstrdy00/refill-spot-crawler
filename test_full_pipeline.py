"""
전체 파이프라인 테스트 스크립트
크롤링 → 데이터 향상 → 위치정보 완성도 확인
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.crawler import DiningCodeCrawler
from src.core.data_enhancement import DataEnhancer
import logging
import json
import pandas as pd
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_full_pipeline.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_full_pipeline():
    """전체 파이프라인 테스트"""
    
    logger.info("=" * 80)
    logger.info("전체 파이프라인 테스트 시작")
    logger.info("=" * 80)
    
    # 1단계: 크롤링
    logger.info("\n[1단계] 크롤링 시작")
    crawler = DiningCodeCrawler()
    
    try:
        # 테스트용으로 적은 수의 가게만 수집
        keyword = "강남 무한리필"
        rect = "37.4979,127.0276,37.5279,127.0576"  # 강남 지역
        
        logger.info(f"검색 키워드: {keyword}")
        logger.info(f"검색 영역: {rect}")
        
        # 가게 목록 수집
        stores = crawler.get_store_list(keyword, rect)
        logger.info(f"\n크롤링 결과: {len(stores)}개 가게 발견")
        
        if not stores:
            logger.error("가게를 찾을 수 없습니다!")
            return
        
        # 위치정보 상태 확인 (크롤링 직후)
        stores_with_location_before = [s for s in stores if s.get('position_lat') and s.get('position_lng')]
        logger.info(f"크롤링 직후 위치정보 있는 가게: {len(stores_with_location_before)}개 ({len(stores_with_location_before)/len(stores)*100:.1f}%)")
        
        # 상세 정보 수집 (처음 5개만)
        logger.info("\n상세 정보 수집 중...")
        detailed_stores = []
        for i, store in enumerate(stores[:5]):
            logger.info(f"상세 정보 수집 중: {i+1}/5 - {store.get('name')}")
            detailed_store = crawler.get_store_detail(store)
            detailed_stores.append(detailed_store)
        
        # 나머지는 기본 정보만 사용
        detailed_stores.extend(stores[5:])
        
        # 상세 정보 수집 후 위치정보 상태
        stores_with_location_detail = [s for s in detailed_stores if s.get('position_lat') and s.get('position_lng')]
        logger.info(f"\n상세 정보 수집 후 위치정보 있는 가게: {len(stores_with_location_detail)}개 ({len(stores_with_location_detail)/len(detailed_stores)*100:.1f}%)")
        
        # 2단계: 데이터 향상
        logger.info("\n[2단계] 데이터 향상 시작")
        data_enhancer = DataEnhancer()
        
        enhanced_stores, enhancement_stats = data_enhancer.enhance_stores_data(detailed_stores)
        
        logger.info(f"\n데이터 향상 완료:")
        logger.info(f"- 지오코딩 성공: {enhancement_stats.geocoding_success}개")
        logger.info(f"- 가격 정규화: {enhancement_stats.price_normalized}개")
        logger.info(f"- 카테고리 매핑: {enhancement_stats.categories_mapped}개")
        logger.info(f"- 중복 제거: {enhancement_stats.duplicates_removed}개")
        
        # 3단계: 최종 결과 분석
        logger.info("\n[3단계] 최종 결과 분석")
        analyze_results(enhanced_stores)
        
        # 결과 저장
        save_results(enhanced_stores)
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        crawler.close()
        logger.info("\n테스트 완료!")

def analyze_results(stores):
    """결과 분석 및 통계 출력"""
    total_count = len(stores)
    
    # 위치정보 분석
    stores_with_location = [s for s in stores if s.get('position_lat') and s.get('position_lng')]
    location_count = len(stores_with_location)
    location_rate = location_count / total_count * 100 if total_count > 0 else 0
    
    # 지오코딩 소스 분석
    source_stats = {
        'javascript': 0,
        'kakao': 0,
        'estimated': 0,
        'none': 0
    }
    
    for store in stores:
        if store.get('position_lat') and store.get('position_lng'):
            source = store.get('geocoding_source', 'javascript')
            if source in source_stats:
                source_stats[source] += 1
            else:
                source_stats['javascript'] += 1
        else:
            source_stats['none'] += 1
    
    # 데이터 완성도 분석
    completeness_stats = {
        'name': 0,
        'address': 0,
        'phone': 0,
        'coordinates': 0,
        'price': 0,
        'categories': 0,
        'images': 0,
        'menu': 0
    }
    
    for store in stores:
        if store.get('name'):
            completeness_stats['name'] += 1
        if store.get('address') or store.get('basic_address'):
            completeness_stats['address'] += 1
        if store.get('phone_number'):
            completeness_stats['phone'] += 1
        if store.get('position_lat') and store.get('position_lng'):
            completeness_stats['coordinates'] += 1
        if store.get('price') or store.get('normalized_price'):
            completeness_stats['price'] += 1
        if store.get('standard_categories'):
            completeness_stats['categories'] += 1
        if store.get('image_urls'):
            completeness_stats['images'] += 1
        if store.get('menu_items'):
            completeness_stats['menu'] += 1
    
    # 결과 출력
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 최종 통계")
    logger.info(f"{'='*60}")
    logger.info(f"총 가게 수: {total_count}개")
    logger.info(f"\n📍 위치정보 완성도: {location_count}/{total_count} ({location_rate:.1f}%)")
    
    logger.info(f"\n📌 위치정보 출처:")
    logger.info(f"  - JavaScript (상세페이지): {source_stats['javascript']}개")
    logger.info(f"  - 카카오 API 지오코딩: {source_stats['kakao']}개")
    logger.info(f"  - 근처 가게 기반 추정: {source_stats['estimated']}개")
    logger.info(f"  - 위치정보 없음: {source_stats['none']}개")
    
    logger.info(f"\n📋 데이터 완성도:")
    for field, count in completeness_stats.items():
        rate = count / total_count * 100 if total_count > 0 else 0
        logger.info(f"  - {field}: {count}/{total_count} ({rate:.1f}%)")
    
    # 상위 5개 가게 샘플 출력
    logger.info(f"\n🏪 가게 샘플 (상위 5개):")
    for i, store in enumerate(stores[:5]):
        logger.info(f"\n[{i+1}] {store.get('name')} ({store.get('branch', '')})")
        logger.info(f"  - 주소: {store.get('address') or store.get('basic_address')}")
        logger.info(f"  - 좌표: ({store.get('position_lat')}, {store.get('position_lng')})")
        logger.info(f"  - 좌표 출처: {store.get('geocoding_source', 'javascript')}")
        logger.info(f"  - 전화: {store.get('phone_number')}")
        logger.info(f"  - 카테고리: {store.get('standard_categories', [])}")

def save_results(stores):
    """결과를 파일로 저장"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # JSON으로 저장
    json_filename = f'test_results_{timestamp}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    logger.info(f"\n결과가 {json_filename}에 저장되었습니다.")
    
    # CSV로도 저장 (주요 필드만)
    csv_data = []
    for store in stores:
        csv_data.append({
            'name': store.get('name'),
            'branch': store.get('branch'),
            'address': store.get('address') or store.get('basic_address'),
            'latitude': store.get('position_lat'),
            'longitude': store.get('position_lng'),
            'geocoding_source': store.get('geocoding_source', 'javascript'),
            'phone': store.get('phone_number'),
            'categories': ', '.join(store.get('standard_categories', []))
        })
    
    csv_filename = f'test_results_{timestamp}.csv'
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    logger.info(f"CSV 결과가 {csv_filename}에 저장되었습니다.")

if __name__ == "__main__":
    test_full_pipeline() 