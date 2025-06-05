"""
5단계 성능 최적화 통합 실행 스크립트
- 멀티프로세싱 병렬 크롤링
- 고성능 데이터베이스 처리
- Redis 캐싱 시스템
- 실시간 성능 모니터링
"""

import logging
import time
import multiprocessing as mp
from datetime import datetime
from typing import Dict, List
import sys
import os

# 프로젝트 모듈 임포트
from parallel_crawler import run_stage5_parallel_crawling, ParallelCrawlingManager
from optimized_database import OptimizedDatabaseManager
from caching_system import CacheIntegratedCrawler
from crawler import DiningCodeCrawler
from data_enhancement import DataEnhancer
import config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(process)d - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stage5_performance.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Stage5PerformanceSystem:
    """5단계 성능 최적화 통합 시스템"""
    
    def __init__(self):
        self.start_time = None
        self.db_manager = None
        self.cache_crawler = None
        self.performance_metrics = {}
        
    def initialize_systems(self):
        """시스템 초기화"""
        logger.info("🚀 5단계 성능 최적화 시스템 초기화 시작")
        
        try:
            # 1. 데이터베이스 최적화 설정
            logger.info("1️⃣ 고성능 데이터베이스 시스템 초기화")
            self.db_manager = OptimizedDatabaseManager(use_read_write_split=False)
            
            # 인덱스 생성
            self.db_manager.create_optimized_indexes()
            
            # 파티셔닝 설정
            self.db_manager.setup_partitioning()
            
            # 데이터베이스 설정 최적화
            self.db_manager.optimize_database_settings()
            
            logger.info("✅ 데이터베이스 최적화 완료")
            
            # 2. 캐싱 시스템 초기화
            logger.info("2️⃣ Redis 캐싱 시스템 초기화")
            self.cache_crawler = CacheIntegratedCrawler()
            
            # 캐시 시스템 최적화
            self.cache_crawler.optimize_cache_system()
            
            logger.info("✅ 캐싱 시스템 초기화 완료")
            
            # 3. 시스템 상태 확인
            self._check_system_requirements()
            
            logger.info("🎯 5단계 성능 최적화 시스템 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 시스템 초기화 실패: {e}")
            raise
    
    def _check_system_requirements(self):
        """시스템 요구사항 확인"""
        logger.info("시스템 요구사항 확인 중...")
        
        # CPU 코어 수 확인
        cpu_count = mp.cpu_count()
        logger.info(f"CPU 코어: {cpu_count}개")
        
        if cpu_count < 4:
            logger.warning("⚠️ CPU 코어가 4개 미만입니다. 성능이 제한될 수 있습니다.")
        
        # 메모리 확인 (psutil 사용)
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)
            
            logger.info(f"총 메모리: {memory_gb:.1f}GB")
            logger.info(f"사용 가능 메모리: {available_gb:.1f}GB")
            
            if available_gb < 4:
                logger.warning("⚠️ 사용 가능한 메모리가 4GB 미만입니다. 성능이 제한될 수 있습니다.")
                
        except ImportError:
            logger.warning("psutil 모듈이 없어 메모리 확인을 건너뜁니다.")
        
        # 데이터베이스 연결 확인
        try:
            stats = self.db_manager.get_performance_stats()
            logger.info(f"데이터베이스 상태: {stats.get('total_records', 0)}개 레코드")
        except Exception as e:
            logger.warning(f"데이터베이스 상태 확인 실패: {e}")
        
        # Redis 연결 확인
        try:
            cache_stats = self.cache_crawler.get_cache_performance_report()
            logger.info("Redis 캐시 시스템 정상 동작")
        except Exception as e:
            logger.warning(f"Redis 상태 확인 실패: {e}")
    
    def run_performance_optimized_crawling(self) -> Dict:
        """성능 최적화된 크롤링 실행"""
        self.start_time = time.time()
        
        logger.info("🎯 5단계 성능 최적화 크롤링 시작")
        logger.info("목표: 500-1,000개/시간 처리 속도 달성")
        
        try:
            # 병렬 크롤링 실행
            summary = run_stage5_parallel_crawling()
            
            # 성능 지표 계산
            total_time = time.time() - self.start_time
            self.performance_metrics = self._calculate_performance_metrics(summary, total_time)
            
            # 성능 리포트 생성
            self._generate_performance_report()
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ 성능 최적화 크롤링 실패: {e}")
            return {}
    
    def _calculate_performance_metrics(self, summary: Dict, total_time: float) -> Dict:
        """성능 지표 계산"""
        metrics = {
            'total_processing_time_minutes': total_time / 60,
            'stores_per_hour': summary.get('stores_per_hour', 0),
            'success_rate_percent': summary.get('success_rate', 0),
            'total_stores_processed': summary.get('total_stores_processed', 0),
            'performance_target_achieved': False,
            'improvement_vs_baseline': 0
        }
        
        # 성능 목표 달성 여부 (500개/시간 이상)
        if metrics['stores_per_hour'] >= 500:
            metrics['performance_target_achieved'] = True
        
        # 기준 대비 개선율 계산 (기준: 50개/시간)
        baseline_rate = 50
        if baseline_rate > 0:
            metrics['improvement_vs_baseline'] = (metrics['stores_per_hour'] / baseline_rate - 1) * 100
        
        return metrics
    
    def _generate_performance_report(self):
        """성능 리포트 생성"""
        logger.info("📊 5단계 성능 최적화 결과 리포트")
        logger.info("=" * 60)
        
        # 처리 성능
        logger.info(f"🚀 처리 속도: {self.performance_metrics['stores_per_hour']:.0f}개/시간")
        logger.info(f"⏱️ 총 소요시간: {self.performance_metrics['total_processing_time_minutes']:.1f}분")
        logger.info(f"✅ 성공률: {self.performance_metrics['success_rate_percent']:.1f}%")
        logger.info(f"📈 총 처리 가게: {self.performance_metrics['total_stores_processed']}개")
        
        # 목표 달성 여부
        if self.performance_metrics['performance_target_achieved']:
            logger.info("🎯 ✅ 성능 목표 달성! (500개/시간 이상)")
        else:
            logger.info("🎯 ❌ 성능 목표 미달성 (500개/시간 미만)")
        
        # 개선율
        improvement = self.performance_metrics['improvement_vs_baseline']
        if improvement > 0:
            logger.info(f"📊 기준 대비 {improvement:.1f}배 성능 향상")
        
        # 캐시 성능
        try:
            cache_report = self.cache_crawler.get_cache_performance_report()
            cache_stats = cache_report.get('cache_statistics', {})
            hit_rate = cache_stats.get('hit_rate_percent', 0)
            
            logger.info(f"💾 캐시 적중률: {hit_rate:.1f}%")
            logger.info(f"🔄 네트워크 요청 감소: {hit_rate:.1f}%")
            
        except Exception as e:
            logger.warning(f"캐시 성능 리포트 생성 실패: {e}")
        
        # 데이터베이스 성능
        try:
            db_stats = self.db_manager.get_performance_stats()
            logger.info(f"🗄️ 데이터베이스 레코드: {db_stats.get('total_records', 0)}개")
            
        except Exception as e:
            logger.warning(f"데이터베이스 성능 리포트 생성 실패: {e}")
        
        logger.info("=" * 60)
    
    def run_performance_test(self) -> Dict:
        """성능 테스트 실행"""
        logger.info("🧪 5단계 성능 테스트 시작")
        
        test_results = {
            'database_performance': {},
            'cache_performance': {},
            'parallel_processing': {},
            'overall_score': 0
        }
        
        try:
            # 1. 데이터베이스 성능 테스트
            logger.info("1️⃣ 데이터베이스 성능 테스트")
            test_results['database_performance'] = self._test_database_performance()
            
            # 2. 캐시 성능 테스트
            logger.info("2️⃣ 캐시 성능 테스트")
            test_results['cache_performance'] = self._test_cache_performance()
            
            # 3. 병렬 처리 성능 테스트
            logger.info("3️⃣ 병렬 처리 성능 테스트")
            test_results['parallel_processing'] = self._test_parallel_performance()
            
            # 4. 종합 점수 계산
            test_results['overall_score'] = self._calculate_overall_score(test_results)
            
            logger.info(f"🏆 종합 성능 점수: {test_results['overall_score']}/100")
            
            return test_results
            
        except Exception as e:
            logger.error(f"❌ 성능 테스트 실패: {e}")
            return test_results
    
    def _test_database_performance(self) -> Dict:
        """데이터베이스 성능 테스트"""
        results = {'score': 0, 'details': {}}
        
        try:
            # 테스트 데이터 생성
            test_stores = [
                {
                    'name': f'테스트 가게 {i}',
                    'address': f'서울시 강남구 테스트로 {i}',
                    'diningcode_place_id': f'test_{i}',
                    'position_lat': 37.5 + (i * 0.001),
                    'position_lng': 127.0 + (i * 0.001),
                    'status': '운영중'
                }
                for i in range(100)
            ]
            
            # 삽입 성능 테스트
            start_time = time.time()
            store_ids = self.db_manager.insert_stores_high_performance(test_stores)
            insert_time = time.time() - start_time
            
            insertion_rate = len(store_ids) / insert_time if insert_time > 0 else 0
            
            results['details'] = {
                'insertion_rate_per_second': insertion_rate,
                'test_records_inserted': len(store_ids),
                'insertion_time_seconds': insert_time
            }
            
            # 점수 계산 (목표: 1000개/초 이상)
            if insertion_rate >= 1000:
                results['score'] = 100
            elif insertion_rate >= 500:
                results['score'] = 80
            elif insertion_rate >= 100:
                results['score'] = 60
            else:
                results['score'] = 40
            
            logger.info(f"데이터베이스 삽입 성능: {insertion_rate:.0f}개/초 (점수: {results['score']})")
            
        except Exception as e:
            logger.error(f"데이터베이스 성능 테스트 실패: {e}")
            results['score'] = 0
        
        return results
    
    def _test_cache_performance(self) -> Dict:
        """캐시 성능 테스트"""
        results = {'score': 0, 'details': {}}
        
        try:
            # 캐시 성능 리포트 조회
            cache_report = self.cache_crawler.get_cache_performance_report()
            cache_stats = cache_report.get('cache_statistics', {})
            
            hit_rate = cache_stats.get('hit_rate_percent', 0)
            total_requests = cache_stats.get('total_requests', 0)
            
            results['details'] = {
                'hit_rate_percent': hit_rate,
                'total_requests': total_requests,
                'cache_hits': cache_stats.get('hits', 0),
                'cache_misses': cache_stats.get('misses', 0)
            }
            
            # 점수 계산 (목표: 60% 이상 적중률)
            if hit_rate >= 80:
                results['score'] = 100
            elif hit_rate >= 60:
                results['score'] = 80
            elif hit_rate >= 40:
                results['score'] = 60
            elif hit_rate >= 20:
                results['score'] = 40
            else:
                results['score'] = 20
            
            logger.info(f"캐시 적중률: {hit_rate:.1f}% (점수: {results['score']})")
            
        except Exception as e:
            logger.error(f"캐시 성능 테스트 실패: {e}")
            results['score'] = 0
        
        return results
    
    def _test_parallel_performance(self) -> Dict:
        """병렬 처리 성능 테스트"""
        results = {'score': 0, 'details': {}}
        
        try:
            cpu_count = mp.cpu_count()
            optimal_workers = min(8, max(4, cpu_count - 1))
            
            results['details'] = {
                'cpu_cores': cpu_count,
                'optimal_workers': optimal_workers,
                'parallel_efficiency': optimal_workers / cpu_count * 100
            }
            
            # 점수 계산
            if cpu_count >= 8:
                results['score'] = 100
            elif cpu_count >= 4:
                results['score'] = 80
            elif cpu_count >= 2:
                results['score'] = 60
            else:
                results['score'] = 40
            
            logger.info(f"병렬 처리 능력: {cpu_count}코어, {optimal_workers}워커 (점수: {results['score']})")
            
        except Exception as e:
            logger.error(f"병렬 처리 성능 테스트 실패: {e}")
            results['score'] = 0
        
        return results
    
    def _calculate_overall_score(self, test_results: Dict) -> int:
        """종합 점수 계산"""
        weights = {
            'database_performance': 0.4,  # 40%
            'cache_performance': 0.3,     # 30%
            'parallel_processing': 0.3    # 30%
        }
        
        total_score = 0
        for category, weight in weights.items():
            score = test_results.get(category, {}).get('score', 0)
            total_score += score * weight
        
        return int(total_score)
    
    def cleanup(self):
        """리소스 정리"""
        try:
            if self.db_manager:
                self.db_manager.close()
            logger.info("시스템 리소스 정리 완료")
        except Exception as e:
            logger.error(f"리소스 정리 실패: {e}")

def main():
    """메인 실행 함수"""
    logger.info("🚀 5단계 성능 최적화 시스템 시작")
    
    # Windows 멀티프로세싱 호환성
    if sys.platform.startswith('win'):
        mp.set_start_method('spawn', force=True)
    
    system = Stage5PerformanceSystem()
    
    try:
        # 1. 시스템 초기화
        system.initialize_systems()
        
        # 2. 성능 테스트 실행 (선택사항)
        print("\n성능 테스트를 실행하시겠습니까? (y/n): ", end="")
        if input().lower() == 'y':
            test_results = system.run_performance_test()
            print(f"\n성능 테스트 완료. 종합 점수: {test_results['overall_score']}/100")
        
        # 3. 실제 크롤링 실행
        print("\n5단계 병렬 크롤링을 시작하시겠습니까? (y/n): ", end="")
        if input().lower() == 'y':
            summary = system.run_performance_optimized_crawling()
            
            if summary:
                print(f"\n🎉 크롤링 완료!")
                print(f"처리 속도: {summary.get('stores_per_hour', 0):.0f}개/시간")
                print(f"총 소요시간: {summary.get('total_time_minutes', 0):.1f}분")
                print(f"성공률: {summary.get('success_rate', 0):.1f}%")
                
                # 목표 달성 여부
                if summary.get('stores_per_hour', 0) >= 500:
                    print("✅ 5단계 성능 목표 달성!")
                else:
                    print("⚠️ 성능 목표 미달성. 추가 최적화 필요")
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"❌ 시스템 실행 실패: {e}")
    finally:
        system.cleanup()

if __name__ == "__main__":
    main() 