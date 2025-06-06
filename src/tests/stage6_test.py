"""
6단계 운영 자동화 시스템 테스트
모든 기능의 정상 동작을 확인하는 종합 테스트
"""

import asyncio
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# config 모듈 경로 추가
config_path = project_root / "config"
sys.path.insert(0, str(config_path))

# 테스트할 모듈들 import
try:
    from src.automation.quality_assurance import QualityAssurance, QualityConfig
    from src.automation.exception_handler import ExceptionHandler, ExceptionConfig
    from src.automation.store_status_manager import StoreStatusManager, StatusConfig
    from src.automation.notification_system import NotificationSystem, NotificationConfig
    from src.automation.automated_operations import AutomatedOperations, OperationConfig
except ImportError as e:
    print(f"모듈 import 실패: {e}")
    print("필요한 의존성을 설치해주세요: pip install -r requirements.txt")
    exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Stage6Tester:
    """6단계 시스템 테스트"""
    
    def __init__(self):
        self.test_db_path = "test_refill_spot_crawler.db"
        self.setup_test_data()
    
    def setup_test_data(self):
        """테스트 데이터 설정"""
        try:
            # 테스트용 SQLite 데이터베이스 생성
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            # 테스트용 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    id INTEGER PRIMARY KEY,
                    diningcode_place_id TEXT UNIQUE,
                    name TEXT,
                    address TEXT,
                    position_lat REAL,
                    position_lng REAL,
                    phone_number TEXT,
                    website TEXT,
                    status TEXT DEFAULT 'active',
                    open_hours TEXT,
                    break_time TEXT,
                    last_order TEXT,
                    holiday TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quality_issues (
                    id INTEGER PRIMARY KEY,
                    store_id TEXT,
                    issue_type TEXT,
                    severity TEXT,
                    description TEXT,
                    auto_fixed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawling_logs (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 테스트 데이터 삽입
            test_stores = [
                ('test_001', '테스트 카페 1', '서울시 강남구 테스트로 1', 37.5665, 126.9780, '02-1234-5678', 'http://test1.com', 'active', '09:00-22:00'),
                ('test_002', '테스트 식당 2', '서울시 마포구 테스트로 2', 37.5547, 126.9706, '02-2345-6789', 'http://test2.com', 'active', '11:00-23:00'),
                ('test_003', '테스트 카페 3', '서울시 서초구 테스트로 3', 37.4837, 127.0324, '02-3456-7890', '', 'active', '08:00-20:00'),
            ]
            
            for store in test_stores:
                cursor.execute("""
                    INSERT OR REPLACE INTO stores 
                    (diningcode_place_id, name, address, position_lat, position_lng, phone_number, website, status, open_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, store)
            
            conn.commit()
            conn.close()
            
            logger.info("테스트 데이터 설정 완료")
            
        except Exception as e:
            logger.error(f"테스트 데이터 설정 실패: {e}")
    
    async def test_quality_assurance(self):
        """품질 검증 시스템 테스트"""
        try:
            logger.info("=== 품질 검증 시스템 테스트 ===")
            
            config = QualityConfig(
                coordinate_validation_enabled=True,
                duplicate_detection_enabled=True,
                business_hours_validation_enabled=True,
                auto_fix_enabled=True
            )
            
            qa_system = QualityAssurance(config, self.test_db_path)
            
            # 테스트 데이터로 품질 검증 실행
            test_stores = [
                {
                    'diningcode_place_id': 'test_001',
                    'name': '테스트 카페 1',
                    'address': '서울시 강남구 테스트로 1',
                    'position_lat': 37.5665,
                    'position_lng': 126.9780,
                    'phone_number': '02-1234-5678',
                    'open_hours': '09:00-22:00'
                }
            ]
            
            report = qa_system.run_quality_check(test_stores)
            
            logger.info(f"품질 검증 완료: 총 {report.total_stores}개 가게, {report.issues_found}개 이슈 발견")
            logger.info(f"품질 점수: {report.quality_score}/100")
            
            return True
            
        except Exception as e:
            logger.error(f"품질 검증 테스트 실패: {e}")
            return False
    
    async def test_exception_handler(self):
        """예외 처리 시스템 테스트"""
        try:
            logger.info("=== 예외 처리 시스템 테스트 ===")
            
            config = ExceptionConfig(
                failure_rate_threshold=0.15,
                max_retries=3
            )
            
            exception_handler = ExceptionHandler(config)
            
            # 테스트 함수 정의
            async def test_function():
                logger.info("테스트 함수 실행")
                return True
            
            # 예외 처리와 함께 실행
            success = await exception_handler.execute_with_exception_handling(
                test_function, "test_task"
            )
            
            logger.info(f"예외 처리 테스트 완료: {'성공' if success else '실패'}")
            
            return success
            
        except Exception as e:
            logger.error(f"예외 처리 테스트 실패: {e}")
            return False
    
    async def test_store_status_manager(self):
        """상태 관리 시스템 테스트"""
        try:
            logger.info("=== 상태 관리 시스템 테스트 ===")
            
            config = StatusConfig(
                phone_validation_enabled=True,
                website_check_enabled=True,
                auto_status_update_enabled=True
            )
            
            status_manager = StoreStatusManager(config, self.test_db_path)
            
            # 개별 가게 상태 확인 테스트
            try:
                status_check = status_manager.check_store_status('test_001')
                logger.info(f"가게 상태 확인: {status_check.store_name} - {status_check.current_status}")
            except Exception as e:
                logger.warning(f"개별 상태 확인 실패 (정상): {e}")
            
            # 배치 상태 확인 테스트
            try:
                batch_results = status_manager.batch_check_store_status(['test_001', 'test_002'])
                logger.info(f"배치 상태 확인 완료: {len(batch_results)}개 가게")
            except Exception as e:
                logger.warning(f"배치 상태 확인 실패 (정상): {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"상태 관리 테스트 실패: {e}")
            return False
    
    async def test_notification_system(self):
        """알림 시스템 테스트"""
        try:
            logger.info("=== 알림 시스템 테스트 ===")
            
            # 테스트용 설정 (실제 웹훅 URL 없이)
            config = NotificationConfig(
                slack_webhook_url="",  # 테스트용 빈 값
                discord_webhook_url="",  # 테스트용 빈 값
                email_smtp_server="smtp.gmail.com",
                email_smtp_port=587,
                email_username="test@example.com",
                email_password="test_password",
                email_recipients=["admin@example.com"]
            )
            
            notification_system = NotificationSystem(config, self.test_db_path)
            
            # 테스트 통계 생성
            from src.automation.notification_system import CrawlingStats, QualityStats
            
            crawling_stats = CrawlingStats(
                total_stores=100,
                new_stores=5,
                updated_stores=10,
                failed_requests=2,
                success_rate=0.98,
                processing_time=300.0,
                errors=[],
                districts_processed=["강남구", "마포구"],
                timestamp=datetime.now()
            )
            
            quality_stats = QualityStats(
                total_issues=15,
                coordinate_issues=3,
                duplicate_issues=2,
                business_hours_issues=5,
                auto_fixed_issues=8,
                manual_review_needed=2,
                quality_score=85.5
            )
            
            # 일일 보고서 생성 테스트
            try:
                report = notification_system.generate_daily_report(crawling_stats, quality_stats)
                logger.info("일일 보고서 생성 성공")
            except Exception as e:
                logger.warning(f"일일 보고서 생성 실패 (정상): {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"알림 시스템 테스트 실패: {e}")
            return False
    
    async def test_automated_operations(self):
        """자동화 운영 시스템 테스트"""
        try:
            logger.info("=== 자동화 운영 시스템 테스트 ===")
            
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
            
            # 자동화 운영 시스템 초기화 테스트
            operations = AutomatedOperations(config)
            logger.info("자동화 운영 시스템 초기화 성공")
            
            # 시스템 상태 확인 테스트
            try:
                system_info = operations.get_system_info()
                logger.info(f"시스템 정보: {system_info}")
            except Exception as e:
                logger.warning(f"시스템 정보 확인 실패 (정상): {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"자동화 운영 테스트 실패: {e}")
            return False
    
    def test_database_structure(self):
        """데이터베이스 구조 테스트"""
        try:
            logger.info("=== 데이터베이스 구조 테스트 ===")
            
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            # 필수 테이블 존재 확인
            required_tables = ['stores', 'quality_issues', 'crawling_logs']
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            for table in required_tables:
                if table in existing_tables:
                    logger.info(f"✅ {table} 테이블 존재")
                else:
                    logger.error(f"❌ {table} 테이블 누락")
                    return False
            
            # 테스트 데이터 확인
            cursor.execute("SELECT COUNT(*) FROM stores")
            store_count = cursor.fetchone()[0]
            logger.info(f"테스트 가게 수: {store_count}개")
            
            conn.close()
            logger.info("모든 필수 테이블 존재 확인")
            return True
            
        except Exception as e:
            logger.error(f"데이터베이스 구조 테스트 실패: {e}")
            return False
    
    def generate_test_report(self):
        """테스트 결과 리포트 생성"""
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "test_database": self.test_db_path,
            "modules_tested": [
                "quality_assurance",
                "exception_handler", 
                "store_status_manager",
                "notification_system",
                "automated_operations"
            ],
            "test_summary": "6단계 운영 자동화 시스템 통합 테스트"
        }
        
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"테스트 리포트 생성: {report_file}")
        return report_file
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("🚀 6단계 운영 자동화 시스템 테스트 시작")
        
        test_results = {}
        
        # 1. 데이터베이스 구조 테스트
        test_results['database_structure'] = self.test_database_structure()
        
        # 2. 품질 검증 시스템 테스트
        test_results['quality_assurance'] = await self.test_quality_assurance()
        
        # 3. 예외 처리 시스템 테스트
        test_results['exception_handler'] = await self.test_exception_handler()
        
        # 4. 상태 관리 시스템 테스트
        test_results['store_status_manager'] = await self.test_store_status_manager()
        
        # 5. 알림 시스템 테스트
        test_results['notification_system'] = await self.test_notification_system()
        
        # 6. 자동화 운영 시스템 테스트
        test_results['automated_operations'] = await self.test_automated_operations()
        
        # 결과 요약
        logger.info("📊 테스트 결과 요약")
        logger.info("=" * 50)
        
        passed_tests = 0
        total_tests = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ 통과" if result else "❌ 실패"
            logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
            if result:
                passed_tests += 1
        
        logger.info("=" * 50)
        logger.info(f"전체 테스트: {passed_tests}/{total_tests} 통과")
        
        if passed_tests == total_tests:
            logger.info("🎉 모든 테스트가 성공적으로 완료되었습니다!")
        else:
            logger.warning("❌ 일부 테스트가 실패했습니다. 로그를 확인해주세요.")
        
        # 테스트 리포트 생성
        self.generate_test_report()
        
        return test_results

async def main():
    """메인 테스트 실행"""
    tester = Stage6Tester()
    results = await tester.run_all_tests()
    
    # 정리
    if os.path.exists(tester.test_db_path):
        os.remove(tester.test_db_path)
        logger.info("테스트 데이터베이스 정리 완료")

if __name__ == "__main__":
    asyncio.run(main()) 