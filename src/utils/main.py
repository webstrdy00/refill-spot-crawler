"""
리필스팟 크롤러 메인 실행 모듈 (간소화된 버전)
앞서 개선한 주소, 영업시간, break_time, last_order 수집 기능 적용
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/main_crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_gangnam_test():
    """강남 지역 테스트 크롤링 (개선된 기능 확인용)"""
    try:
        # 로그 디렉토리 생성
        os.makedirs('logs', exist_ok=True)
        
        logger.info("🚀 강남 지역 테스트 크롤링 시작")
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
                logger.info(f"데이터베이스 저장 완료: {len(inserted_count)}개")
                
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
        logger.error(f"강남 테스트 크롤링 실행 중 오류: {e}")
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

def run_basic_test():
    """기본 테스트 (단일 가게 상세 정보 확인)"""
    try:
        logger.info("🔍 기본 테스트 시작 (단일 가게 상세 정보 확인)")
        
        from src.core.crawler import DiningCodeCrawler
        from src.core.database import DatabaseManager
        
        crawler = DiningCodeCrawler()
        db = DatabaseManager()
        
        # 강남 지역에서 첫 번째 가게 찾기
        keyword = "서울 강남 무한리필"
        rect = "37.4979,127.0276,37.5279,127.0576"
        
        stores = crawler.get_store_list(keyword, rect)
        
        if not stores:
            logger.warning("테스트할 가게를 찾을 수 없습니다.")
            return False
        
        # 첫 번째 가게 상세 정보 수집
        test_store = stores[0]
        logger.info(f"테스트 대상: {test_store.get('name')}")
        
        detail_info = crawler.get_store_detail(test_store)
        
        if detail_info:
            logger.info("=== 기본 테스트 결과 ===")
            logger.info(f"📍 가게명: {detail_info.get('name')}")
            logger.info(f"📍 주소: {detail_info.get('address')}")
            logger.info(f"📞 전화번호: {detail_info.get('phone_number')}")
            logger.info(f"⭐ 평점: {detail_info.get('diningcode_rating')}")
            logger.info(f"🕐 영업시간: {detail_info.get('open_hours')}")
            logger.info(f"☕ 브레이크타임: {detail_info.get('break_time')}")
            logger.info(f"🍽️ 라스트오더: {detail_info.get('last_order')}")
            logger.info(f"🚫 휴무일: {detail_info.get('holiday')}")
            logger.info(f"💰 가격: {detail_info.get('price')}")
            logger.info(f"🖼️ 이미지 수: {len(detail_info.get('image_urls', []))}")
            
            # 카테고리 정보 확인
            raw_categories = detail_info.get('raw_categories_diningcode', [])
            logger.info(f"🏷️ 카테고리: {raw_categories}")
            
            # 데이터베이스에 저장 (카테고리 연결 포함)
            try:
                logger.info("📊 save_crawled_data 메서드로 저장 (카테고리 연결 포함)")
                db.save_crawled_data([detail_info], keyword="기본 테스트", rect_area="강남 지역")
                logger.info(f"✅ 데이터베이스 저장 성공: 1개 가게 (카테고리 연결 포함)")
                
                # 카테고리 저장 확인
                logger.info("🔍 카테고리 저장 상태 확인...")
                cursor = db.pg_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM categories")
                category_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM store_categories")
                store_category_count = cursor.fetchone()[0]
                
                # 방금 저장된 가게의 카테고리 연결 확인
                cursor.execute("""
                    SELECT s.name, array_agg(c.name ORDER BY c.name) as categories
                    FROM stores s
                    LEFT JOIN store_categories sc ON s.id = sc.store_id
                    LEFT JOIN categories c ON sc.category_id = c.id
                    WHERE s.diningcode_place_id = %s
                    GROUP BY s.name
                """, (detail_info.get('diningcode_place_id'),))
                
                result = cursor.fetchone()
                if result:
                    store_name, linked_categories = result
                    logger.info(f"🏪 저장된 가게: {store_name}")
                    logger.info(f"🏷️ 연결된 카테고리: {linked_categories if linked_categories[0] else '없음'}")
                
                cursor.close()
                
                logger.info(f"📊 총 카테고리 수: {category_count}개")
                logger.info(f"📊 가게-카테고리 연결 수: {store_category_count}개")
                    
            except Exception as e:
                logger.error(f"❌ 데이터베이스 저장 실패: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
            
            return True
        else:
            logger.error("상세 정보 수집 실패")
            return False
            
    except Exception as e:
        logger.error(f"기본 테스트 실행 중 오류: {e}")
        return False
    
    finally:
        try:
            crawler.close()
            db.close()
        except:
            pass

def run_seoul_full_crawling():
    """서울 전지역 크롤링 (개선된 에러 핸들링)"""
    try:
        logger.info("🌍 서울 전지역 크롤링 시작")
        
        from src.core.crawler import DiningCodeCrawler
        from src.core.database import DatabaseManager
        
        crawler = DiningCodeCrawler()
        db = DatabaseManager()
        
        # 서울시 25개 구 설정 (간소화)
        seoul_regions = [
            {"name": "강남구", "keyword": "서울 강남 무한리필", "rect": "37.4979,127.0276,37.5279,127.0576"},
            {"name": "강북구", "keyword": "서울 강북 무한리필", "rect": "37.6279,127.0076,37.6579,127.0376"},
            {"name": "강서구", "keyword": "서울 강서 무한리필", "rect": "37.5379,126.8176,37.5679,126.8476"},
            {"name": "관악구", "keyword": "서울 관악 무한리필", "rect": "37.4579,126.9276,37.4879,126.9576"},
            {"name": "광진구", "keyword": "서울 광진 무한리필", "rect": "37.5279,127.0676,37.5579,127.0976"},
            {"name": "구로구", "keyword": "서울 구로 무한리필", "rect": "37.4879,126.8576,37.5179,126.8876"},
            {"name": "금천구", "keyword": "서울 금천 무한리필", "rect": "37.4479,126.8776,37.4779,126.9076"},
            {"name": "노원구", "keyword": "서울 노원 무한리필", "rect": "37.6379,127.0576,37.6679,127.0876"},
            {"name": "도봉구", "keyword": "서울 도봉 무한리필", "rect": "37.6579,127.0276,37.6879,127.0576"},
            {"name": "동대문구", "keyword": "서울 동대문 무한리필", "rect": "37.5579,127.0376,37.5879,127.0676"},
            {"name": "동작구", "keyword": "서울 동작 무한리필", "rect": "37.4979,126.9376,37.5279,126.9676"},
            {"name": "마포구", "keyword": "서울 마포 무한리필", "rect": "37.5379,126.8976,37.5679,126.9276"},
            {"name": "서대문구", "keyword": "서울 서대문 무한리필", "rect": "37.5679,126.9176,37.5979,126.9476"},
            {"name": "서초구", "keyword": "서울 서초 무한리필", "rect": "37.4679,127.0076,37.4979,127.0376"},
            {"name": "성동구", "keyword": "서울 성동 무한리필", "rect": "37.5479,127.0176,37.5779,127.0476"},
            {"name": "성북구", "keyword": "서울 성북 무한리필", "rect": "37.5879,127.0076,37.6179,127.0376"},
            {"name": "송파구", "keyword": "서울 송파 무한리필", "rect": "37.4779,127.0876,37.5079,127.1176"},
            {"name": "양천구", "keyword": "서울 양천 무한리필", "rect": "37.5179,126.8476,37.5479,126.8776"},
            {"name": "영등포구", "keyword": "서울 영등포 무한리필", "rect": "37.5079,126.8876,37.5379,126.9176"},
            {"name": "용산구", "keyword": "서울 용산 무한리필", "rect": "37.5179,126.9676,37.5479,126.9976"},
            {"name": "은평구", "keyword": "서울 은평 무한리필", "rect": "37.5879,126.9076,37.6179,126.9376"},
            {"name": "종로구", "keyword": "서울 종로 무한리필", "rect": "37.5679,126.9776,37.5979,127.0076"},
            {"name": "중구", "keyword": "서울 중구 무한리필", "rect": "37.5479,126.9776,37.5779,127.0076"},
            {"name": "중랑구", "keyword": "서울 중랑 무한리필", "rect": "37.5979,127.0676,37.6279,127.0976"},
            {"name": "강동구", "keyword": "서울 강동 무한리필", "rect": "37.5179,127.1076,37.5479,127.1376"}
        ]
        
        total_stores = 0
        successful_regions = 0
        failed_stores = []  # 실패한 가게 정보 저장
        region_results = {}  # 지역별 결과 저장
        
        for i, region in enumerate(seoul_regions, 1):
            logger.info(f"📍 [{i}/{len(seoul_regions)}] {region['name']} 크롤링 시작")
            
            region_start_time = datetime.now()
            region_success_count = 0
            region_failed_count = 0
            region_failed_stores = []
            
            try:
                # 지역별 크롤링
                stores = crawler.get_store_list(region['keyword'], region['rect'])
                
                if stores:
                    # 상세 정보 수집 (개선된 에러 핸들링)
                    detailed_stores = []
                    for j, store in enumerate(stores, 1):
                        try:
                            logger.info(f"  상세 정보 수집 중... ({j}/{len(stores)}) {store.get('name', 'Unknown')}")
                            
                            detail_info = crawler.get_store_detail(store)
                            if detail_info:
                                # 데이터 품질 검사
                                quality_score = detail_info.get('data_quality_score', 0)
                                
                                if quality_score >= 30:  # 최소 품질 기준
                                    detailed_stores.append(detail_info)
                                    region_success_count += 1
                                    
                                    # 성공적으로 수집된 정보 로깅
                                    logger.info(f"    ✅ 성공: 품질점수 {quality_score}%")
                                else:
                                    # 품질이 낮은 가게 정보
                                    failed_store = {
                                        'region': region['name'],
                                        'store_info': store,
                                        'detail_info': detail_info,
                                        'reason': f'낮은 품질 점수: {quality_score}%',
                                        'timestamp': datetime.now().isoformat()
                                    }
                                    region_failed_stores.append(failed_store)
                                    region_failed_count += 1
                                    logger.warning(f"    ⚠️ 품질 부족: {quality_score}% (최소 30% 필요)")
                            else:
                                # 상세 정보 수집 실패
                                failed_store = {
                                    'region': region['name'],
                                    'store_info': store,
                                    'reason': '상세 정보 수집 실패',
                                    'timestamp': datetime.now().isoformat()
                                }
                                region_failed_stores.append(failed_store)
                                region_failed_count += 1
                                logger.warning(f"    ❌ 상세 정보 수집 실패")
                                
                        except Exception as e:
                            # 개별 가게 크롤링 실패
                            failed_store = {
                                'region': region['name'],
                                'store_info': store,
                                'reason': f'크롤링 오류: {str(e)}',
                                'timestamp': datetime.now().isoformat()
                            }
                            region_failed_stores.append(failed_store)
                            region_failed_count += 1
                            logger.error(f"    ❌ 가게 크롤링 실패: {e}")
                            continue
                    
                    # 데이터베이스 저장
                    if detailed_stores:
                        try:
                            inserted_count = db.insert_stores_batch(detailed_stores)
                            total_stores += len(inserted_count)
                            successful_regions += 1
                            logger.info(f"✅ {region['name']}: {len(inserted_count)}개 저장")
                        except Exception as e:
                            logger.error(f"❌ {region['name']} 데이터베이스 저장 실패: {e}")
                            # 저장 실패한 가게들도 실패 목록에 추가
                            for store in detailed_stores:
                                failed_store = {
                                    'region': region['name'],
                                    'store_info': store,
                                    'reason': f'데이터베이스 저장 실패: {str(e)}',
                                    'timestamp': datetime.now().isoformat()
                                }
                                region_failed_stores.append(failed_store)
                    else:
                        logger.warning(f"❌ {region['name']}: 저장할 데이터 없음")
                else:
                    logger.warning(f"❌ {region['name']}: 검색 결과 없음")
                
                # 지역별 결과 요약
                region_end_time = datetime.now()
                region_duration = (region_end_time - region_start_time).total_seconds()
                
                region_results[region['name']] = {
                    'success_count': region_success_count,
                    'failed_count': region_failed_count,
                    'total_found': len(stores) if stores else 0,
                    'duration_seconds': region_duration,
                    'failed_stores': region_failed_stores
                }
                
                failed_stores.extend(region_failed_stores)
                
                logger.info(f"📊 {region['name']} 완료: 성공 {region_success_count}개, 실패 {region_failed_count}개, 소요시간 {region_duration:.1f}초")
            
            except Exception as e:
                logger.error(f"❌ {region['name']} 크롤링 실패: {e}")
                # 지역 전체 실패 기록
                region_results[region['name']] = {
                    'success_count': 0,
                    'failed_count': 0,
                    'total_found': 0,
                    'duration_seconds': 0,
                    'error': str(e)
                }
                continue
            
            # 지역 간 휴식 (서버 부하 방지)
            if i < len(seoul_regions):
                logger.info("⏰ 5초 휴식...")
                import time
                time.sleep(5)
        
        # 실패한 가게 정보 저장
        if failed_stores:
            failed_stores_file = f"failed_stores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(failed_stores_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(failed_stores, f, ensure_ascii=False, indent=2)
            logger.info(f"📋 실패한 가게 정보 저장: {failed_stores_file} ({len(failed_stores)}개)")
        
        # 지역별 결과 저장
        results_file = f"seoul_crawling_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(region_results, f, ensure_ascii=False, indent=2)
        logger.info(f"📊 지역별 결과 저장: {results_file}")
        
        # 최종 결과 요약
        total_failed = len(failed_stores)
        success_rate = (total_stores / (total_stores + total_failed) * 100) if (total_stores + total_failed) > 0 else 0
        
        logger.info(f"🎉 서울 전지역 크롤링 완료!")
        logger.info(f"📊 성공한 구: {successful_regions}/{len(seoul_regions)}개")
        logger.info(f"📊 총 수집 가게: {total_stores}개")
        logger.info(f"📊 실패한 가게: {total_failed}개")
        logger.info(f"📊 전체 성공률: {success_rate:.1f}%")
        
        # 재시도 가능한 실패 가게 분석
        retry_candidates = [store for store in failed_stores 
                          if '타임아웃' in store['reason'] or '네트워크' in store['reason'] or '연결' in store['reason']]
        
        if retry_candidates:
            logger.info(f"🔄 재시도 가능한 가게: {len(retry_candidates)}개")
            retry_file = f"retry_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(retry_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(retry_candidates, f, ensure_ascii=False, indent=2)
            logger.info(f"📋 재시도 대상 저장: {retry_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"서울 전지역 크롤링 실행 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
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
            
            if store_count > 0:
                # 개선된 필드 확인
                cursor.execute("SELECT COUNT(*) FROM stores WHERE address IS NOT NULL AND address != ''")
                address_count = cursor.fetchone()[0]
                address_rate = (address_count / store_count * 100)
                logger.info(f"📍 주소 보유 가게: {address_count}개 ({address_rate:.1f}%)")
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE break_time IS NOT NULL AND break_time != ''")
                break_time_count = cursor.fetchone()[0]
                break_time_rate = (break_time_count / store_count * 100)
                logger.info(f"☕ 브레이크타임 보유 가게: {break_time_count}개 ({break_time_rate:.1f}%)")
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE last_order IS NOT NULL AND last_order != ''")
                last_order_count = cursor.fetchone()[0]
                last_order_rate = (last_order_count / store_count * 100)
                logger.info(f"🍽️ 라스트오더 보유 가게: {last_order_count}개 ({last_order_rate:.1f}%)")
            
            cursor.close()
            
        except Exception as e:
            logger.warning(f"테이블 상태 확인 실패: {e}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 상태 확인 실패: {e}")
        return False

def retry_failed_stores(failed_stores_file: str):
    """실패한 가게들 재시도"""
    try:
        logger.info(f"🔄 실패한 가게 재시도 시작: {failed_stores_file}")
        
        import json
        with open(failed_stores_file, 'r', encoding='utf-8') as f:
            failed_stores = json.load(f)
        
        if not failed_stores:
            logger.warning("재시도할 가게가 없습니다.")
            return False
        
        from src.core.crawler import DiningCodeCrawler
        from src.core.database import DatabaseManager
        
        crawler = DiningCodeCrawler()
        db = DatabaseManager()
        
        retry_success = 0
        retry_failed = 0
        new_failed_stores = []
        
        logger.info(f"총 {len(failed_stores)}개 가게 재시도 시작")
        
        for i, failed_store in enumerate(failed_stores, 1):
            try:
                store_info = failed_store['store_info']
                region = failed_store['region']
                original_reason = failed_store['reason']
                
                logger.info(f"[{i}/{len(failed_stores)}] 재시도: {store_info.get('name', 'Unknown')} ({region})")
                logger.info(f"  원래 실패 사유: {original_reason}")
                
                # 재시도 수행
                detail_info = crawler.get_store_detail(store_info)
                
                if detail_info:
                    quality_score = detail_info.get('data_quality_score', 0)
                    
                    if quality_score >= 30:
                        # 데이터베이스 저장 시도
                        try:
                            inserted_count = db.insert_stores_batch([detail_info])
                            if len(inserted_count) > 0:
                                retry_success += 1
                                logger.info(f"  ✅ 재시도 성공: 품질점수 {quality_score}%")
                            else:
                                retry_failed += 1
                                new_failed_stores.append({
                                    **failed_store,
                                    'retry_reason': '데이터베이스 저장 실패 (재시도)',
                                    'retry_timestamp': datetime.now().isoformat()
                                })
                                logger.warning(f"  ❌ 데이터베이스 저장 실패 (재시도)")
                        except Exception as e:
                            retry_failed += 1
                            new_failed_stores.append({
                                **failed_store,
                                'retry_reason': f'저장 오류: {str(e)}',
                                'retry_timestamp': datetime.now().isoformat()
                            })
                            logger.error(f"  ❌ 저장 오류 (재시도): {e}")
                    else:
                        retry_failed += 1
                        new_failed_stores.append({
                            **failed_store,
                            'retry_reason': f'낮은 품질 점수: {quality_score}% (재시도)',
                            'retry_timestamp': datetime.now().isoformat()
                        })
                        logger.warning(f"  ⚠️ 품질 부족 (재시도): {quality_score}%")
                else:
                    retry_failed += 1
                    new_failed_stores.append({
                        **failed_store,
                        'retry_reason': '상세 정보 수집 실패 (재시도)',
                        'retry_timestamp': datetime.now().isoformat()
                    })
                    logger.warning(f"  ❌ 상세 정보 수집 실패 (재시도)")
                
                # 요청 간 지연
                if i % 10 == 0:  # 10개마다 휴식
                    logger.info("⏰ 3초 휴식...")
                    import time
                    time.sleep(3)
                
            except Exception as e:
                retry_failed += 1
                new_failed_stores.append({
                    **failed_store,
                    'retry_reason': f'재시도 오류: {str(e)}',
                    'retry_timestamp': datetime.now().isoformat()
                })
                logger.error(f"  ❌ 재시도 오류: {e}")
                continue
        
        # 재시도 결과 저장
        if new_failed_stores:
            retry_failed_file = f"retry_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(retry_failed_file, 'w', encoding='utf-8') as f:
                json.dump(new_failed_stores, f, ensure_ascii=False, indent=2)
            logger.info(f"📋 재시도 실패 정보 저장: {retry_failed_file} ({len(new_failed_stores)}개)")
        
        # 재시도 결과 요약
        total_retry = retry_success + retry_failed
        success_rate = (retry_success / total_retry * 100) if total_retry > 0 else 0
        
        logger.info(f"🎉 재시도 완료!")
        logger.info(f"📊 재시도 성공: {retry_success}개")
        logger.info(f"📊 재시도 실패: {retry_failed}개")
        logger.info(f"📊 재시도 성공률: {success_rate:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"재시도 실행 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
        try:
            crawler.close()
            db.close()
        except:
            pass

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='리필스팟 크롤러 (개선된 버전)')
    parser.add_argument('mode', choices=['gangnam', 'basic', 'seoul', 'check', 'stage4', 'retry'], 
                       help='실행 모드: gangnam(강남테스트), basic(기본테스트), seoul(서울전지역), check(DB상태), stage4(호환성), retry(재시도)')
    parser.add_argument('--retry-file', type=str, 
                       help='재시도할 실패 가게 JSON 파일 경로 (retry 모드에서 필수)')
    
    args = parser.parse_args()
    
    print("🍽️ 리필스팟 크롤러 (개선된 버전)")
    print("=" * 50)
    print("✨ 개선된 기능:")
    print("  - 주소 정확 추출")
    print("  - 요일별 영업시간 수집 (개선된 파싱)")
    print("  - 브레이크타임 정보 수집")
    print("  - 라스트오더 정보 수집")
    print("  - 휴무일 정보 수집")
    print("  - 가격 정보 추출 (개선된 셀렉터)")
    print("  - 강화된 에러 핸들링")
    print("  - 데이터 품질 검증")
    print("  - 실패 가게 재시도 기능")
    print("=" * 50)
    
    if args.mode == 'gangnam':
        print("🚀 강남 지역 테스트 크롤링")
        success = run_gangnam_test()
    elif args.mode == 'basic':
        print("🔍 기본 테스트 (단일 가게)")
        success = run_basic_test()
    elif args.mode == 'seoul':
        print("🌍 서울 전지역 크롤링")
        success = run_seoul_full_crawling()
    elif args.mode == 'check':
        print("🔍 데이터베이스 상태 확인")
        success = check_database_status()
    elif args.mode == 'stage4':
        print("🔄 Stage4 호환 모드 (강남 지역)")
        success = run_gangnam_test()
    elif args.mode == 'retry':
        if not args.retry_file:
            print("❌ 재시도 모드에서는 --retry-file 옵션이 필요합니다.")
            print("사용법: python src/utils/main.py retry --retry-file failed_stores_20240629_123456.json")
            sys.exit(1)
        print(f"🔄 실패한 가게 재시도 모드: {args.retry_file}")
        success = retry_failed_stores(args.retry_file)
    
    if success:
        print("✅ 실행 완료!")
        if args.mode == 'seoul':
            print("\n📋 생성된 파일들:")
            print("  - seoul_crawling_results_YYYYMMDD_HHMMSS.json: 지역별 상세 결과")
            print("  - failed_stores_YYYYMMDD_HHMMSS.json: 실패한 가게 목록")
            print("  - retry_candidates_YYYYMMDD_HHMMSS.json: 재시도 가능한 가게 목록")
            print("\n🔄 재시도 방법:")
            print("  python src/utils/main.py retry --retry-file retry_candidates_YYYYMMDD_HHMMSS.json")
    else:
        print("❌ 실행 실패!")
        sys.exit(1)

if __name__ == "__main__":
    main()