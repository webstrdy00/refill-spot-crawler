"""
종합적인 크롤러 테스트 - 다양한 유형의 가게 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.crawler import DiningCodeCrawler
from src.core.database import DatabaseManager
from src.utils.seoul_districts import SeoulDistricts
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/comprehensive_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_various_stores():
    """다양한 유형의 가게들을 테스트"""
    crawler = DiningCodeCrawler()
    db = DatabaseManager()
    
    # 테스트할 가게들 (다양한 유형)
    test_stores = [
        {
            'name': '우래옥 본점',
            'place_id': 'SXLVXGKDNM',
            'expected': '냉면 전문점, 일요일 휴무 예상'
        },
        {
            'name': '농민백암순대 본점',
            'place_id': 'YQDCVHQMZD',
            'expected': '연중무휴 예상'
        },
        {
            'name': '오레노라멘 본점',
            'place_id': 'KPXVQPXVHZ',
            'expected': '라멘 전문점'
        },
        {
            'name': '놀부부대찌개 강남점',
            'place_id': 'BXJQCHLVXK',
            'expected': '프랜차이즈, 정규 영업시간'
        },
        {
            'name': '제주몬트락',
            'place_id': 'MQFXLVQHZX',
            'expected': '제주 음식점'
        }
    ]
    
    results = []
    
    try:
        for idx, store in enumerate(test_stores, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"테스트 {idx}/{len(test_stores)}: {store['name']}")
            logger.info(f"예상: {store['expected']}")
            logger.info(f"{'='*60}")
            
            # 상세 정보 수집
            store_info = {
                'diningcode_place_id': store['place_id'],
                'name': store['name']
            }
            
            detail_info = crawler.get_store_detail(store_info)
            
            # 결과 분석
            result = {
                'name': store['name'],
                'address': detail_info.get('address', 'N/A'),
                'open_hours': detail_info.get('open_hours', 'N/A'),
                'holiday': detail_info.get('holiday', 'N/A'),
                'phone': detail_info.get('phone_number', 'N/A'),
                'menu_count': len(detail_info.get('menu_items', [])),
                'has_coordinates': bool(detail_info.get('position_lat') and detail_info.get('position_lng')),
                'refill_info': detail_info.get('is_confirmed_refill', False)
            }
            
            results.append(result)
            
            # 상세 결과 출력
            logger.info(f"\n[수집 결과]")
            logger.info(f"주소: {result['address']}")
            logger.info(f"영업시간: {result['open_hours']}")
            logger.info(f"휴무일: {result['holiday']}")
            logger.info(f"전화번호: {result['phone']}")
            logger.info(f"메뉴 수: {result['menu_count']}개")
            logger.info(f"좌표 정보: {'있음' if result['has_coordinates'] else '없음'}")
            logger.info(f"무한리필: {'확인됨' if result['refill_info'] else '미확인'}")
            
            # 영업시간 분석
            if result['open_hours'] and result['open_hours'] != 'N/A':
                days_with_hours = result['open_hours'].count(':')
                logger.info(f"영업시간 정보가 있는 요일 수: {days_with_hours}개")
                
                # 모든 요일이 있는지 확인
                all_days = ['월', '화', '수', '목', '금', '토', '일']
                for day in all_days:
                    if day + ':' in result['open_hours']:
                        logger.info(f"  {day}요일: ✓")
                    else:
                        logger.info(f"  {day}요일: ✗")
            
            # 데이터베이스에 저장
            if detail_info.get('name'):
                stores_to_insert = [{
                    **store_info,
                    **detail_info,
                    'source': 'comprehensive_test'
                }]
                
                inserted_count = db.insert_stores_batch(stores_to_insert)
                logger.info(f"데이터베이스 저장: {'성공' if inserted_count > 0 else '실패'}")
            
            # 잠시 대기
            import time
            time.sleep(3)
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        crawler.close()
        db.close()
    
    # 최종 요약
    logger.info(f"\n{'='*60}")
    logger.info("테스트 요약")
    logger.info(f"{'='*60}")
    
    total = len(results)
    with_address = sum(1 for r in results if r['address'] != 'N/A' and len(r['address']) > 5)
    with_hours = sum(1 for r in results if r['open_hours'] != 'N/A' and len(r['open_hours']) > 5)
    with_holiday = sum(1 for r in results if r['holiday'] != 'N/A' and len(r['holiday']) > 2)
    with_coords = sum(1 for r in results if r['has_coordinates'])
    
    logger.info(f"총 테스트 가게 수: {total}")
    logger.info(f"주소 수집 성공: {with_address}/{total} ({with_address/total*100:.1f}%)")
    logger.info(f"영업시간 수집 성공: {with_hours}/{total} ({with_hours/total*100:.1f}%)")
    logger.info(f"휴무일 정보 있음: {with_holiday}/{total} ({with_holiday/total*100:.1f}%)")
    logger.info(f"좌표 정보 있음: {with_coords}/{total} ({with_coords/total*100:.1f}%)")
    
    # 영업시간 완성도 분석
    logger.info(f"\n[영업시간 완성도 분석]")
    for result in results:
        if result['open_hours'] != 'N/A':
            days_count = result['open_hours'].count(':')
            logger.info(f"{result['name']}: {days_count}/7 요일 정보")

if __name__ == "__main__":
    test_various_stores() 