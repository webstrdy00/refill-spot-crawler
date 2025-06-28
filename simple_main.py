"""
리필스팟 크롤러 간소화된 메인 실행 파일
앞서 개선한 주소, 영업시간, break_time, last_order 수집 기능 적용
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/simple_crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_enhanced_crawling():
    """개선된 크롤링 실행 (강남 지역 테스트)"""
    try:
        # 로그 디렉토리 생성
        os.makedirs('logs', exist_ok=True)
        
        logger.info("🚀 개선된 크롤링 시스템 시작")
        logger.info("📍 강남 지역 크롤링을 실행합니다...")
        logger.info("✨ 개선된 기능: 주소 추출, 영업시간, break_time, last_order 수집")
        
        # 크롤러 임포트 및 실행
        from src.core.crawler import DiningCodeCrawler
        from src.core.database import DatabaseManager
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        db = DatabaseManager()
        
        # 강남 지역 크롤링 설정
        keyword = "서울 강남 무한리필"
        rect = "37.4979,127.0276,37.5279,127.0576"  # 강남 지역 좌표
        
        logger.info(f"검색 키워드: {keyword}")
        logger.info(f"검색 영역: {rect}")
        
        # 가게 목록 수집
        stores = crawler.get_store_list(keyword, rect)
        logger.info(f"수집된 가게 수: {len(stores)}개")
        
        if not stores:
            logger.warning("수집된 가게가 없습니다.")
            return False
        
        # 상세 정보 수집
        detailed_stores = []
        success_count = 0
        
        for i, store in enumerate(stores, 1):
            try:
                logger.info(f"상세 정보 수집 중... ({i}/{len(stores)}) {store.get('name', 'Unknown')}")
                
                detail_info = crawler.get_store_detail(store)
                if detail_info:
                    detailed_stores.append(detail_info)
                    success_count += 1
                    
                    # 개선된 기능 확인 로그
                    logger.info(f"  ✅ 주소: {detail_info.get('address', 'N/A')[:50]}...")
                    logger.info(f"  ✅ 영업시간: {detail_info.get('open_hours', 'N/A')[:50]}...")
                    logger.info(f"  ✅ 브레이크타임: {detail_info.get('break_time', 'N/A')}")
                    logger.info(f"  ✅ 라스트오더: {detail_info.get('last_order', 'N/A')}")
                    logger.info(f"  ✅ 휴무일: {detail_info.get('holiday', 'N/A')}")
                    
            except Exception as e:
                logger.error(f"가게 상세 정보 수집 실패: {e}")
                continue
        
        logger.info(f"상세 정보 수집 완료: {success_count}/{len(stores)}개")
        
        # 데이터베이스 저장
        if detailed_stores:
            try:
                inserted_count = db.insert_stores_batch(detailed_stores)
                logger.info(f"데이터베이스 저장 완료: {inserted_count}개")
                
                # 성공 통계
                success_rate = (success_count / len(stores)) * 100
                logger.info(f"전체 성공률: {success_rate:.1f}%")
                
                # 개선된 기능 통계
                check_improvement_stats(detailed_stores)
                
                return True
                
            except Exception as e:
                logger.error(f"데이터베이스 저장 실패: {e}")
                return False
        else:
            logger.warning("저장할 데이터가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"크롤링 실행 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
        # 리소스 정리
        try:
            crawler.close()
            db.close()
        except:
            pass

def check_improvement_stats(stores):
    """개선된 기능 통계 확인"""
    logger.info("🔍 개선된 기능 통계 확인:")
    
    # 주소 수집률
    address_count = sum(1 for store in stores if store.get('address'))
    address_rate = (address_count / len(stores)) * 100
    logger.info(f"  📍 주소 수집률: {address_count}/{len(stores)} ({address_rate:.1f}%)")
    
    # 영업시간 수집률
    hours_count = sum(1 for store in stores if store.get('open_hours'))
    hours_rate = (hours_count / len(stores)) * 100
    logger.info(f"  🕐 영업시간 수집률: {hours_count}/{len(stores)} ({hours_rate:.1f}%)")
    
    # 브레이크타임 수집률
    break_count = sum(1 for store in stores if store.get('break_time'))
    break_rate = (break_count / len(stores)) * 100
    logger.info(f"  ☕ 브레이크타임 수집률: {break_count}/{len(stores)} ({break_rate:.1f}%)")
    
    # 라스트오더 수집률
    last_order_count = sum(1 for store in stores if store.get('last_order'))
    last_order_rate = (last_order_count / len(stores)) * 100
    logger.info(f"  🍽️ 라스트오더 수집률: {last_order_count}/{len(stores)} ({last_order_rate:.1f}%)")
    
    # 휴무일 수집률
    holiday_count = sum(1 for store in stores if store.get('holiday'))
    holiday_rate = (holiday_count / len(stores)) * 100
    logger.info(f"  🚫 휴무일 수집률: {holiday_count}/{len(stores)} ({holiday_rate:.1f}%)")
    
    # 요일별 영업시간 수집률 (월화수목금토일 패턴 확인)
    weekday_pattern_count = 0
    for store in stores:
        hours = store.get('open_hours', '')
        if any(day in hours for day in ['월', '화', '수', '목', '금', '토', '일']):
            weekday_pattern_count += 1
    
    weekday_rate = (weekday_pattern_count / len(stores)) * 100
    logger.info(f"  📅 요일별 영업시간 수집률: {weekday_pattern_count}/{len(stores)} ({weekday_rate:.1f}%)")

def run_full_crawling():
    """전체 서울 크롤링 실행 (간소화 버전)"""
    try:
        logger.info("🚀 전체 서울 크롤링 시스템 시작")
        
        from src.core.crawler import DiningCodeCrawler
        from src.core.database import DatabaseManager
        
        crawler = DiningCodeCrawler()
        db = DatabaseManager()
        
        # 서울시 주요 지역 설정 (간소화)
        seoul_regions = [
            {"name": "강남", "keyword": "서울 강남 무한리필", "rect": "37.4979,127.0276,37.5279,127.0576"},
            {"name": "강북", "keyword": "서울 강북 무한리필", "rect": "37.6279,127.0076,37.6579,127.0376"},
            {"name": "마포", "keyword": "서울 마포 무한리필", "rect": "37.5379,126.8976,37.5679,126.9276"},
            {"name": "송파", "keyword": "서울 송파 무한리필", "rect": "37.4779,127.0876,37.5079,127.1176"},
            {"name": "영등포", "keyword": "서울 영등포 무한리필", "rect": "37.5079,126.8876,37.5379,126.9176"}
        ]
        
        total_stores = 0
        
        for region in seoul_regions:
            logger.info(f"📍 {region['name']} 지역 크롤링 시작")
            
            try:
                # 지역별 크롤링
                stores = crawler.get_store_list(region['keyword'], region['rect'])
                
                if stores:
                    # 상세 정보 수집
                    detailed_stores = []
                    for store in stores:
                        detail_info = crawler.get_store_detail(store)
                        if detail_info:
                            detailed_stores.append(detail_info)
                    
                    if detailed_stores:
                        inserted_count = db.insert_stores_batch(detailed_stores)
                        total_stores += inserted_count
                        logger.info(f"{region['name']} 지역: {inserted_count}개 저장")
            
            except Exception as e:
                logger.error(f"{region['name']} 지역 크롤링 실패: {e}")
                continue
        
        logger.info(f"🎉 전체 크롤링 완료! 총 {total_stores}개 가게 수집")
        return True
        
    except Exception as e:
        logger.error(f"전체 크롤링 실행 중 오류: {e}")
        return False
    
    finally:
        try:
            crawler.close()
            db.close()
        except:
            pass

def check_database_status():
    """데이터베이스 상태 확인"""
    try:
        logger.info("🔍 데이터베이스 상태 확인")
        
        from src.core.database import DatabaseManager
        db = DatabaseManager()
        
        # 기본 연결 테스트
        if not db.test_connection():
            logger.error("❌ 데이터베이스 연결 실패")
            return False
        
        logger.info("✅ 데이터베이스 연결 성공")
        
        # 테이블 확인
        try:
            cursor = db.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM stores")
            store_count = cursor.fetchone()[0]
            logger.info(f"📊 현재 저장된 가게 수: {store_count}개")
            
            # 개선된 필드 확인
            cursor.execute("SELECT COUNT(*) FROM stores WHERE address IS NOT NULL AND address != ''")
            address_count = cursor.fetchone()[0]
            address_rate = (address_count / store_count * 100) if store_count > 0 else 0
            logger.info(f"📍 주소 보유 가게: {address_count}개 ({address_rate:.1f}%)")
            
            cursor.execute("SELECT COUNT(*) FROM stores WHERE break_time IS NOT NULL AND break_time != ''")
            break_time_count = cursor.fetchone()[0]
            break_time_rate = (break_time_count / store_count * 100) if store_count > 0 else 0
            logger.info(f"☕ 브레이크타임 보유 가게: {break_time_count}개 ({break_time_rate:.1f}%)")
            
            cursor.execute("SELECT COUNT(*) FROM stores WHERE last_order IS NOT NULL AND last_order != ''")
            last_order_count = cursor.fetchone()[0]
            last_order_rate = (last_order_count / store_count * 100) if store_count > 0 else 0
            logger.info(f"🍽️ 라스트오더 보유 가게: {last_order_count}개 ({last_order_rate:.1f}%)")
            
            cursor.close()
            
        except Exception as e:
            logger.warning(f"테이블 상태 확인 실패: {e}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 상태 확인 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='리필스팟 크롤러 (개선된 버전)')
    parser.add_argument('mode', choices=['enhanced', 'full', 'stage4', 'check'], 
                       help='실행 모드: enhanced(강남만), full(주요지역), stage4(호환성), check(DB상태확인)')
    
    args = parser.parse_args()
    
    print("🍽️ 리필스팟 크롤러 (개선된 버전)")
    print("=" * 50)
    print("✨ 개선된 기능:")
    print("  - 주소 정확 추출")
    print("  - 요일별 영업시간 수집")
    print("  - 브레이크타임 정보 수집")
    print("  - 라스트오더 정보 수집")
    print("  - 휴무일 정보 수집")
    print("=" * 50)
    
    if args.mode == 'enhanced':
        print("🚀 개선된 크롤링 모드 (강남 지역)")
        success = run_enhanced_crawling()
    elif args.mode == 'full':
        print("🌍 전체 서울 주요 지역 크롤링 모드")
        success = run_full_crawling()
    elif args.mode == 'stage4':
        print("🔄 Stage4 호환 모드 (강남 지역)")
        success = run_enhanced_crawling()
    elif args.mode == 'check':
        print("🔍 데이터베이스 상태 확인 모드")
        success = check_database_status()
    
    if success:
        print("✅ 실행 완료!")
    else:
        print("❌ 실행 실패!")
        sys.exit(1)

if __name__ == "__main__":
    main() 