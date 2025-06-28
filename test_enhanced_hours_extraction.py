"""
개선된 영업시간 추출 기능 테스트
break_time, last_order, 모든 요일 영업시간 수집 확인
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.crawler import DiningCodeCrawler
from src.core.database import DatabaseManager
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/enhanced_hours_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def safe_get_length(value):
    """안전하게 길이를 가져오는 함수"""
    if value is None:
        return 0
    return len(str(value))

def test_enhanced_hours_extraction():
    """개선된 영업시간 추출 기능 테스트"""
    crawler = DiningCodeCrawler()
    db = DatabaseManager()
    
    # 테스트할 가게들 (우래옥 본점으로 집중 테스트)
    test_stores = [
        {
            'name': '우래옥 본점',
            'diningcode_place_id': 'TjHHaWq8Ylqt',
            'expected': '일요일 휴무, 라스트오더 정보 포함'
        }
    ]
    
    results = []
    
    try:
        for idx, store in enumerate(test_stores, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"테스트 {idx}/{len(test_stores)}: {store['name']}")
            logger.info(f"예상: {store['expected']}")
            logger.info(f"{'='*80}")
            
            # 상세 정보 수집
            store_info = {
                'diningcode_place_id': store['diningcode_place_id'],
                'name': store['name']
            }
            
            detail_info = crawler.get_store_detail(store_info)
            
            # 결과 분석
            result = {
                'name': store['name'],
                'address': detail_info.get('address', ''),
                'open_hours': detail_info.get('open_hours', ''),
                'holiday': detail_info.get('holiday', ''),
                'break_time': detail_info.get('break_time', ''),
                'last_order': detail_info.get('last_order', ''),
                'phone': detail_info.get('phone_number', '')
            }
            
            results.append(result)
            
            # 상세 결과 출력
            logger.info(f"\n[수집 결과]")
            logger.info(f"가게명: {result['name']}")
            logger.info(f"주소: {result['address'] or 'N/A'}")
            logger.info(f"전화번호: {result['phone'] or 'N/A'}")
            logger.info(f"\n[영업시간 정보]")
            logger.info(f"영업시간: {result['open_hours'] or 'N/A'}")
            logger.info(f"휴무일: {result['holiday'] or 'N/A'}")
            logger.info(f"브레이크타임: {result['break_time'] or 'N/A'}")
            logger.info(f"라스트오더: {result['last_order'] or 'N/A'}")
            
            # 영업시간 상세 분석
            if result['open_hours']:
                logger.info(f"\n[영업시간 상세 분석]")
                
                # 요일별 영업시간 확인
                all_days = ['월', '화', '수', '목', '금', '토', '일']
                days_with_hours = 0
                
                for day in all_days:
                    if f"{day}:" in result['open_hours']:
                        days_with_hours += 1
                        # 해당 요일의 영업시간 추출
                        day_parts = [part.strip() for part in result['open_hours'].split(', ') if part.startswith(f"{day}:")]
                        if day_parts:
                            logger.info(f"  {day_parts[0]}")
                    else:
                        logger.info(f"  {day}: 정보 없음")
                
                logger.info(f"\n영업시간 완성도: {days_with_hours}/7 요일 ({days_with_hours/7*100:.1f}%)")
                
                # 브레이크타임 분석
                if result['break_time']:
                    logger.info(f"✓ 브레이크타임 수집 성공: {result['break_time']}")
                else:
                    logger.info(f"✗ 브레이크타임 정보 없음")
                
                # 라스트오더 분석
                if result['last_order']:
                    logger.info(f"✓ 라스트오더 수집 성공: {result['last_order']}")
                else:
                    logger.info(f"✗ 라스트오더 정보 없음")
            
            # 데이터베이스에 저장
            if detail_info.get('name'):
                stores_to_insert = [{
                    **store_info,
                    **detail_info,
                    'source': 'enhanced_hours_test'
                }]
                
                try:
                    inserted_count = db.insert_stores_batch(stores_to_insert)
                    logger.info(f"✓ 데이터베이스 저장 성공")
                except Exception as e:
                    logger.error(f"✗ 데이터베이스 저장 실패: {e}")
            
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
    logger.info(f"\n{'='*80}")
    logger.info("테스트 요약")
    logger.info(f"{'='*80}")
    
    total = len(results)
    with_address = sum(1 for r in results if r['address'] and safe_get_length(r['address']) > 5)
    with_hours = sum(1 for r in results if r['open_hours'] and safe_get_length(r['open_hours']) > 5)
    with_break_time = sum(1 for r in results if r['break_time'])
    with_last_order = sum(1 for r in results if r['last_order'])
    
    logger.info(f"총 테스트 가게 수: {total}")
    logger.info(f"주소 수집 성공: {with_address}/{total} ({with_address/total*100:.1f}%)")
    logger.info(f"영업시간 수집 성공: {with_hours}/{total} ({with_hours/total*100:.1f}%)")
    logger.info(f"브레이크타임 수집 성공: {with_break_time}/{total} ({with_break_time/total*100:.1f}%)")
    logger.info(f"라스트오더 수집 성공: {with_last_order}/{total} ({with_last_order/total*100:.1f}%)")
    
    # 영업시간 완성도 분석
    logger.info(f"\n[영업시간 완성도 분석]")
    for result in results:
        if result['open_hours']:
            days_count = result['open_hours'].count(':')
            completeness = f"{days_count}/7 요일"
            
            extra_info = []
            if result['break_time']:
                extra_info.append("브레이크타임")
            if result['last_order']:
                extra_info.append("라스트오더")
            
            extra_str = f" + {', '.join(extra_info)}" if extra_info else ""
            logger.info(f"{result['name']}: {completeness}{extra_str}")
    
    # 개선 효과 분석
    logger.info(f"\n[개선 효과 분석]")
    complete_hours = sum(1 for r in results if r['open_hours'] and r['open_hours'].count(':') >= 6)  # 6개 이상 요일
    logger.info(f"거의 완전한 영업시간 수집: {complete_hours}/{total} ({complete_hours/total*100:.1f}%)")
    
    additional_info = sum(1 for r in results if r['break_time'] or r['last_order'])
    logger.info(f"추가 정보(브레이크타임/라스트오더) 수집: {additional_info}/{total} ({additional_info/total*100:.1f}%)")

if __name__ == "__main__":
    # logs 폴더 생성
    os.makedirs('logs', exist_ok=True)
    test_enhanced_hours_extraction() 