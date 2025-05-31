"""
개선된 다이닝코드 크롤링 테스트
"""

import logging
import json
import time
import os
from datetime import datetime
from crawler import DiningCodeCrawler
import config

# data 폴더 생성 (없으면)
os.makedirs('data', exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_improved_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_improved_crawler():
    """개선된 크롤러 테스트"""
    crawler = None
    
    try:
        logger.info("=== 개선된 다이닝코드 크롤러 테스트 시작 ===")
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        
        # 테스트 설정 - 강남 지역으로 변경 (뷔페 제외)
        test_keywords = ["서울 강남 무한리필", "강남 고기무한리필"]
        test_rect = config.REGIONS["강남"]["rect"]  # 강남 지역 좌표
        
        logger.info(f"검색 지역: {config.REGIONS['강남']['name']}")
        logger.info(f"검색 영역: {test_rect}")
        
        all_results = []
        
        for keyword in test_keywords:
            logger.info(f"\n=== 키워드 '{keyword}' 테스트 ===")
            
            # 1. 가게 목록 수집
            stores = crawler.get_store_list(keyword, test_rect)
            logger.info(f"목록 수집 결과: {len(stores)}개 가게 발견")
            
            if not stores:
                logger.warning(f"키워드 '{keyword}'로 검색된 가게가 없습니다.")
                continue
            
            # 2. 상위 3개 가게의 상세 정보 수집
            detailed_stores = []
            for i, store in enumerate(stores[:3]):
                try:
                    logger.info(f"\n상세 정보 수집 {i+1}/3: {store.get('name')}")
                    
                    # 상세 정보 수집
                    detailed_store = crawler.get_store_detail(store)
                    detailed_stores.append(detailed_store)
                    
                    # 결과 요약 출력
                    logger.info("=== 수집된 정보 요약 ===")
                    logger.info(f"가게명: {detailed_store.get('name')}")
                    logger.info(f"지점: {detailed_store.get('branch', 'N/A')}")
                    logger.info(f"주소: {detailed_store.get('address', 'N/A')}")
                    logger.info(f"전화번호: {detailed_store.get('phone_number', 'N/A')}")
                    logger.info(f"좌표: ({detailed_store.get('position_lat')}, {detailed_store.get('position_lng')})")
                    logger.info(f"평점: {detailed_store.get('diningcode_rating', 'N/A')}")
                    logger.info(f"카테고리: {detailed_store.get('raw_categories_diningcode', [])}")
                    logger.info(f"이미지 수: {len(detailed_store.get('image_urls', []))}")
                    
                    # 데이터 품질 체크
                    quality_score = 0
                    if detailed_store.get('position_lat') and detailed_store.get('position_lng'):
                        quality_score += 30
                    if detailed_store.get('address'):
                        quality_score += 20
                    if detailed_store.get('phone_number'):
                        quality_score += 20
                    if detailed_store.get('raw_categories_diningcode'):
                        quality_score += 15
                    if detailed_store.get('image_urls'):
                        quality_score += 15
                    
                    logger.info(f"데이터 품질 점수: {quality_score}/100")
                    
                    # 무한리필 관련성 체크 (개선된 로직)
                    refill_relevance = check_refill_relevance(detailed_store, keyword)
                    logger.info(f"무한리필 관련성: {'✅' if refill_relevance else '❌'}")
                    
                    time.sleep(3)  # 요청 간 지연
                    
                except Exception as e:
                    logger.error(f"상세 정보 수집 실패: {store.get('name')} - {e}")
                    continue
            
            # 키워드별 결과 저장
            keyword_result = {
                'keyword': keyword,
                'search_area': test_rect,
                'region_name': config.REGIONS['강남']['name'],
                'total_found': len(stores),
                'detailed_collected': len(detailed_stores),
                'stores': detailed_stores,
                'timestamp': datetime.now().isoformat()
            }
            
            all_results.append(keyword_result)
            
            logger.info(f"\n키워드 '{keyword}' 완료: {len(detailed_stores)}개 상세 정보 수집")
            
            # 키워드 간 지연
            time.sleep(5)
        
        # 전체 결과 저장
        result_filename = f"data/improved_crawler_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n=== 테스트 완료 ===")
        logger.info(f"전체 결과를 {result_filename}에 저장했습니다.")
        
        # 결과 요약
        total_stores = sum(len(result['stores']) for result in all_results)
        logger.info(f"총 수집된 가게 수: {total_stores}개")
        
        # 데이터 품질 분석
        quality_analysis = analyze_data_quality(all_results)
        logger.info("\n=== 데이터 품질 분석 ===")
        for key, value in quality_analysis.items():
            logger.info(f"{key}: {value}")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
    
    finally:
        if crawler:
            crawler.close()

def check_refill_relevance(store, search_keyword):
    """무한리필 관련성 체크 (개선된 로직)"""
    refill_keywords = ['무한리필', '뷔페', '무제한', '리필', '자유이용권']
    
    # 1. 검색 키워드 자체에 무한리필 관련 단어가 있으면 관련성 있음
    for keyword in refill_keywords:
        if keyword in search_keyword:
            return True
    
    # 2. 가게 이름에서 확인
    name = store.get('name', '')
    for keyword in refill_keywords:
        if keyword in name:
            return True
    
    # 3. 카테고리에서 확인
    categories = store.get('raw_categories_diningcode', [])
    for category in categories:
        for keyword in refill_keywords:
            if keyword in category:
                return True
    
    # 4. 설명에서 확인
    description = store.get('description', '')
    for keyword in refill_keywords:
        if keyword in description:
            return True
    
    return False

def analyze_data_quality(results):
    """데이터 품질 분석"""
    analysis = {
        '총 가게 수': 0,
        '좌표 정보 있음': 0,
        '주소 정보 있음': 0,
        '전화번호 있음': 0,
        '카테고리 정보 있음': 0,
        '이미지 있음': 0,
        '무한리필 관련성 있음': 0
    }
    
    for result in results:
        search_keyword = result['keyword']
        for store in result['stores']:
            analysis['총 가게 수'] += 1
            
            if store.get('position_lat') and store.get('position_lng'):
                analysis['좌표 정보 있음'] += 1
            
            if store.get('address'):
                analysis['주소 정보 있음'] += 1
            
            if store.get('phone_number'):
                analysis['전화번호 있음'] += 1
            
            if store.get('raw_categories_diningcode'):
                analysis['카테고리 정보 있음'] += 1
            
            if store.get('image_urls'):
                analysis['이미지 있음'] += 1
            
            # 개선된 무한리필 관련성 체크
            if check_refill_relevance(store, search_keyword):
                analysis['무한리필 관련성 있음'] += 1
    
    # 비율 계산
    total = analysis['총 가게 수']
    if total > 0:
        for key in analysis:
            if key != '총 가게 수':
                count = analysis[key]
                percentage = (count / total) * 100
                analysis[key] = f"{count}/{total} ({percentage:.1f}%)"
    
    return analysis

def test_single_store():
    """단일 가게 상세 테스트 (강남 지역)"""
    crawler = None
    
    try:
        logger.info("=== 단일 가게 상세 테스트 (강남 지역) ===")
        
        crawler = DiningCodeCrawler()
        
        # 강남 지역에서 무한리필 검색
        keyword = "서울 강남 무한리필"
        rect = config.REGIONS["강남"]["rect"]
        
        logger.info(f"검색 키워드: {keyword}")
        logger.info(f"검색 지역: {config.REGIONS['강남']['name']}")
        logger.info(f"검색 영역: {rect}")
        
        stores = crawler.get_store_list(keyword, rect)
        
        if stores:
            test_store = stores[0]
            logger.info(f"테스트 대상: {test_store.get('name')}")
            
            # 상세 정보 수집
            detailed_store = crawler.get_store_detail(test_store)
            
            # 무한리필 관련성 체크
            refill_relevance = check_refill_relevance(detailed_store, keyword)
            detailed_store['refill_relevance'] = refill_relevance
            
            # 결과 출력
            logger.info("\n=== 상세 정보 ===")
            for key, value in detailed_store.items():
                logger.info(f"{key}: {value}")
            
            logger.info(f"\n무한리필 관련성: {'✅ 관련 있음' if refill_relevance else '❌ 관련 없음'}")
            
            # JSON 저장
            with open('data/single_store_test.json', 'w', encoding='utf-8') as f:
                json.dump(detailed_store, f, ensure_ascii=False, indent=2)
            
            logger.info("\n결과를 data/single_store_test.json에 저장했습니다.")
        else:
            logger.warning("테스트할 가게를 찾을 수 없습니다.")
    
    except Exception as e:
        logger.error(f"단일 가게 테스트 중 오류: {e}")
    
    finally:
        if crawler:
            crawler.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        test_single_store()
    else:
        test_improved_crawler() 