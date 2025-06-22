"""
6단계: 통합 자동화 운영 시스템
무인 운영을 위한 스케줄링, 모니터링, 자동 복구
"""

import asyncio
import logging
import schedule
import time
import json
import psutil
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from ..core.database import DatabaseManager

# 기존 모듈들 import
from .quality_assurance import QualityAssurance, QualityConfig
from .exception_handler import ExceptionHandler, ExceptionConfig
from .store_status_manager import StoreStatusManager, StatusConfig
from .notification_system import NotificationSystem, NotificationConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automated_operations.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class OperationConfig:
    """운영 설정"""
    # 스케줄링 설정
    daily_crawling_time: str = "02:00"  # 새벽 2시 일일 크롤링
    quality_check_time: str = "03:00"   # 새벽 3시 품질 검증
    status_check_time: str = "04:00"    # 새벽 4시 상태 확인
    weekly_report_day: str = "monday"   # 월요일 주간 보고서
    weekly_report_time: str = "09:00"   # 오전 9시 주간 보고서
    
    # 모니터링 설정
    health_check_interval: int = 30     # 30분마다 상태 확인
    error_alert_threshold: int = 5      # 5회 연속 실패 시 알림
    
    # 자동 복구 설정
    auto_recovery_enabled: bool = True
    max_recovery_attempts: int = 3
    recovery_delay_minutes: int = 10
    
    # 데이터 보관 설정
    log_retention_days: int = 30        # 로그 보관 기간
    report_retention_days: int = 90     # 보고서 보관 기간

@dataclass
class SystemStatus:
    """시스템 상태"""
    is_running: bool = False
    last_crawling: Optional[datetime] = None
    last_quality_check: Optional[datetime] = None
    last_status_check: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    total_stores: int = 0
    active_stores: int = 0
    failed_stores: int = 0

class AutomatedOperations:
    """통합 자동화 운영 시스템"""
    
    def __init__(self, config: OperationConfig):
        self.config = config
        self.db_path = "refill_spot_crawler.db"  # DATABASE_CONFIG['database']
        self.is_running = False
        self.scheduler_thread = None
        
        # 시스템 상태
        self.status = SystemStatus()
        
        # 하위 시스템 초기화
        self._initialize_subsystems()
        
        # 스케줄러 설정
        self._setup_scheduler()
        
        # 상태 파일 경로
        self.status_file = Path("system_status.json")
        
        logger.info("자동화 운영 시스템 초기화 완료")
    
    def _initialize_subsystems(self):
        """하위 시스템 초기화"""
        try:
            # 품질 검증 시스템
            quality_config = QualityConfig(
                coordinate_validation_enabled=True,
                duplicate_detection_enabled=True,
                business_hours_validation_enabled=True,
                auto_fix_enabled=True,
                similarity_threshold=0.85,
                cluster_eps=0.3
            )
            self.quality_system = QualityAssurance(quality_config, self.db_path)
            
            # 예외 처리 시스템
            exception_config = ExceptionConfig(
                failure_rate_threshold=0.15,
                structure_change_threshold=0.3,
                ip_block_detection_enabled=True,
                proxy_rotation_enabled=True,
                backup_strategy_enabled=True,
                max_retries=3,
                retry_delay=5
            )
            self.exception_handler = ExceptionHandler(exception_config)
            
            # 상태 관리 시스템
            status_config = StatusConfig(
                phone_validation_enabled=True,
                website_check_enabled=True,
                review_monitoring_enabled=True,
                auto_status_update_enabled=True,
                closure_detection_days=30,
                inactive_threshold_days=90
            )
            self.status_manager = StoreStatusManager(status_config, self.db_path)
            
            # 알림 시스템
            notification_config = NotificationConfig(
                slack_webhook_url=None,  # 실제 사용 시 설정
                discord_webhook_url=None,  # 실제 사용 시 설정
                email_smtp_server="smtp.gmail.com",
                email_smtp_port=587,
                email_username=None,  # 실제 사용 시 설정
                email_password=None,  # 실제 사용 시 설정
                email_recipients=[]
            )
            self.notification_system = NotificationSystem(notification_config, self.db_path)
            
            logger.info("모든 하위 시스템 초기화 완료")
            
        except Exception as e:
            logger.error(f"하위 시스템 초기화 실패: {e}")
            raise
    
    def _setup_scheduler(self):
        """스케줄러 설정"""
        try:
            # 일일 크롤링
            schedule.every().day.at(self.config.daily_crawling_time).do(
                self._schedule_daily_crawling
            )
            
            # 품질 검증
            schedule.every().day.at(self.config.quality_check_time).do(
                self._schedule_quality_check
            )
            
            # 상태 확인
            schedule.every().day.at(self.config.status_check_time).do(
                self._schedule_status_check
            )
            
            # 주간 보고서
            getattr(schedule.every(), self.config.weekly_report_day).at(
                self.config.weekly_report_time
            ).do(self._schedule_weekly_report)
            
            # 상태 모니터링
            schedule.every(self.config.health_check_interval).minutes.do(
                self._schedule_health_check
            )
            
            # 일일 정리 작업
            schedule.every().day.at("01:00").do(self._schedule_cleanup)
            
            logger.info("스케줄러 설정 완료")
            
        except Exception as e:
            logger.error(f"스케줄러 설정 실패: {e}")
            raise
    
    def _schedule_daily_crawling(self):
        """일일 크롤링 스케줄"""
        asyncio.create_task(self.run_daily_crawling())
    
    def _schedule_quality_check(self):
        """품질 검증 스케줄"""
        asyncio.create_task(self.run_quality_check())
    
    def _schedule_status_check(self):
        """상태 확인 스케줄"""
        asyncio.create_task(self.run_status_check())
    
    def _schedule_weekly_report(self):
        """주간 보고서 스케줄"""
        asyncio.create_task(self.generate_weekly_report())
    
    def _schedule_health_check(self):
        """상태 모니터링 스케줄"""
        asyncio.create_task(self.health_check())
    
    def _schedule_cleanup(self):
        """정리 작업 스케줄"""
        asyncio.create_task(self.cleanup_old_data())
    
    async def run_daily_crawling(self):
        """일일 크롤링 실행"""
        try:
            logger.info("일일 크롤링 시작")
            start_time = datetime.now()
            
            # 크롤링 실행 (서울 전체 크롤링)
            from main import run_stage4_seoul_coverage
            
            # 예외 처리와 함께 크롤링 실행
            success = await self.exception_handler.execute_with_exception_handling(
                run_stage4_seoul_coverage, "daily_crawling"
            )
            
            if success:
                self.status.last_crawling = datetime.now()
                self.status.error_count = 0
                
                # 일일 보고서 발송
                await self.notification_system.send_daily_report()
                
                logger.info(f"일일 크롤링 완료 (소요시간: {datetime.now() - start_time})")
            else:
                self.status.error_count += 1
                await self.notification_system.send_error_alert(
                    "일일 크롤링 실패", 
                    f"크롤링 실행 중 오류 발생 (연속 실패: {self.status.error_count}회)",
                    "high"
                )
                
        except Exception as e:
            logger.error(f"일일 크롤링 실행 중 오류: {e}")
            self.status.last_error = str(e)
            self.status.error_count += 1
            
            await self.notification_system.send_error_alert(
                "크롤링 시스템 오류", str(e), "high"
            )
    
    async def run_quality_check(self):
        """품질 검증 실행"""
        try:
            logger.info("품질 검증 시작")
            
            # 품질 검증 실행
            report = await self.quality_system.run_comprehensive_quality_check()
            
            self.status.last_quality_check = datetime.now()
            
            # 심각한 품질 이슈가 있으면 알림
            if report.critical_issues > 0:
                await self.notification_system.send_error_alert(
                    "품질 이슈 발견",
                    f"심각한 품질 이슈 {report.critical_issues}건 발견",
                    "medium"
                )
            
            logger.info(f"품질 검증 완료 (총 이슈: {report.total_issues}건)")
            
        except Exception as e:
            logger.error(f"품질 검증 실행 중 오류: {e}")
            await self.notification_system.send_error_alert(
                "품질 검증 오류", str(e), "medium"
            )
    
    async def run_status_check(self):
        """상태 확인 실행"""
        try:
            logger.info("상태 확인 시작")
            
            # 가게 상태 확인
            status_report = await self.status_manager.run_comprehensive_status_check()
            
            self.status.last_status_check = datetime.now()
            
            # 대량 폐업 감지 시 알림
            if status_report.newly_closed > 50:  # 50개 이상 폐업 시
                await self.notification_system.send_error_alert(
                    "대량 폐업 감지",
                    f"신규 폐업 가게 {status_report.newly_closed}개 감지",
                    "medium"
                )
            
            logger.info(f"상태 확인 완료 (폐업: {status_report.newly_closed}개)")
            
        except Exception as e:
            logger.error(f"상태 확인 실행 중 오류: {e}")
            await self.notification_system.send_error_alert(
                "상태 확인 오류", str(e), "medium"
            )
    
    async def generate_weekly_report(self):
        """주간 보고서 생성"""
        try:
            logger.info("주간 보고서 생성 시작")
            
            # 주간 보고서 생성
            report_path = self.notification_system.generate_weekly_report()
            
            if report_path:
                logger.info(f"주간 보고서 생성 완료: {report_path}")
            else:
                await self.notification_system.send_error_alert(
                    "보고서 생성 실패", "주간 보고서 생성에 실패했습니다.", "low"
                )
                
        except Exception as e:
            logger.error(f"주간 보고서 생성 중 오류: {e}")
            await self.notification_system.send_error_alert(
                "보고서 생성 오류", str(e), "low"
            )
    
    async def health_check(self):
        """시스템 상태 확인"""
        try:
            # 데이터베이스 연결 확인
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stores WHERE status = 'active'")
                self.status.active_stores = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stores")
                self.status.total_stores = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE status = 'failed'")
                self.status.failed_stores = cursor.fetchone()[0]
            
            # 시스템 상태 저장
            self._save_status()
            
            # 연속 실패 시 알림
            if self.status.error_count >= self.config.error_alert_threshold:
                await self.notification_system.send_error_alert(
                    "시스템 불안정",
                    f"연속 {self.status.error_count}회 오류 발생",
                    "high"
                )
                
                # 자동 복구 시도
                if self.config.auto_recovery_enabled:
                    await self._attempt_auto_recovery()
            
        except Exception as e:
            logger.error(f"상태 확인 중 오류: {e}")
            self.status.last_error = str(e)
    
    async def _attempt_auto_recovery(self):
        """자동 복구 시도"""
        try:
            logger.info("자동 복구 시도 시작")
            
            for attempt in range(self.config.max_recovery_attempts):
                logger.info(f"복구 시도 {attempt + 1}/{self.config.max_recovery_attempts}")
                
                # 시스템 재시작 시뮬레이션
                await asyncio.sleep(self.config.recovery_delay_minutes * 60)
                
                # 간단한 테스트 실행
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1")
                        
                    logger.info(f"복구 시도 {attempt + 1} 성공")
                    self.status.error_count = 0
                    
                    await self.notification_system.send_error_alert(
                        "자동 복구 성공",
                        f"{attempt + 1}번째 시도에서 시스템 복구 성공",
                        "low"
                    )
                    return True
                    
                except Exception as e:
                    logger.error(f"복구 시도 {attempt + 1} 실패: {e}")
                    continue
            
            # 모든 복구 시도 실패
            await self.notification_system.send_error_alert(
                "자동 복구 실패",
                f"{self.config.max_recovery_attempts}회 복구 시도 모두 실패",
                "high"
            )
            return False
            
        except Exception as e:
            logger.error(f"자동 복구 중 오류: {e}")
            return False
    
    async def cleanup_old_data(self):
        """오래된 데이터 정리"""
        try:
            logger.info("데이터 정리 작업 시작")
            
            # 오래된 로그 삭제
            log_cutoff = datetime.now() - timedelta(days=self.config.log_retention_days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 오래된 크롤링 로그 삭제
                cursor.execute("""
                    DELETE FROM crawling_logs 
                    WHERE created_at < ?
                """, (log_cutoff,))
                
                # 오래된 품질 이슈 삭제
                cursor.execute("""
                    DELETE FROM quality_issues 
                    WHERE created_at < ? AND resolved = 1
                """, (log_cutoff,))
                
                deleted_logs = cursor.rowcount
                conn.commit()
            
            # 오래된 보고서 파일 삭제
            reports_dir = Path("reports")
            if reports_dir.exists():
                report_cutoff = datetime.now() - timedelta(days=self.config.report_retention_days)
                
                for file_path in reports_dir.glob("*"):
                    if file_path.stat().st_mtime < report_cutoff.timestamp():
                        file_path.unlink()
            
            logger.info(f"데이터 정리 완료 (삭제된 로그: {deleted_logs}건)")
            
        except Exception as e:
            logger.error(f"데이터 정리 중 오류: {e}")
    
    def _save_status(self):
        """시스템 상태 저장"""
        try:
            status_data = asdict(self.status)
            # datetime 객체를 문자열로 변환
            for key, value in status_data.items():
                if isinstance(value, datetime):
                    status_data[key] = value.isoformat() if value else None
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")
    
    def _load_status(self):
        """시스템 상태 로드"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                # 문자열을 datetime 객체로 변환
                for key, value in status_data.items():
                    if key in ['last_crawling', 'last_quality_check', 'last_status_check'] and value:
                        status_data[key] = datetime.fromisoformat(value)
                
                self.status = SystemStatus(**status_data)
                logger.info("시스템 상태 로드 완료")
                
        except Exception as e:
            logger.error(f"상태 로드 실패: {e}")
    
    def start(self):
        """시스템 시작"""
        try:
            logger.info("자동화 운영 시스템 시작")
            
            # 기존 상태 로드
            self._load_status()
            
            self.status.is_running = True
            
            # 스케줄러 실행
            def run_scheduler():
                while self.status.is_running:
                    schedule.run_pending()
                    time.sleep(60)  # 1분마다 확인
            
            # 별도 스레드에서 스케줄러 실행
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            
            logger.info("자동화 운영 시스템 시작 완료")
            
        except Exception as e:
            logger.error(f"시스템 시작 실패: {e}")
            raise
    
    def stop(self):
        """시스템 중지"""
        try:
            logger.info("자동화 운영 시스템 중지")
            
            self.status.is_running = False
            self._save_status()
            
            logger.info("자동화 운영 시스템 중지 완료")
            
        except Exception as e:
            logger.error(f"시스템 중지 실패: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """시스템 정보 조회"""
        return {
            "status": asdict(self.status),
            "config": asdict(self.config),
            "uptime": datetime.now().isoformat(),
            "next_scheduled_tasks": [
                {
                    "job": str(job.job_func),
                    "next_run": job.next_run.isoformat() if job.next_run else None
                }
                for job in schedule.jobs
            ]
        }
    
    async def manual_trigger(self, task_type: str) -> bool:
        """수동 작업 실행"""
        try:
            logger.info(f"수동 작업 실행: {task_type}")
            
            if task_type == "crawling":
                await self.run_daily_crawling()
            elif task_type == "quality_check":
                await self.run_quality_check()
            elif task_type == "status_check":
                await self.run_status_check()
            elif task_type == "weekly_report":
                await self.generate_weekly_report()
            elif task_type == "health_check":
                await self.health_check()
            elif task_type == "cleanup":
                await self.cleanup_old_data()
            else:
                logger.error(f"알 수 없는 작업 유형: {task_type}")
                return False
            
            logger.info(f"수동 작업 완료: {task_type}")
            return True
            
        except Exception as e:
            logger.error(f"수동 작업 실행 실패 ({task_type}): {e}")
            return False

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    # 운영 설정
    config = OperationConfig(
        daily_crawling_time="02:00",
        quality_check_time="03:00",
        status_check_time="04:00",
        weekly_report_day="monday",
        weekly_report_time="09:00",
        health_check_interval=30,
        error_alert_threshold=5,
        auto_recovery_enabled=True,
        max_recovery_attempts=3,
        recovery_delay_minutes=10,
        log_retention_days=30,
        report_retention_days=90
    )
    
    # 자동화 시스템 초기화
    automation = AutomatedOperations(config)
    
    try:
        # 시스템 시작
        automation.start()
        
        # 시스템 정보 출력
        system_info = automation.get_system_info()
        logger.info(f"시스템 정보: {json.dumps(system_info, ensure_ascii=False, indent=2)}")
        
        # 무한 실행 (실제 운영 시)
        while True:
            await asyncio.sleep(3600)  # 1시간마다 대기
            
    except KeyboardInterrupt:
        logger.info("사용자에 의한 시스템 중지")
    except Exception as e:
        logger.error(f"시스템 실행 중 오류: {e}")
    finally:
        automation.stop()

if __name__ == "__main__":
    asyncio.run(main()) 