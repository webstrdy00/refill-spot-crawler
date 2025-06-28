"""
개선된 주소 및 영업시간 추출 테스트
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_improved_address_hours.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_improved_extraction():
    """개선된 주소 및 영업시간 추출 테스트"""
    crawler = DiningCodeCrawler()
    
    try:
        # 테스트할 가게 ID 목록 (다이닝코드 ID)
        test_stores = [
            {'diningcode_place_id': 'C220822145548', 'name': '테스트 가게 1'},
            {'diningcode_place_id': 'C220822145549', 'name': '테스트 가게 2'}
        ]
        
        # 실제로는 목록에서 가게를 가져오겠습니다
        logger.info("가게 목록 수집 중...")
        stores = crawler.get_store_list("서울 강남 무한리필", "37.4979,127.0276,37.5279,127.0576")
        
        if not stores:
            logger.warning("가게 목록을 찾을 수 없습니다.")
            return
        
        # 처음 3개 가게만 테스트
        test_count = min(3, len(stores))
        results = []
        
        for i in range(test_count):
            store = stores[i]
            logger.info(f"\n{'='*50}")
            logger.info(f"테스트 {i+1}/{test_count}: {store.get('name')}")
            logger.info(f"가게 ID: {store.get('diningcode_place_id')}")
            
            # 상세 정보 수집
            detailed_info = crawler.get_store_detail(store)
            
            # 주요 정보 추출
            result = {
                'name': detailed_info.get('name'),
                'diningcode_place_id': detailed_info.get('diningcode_place_id'),
                'address': detailed_info.get('address'),
                'basic_address': detailed_info.get('basic_address'),
                'road_address': detailed_info.get('road_address'),
                'open_hours': detailed_info.get('open_hours'),
                'open_hours_raw': detailed_info.get('open_hours_raw'),
                'break_time': detailed_info.get('break_time'),
                'last_order': detailed_info.get('last_order'),
                'holiday': detailed_info.get('holiday'),
                'phone_number': detailed_info.get('phone_number'),
                'position_lat': detailed_info.get('position_lat'),
                'position_lng': detailed_info.get('position_lng')
            }
            
            # 결과 출력
            logger.info(f"\n[주소 정보]")
            logger.info(f"  - 주소: {result['address'] or 'N/A'}")
            logger.info(f"  - 지번 주소: {result['basic_address'] or 'N/A'}")
            logger.info(f"  - 도로명 주소: {result['road_address'] or 'N/A'}")
            
            logger.info(f"\n[영업시간 정보]")
            logger.info(f"  - 영업시간: {result['open_hours'] or 'N/A'}")
            logger.info(f"  - 영업시간(원본): {result['open_hours_raw'] or 'N/A'}")
            logger.info(f"  - 브레이크타임: {result['break_time'] or 'N/A'}")
            logger.info(f"  - 라스트오더: {result['last_order'] or 'N/A'}")
            logger.info(f"  - 휴무일: {result['holiday'] or 'N/A'}")
            
            logger.info(f"\n[기타 정보]")
            logger.info(f"  - 전화번호: {result['phone_number'] or 'N/A'}")
            logger.info(f"  - 좌표: ({result['position_lat']}, {result['position_lng']})")
            
            results.append(result)
        
        # 결과를 JSON 파일로 저장
        with open('test_improved_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"테스트 완료! 결과가 test_improved_results.json에 저장되었습니다.")
        
        # 통계 출력
        address_count = sum(1 for r in results if r['address'])
        hours_count = sum(1 for r in results if r['open_hours'])
        holiday_count = sum(1 for r in results if r['holiday'] and '요일' in r['holiday'])
        
        logger.info(f"\n[수집 통계]")
        logger.info(f"  - 주소 수집: {address_count}/{test_count} ({address_count/test_count*100:.1f}%)")
        logger.info(f"  - 영업시간 수집: {hours_count}/{test_count} ({hours_count/test_count*100:.1f}%)")
        logger.info(f"  - 요일별 휴무일: {holiday_count}/{test_count} ({holiday_count/test_count*100:.1f}%)")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)
    finally:
        crawler.close()

if __name__ == "__main__":
    test_improved_extraction() 