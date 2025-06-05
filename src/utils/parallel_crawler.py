"""
5단계: 병렬 크롤링 시스템
멀티프로세싱을 활용한 고성능 크롤링
"""

import logging
import time
import multiprocessing as mp
from multiprocessing import Pool, Manager, Queue
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import psutil
import os
import signal
import sys
from dataclasses import dataclass, asdict
import json
from pathlib import Path

# 프로젝트 모듈 import
from ..core.database import DatabaseManager
from ..core.crawler import DiningCodeCrawler
from ..core.caching_system import CacheManager
from .seoul_districts import SEOUL_DISTRICTS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parallel_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CrawlingTask:
    """크롤링 작업 단위"""
    district_name: str
    district_info: Dict
    task_id: str
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3
    
@dataclass
class CrawlingResult:
    """크롤링 결과"""
    task_id: str
    district_name: str
    success: bool
    stores_found: int
    stores_processed: int
    processing_time: float
    error_message: Optional[str] = None
    memory_usage_mb: float = 0.0

class PerformanceMonitor:
    """실시간 성능 모니터링"""
    
    def __init__(self):
        self.redis_client = None
        self.setup_redis()
        
    def setup_redis(self):
        """Redis 연결 설정"""
        try:
            self.redis_client = redis.Redis(
                host='localhost', 
                port=6379, 
                db=0, 
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis 연결 성공")
        except Exception as e:
            logger.warning(f"Redis 연결 실패: {e}. 메모리 모니터링만 사용")
            self.redis_client = None
    
    def log_performance(self, process_id: int, district: str, metrics: Dict):
        """성능 지표 로깅"""
        timestamp = datetime.now().isoformat()
        
        # 메모리 사용량 측정
        process = psutil.Process(process_id)
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        performance_data = {
            'timestamp': timestamp,
            'process_id': process_id,
            'district': district,
            'memory_mb': memory_mb,
            'cpu_percent': process.cpu_percent(),
            **metrics
        }
        
        # Redis에 저장 (가능한 경우)
        if self.redis_client:
            try:
                key = f"performance:{process_id}:{timestamp}"
                self.redis_client.setex(key, 3600, json.dumps(performance_data))
            except Exception as e:
                logger.warning(f"Redis 성능 데이터 저장 실패: {e}")
        
        # 로그에도 기록
        logger.info(f"성능 지표 - PID:{process_id}, 구:{district}, "
                   f"메모리:{memory_mb:.1f}MB, CPU:{performance_data.get('cpu_percent', 0):.1f}%")
        
        return performance_data
    
    def get_system_status(self) -> Dict:
        """시스템 전체 상태 조회"""
        return {
            'total_memory_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'available_memory_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'memory_percent': psutil.virtual_memory().percent,
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'timestamp': datetime.now().isoformat()
        }

class AdaptiveConcurrencyController:
    """적응형 동시성 제어"""
    
    def __init__(self, initial_workers: int = 4):
        self.current_workers = initial_workers
        self.min_workers = 2
        self.max_workers = min(8, mp.cpu_count())
        self.performance_history = []
        self.adjustment_threshold = 5  # 5번의 측정 후 조정
        
    def should_adjust_workers(self, performance_metrics: List[Dict]) -> Optional[int]:
        """워커 수 조정 필요성 판단"""
        if len(performance_metrics) < self.adjustment_threshold:
            return None
            
        recent_metrics = performance_metrics[-self.adjustment_threshold:]
        
        # 평균 성능 지표 계산
        avg_memory = sum(m.get('memory_mb', 0) for m in recent_metrics) / len(recent_metrics)
        avg_processing_time = sum(m.get('processing_time', 0) for m in recent_metrics) / len(recent_metrics)
        avg_success_rate = sum(m.get('success_rate', 100) for m in recent_metrics) / len(recent_metrics)
        
        # 조정 로직
        if avg_memory > 1500:  # 1.5GB 이상 사용 시 워커 감소
            new_workers = max(self.min_workers, self.current_workers - 1)
            logger.info(f"메모리 사용량 높음({avg_memory:.1f}MB). 워커 수 감소: {self.current_workers} -> {new_workers}")
            return new_workers
            
        elif avg_success_rate < 80:  # 성공률 80% 미만 시 워커 감소
            new_workers = max(self.min_workers, self.current_workers - 1)
            logger.info(f"성공률 낮음({avg_success_rate:.1f}%). 워커 수 감소: {self.current_workers} -> {new_workers}")
            return new_workers
            
        elif avg_memory < 800 and avg_success_rate > 95 and avg_processing_time < 300:  # 여유 있을 때 워커 증가
            new_workers = min(self.max_workers, self.current_workers + 1)
            logger.info(f"성능 여유 있음. 워커 수 증가: {self.current_workers} -> {new_workers}")
            return new_workers
            
        return None
    
    def update_workers(self, new_count: int):
        """워커 수 업데이트"""
        self.current_workers = new_count

def crawl_district_worker(task: CrawlingTask) -> CrawlingResult:
    """개별 구 크롤링 워커 함수"""
    start_time = time.time()
    process_id = os.getpid()
    
    logger.info(f"[PID:{process_id}] {task.district_name} 크롤링 시작")
    
    crawler = None
    db_manager = None
    enhancer = None
    
    try:
        # 성능 모니터 초기화
        monitor = PerformanceMonitor()
        
        # 크롤러 초기화
        crawler = DiningCodeCrawler()
        db_manager = DatabaseManager()
        enhancer = DataEnhancer()
        
        district_info = task.district_info
        all_stores = []
        
        # 구별 키워드로 크롤링
        keywords = district_info.get('keywords', [])
        rect = district_info.get('rect', '')
        
        # keywords가 없으면 기본 키워드 생성
        if not keywords:
            district_name = task.district_name
            keywords = [
                f"{district_name} 무한리필",
                f"{district_name} 고기무한리필", 
                f"{district_name} 무한리필 맛집"
            ]
        
        for keyword in keywords:
            try:
                logger.info(f"[PID:{process_id}] {task.district_name} - 키워드: {keyword}")
                
                # 가게 목록 수집
                stores = crawler.get_store_list(keyword, rect)
                
                if stores:
                    # 상세 정보 수집 (배치 처리)
                    detailed_stores = []
                    for store in stores:
                        try:
                            detailed_store = crawler.get_store_detail(store)
                            if detailed_store:
                                detailed_stores.append(detailed_store)
                        except Exception as e:
                            logger.warning(f"[PID:{process_id}] 가게 상세정보 수집 실패: {e}")
                            continue
                    
                    all_stores.extend(detailed_stores)
                    
                    # 성능 지표 기록
                    monitor.log_performance(process_id, task.district_name, {
                        'keyword': keyword,
                        'stores_found': len(stores),
                        'stores_detailed': len(detailed_stores),
                        'processing_time': time.time() - start_time
                    })
                
                # 키워드 간 지연
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"[PID:{process_id}] 키워드 '{keyword}' 처리 실패: {e}")
                continue
        
        # 중복 제거
        unique_stores = remove_duplicates(all_stores)
        
        # 데이터 고도화
        enhanced_stores, enhancement_stats = enhancer.enhance_stores_data(unique_stores)
        
        # 데이터베이스 저장
        if enhanced_stores:
            store_ids = db_manager.insert_stores_batch(enhanced_stores)
            logger.info(f"[PID:{process_id}] {task.district_name}: {len(store_ids)}개 가게 저장 완료")
        
        processing_time = time.time() - start_time
        
        # 최종 성능 지표
        final_memory = psutil.Process(process_id).memory_info().rss / 1024 / 1024
        
        result = CrawlingResult(
            task_id=task.task_id,
            district_name=task.district_name,
            success=True,
            stores_found=len(all_stores),
            stores_processed=len(enhanced_stores) if enhanced_stores else 0,
            processing_time=processing_time,
            memory_usage_mb=final_memory
        )
        
        logger.info(f"[PID:{process_id}] {task.district_name} 완료: "
                   f"{result.stores_processed}개 처리, {processing_time:.1f}초 소요")
        
        return result
        
    except Exception as e:
        error_msg = f"구 크롤링 실패: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"[PID:{process_id}] {task.district_name} 실패: {error_msg}")
        
        return CrawlingResult(
            task_id=task.task_id,
            district_name=task.district_name,
            success=False,
            stores_found=0,
            stores_processed=0,
            processing_time=time.time() - start_time,
            error_message=error_msg
        )
        
    finally:
        # 리소스 정리
        if crawler:
            try:
                crawler.close()
            except:
                pass
        if db_manager:
            try:
                db_manager.close()
            except:
                pass

def remove_duplicates(stores: List[Dict]) -> List[Dict]:
    """중복 가게 제거 (간단한 버전)"""
    seen = set()
    unique_stores = []
    
    for store in stores:
        # diningcode_place_id 기준으로 중복 제거
        place_id = store.get('diningcode_place_id')
        if place_id and place_id not in seen:
            seen.add(place_id)
            unique_stores.append(store)
    
    logger.info(f"중복 제거: {len(stores)} -> {len(unique_stores)}")
    return unique_stores

class ParallelCrawlingManager:
    """병렬 크롤링 관리자"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.monitor = PerformanceMonitor()
        self.concurrency_controller = AdaptiveConcurrencyController(max_workers)
        self.results = []
        self.failed_tasks = []
        
    def create_crawling_tasks(self) -> List[CrawlingTask]:
        """크롤링 작업 생성"""
        tasks = []
        
        for i, (district_name, district_info) in enumerate(SEOUL_DISTRICTS.items()):
            task = CrawlingTask(
                district_name=district_name,
                district_info=district_info,
                task_id=f"task_{i:02d}_{district_name}",
                priority=1
            )
            tasks.append(task)
        
        logger.info(f"총 {len(tasks)}개 크롤링 작업 생성")
        return tasks
    
    def run_parallel_crawling(self) -> Dict:
        """병렬 크롤링 실행"""
        start_time = time.time()
        tasks = self.create_crawling_tasks()
        
        logger.info(f"=== 병렬 크롤링 시작: {len(tasks)}개 구, {self.max_workers}개 워커 ===")
        
        # 시스템 상태 확인
        system_status = self.monitor.get_system_status()
        logger.info(f"시스템 상태: 메모리 {system_status['available_memory_gb']:.1f}GB 사용 가능, "
                   f"CPU {system_status['cpu_count']}코어")
        
        completed_tasks = 0
        total_stores_found = 0
        total_stores_processed = 0
        
        # ProcessPoolExecutor로 병렬 실행
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 작업 제출
            future_to_task = {executor.submit(crawl_district_worker, task): task for task in tasks}
            
            # 결과 수집
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                
                try:
                    result = future.result()
                    self.results.append(result)
                    
                    if result.success:
                        completed_tasks += 1
                        total_stores_found += result.stores_found
                        total_stores_processed += result.stores_processed
                        
                        logger.info(f"✅ {result.district_name} 완료 "
                                   f"({completed_tasks}/{len(tasks)}) - "
                                   f"{result.stores_processed}개 처리")
                    else:
                        self.failed_tasks.append(task)
                        logger.error(f"❌ {result.district_name} 실패: {result.error_message}")
                        
                except Exception as e:
                    logger.error(f"작업 결과 처리 실패: {e}")
                    self.failed_tasks.append(task)
        
        total_time = time.time() - start_time
        
        # 최종 결과 요약
        summary = {
            'total_tasks': len(tasks),
            'completed_tasks': completed_tasks,
            'failed_tasks': len(self.failed_tasks),
            'success_rate': completed_tasks / len(tasks) * 100,
            'total_stores_found': total_stores_found,
            'total_stores_processed': total_stores_processed,
            'total_time_minutes': total_time / 60,
            'average_time_per_district': total_time / len(tasks),
            'stores_per_hour': total_stores_processed / (total_time / 3600) if total_time > 0 else 0
        }
        
        logger.info("=== 병렬 크롤링 완료 ===")
        logger.info(f"성공률: {summary['success_rate']:.1f}% ({completed_tasks}/{len(tasks)})")
        logger.info(f"총 처리: {total_stores_processed}개 가게")
        logger.info(f"소요시간: {summary['total_time_minutes']:.1f}분")
        logger.info(f"처리속도: {summary['stores_per_hour']:.0f}개/시간")
        
        return summary
    
    def retry_failed_tasks(self) -> Dict:
        """실패한 작업 재시도"""
        if not self.failed_tasks:
            logger.info("재시도할 실패 작업이 없습니다.")
            return {}
        
        logger.info(f"실패한 {len(self.failed_tasks)}개 작업 재시도 시작")
        
        retry_results = []
        for task in self.failed_tasks:
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                logger.info(f"{task.district_name} 재시도 ({task.retry_count}/{task.max_retries})")
                
                try:
                    result = crawl_district_worker(task)
                    retry_results.append(result)
                    
                    if result.success:
                        logger.info(f"✅ {task.district_name} 재시도 성공")
                    else:
                        logger.error(f"❌ {task.district_name} 재시도 실패")
                        
                except Exception as e:
                    logger.error(f"{task.district_name} 재시도 중 오류: {e}")
        
        return {
            'retry_attempts': len(retry_results),
            'retry_successes': sum(1 for r in retry_results if r.success),
            'retry_results': retry_results
        }

def run_stage5_parallel_crawling():
    """5단계 병렬 크롤링 실행"""
    logger.info("🚀 5단계 병렬 크롤링 시스템 시작")
    
    # 최적 워커 수 결정 (CPU 코어 수 기반)
    cpu_count = mp.cpu_count()
    optimal_workers = min(8, max(4, cpu_count - 1))  # 최소 4개, 최대 8개
    
    logger.info(f"시스템 정보: CPU {cpu_count}코어, 워커 {optimal_workers}개 사용")
    
    # 병렬 크롤링 매니저 생성
    manager = ParallelCrawlingManager(max_workers=optimal_workers)
    
    try:
        # 메인 크롤링 실행
        summary = manager.run_parallel_crawling()
        
        # 실패한 작업 재시도
        if manager.failed_tasks:
            retry_summary = manager.retry_failed_tasks()
            summary.update(retry_summary)
        
        # 최종 성과 리포트
        logger.info("🎯 5단계 병렬 크롤링 성과 리포트")
        logger.info(f"• 처리 속도: {summary['stores_per_hour']:.0f}개/시간 (목표: 500-1,000개/시간)")
        logger.info(f"• 총 소요시간: {summary['total_time_minutes']:.1f}분")
        logger.info(f"• 성공률: {summary['success_rate']:.1f}%")
        logger.info(f"• 총 처리 가게: {summary['total_stores_processed']}개")
        
        # 성능 목표 달성 여부 확인
        if summary['stores_per_hour'] >= 500:
            logger.info("✅ 5단계 성능 목표 달성!")
        else:
            logger.warning("⚠️ 성능 목표 미달성. 추가 최적화 필요")
        
        return summary
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        return {}
    except Exception as e:
        logger.error(f"병렬 크롤링 실행 중 오류: {e}")
        return {}

if __name__ == "__main__":
    # 멀티프로세싱 시작점 설정 (Windows 호환성)
    mp.set_start_method('spawn', force=True)
    
    # 병렬 크롤링 실행
    result = run_stage5_parallel_crawling()
    
    if result:
        print(f"\n🎉 병렬 크롤링 완료!")
        print(f"처리 속도: {result.get('stores_per_hour', 0):.0f}개/시간")
        print(f"총 소요시간: {result.get('total_time_minutes', 0):.1f}분") 