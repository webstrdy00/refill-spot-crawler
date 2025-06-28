"""
개선된 위치정보 수집 크롤러 테스트
JavaScript 변수 추출 방식을 적용한 크롤러 성능 테스트
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
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_improved_location.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_improved_location_crawler():
    """개선된 위치정보 수집 크롤러 테스트"""
    
    logger.info("=" * 80)
    logger.info("개선된 위치정보 수집 크롤러 테스트 시작")
    logger.info("=" * 80)
    
    start_time = time.time()
    crawler = DiningCodeCrawler()
    
    try:
        # 1단계: 가게 목록 수집
        logger.info("\n[1단계] 가게 목록 수집")
        keyword = "강남 무한리필"
        rect = "37.4979,127.027,37.5178,127.047"
        
        stores = crawler.get_store_list(keyword, rect)
        logger.info(f"총 {len(stores)}개 가게 발견")
        
        if not stores:
            logger.error("가게 목록을 찾을 수 없습니다.")
            return False
        
        # 2단계: 모든 가게의 상세 정보 수집 (위치정보 포함)
        logger.info(f"\n[2단계] 모든 가게의 상세 정보 및 위치정보 수집")
        detailed_stores = []
        success_count = 0
        location_success_count = 0
        
        for i, store in enumerate(stores[:15], 1):  # 처음 15개만 테스트
            logger.info(f"\n--- {i}/{min(15, len(stores))} 가게 처리 중 ---")
            logger.info(f"가게명: {store.get('name', 'Unknown')}")
            
            try:
                # 상세 정보 수집
                detailed_store = crawler.get_store_detail(store)
                
                if detailed_store:
                    detailed_stores.append(detailed_store)
                    success_count += 1
                    
                    # 위치정보 확인
                    if detailed_store.get('position_lat') and detailed_store.get('position_lng'):
                        location_success_count += 1
                        logger.info(f"✅ 위치정보 수집 성공: ({detailed_store['position_lat']}, {detailed_store['position_lng']})")
                    else:
                        logger.warning("❌ 위치정보 수집 실패")
                        
                    # 진행률 표시
                    logger.info(f"진행률: {i}/{min(15, len(stores))} ({i/min(15, len(stores))*100:.1f}%)")
                    
                else:
                    logger.warning(f"가게 상세 정보 수집 실패: {store.get('name')}")
                    
            except Exception as e:
                logger.error(f"가게 처리 중 오류: {e}")
                continue
            
            # 간격 조정
            time.sleep(1)
        
        # 3단계: 결과 분석
        logger.info("\n[3단계] 결과 분석")
        total_processed = min(15, len(stores))
        
        logger.info(f"전체 처리 가게 수: {total_processed}")
        logger.info(f"상세 정보 수집 성공: {success_count}개 ({success_count/total_processed*100:.1f}%)")
        logger.info(f"위치정보 수집 성공: {location_success_count}개 ({location_success_count/total_processed*100:.1f}%)")
        
        # 4단계: 데이터 향상 (지오코딩)
        if detailed_stores:
            logger.info("\n[4단계] 데이터 향상 (지오코딩)")
            enhancer = DataEnhancer()
            
            # 위치정보가 없는 가게들에 대해 지오코딩 시도
            no_location_stores = [store for store in detailed_stores 
                                if not store.get('position_lat') and store.get('address')]
            
            if no_location_stores:
                logger.info(f"{len(no_location_stores)}개 가게에 대해 지오코딩 시도")
                enhanced_stores = enhancer.enhance_store_data(detailed_stores)
                
                # 지오코딩 성공률 계산
                geocoding_success = sum(1 for store in enhanced_stores 
                                      if store.get('position_lat') and store.get('position_lng'))
                final_location_success = geocoding_success
                
                logger.info(f"지오코딩 후 최종 위치정보 보유: {final_location_success}개 ({final_location_success/total_processed*100:.1f}%)")
                detailed_stores = enhanced_stores
            else:
                logger.info("지오코딩이 필요한 가게가 없습니다.")
        
        # 5단계: 결과 저장
        logger.info("\n[5단계] 결과 저장")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # CSV 저장
        if detailed_stores:
            df = pd.DataFrame(detailed_stores)
            csv_filename = f"improved_location_test_{timestamp}.csv"
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            logger.info(f"CSV 파일 저장: {csv_filename}")
            
            # JSON 저장
            json_filename = f"improved_location_test_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(detailed_stores, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON 파일 저장: {json_filename}")
        
        # 6단계: 최종 결과 요약
        end_time = time.time()
        total_time = end_time - start_time
        
        logger.info("\n" + "=" * 80)
        logger.info("최종 테스트 결과 요약")
        logger.info("=" * 80)
        logger.info(f"총 소요 시간: {total_time:.1f}초")
        logger.info(f"처리된 가게 수: {len(detailed_stores)}개")
        logger.info(f"위치정보 보유 가게: {sum(1 for s in detailed_stores if s.get('position_lat'))}개")
        logger.info(f"위치정보 성공률: {sum(1 for s in detailed_stores if s.get('position_lat'))/len(detailed_stores)*100:.1f}%" if detailed_stores else "0%")
        
        # 위치정보가 있는 가게들의 좌표 출력
        location_stores = [s for s in detailed_stores if s.get('position_lat')]
        if location_stores:
            logger.info("\n📍 위치정보가 수집된 가게들:")
            for store in location_stores:
                logger.info(f"- {store.get('name', 'Unknown')}: ({store['position_lat']}, {store['position_lng']})")
        
        return len(detailed_stores) > 0 and sum(1 for s in detailed_stores if s.get('position_lat')) > 0
        
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        crawler.close()

if __name__ == "__main__":
    success = test_improved_location_crawler()
    if success:
        print("\n✅ 개선된 위치정보 수집 테스트 성공!")
    else:
        print("\n❌ 개선된 위치정보 수집 테스트 실패!") 