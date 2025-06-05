"""
5단계 성능 최적화 시스템 소규모 실제 테스트
2-3개 구만 대상으로 실제 병렬 크롤링을 테스트합니다.
"""

import logging
import time
import multiprocessing as mp
from typing import Dict, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(process)d - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 테스트용 소규모 지역 설정
TEST_DISTRICTS = {
    "강남구": {
        "keywords": ["강남구 무한리필", "강남 고기무한리필", "강남역 무한리필"],
        "rect": "37.4979,127.0276,37.5279,127.0576"
    },
    "서초구": {
        "keywords": ["서초구 무한리필", "서초 고기무한리필", "교대역 무한리필"], 
        "rect": "37.4833,127.0322,37.5133,127.0622"
    }
}

def mini_crawl_district_worker(district_name: str, district_info: Dict) -> Dict:
    """소규모 구 크롤링 워커"""
    start_time = time.time()
    process_id = mp.current_process().pid
    
    logger.info(f"[PID:{process_id}] {district_name} 크롤링 시작")
    
    try:
        from crawler import DiningCodeCrawler
        from data_enhancement import DataEnhancer
        from optimized_database import OptimizedDatabaseManager
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        enhancer = DataEnhancer()
        db_manager = OptimizedDatabaseManager()
        
        all_stores = []
        keywords = district_info.get('keywords', [])
        rect = district_info.get('rect', '')
        
        # 키워드별 크롤링 (제한적으로)
        for keyword in keywords[:1]:  # 첫 번째 키워드만 테스트
            logger.info(f"[PID:{process_id}] {district_name} - 키워드: {keyword}")
            
            stores = crawler.get_store_list(keyword, rect)
            
            if stores:
                # 상위 3개만 상세 정보 수집 (테스트용)
                detailed_stores = []
                for store in stores[:3]:
                    try:
                        detailed_store = crawler.get_store_detail(store)
                        if detailed_store:
                            detailed_stores.append(detailed_store)
                    except Exception as e:
                        logger.warning(f"[PID:{process_id}] 상세정보 수집 실패: {e}")
                        continue
                
                all_stores.extend(detailed_stores)
                logger.info(f"[PID:{process_id}] {district_name} - {len(detailed_stores)}개 상세정보 수집")
        
        # 데이터 강화
        if all_stores:
            enhanced_stores, enhancement_stats = enhancer.enhance_stores_data(all_stores)
            
            # 데이터베이스 저장 (고성능 삽입 사용)
            if enhanced_stores:
                store_ids = db_manager.insert_stores_high_performance(enhanced_stores)
                logger.info(f"[PID:{process_id}] {district_name}: {len(store_ids)}개 가게 저장 완료")
        
        processing_time = time.time() - start_time
        
        result = {
            'district_name': district_name,
            'success': True,
            'stores_found': len(all_stores),
            'stores_processed': len(enhanced_stores) if 'enhanced_stores' in locals() else 0,
            'processing_time': processing_time,
            'process_id': process_id
        }
        
        logger.info(f"[PID:{process_id}] {district_name} 완료: "
                   f"{result['stores_processed']}개 처리, {processing_time:.1f}초 소요")
        
        # 리소스 정리
        crawler.close()
        db_manager.close()
        
        return result
        
    except Exception as e:
        logger.error(f"[PID:{process_id}] {district_name} 실패: {e}")
        return {
            'district_name': district_name,
            'success': False,
            'error': str(e),
            'processing_time': time.time() - start_time,
            'process_id': process_id
        }

def run_mini_parallel_test():
    """소규모 병렬 크롤링 테스트 실행"""
    logger.info("🧪 5단계 시스템 소규모 병렬 테스트 시작")
    
    start_time = time.time()
    
    # 멀티프로세싱 설정
    mp.set_start_method('spawn', force=True)
    
    # 병렬 실행
    with mp.Pool(processes=2) as pool:
        # 작업 생성
        tasks = [(name, info) for name, info in TEST_DISTRICTS.items()]
        
        # 병렬 실행
        results = pool.starmap(mini_crawl_district_worker, tasks)
    
    total_time = time.time() - start_time
    
    # 결과 분석
    successful_results = [r for r in results if r.get('success', False)]
    failed_results = [r for r in results if not r.get('success', False)]
    
    total_stores_processed = sum(r.get('stores_processed', 0) for r in successful_results)
    total_stores_found = sum(r.get('stores_found', 0) for r in successful_results)
    
    # 성능 계산
    stores_per_hour = (total_stores_processed / total_time * 3600) if total_time > 0 else 0
    
    # 결과 리포트
    logger.info("="*60)
    logger.info("📊 소규모 병렬 테스트 결과")
    logger.info("="*60)
    logger.info(f"테스트 지역: {len(TEST_DISTRICTS)}개 구")
    logger.info(f"성공: {len(successful_results)}개, 실패: {len(failed_results)}개")
    logger.info(f"총 발견 가게: {total_stores_found}개")
    logger.info(f"총 처리 가게: {total_stores_processed}개")
    logger.info(f"총 소요시간: {total_time:.1f}초")
    logger.info(f"처리 속도: {stores_per_hour:.0f}개/시간")
    
    # 개별 결과
    for result in results:
        status = "✅" if result.get('success') else "❌"
        district = result['district_name']
        time_taken = result.get('processing_time', 0)
        processed = result.get('stores_processed', 0)
        logger.info(f"{status} {district}: {processed}개 처리, {time_taken:.1f}초")
    
    # 성능 평가
    if stores_per_hour >= 100:
        logger.info("🎯 성능 목표 달성! (100개/시간 이상)")
    elif stores_per_hour >= 50:
        logger.info("⚡ 양호한 성능 (50개/시간 이상)")
    else:
        logger.info("🔧 성능 개선 필요 (50개/시간 미만)")
    
    logger.info("="*60)
    
    return {
        'total_time': total_time,
        'stores_per_hour': stores_per_hour,
        'success_rate': len(successful_results) / len(results) * 100,
        'total_processed': total_stores_processed,
        'results': results
    }

if __name__ == "__main__":
    result = run_mini_parallel_test()
    
    print(f"\n🎉 테스트 완료!")
    print(f"처리 속도: {result['stores_per_hour']:.0f}개/시간")
    print(f"성공률: {result['success_rate']:.1f}%")
    print(f"총 처리: {result['total_processed']}개 가게") 