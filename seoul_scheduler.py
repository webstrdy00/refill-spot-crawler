"""
서울 전용 스케줄링 시스템 및 자동화 모니터링
4단계: 서울 25개 구 순차 크롤링 전략
"""

import logging
import schedule
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import queue
from seoul_districts import SeoulDistrictManager, DistrictInfo

logger = logging.getLogger(__name__)

class CrawlingStatus(Enum):
    """크롤링 상태 열거형"""
    PENDING = "대기"
    RUNNING = "진행중"
    COMPLETED = "완료"
    ERROR = "오류"
    PAUSED = "일시정지"
    CANCELLED = "취소"

@dataclass
class CrawlingSession:
    """크롤링 세션 정보"""
    session_id: str
    district_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: CrawlingStatus = CrawlingStatus.PENDING
    stores_found: int = 0
    stores_processed: int = 0
    errors: List[str] = None
    keywords_used: List[str] = None
    processing_time_seconds: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.keywords_used is None:
            self.keywords_used = []

@dataclass
class WeeklyScheduleConfig:
    """주간 스케줄 설정"""
    day: str
    districts: List[str]
    time_slots: List[str]
    expected_duration_hours: float
    priority: str

# 서울 25개 구 주간 순환 크롤링 스케줄
SEOUL_WEEKLY_SCHEDULE = {
    # 월요일: Tier 1 (초고밀도 상권)
    "monday": WeeklyScheduleConfig(
        day="monday",
        districts=["강남구", "마포구", "서초구"],
        time_slots=["02:00", "04:00", "06:00"],
        expected_duration_hours=2.0,
        priority="highest"
    ),
    
    # 화요일: Tier 2 (고밀도 상권) - 1그룹
    "tuesday": WeeklyScheduleConfig(
        day="tuesday",
        districts=["송파구", "영등포구", "용산구"],
        time_slots=["02:00", "04:00", "06:00"],
        expected_duration_hours=1.5,
        priority="high"
    ),
    
    # 수요일: Tier 2 (고밀도 상권) - 2그룹  
    "wednesday": WeeklyScheduleConfig(
        day="wednesday",
        districts=["성동구", "광진구"],
        time_slots=["02:00", "04:00"],
        expected_duration_hours=1.5,
        priority="high"
    ),
    
    # 목요일: Tier 3 (중밀도 상권) - 1그룹
    "thursday": WeeklyScheduleConfig(
        day="thursday",
        districts=["관악구", "서대문구", "종로구", "중구"],
        time_slots=["01:00", "03:00", "05:00", "07:00"],
        expected_duration_hours=1.0,
        priority="medium"
    ),
    
    # 금요일: Tier 3 (중밀도 상권) - 2그룹
    "friday": WeeklyScheduleConfig(
        day="friday",
        districts=["성북구", "동대문구"],
        time_slots=["02:00", "04:00"],
        expected_duration_hours=1.0,
        priority="medium"
    ),
    
    # 토요일: Tier 4 (주거 중심) - 1그룹
    "saturday": WeeklyScheduleConfig(
        day="saturday",
        districts=["노원구", "강북구", "은평구", "강서구", "양천구"],
        time_slots=["01:00", "02:30", "04:00", "05:30", "07:00"],
        expected_duration_hours=0.75,
        priority="low"
    ),
    
    # 일요일: Tier 4&5 (나머지 지역)
    "sunday": WeeklyScheduleConfig(
        day="sunday",
        districts=["구로구", "금천구", "동작구", "강동구", "중랑구", "도봉구"],
        time_slots=["01:00", "02:00", "03:00", "04:00", "05:00", "06:00"],
        expected_duration_hours=0.5,
        priority="low"
    )
}

class SeoulCrawlingScheduler:
    """서울 전용 크롤링 스케줄러"""
    
    def __init__(self, district_manager: SeoulDistrictManager):
        self.district_manager = district_manager
        self.sessions: Dict[str, CrawlingSession] = {}
        self.current_session: Optional[CrawlingSession] = None
        self.is_running = False
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.dashboard = SeoulDashboard(self)
        
    def setup_weekly_schedule(self):
        """주간 스케줄 설정"""
        logger.info("=== 서울 25개 구 주간 스케줄 설정 ===")
        
        # 기존 스케줄 초기화
        schedule.clear()
        
        for day_name, config in SEOUL_WEEKLY_SCHEDULE.items():
            for i, (district, time_slot) in enumerate(zip(config.districts, config.time_slots)):
                # 각 구별로 스케줄 등록
                getattr(schedule.every(), day_name).at(time_slot).do(
                    self._schedule_district_crawling,
                    district_name=district,
                    priority=config.priority
                ).tag(f"{day_name}_{district}")
                
                logger.info(f"{day_name.capitalize()} {time_slot}: {district} (우선순위: {config.priority})")
        
        # 주간 통계 리포트 스케줄 (일요일 23:00)
        schedule.every().sunday.at("23:00").do(
            self._generate_weekly_report
        ).tag("weekly_report")
        
        logger.info("주간 스케줄 설정 완료")
        
        # 예상 처리량 계산
        self._calculate_weekly_estimates()
    
    def _calculate_weekly_estimates(self):
        """주간 예상 처리량 계산"""
        total_districts = 0
        total_stores = 0
        
        for config in SEOUL_WEEKLY_SCHEDULE.values():
            total_districts += len(config.districts)
            for district in config.districts:
                district_info = self.district_manager.get_district_info(district)
                if district_info:
                    total_stores += district_info.expected_stores
        
        logger.info(f"주간 예상 처리량:")
        logger.info(f"  총 구 수: {total_districts}개")
        logger.info(f"  예상 가게 수: {total_stores:,}개")
        logger.info(f"  평균 구당 가게: {total_stores/total_districts:.1f}개")
    
    def _schedule_district_crawling(self, district_name: str, priority: str):
        """구별 크롤링 스케줄 실행"""
        logger.info(f"스케줄 실행: {district_name} (우선순위: {priority})")
        
        # 현재 실행 중인 작업이 있는지 확인
        if self.current_session and self.current_session.status == CrawlingStatus.RUNNING:
            logger.warning(f"이미 실행 중인 세션이 있습니다: {self.current_session.district_name}")
            return
        
        # 크롤링 세션 생성
        session = self._create_crawling_session(district_name)
        
        # 작업 큐에 추가
        self.task_queue.put({
            "type": "district_crawling",
            "session": session,
            "priority": priority
        })
        
        # 워커 스레드 시작 (아직 실행 중이 아닌 경우)
        if not self.is_running:
            self._start_worker_thread()
    
    def _create_crawling_session(self, district_name: str) -> CrawlingSession:
        """크롤링 세션 생성"""
        session_id = f"{district_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = CrawlingSession(
            session_id=session_id,
            district_name=district_name,
            start_time=datetime.now(),
            status=CrawlingStatus.PENDING
        )
        
        self.sessions[session_id] = session
        return session
    
    def _start_worker_thread(self):
        """워커 스레드 시작"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("크롤링 워커 스레드 시작")
    
    def _worker_loop(self):
        """워커 스레드 메인 루프"""
        while self.is_running:
            try:
                # 작업 큐에서 작업 가져오기 (타임아웃 5초)
                task = self.task_queue.get(timeout=5)
                
                if task["type"] == "district_crawling":
                    self._execute_district_crawling(task["session"])
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"워커 스레드 오류: {e}")
                continue
    
    def _execute_district_crawling(self, session: CrawlingSession):
        """구별 크롤링 실행"""
        self.current_session = session
        session.status = CrawlingStatus.RUNNING
        
        logger.info(f"=== {session.district_name} 크롤링 시작 ===")
        
        try:
            # 구 정보 조회
            district_info = self.district_manager.get_district_info(session.district_name)
            if not district_info:
                raise Exception(f"구 정보를 찾을 수 없습니다: {session.district_name}")
            
            # 크롤링 실행 (실제 크롤링 로직 호출)
            result = self._run_district_crawling(district_info, session)
            
            # 결과 처리
            session.stores_found = result.get("stores_found", 0)
            session.stores_processed = result.get("stores_processed", 0)
            session.keywords_used = result.get("keywords_used", [])
            session.status = CrawlingStatus.COMPLETED
            session.end_time = datetime.now()
            session.processing_time_seconds = (session.end_time - session.start_time).total_seconds()
            
            # 구 상태 업데이트
            self.district_manager.update_district_status(
                session.district_name, "완료", session.stores_processed
            )
            
            logger.info(f"{session.district_name} 크롤링 완료: {session.stores_processed}개 가게 처리")
            
        except Exception as e:
            session.status = CrawlingStatus.ERROR
            session.errors.append(str(e))
            session.end_time = datetime.now()
            
            logger.error(f"{session.district_name} 크롤링 실패: {e}")
            
            # 구 상태를 오류로 업데이트
            self.district_manager.update_district_status(session.district_name, "오류")
            
        finally:
            self.current_session = None
    
    def _run_district_crawling(self, district_info: DistrictInfo, session: CrawlingSession) -> Dict:
        """실제 구별 크롤링 실행"""
        # 여기서 실제 크롤링 로직을 호출
        # main.py의 run_enhanced_crawling과 연동
        
        from main import run_enhanced_crawling
        import config
        
        # 임시로 설정 변경
        original_region = getattr(config, 'TEST_REGION', None)
        original_rect = getattr(config, 'TEST_RECT', None)
        original_keywords = getattr(config, 'TEST_KEYWORDS', None)
        
        try:
            # 구별 설정으로 변경
            config.TEST_REGION = district_info.name
            config.TEST_RECT = district_info.rect
            config.TEST_KEYWORDS = district_info.keywords
            
            # 크롤링 실행
            stores = run_enhanced_crawling()
            
            return {
                "stores_found": len(stores) if stores else 0,
                "stores_processed": len(stores) if stores else 0,
                "keywords_used": district_info.keywords
            }
            
        finally:
            # 설정 복원
            if original_region:
                config.TEST_REGION = original_region
            if original_rect:
                config.TEST_RECT = original_rect
            if original_keywords:
                config.TEST_KEYWORDS = original_keywords
    
    def _generate_weekly_report(self):
        """주간 리포트 생성"""
        logger.info("=== 주간 크롤링 리포트 생성 ===")
        
        # 지난 주 세션들 조회
        week_ago = datetime.now() - timedelta(days=7)
        weekly_sessions = [
            session for session in self.sessions.values()
            if session.start_time >= week_ago
        ]
        
        # 통계 계산
        total_sessions = len(weekly_sessions)
        completed_sessions = len([s for s in weekly_sessions if s.status == CrawlingStatus.COMPLETED])
        error_sessions = len([s for s in weekly_sessions if s.status == CrawlingStatus.ERROR])
        total_stores = sum(s.stores_processed for s in weekly_sessions)
        
        # 리포트 생성
        report = {
            "period": f"{week_ago.strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}",
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "error_sessions": error_sessions,
            "success_rate": completed_sessions / total_sessions * 100 if total_sessions > 0 else 0,
            "total_stores_processed": total_stores,
            "average_stores_per_district": total_stores / completed_sessions if completed_sessions > 0 else 0,
            "districts_completed": [s.district_name for s in weekly_sessions if s.status == CrawlingStatus.COMPLETED],
            "districts_with_errors": [s.district_name for s in weekly_sessions if s.status == CrawlingStatus.ERROR]
        }
        
        # 리포트 저장
        report_filename = f"weekly_report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"주간 리포트 저장: {report_filename}")
        logger.info(f"완료율: {report['success_rate']:.1f}%, 총 가게: {report['total_stores_processed']:,}개")
    
    def start_scheduler(self):
        """스케줄러 시작"""
        logger.info("=== 서울 크롤링 스케줄러 시작 ===")
        self.setup_weekly_schedule()
        
        # 대시보드 시작
        self.dashboard.start()
        
        # 스케줄 실행 루프
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
            except KeyboardInterrupt:
                logger.info("스케줄러 중지 요청")
                break
            except Exception as e:
                logger.error(f"스케줄러 오류: {e}")
                time.sleep(60)
        
        self.stop_scheduler()
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        logger.info("스케줄러 중지 중...")
        self.is_running = False
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
        
        self.dashboard.stop()
        logger.info("스케줄러 중지 완료")
    
    def get_current_status(self) -> Dict:
        """현재 상태 조회"""
        return {
            "is_running": self.is_running,
            "current_session": asdict(self.current_session) if self.current_session else None,
            "queue_size": self.task_queue.qsize(),
            "total_sessions": len(self.sessions),
            "recent_sessions": [
                asdict(session) for session in 
                sorted(self.sessions.values(), key=lambda x: x.start_time, reverse=True)[:5]
            ]
        }
    
    def force_run_district(self, district_name: str) -> bool:
        """특정 구 강제 실행"""
        if self.current_session and self.current_session.status == CrawlingStatus.RUNNING:
            logger.warning("이미 실행 중인 세션이 있습니다")
            return False
        
        session = self._create_crawling_session(district_name)
        self.task_queue.put({
            "type": "district_crawling",
            "session": session,
            "priority": "manual"
        })
        
        if not self.is_running:
            self._start_worker_thread()
        
        logger.info(f"수동 실행 요청: {district_name}")
        return True

class SeoulDashboard:
    """서울 전용 실시간 모니터링 대시보드"""
    
    def __init__(self, scheduler: SeoulCrawlingScheduler):
        self.scheduler = scheduler
        self.is_running = False
        self.dashboard_thread = None
    
    def start(self):
        """대시보드 시작"""
        if self.dashboard_thread and self.dashboard_thread.is_alive():
            return
        
        self.is_running = True
        self.dashboard_thread = threading.Thread(target=self._dashboard_loop, daemon=True)
        self.dashboard_thread.start()
        logger.info("서울 대시보드 시작")
    
    def stop(self):
        """대시보드 중지"""
        self.is_running = False
        if self.dashboard_thread and self.dashboard_thread.is_alive():
            self.dashboard_thread.join(timeout=5)
    
    def _dashboard_loop(self):
        """대시보드 메인 루프"""
        while self.is_running:
            try:
                # 10분마다 현황 업데이트
                self._update_dashboard()
                time.sleep(600)  # 10분
            except Exception as e:
                logger.error(f"대시보드 오류: {e}")
                time.sleep(60)
    
    def _update_dashboard(self):
        """대시보드 현황 업데이트"""
        # 서울 커버리지 통계
        coverage_stats = self.scheduler.district_manager.get_seoul_coverage_stats()
        
        # 현재 스케줄러 상태
        scheduler_status = self.scheduler.get_current_status()
        
        # 대시보드 정보 생성
        dashboard_info = {
            "timestamp": datetime.now().isoformat(),
            "seoul_coverage": coverage_stats,
            "scheduler_status": scheduler_status,
            "next_scheduled": self._get_next_scheduled_districts(),
            "performance_metrics": self._calculate_performance_metrics()
        }
        
        # 대시보드 파일 저장
        with open("seoul_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(dashboard_info, f, ensure_ascii=False, indent=2, default=str)
        
        # 콘솔 출력
        self._print_dashboard_summary(dashboard_info)
    
    def _get_next_scheduled_districts(self) -> List[Dict]:
        """다음 예정된 구 목록"""
        next_jobs = []
        
        # schedule 라이브러리에서 다음 작업들 조회
        for job in schedule.jobs:
            if hasattr(job, 'next_run') and job.next_run:
                # 태그에서 구 이름 추출
                tag = job.tags.pop() if job.tags else "unknown"
                if "_" in tag:
                    day, district = tag.split("_", 1)
                    next_jobs.append({
                        "district": district,
                        "scheduled_time": job.next_run.isoformat(),
                        "day": day
                    })
        
        # 시간순 정렬
        next_jobs.sort(key=lambda x: x["scheduled_time"])
        return next_jobs[:5]  # 다음 5개만
    
    def _calculate_performance_metrics(self) -> Dict:
        """성능 지표 계산"""
        recent_sessions = [
            session for session in self.scheduler.sessions.values()
            if session.start_time >= datetime.now() - timedelta(days=1)
        ]
        
        if not recent_sessions:
            return {"message": "최근 24시간 내 세션 없음"}
        
        completed_sessions = [s for s in recent_sessions if s.status == CrawlingStatus.COMPLETED]
        
        if not completed_sessions:
            return {"message": "최근 24시간 내 완료된 세션 없음"}
        
        avg_processing_time = sum(s.processing_time_seconds for s in completed_sessions) / len(completed_sessions)
        avg_stores_per_session = sum(s.stores_processed for s in completed_sessions) / len(completed_sessions)
        
        return {
            "recent_sessions_24h": len(recent_sessions),
            "completed_sessions_24h": len(completed_sessions),
            "success_rate_24h": len(completed_sessions) / len(recent_sessions) * 100,
            "avg_processing_time_minutes": avg_processing_time / 60,
            "avg_stores_per_session": avg_stores_per_session,
            "total_stores_24h": sum(s.stores_processed for s in completed_sessions)
        }
    
    def _print_dashboard_summary(self, dashboard_info: Dict):
        """대시보드 요약 콘솔 출력"""
        logger.info("=== 서울 크롤링 현황 대시보드 ===")
        
        coverage = dashboard_info["seoul_coverage"]
        logger.info(f"서울 커버리지: {coverage['completion_rate']:.1f}% ({coverage['completed']}/{coverage['total_districts']})")
        
        scheduler = dashboard_info["scheduler_status"]
        if scheduler["current_session"]:
            current = scheduler["current_session"]
            logger.info(f"현재 실행 중: {current['district_name']} ({current['status']})")
        else:
            logger.info("현재 실행 중인 세션 없음")
        
        next_districts = dashboard_info["next_scheduled"]
        if next_districts:
            next_district = next_districts[0]
            logger.info(f"다음 예정: {next_district['district']} ({next_district['scheduled_time']})")
        
        metrics = dashboard_info["performance_metrics"]
        if "success_rate_24h" in metrics:
            logger.info(f"24시간 성공률: {metrics['success_rate_24h']:.1f}%")
            logger.info(f"24시간 총 가게: {metrics['total_stores_24h']}개")

class SeoulErrorHandler:
    """서울 크롤링 특화 장애 대응"""
    
    def __init__(self, scheduler: SeoulCrawlingScheduler):
        self.scheduler = scheduler
        self.error_patterns = {
            "low_search_results": self._handle_low_search_results,
            "too_many_results": self._handle_too_many_results,
            "outdated_keywords": self._handle_outdated_keywords,
            "network_error": self._handle_network_error,
            "rate_limit": self._handle_rate_limit
        }
    
    def handle_district_error(self, district_name: str, error_type: str, error_details: str):
        """구별 오류 처리"""
        logger.warning(f"구별 오류 발생: {district_name} - {error_type}")
        
        if error_type in self.error_patterns:
            handler = self.error_patterns[error_type]
            handler(district_name, error_details)
        else:
            self._handle_unknown_error(district_name, error_type, error_details)
    
    def _handle_low_search_results(self, district_name: str, error_details: str):
        """검색 결과 부족 처리"""
        logger.info(f"{district_name}: 검색 결과 부족 → 지역 특화 키워드 추가")
        
        # 지역 특화 키워드 생성
        additional_keywords = self._generate_district_specific_keywords(district_name)
        
        # 구 정보 업데이트
        district_info = self.scheduler.district_manager.get_district_info(district_name)
        if district_info:
            district_info.keywords.extend(additional_keywords)
            logger.info(f"추가된 키워드: {additional_keywords}")
    
    def _handle_too_many_results(self, district_name: str, error_details: str):
        """결과 과다 처리"""
        logger.info(f"{district_name}: 결과 과다 → 격자 세분화 필요")
        
        # 격자 세분화 로직 (SeoulGridSystem과 연동)
        # 실제 구현에서는 격자 시스템과 연동하여 처리
        pass
    
    def _handle_outdated_keywords(self, district_name: str, error_details: str):
        """키워드 효과 저하 처리"""
        logger.info(f"{district_name}: 키워드 효과 저하 → 트렌딩 키워드 업데이트")
        
        # 트렌딩 키워드 분석 및 업데이트
        trending_keywords = self._analyze_trending_keywords(district_name)
        
        district_info = self.scheduler.district_manager.get_district_info(district_name)
        if district_info:
            # 기존 키워드 중 효과 낮은 것들 제거하고 새로운 키워드 추가
            district_info.keywords = trending_keywords
    
    def _handle_network_error(self, district_name: str, error_details: str):
        """네트워크 오류 처리"""
        logger.info(f"{district_name}: 네트워크 오류 → 재시도 스케줄링")
        
        # 30분 후 재시도 스케줄링
        retry_time = datetime.now() + timedelta(minutes=30)
        schedule.every().day.at(retry_time.strftime("%H:%M")).do(
            self.scheduler.force_run_district,
            district_name=district_name
        ).tag(f"retry_{district_name}")
    
    def _handle_rate_limit(self, district_name: str, error_details: str):
        """요청 한도 초과 처리"""
        logger.info(f"{district_name}: 요청 한도 초과 → 지연 후 재시도")
        
        # 2시간 후 재시도
        retry_time = datetime.now() + timedelta(hours=2)
        schedule.every().day.at(retry_time.strftime("%H:%M")).do(
            self.scheduler.force_run_district,
            district_name=district_name
        ).tag(f"rate_limit_retry_{district_name}")
    
    def _handle_unknown_error(self, district_name: str, error_type: str, error_details: str):
        """알 수 없는 오류 처리"""
        logger.error(f"{district_name}: 알 수 없는 오류 - {error_type}: {error_details}")
        
        # 오류 로그 저장
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "district": district_name,
            "error_type": error_type,
            "error_details": error_details
        }
        
        with open("seoul_error_log.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(error_log, ensure_ascii=False) + "\n")
    
    def _generate_district_specific_keywords(self, district_name: str) -> List[str]:
        """구별 특화 키워드 생성"""
        # 구별 특성에 맞는 키워드 생성
        special_keywords = {
            "성북구": ["성신여대", "한성대", "정릉"],
            "관악구": ["서울대", "신림동", "봉천동"],
            "서대문구": ["연세대", "이화여대", "신촌"],
            "동대문구": ["한국외대", "경희대", "회기동"],
            "종로구": ["대학로", "인사동", "삼청동"],
            "중구": ["명동", "남대문", "동대문"],
            "용산구": ["이태원", "한남동", "용산역"],
            "영등포구": ["여의도", "타임스퀘어", "영등포역"]
        }
        
        base_keywords = special_keywords.get(district_name, [])
        
        # 무한리필 키워드와 조합
        additional = []
        for keyword in base_keywords:
            additional.extend([
                f"{keyword} 무한리필",
                f"{keyword} 고기무한리필",
                f"{keyword} 뷔페"
            ])
        
        return additional
    
    def _analyze_trending_keywords(self, district_name: str) -> List[str]:
        """트렌딩 키워드 분석"""
        # 실제로는 검색 트렌드 API나 소셜미디어 분석을 통해 구현
        # 여기서는 기본 키워드 반환
        district_info = self.scheduler.district_manager.get_district_info(district_name)
        return district_info.keywords if district_info else []

def test_seoul_scheduler():
    """서울 스케줄러 테스트"""
    logger.info("=== 서울 스케줄러 테스트 ===")
    
    # 구 관리자 초기화
    from seoul_districts import SeoulDistrictManager
    district_manager = SeoulDistrictManager()
    
    # 스케줄러 초기화
    scheduler = SeoulCrawlingScheduler(district_manager)
    
    # 스케줄 설정 테스트
    scheduler.setup_weekly_schedule()
    
    # 현재 상태 확인
    status = scheduler.get_current_status()
    logger.info(f"스케줄러 상태: {status}")
    
    # 수동 실행 테스트
    test_district = "강남구"
    if scheduler.force_run_district(test_district):
        logger.info(f"{test_district} 수동 실행 요청 성공")
    
    # 대시보드 테스트
    dashboard_info = {
        "seoul_coverage": district_manager.get_seoul_coverage_stats(),
        "scheduler_status": status
    }
    
    logger.info("대시보드 정보:")
    logger.info(f"  서울 커버리지: {dashboard_info['seoul_coverage']['completion_rate']:.1f}%")
    logger.info(f"  총 예상 가게: {dashboard_info['seoul_coverage']['total_expected_stores']:,}개")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_seoul_scheduler() 