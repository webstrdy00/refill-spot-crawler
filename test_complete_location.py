"""
완전한 위치정보 수집 테스트
모든 가게의 상세 페이지를 방문하여 위치정보 수집
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
        logging.FileHandler('test_complete_location.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_complete_location_extraction():
    """모든 가게의 위치정보를 완전히 수집하는 테스트"""
    
    logger.info("=" * 80)
    logger.info("완전한 위치정보 수집 테스트 시작")
    logger.info("=" * 80)
    
    crawler = DiningCodeCrawler()
    
    try:
        # 1단계: 가게 목록 수집
        keyword = "강남 무한리필"
        rect = "37.4979,127.0276,37.5279,127.0576"
        
        logger.info(f"검색 키워드: {keyword}")
        logger.info(f"검색 영역: {rect}")
        
        stores = crawler.get_store_list(keyword, rect)
        logger.info(f"\n총 {len(stores)}개 가게 발견")
        
        if not stores:
            logger.error("가게를 찾을 수 없습니다!")
            return
        
        # 테스트를 위해 10개로 제한
        test_stores = stores[:10]
        logger.info(f"테스트를 위해 상위 {len(test_stores)}개 가게만 처리")
        
        # 2단계: 모든 가게의 상세 정보 수집
        logger.info("\n[상세 정보 수집 시작]")
        detailed_stores = []
        
        for i, store in enumerate(test_stores):
            logger.info(f"\n상세 정보 수집: {i+1}/{len(test_stores)} - {store.get('name')}")
            
            try:
                detailed_store = crawler.get_store_detail(store)
                detailed_stores.append(detailed_store)
                
                # 수집된 정보 요약
                logger.info(f"  - 좌표: ({detailed_store.get('position_lat')}, {detailed_store.get('position_lng')})")
                logger.info(f"  - 주소: {detailed_store.get('address')}")
                logger.info(f"  - 전화: {detailed_store.get('phone_number')}")
                
            except Exception as e:
                logger.error(f"  - 상세 정보 수집 실패: {e}")
                detailed_stores.append(store)  # 기본 정보라도 유지
        
        # 3단계: 위치정보 상태 분석
        logger.info("\n[위치정보 수집 상태 분석]")
        analyze_location_status(detailed_stores, "상세 정보 수집 후")
        
        # 4단계: 데이터 향상 (지오코딩 포함)
        logger.info("\n[데이터 향상 시작]")
        data_enhancer = DataEnhancer()
        enhanced_stores, stats = data_enhancer.enhance_stores_data(detailed_stores)
        
        logger.info(f"\n데이터 향상 통계:")
        logger.info(f"- 지오코딩 성공: {stats.geocoding_success}개")
        logger.info(f"- 가격 정규화: {stats.price_normalized}개")
        logger.info(f"- 카테고리 매핑: {stats.categories_mapped}개")
        
        # 5단계: 최종 위치정보 상태 분석
        logger.info("\n[최종 위치정보 상태]")
        analyze_location_status(enhanced_stores, "데이터 향상 후")
        
        # 6단계: 결과 저장
        save_detailed_results(enhanced_stores)
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        crawler.close()
        logger.info("\n테스트 완료!")

def analyze_location_status(stores, stage_name):
    """위치정보 수집 상태 분석"""
    total = len(stores)
    
    # 위치정보 있는 가게
    with_coords = [s for s in stores if s.get('position_lat') and s.get('position_lng')]
    
    # 주소 있는 가게
    with_address = [s for s in stores if s.get('address') or s.get('basic_address')]
    
    # 좌표 출처별 분류
    source_count = {
        'javascript': 0,
        'kakao': 0,
        'estimated': 0,
        'none': 0
    }
    
    for store in stores:
        if store.get('position_lat') and store.get('position_lng'):
            source = store.get('geocoding_source', 'javascript')
            if source in source_count:
                source_count[source] += 1
        else:
            source_count['none'] += 1
    
    # 통계 출력
    logger.info(f"\n=== {stage_name} ===")
    logger.info(f"총 가게 수: {total}개")
    logger.info(f"좌표 있는 가게: {len(with_coords)}개 ({len(with_coords)/total*100:.1f}%)")
    logger.info(f"주소 있는 가게: {len(with_address)}개 ({len(with_address)/total*100:.1f}%)")
    logger.info(f"\n좌표 출처:")
    logger.info(f"  - JavaScript: {source_count['javascript']}개")
    logger.info(f"  - 카카오 API: {source_count['kakao']}개")
    logger.info(f"  - 추정: {source_count['estimated']}개")
    logger.info(f"  - 없음: {source_count['none']}개")

def save_detailed_results(stores):
    """상세 결과 저장"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. JSON으로 전체 데이터 저장
    json_filename = f'complete_location_test_{timestamp}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    logger.info(f"\n전체 데이터가 {json_filename}에 저장되었습니다.")
    
    # 2. CSV로 위치정보 중심 데이터 저장
    location_data = []
    for store in stores:
        location_data.append({
            'name': store.get('name'),
            'branch': store.get('branch'),
            'address': store.get('address') or store.get('basic_address'),
            'latitude': store.get('position_lat'),
            'longitude': store.get('position_lng'),
            'geocoding_source': store.get('geocoding_source', 'javascript' if store.get('position_lat') else 'none'),
            'phone': store.get('phone_number'),
            'categories': ', '.join(store.get('standard_categories', [])),
            'diningcode_id': store.get('diningcode_place_id'),
            'detail_url': f"https://www.diningcode.com/profile.php?rid={store.get('diningcode_place_id')}" if store.get('diningcode_place_id') else ''
        })
    
    csv_filename = f'complete_location_test_{timestamp}.csv'
    df = pd.DataFrame(location_data)
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    logger.info(f"위치정보 요약이 {csv_filename}에 저장되었습니다.")
    
    # 3. 위치정보 없는 가게 별도 저장
    no_location_stores = [s for s in stores if not s.get('position_lat') or not s.get('position_lng')]
    if no_location_stores:
        no_location_filename = f'no_location_stores_{timestamp}.json'
        with open(no_location_filename, 'w', encoding='utf-8') as f:
            json.dump(no_location_stores, f, ensure_ascii=False, indent=2)
        logger.info(f"위치정보 없는 {len(no_location_stores)}개 가게가 {no_location_filename}에 저장되었습니다.")

if __name__ == "__main__":
    test_complete_location_extraction() 