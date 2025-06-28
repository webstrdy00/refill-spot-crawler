"""
위치정보 추출 테스트 스크립트
다이닝코드에서 가게 위치정보(위도, 경도)가 제대로 수집되는지 확인
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.crawler import DiningCodeCrawler
import logging
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_location.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_location_extraction():
    """위치정보 추출 테스트"""
    crawler = DiningCodeCrawler()
    
    try:
        # 1. 가게 목록에서 위치정보 추출 테스트
        logger.info("=" * 60)
        logger.info("1단계: 가게 목록에서 위치정보 추출 테스트")
        logger.info("=" * 60)
        
        # 강남 지역 무한리필 가게 검색
        keyword = "강남 무한리필"
        rect = "37.4979,127.0276,37.5279,127.0576"  # 강남 지역 좌표
        
        logger.info(f"검색 키워드: {keyword}")
        logger.info(f"검색 영역: {rect}")
        
        stores = crawler.get_store_list(keyword, rect)
        
        if stores:
            logger.info(f"\n총 {len(stores)}개 가게 발견!")
            
            # 위치정보가 있는 가게 수 확인
            stores_with_location = [s for s in stores if s.get('position_lat') and s.get('position_lng')]
            logger.info(f"위치정보가 있는 가게: {len(stores_with_location)}개")
            
            # 처음 5개 가게의 위치정보 출력
            logger.info("\n[가게 목록의 위치정보]")
            for i, store in enumerate(stores[:5]):
                logger.info(f"\n{i+1}. {store.get('name', 'Unknown')} {store.get('branch', '')}")
                logger.info(f"   ID: {store.get('diningcode_place_id', 'N/A')}")
                logger.info(f"   위도: {store.get('position_lat', 'N/A')}")
                logger.info(f"   경도: {store.get('position_lng', 'N/A')}")
                logger.info(f"   주소: {store.get('basic_address', 'N/A')}")
                logger.info(f"   도로명주소: {store.get('road_address', 'N/A')}")
                
            # 2. 상세 페이지에서 위치정보 추출 테스트
            if stores:
                logger.info("\n" + "=" * 60)
                logger.info("2단계: 상세 페이지에서 위치정보 추출 테스트")
                logger.info("=" * 60)
                
                # 첫 번째 가게의 상세 정보 가져오기
                test_store = stores[0]
                logger.info(f"\n테스트 대상: {test_store.get('name')} (ID: {test_store.get('diningcode_place_id')})")
                
                detailed_info = crawler.get_store_detail(test_store)
                
                logger.info("\n[상세 페이지의 위치정보]")
                logger.info(f"가게명: {detailed_info.get('name', 'Unknown')}")
                logger.info(f"위도: {detailed_info.get('position_lat', 'N/A')}")
                logger.info(f"경도: {detailed_info.get('position_lng', 'N/A')}")
                logger.info(f"주소: {detailed_info.get('address', 'N/A')}")
                
                # 위치정보 비교 (목록 vs 상세)
                if test_store.get('position_lat') and detailed_info.get('position_lat'):
                    logger.info("\n[위치정보 비교]")
                    logger.info(f"목록 페이지 좌표: ({test_store.get('position_lat')}, {test_store.get('position_lng')})")
                    logger.info(f"상세 페이지 좌표: ({detailed_info.get('position_lat')}, {detailed_info.get('position_lng')})")
                    
                    # 좌표 차이 계산
                    lat_diff = abs(float(test_store.get('position_lat', 0)) - float(detailed_info.get('position_lat', 0)))
                    lng_diff = abs(float(test_store.get('position_lng', 0)) - float(detailed_info.get('position_lng', 0)))
                    
                    if lat_diff < 0.001 and lng_diff < 0.001:
                        logger.info("✓ 좌표가 일치합니다!")
                    else:
                        logger.warning(f"좌표 차이 발생 - 위도차: {lat_diff}, 경도차: {lng_diff}")
                
                # 결과 저장
                result = {
                    'test_date': str(pd.Timestamp.now()),
                    'keyword': keyword,
                    'total_stores': len(stores),
                    'stores_with_location': len(stores_with_location),
                    'location_rate': f"{len(stores_with_location)/len(stores)*100:.1f}%" if stores else "0%",
                    'test_store': {
                        'name': detailed_info.get('name'),
                        'lat': detailed_info.get('position_lat'),
                        'lng': detailed_info.get('position_lng'),
                        'address': detailed_info.get('address')
                    }
                }
                
                with open('test_location_result.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                logger.info("\n테스트 결과가 test_location_result.json에 저장되었습니다.")
                
        else:
            logger.error("가게를 찾을 수 없습니다!")
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        crawler.close()
        logger.info("\n테스트 완료!")

if __name__ == "__main__":
    import pandas as pd
    test_location_extraction() 