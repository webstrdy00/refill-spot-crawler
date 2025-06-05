"""
6단계: 휴업/폐업 가게 관리 시스템
주기적 상태 확인 및 자동 상태 업데이트
"""

import logging
import time
import json
import requests
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import phonenumbers
from phonenumbers import NumberParseException
from database import DatabaseManager

logger = logging.getLogger(__name__)

@dataclass
class StatusConfig:
    """상태 관리 설정"""
    phone_validation_enabled: bool = True
    website_check_enabled: bool = True
    review_monitoring_enabled: bool = True
    auto_status_update_enabled: bool = True
    closure_detection_days: int = 30
    inactive_threshold_days: int = 90

@dataclass
class StoreStatusCheck:
    """가게 상태 확인 결과"""
    store_id: str
    store_name: str
    current_status: str
    new_status: str
    check_type: str  # 'phone', 'website', 'review_activity', 'manual'
    confidence: float  # 0.0 ~ 1.0
    evidence: List[str]
    checked_at: datetime
    needs_manual_review: bool = False

@dataclass
class PhoneValidationResult:
    """전화번호 검증 결과"""
    phone_number: str
    is_valid: bool
    is_reachable: bool
    status_indicator: str  # 'active', 'disconnected', 'changed', 'unknown'
    error_message: str = ""
    response_time: float = 0.0

@dataclass
class WebsiteCheckResult:
    """웹사이트 접근성 확인 결과"""
    url: str
    is_accessible: bool
    status_code: int
    response_time: float
    content_indicators: List[str]  # 폐업/휴업 관련 키워드
    last_updated: Optional[datetime] = None

class PhoneValidator:
    """전화번호 유효성 검증"""
    
    def __init__(self):
        self.timeout = 10  # 10초 타임아웃
        self.disconnected_indicators = [
            '연결할 수 없는 번호', '사용하지 않는 번호', '결번',
            '서비스가 중단', '번호가 변경', '통화 불가'
        ]
    
    def validate_phone_number(self, phone_number: str, store_name: str = "") -> PhoneValidationResult:
        """전화번호 유효성 확인"""
        start_time = time.time()
        
        # 1. 형식 검증
        format_result = self._validate_phone_format(phone_number)
        if not format_result['is_valid']:
            return PhoneValidationResult(
                phone_number=phone_number,
                is_valid=False,
                is_reachable=False,
                status_indicator='invalid_format',
                error_message=format_result['error'],
                response_time=time.time() - start_time
            )
        
        # 2. 실제 연결 가능성 확인 (시뮬레이션)
        reachability_result = self._check_phone_reachability(phone_number)
        
        response_time = time.time() - start_time
        
        return PhoneValidationResult(
            phone_number=phone_number,
            is_valid=format_result['is_valid'],
            is_reachable=reachability_result['is_reachable'],
            status_indicator=reachability_result['status'],
            error_message=reachability_result.get('error', ''),
            response_time=response_time
        )
    
    def _validate_phone_format(self, phone_number: str) -> Dict:
        """전화번호 형식 검증"""
        try:
            # 한국 전화번호로 파싱
            parsed = phonenumbers.parse(phone_number, "KR")
            
            if phonenumbers.is_valid_number(parsed):
                return {'is_valid': True, 'error': ''}
            else:
                return {'is_valid': False, 'error': '유효하지 않은 전화번호 형식'}
                
        except NumberParseException as e:
            return {'is_valid': False, 'error': f'전화번호 파싱 오류: {e}'}
    
    def _check_phone_reachability(self, phone_number: str) -> Dict:
        """전화번호 연결 가능성 확인 (시뮬레이션)"""
        # 실제로는 통신사 API나 전화 서비스를 사용해야 하지만,
        # 여기서는 패턴 기반 시뮬레이션으로 구현
        
        clean_number = re.sub(r'[^0-9]', '', phone_number)
        
        # 일반적으로 사용되지 않는 번호 패턴 확인
        if self._is_likely_invalid_number(clean_number):
            return {
                'is_reachable': False,
                'status': 'disconnected',
                'error': '사용되지 않는 번호 패턴'
            }
        
        # 실제 환경에서는 여기서 통신사 API 호출
        # 현재는 랜덤하게 시뮬레이션
        import random
        
        # 90% 확률로 연결 가능으로 가정
        if random.random() < 0.9:
            return {
                'is_reachable': True,
                'status': 'active'
            }
        else:
            return {
                'is_reachable': False,
                'status': 'disconnected',
                'error': '연결할 수 없는 번호'
            }
    
    def _is_likely_invalid_number(self, clean_number: str) -> bool:
        """명백히 유효하지 않은 번호 패턴 확인"""
        # 너무 짧거나 긴 번호
        if len(clean_number) < 9 or len(clean_number) > 11:
            return True
        
        # 모든 자릿수가 같은 번호
        if len(set(clean_number)) == 1:
            return True
        
        # 연속된 숫자 패턴
        if '1234567890' in clean_number or '0987654321' in clean_number:
            return True
        
        return False

class WebsiteAccessibilityChecker:
    """웹사이트 접근 가능성 확인"""
    
    def __init__(self):
        self.timeout = 15
        self.closure_keywords = [
            '폐업', '영업종료', '문을 닫았습니다', '운영중단', '임시휴업',
            '휴업', '잠시 문을 닫습니다', '리뉴얼', '이전', '폐점'
        ]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def check_website_accessibility(self, url: str) -> WebsiteCheckResult:
        """웹사이트 접근성 및 내용 확인"""
        start_time = time.time()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response_time = time.time() - start_time
            
            # 상태 코드 확인
            if response.status_code == 404:
                return WebsiteCheckResult(
                    url=url,
                    is_accessible=False,
                    status_code=404,
                    response_time=response_time,
                    content_indicators=['페이지 없음']
                )
            
            # 내용 분석
            content_indicators = self._analyze_content_for_closure(response.text)
            
            return WebsiteCheckResult(
                url=url,
                is_accessible=True,
                status_code=response.status_code,
                response_time=response_time,
                content_indicators=content_indicators
            )
            
        except requests.exceptions.Timeout:
            return WebsiteCheckResult(
                url=url,
                is_accessible=False,
                status_code=0,
                response_time=self.timeout,
                content_indicators=['타임아웃']
            )
        except requests.exceptions.ConnectionError:
            return WebsiteCheckResult(
                url=url,
                is_accessible=False,
                status_code=0,
                response_time=time.time() - start_time,
                content_indicators=['연결 실패']
            )
        except Exception as e:
            return WebsiteCheckResult(
                url=url,
                is_accessible=False,
                status_code=0,
                response_time=time.time() - start_time,
                content_indicators=[f'오류: {str(e)}']
            )
    
    def _analyze_content_for_closure(self, content: str) -> List[str]:
        """페이지 내용에서 폐업/휴업 관련 키워드 찾기"""
        indicators = []
        
        for keyword in self.closure_keywords:
            if keyword in content:
                indicators.append(f'키워드 발견: {keyword}')
        
        # 추가 패턴 확인
        if '준비중' in content and '오픈' not in content:
            indicators.append('준비중 상태')
        
        if '공사중' in content or '리모델링' in content:
            indicators.append('공사/리모델링 중')
        
        return indicators

class ReviewActivityMonitor:
    """리뷰 업데이트 중단 감지"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.inactivity_threshold = timedelta(days=90)  # 90일 비활성
        self.review_sources = ['naver', 'google', 'diningcode']
    
    def check_review_activity(self, store_id: str) -> Dict:
        """리뷰 활동 확인"""
        try:
            # 최근 리뷰 데이터 조회
            query = """
            SELECT 
                MAX(created_at) as last_review_date,
                COUNT(*) as total_reviews,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as recent_reviews
            FROM store_reviews 
            WHERE store_id = %s
            """
            
            result = self.db_manager.execute_query(query, (store_id,))
            
            if not result:
                return {
                    'has_activity': False,
                    'last_activity': None,
                    'activity_score': 0.0,
                    'indicators': ['리뷰 데이터 없음']
                }
            
            row = result[0]
            last_review_date = row[0]
            total_reviews = row[1] or 0
            recent_reviews = row[2] or 0
            
            # 활동성 점수 계산
            activity_score = self._calculate_activity_score(
                last_review_date, total_reviews, recent_reviews
            )
            
            indicators = []
            if last_review_date:
                days_since_last = (datetime.now() - last_review_date).days
                if days_since_last > 90:
                    indicators.append(f'{days_since_last}일간 리뷰 없음')
                elif days_since_last > 30:
                    indicators.append(f'{days_since_last}일간 리뷰 없음')
            
            if recent_reviews == 0:
                indicators.append('최근 30일 리뷰 없음')
            
            return {
                'has_activity': activity_score > 0.3,
                'last_activity': last_review_date,
                'activity_score': activity_score,
                'indicators': indicators,
                'total_reviews': total_reviews,
                'recent_reviews': recent_reviews
            }
            
        except Exception as e:
            logger.error(f"리뷰 활동 확인 실패: {e}")
            return {
                'has_activity': None,
                'last_activity': None,
                'activity_score': 0.0,
                'indicators': [f'확인 실패: {str(e)}']
            }
    
    def _calculate_activity_score(self, last_review_date: Optional[datetime], 
                                total_reviews: int, recent_reviews: int) -> float:
        """활동성 점수 계산 (0.0 ~ 1.0)"""
        score = 0.0
        
        # 최근 리뷰 점수 (50%)
        if recent_reviews > 0:
            score += min(0.5, recent_reviews * 0.1)
        
        # 마지막 리뷰 날짜 점수 (30%)
        if last_review_date:
            days_since = (datetime.now() - last_review_date).days
            if days_since <= 7:
                score += 0.3
            elif days_since <= 30:
                score += 0.2
            elif days_since <= 90:
                score += 0.1
        
        # 총 리뷰 수 점수 (20%)
        if total_reviews > 0:
            score += min(0.2, total_reviews * 0.01)
        
        return min(1.0, score)

class StoreStatusManager:
    """가게 상태 관리 통합 시스템"""
    
    def __init__(self, config: StatusConfig, db_path: str):
        self.config = config
        self.db_path = db_path
        self.db_manager = DatabaseManager()
        self.phone_validator = PhoneValidator()
        self.website_checker = WebsiteAccessibilityChecker()
        self.review_monitor = ReviewActivityMonitor()
        
        self.status_transitions = {
            '운영중': ['휴업', '폐업'],
            '휴업': ['운영중', '폐업'],
            '폐업': []  # 폐업에서는 되돌릴 수 없음
        }
    
    def check_store_status(self, store_id: str) -> StoreStatusCheck:
        """개별 가게 상태 확인"""
        # 가게 정보 조회
        store_info = self._get_store_info(store_id)
        if not store_info:
            raise ValueError(f"가게 정보를 찾을 수 없습니다: {store_id}")
        
        current_status = store_info.get('status', '운영중')
        evidence = []
        confidence_scores = []
        
        # 1. 전화번호 유효성 확인
        phone_number = store_info.get('phone_number')
        if phone_number:
            phone_result = self.phone_validator.validate_phone_number(
                phone_number, store_info.get('name', '')
            )
            
            if not phone_result.is_reachable:
                evidence.append(f'전화번호 연결 불가: {phone_result.status_indicator}')
                confidence_scores.append(0.7)  # 전화 연결 불가는 높은 신뢰도
            else:
                evidence.append('전화번호 연결 가능')
                confidence_scores.append(0.1)  # 연결 가능은 낮은 변경 신뢰도
        
        # 2. 웹사이트 접근성 확인
        website = store_info.get('website')
        if website:
            website_result = self.website_checker.check_website_accessibility(website)
            
            if not website_result.is_accessible:
                evidence.append(f'웹사이트 접근 불가: {website_result.content_indicators}')
                confidence_scores.append(0.5)
            elif website_result.content_indicators:
                evidence.append(f'웹사이트 폐업 징후: {website_result.content_indicators}')
                confidence_scores.append(0.8)
            else:
                evidence.append('웹사이트 정상 접근')
                confidence_scores.append(0.1)
        
        # 3. 리뷰 활동 확인
        review_activity = self.review_monitor.check_review_activity(store_id)
        
        if not review_activity['has_activity']:
            evidence.extend(review_activity['indicators'])
            confidence_scores.append(0.4)  # 리뷰 비활성은 중간 신뢰도
        else:
            evidence.append(f'리뷰 활동 있음 (점수: {review_activity["activity_score"]:.2f})')
            confidence_scores.append(0.1)
        
        # 4. 종합 판단
        overall_confidence = max(confidence_scores) if confidence_scores else 0.0
        new_status = self._determine_new_status(current_status, evidence, overall_confidence)
        
        return StoreStatusCheck(
            store_id=store_id,
            store_name=store_info.get('name', ''),
            current_status=current_status,
            new_status=new_status,
            check_type='comprehensive',
            confidence=overall_confidence,
            evidence=evidence,
            checked_at=datetime.now(),
            needs_manual_review=overall_confidence > 0.6 and new_status != current_status
        )
    
    def _get_store_info(self, store_id: str) -> Optional[Dict]:
        """가게 정보 조회"""
        try:
            query = """
            SELECT diningcode_place_id, name, phone_number, website, status, address
            FROM refill_spots 
            WHERE diningcode_place_id = %s
            """
            
            result = self.db_manager.execute_query(query, (store_id,))
            
            if result:
                row = result[0]
                return {
                    'diningcode_place_id': row[0],
                    'name': row[1],
                    'phone_number': row[2],
                    'website': row[3],
                    'status': row[4],
                    'address': row[5]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"가게 정보 조회 실패: {e}")
            return None
    
    def _determine_new_status(self, current_status: str, evidence: List[str], 
                            confidence: float) -> str:
        """새로운 상태 결정"""
        # 폐업 징후가 강한 경우
        closure_indicators = [
            '전화번호 연결 불가', '웹사이트 접근 불가', '폐업 징후',
            '90일간 리뷰 없음'
        ]
        
        strong_closure_evidence = sum(
            1 for indicator in closure_indicators
            if any(indicator in ev for ev in evidence)
        )
        
        # 휴업 징후
        temporary_closure_indicators = [
            '준비중', '공사', '리모델링', '30일간 리뷰 없음'
        ]
        
        temporary_evidence = sum(
            1 for indicator in temporary_closure_indicators
            if any(indicator in ev for ev in evidence)
        )
        
        # 상태 결정 로직
        if confidence > 0.7 and strong_closure_evidence >= 2:
            return '폐업'
        elif confidence > 0.5 and (strong_closure_evidence >= 1 or temporary_evidence >= 2):
            return '휴업'
        else:
            return current_status
    
    def batch_check_stores(self, store_ids: List[str] = None, 
                          max_workers: int = 5) -> List[StoreStatusCheck]:
        """배치 가게 상태 확인"""
        if store_ids is None:
            store_ids = self._get_all_active_store_ids()
        
        logger.info(f"배치 상태 확인 시작: {len(store_ids)}개 가게")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_store = {
                executor.submit(self.check_store_status, store_id): store_id
                for store_id in store_ids
            }
            
            # 결과 수집
            for future in as_completed(future_to_store):
                store_id = future_to_store[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.new_status != result.current_status:
                        logger.info(f"상태 변경 감지: {result.store_name} "
                                  f"({result.current_status} → {result.new_status})")
                    
                except Exception as e:
                    logger.error(f"가게 상태 확인 실패: {store_id} - {e}")
        
        logger.info(f"배치 상태 확인 완료: {len(results)}개 결과")
        return results
    
    def _get_all_active_store_ids(self) -> List[str]:
        """모든 활성 가게 ID 조회"""
        try:
            query = """
            SELECT diningcode_place_id 
            FROM refill_spots 
            WHERE status IN ('운영중', '휴업')
            ORDER BY updated_at DESC
            """
            
            results = self.db_manager.execute_query(query)
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"활성 가게 ID 조회 실패: {e}")
            return []
    
    def update_store_status(self, check_result: StoreStatusCheck, 
                          auto_update: bool = True) -> bool:
        """가게 상태 업데이트"""
        if check_result.new_status == check_result.current_status:
            return True  # 변경 없음
        
        # 수동 검토 필요한 경우
        if check_result.needs_manual_review and not auto_update:
            logger.info(f"수동 검토 필요: {check_result.store_name} "
                       f"({check_result.current_status} → {check_result.new_status})")
            return False
        
        # 상태 전환 가능성 확인
        if check_result.new_status not in self.status_transitions.get(check_result.current_status, []):
            logger.warning(f"불가능한 상태 전환: {check_result.current_status} → {check_result.new_status}")
            return False
        
        try:
            # 데이터베이스 업데이트
            query = """
            UPDATE refill_spots 
            SET status = %s, 
                status_updated_at = NOW(),
                status_check_evidence = %s,
                updated_at = NOW()
            WHERE diningcode_place_id = %s
            """
            
            evidence_json = json.dumps(check_result.evidence, ensure_ascii=False)
            
            self.db_manager.execute_query(
                query, 
                (check_result.new_status, evidence_json, check_result.store_id)
            )
            
            # 상태 변경 로그 기록
            self._log_status_change(check_result)
            
            logger.info(f"가게 상태 업데이트 완료: {check_result.store_name} "
                       f"({check_result.current_status} → {check_result.new_status})")
            
            return True
            
        except Exception as e:
            logger.error(f"가게 상태 업데이트 실패: {e}")
            return False
    
    def _log_status_change(self, check_result: StoreStatusCheck):
        """상태 변경 로그 기록"""
        try:
            log_query = """
            INSERT INTO store_status_changes 
            (store_id, store_name, old_status, new_status, check_type, 
             confidence, evidence, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            evidence_json = json.dumps(check_result.evidence, ensure_ascii=False)
            
            self.db_manager.execute_query(
                log_query,
                (
                    check_result.store_id,
                    check_result.store_name,
                    check_result.current_status,
                    check_result.new_status,
                    check_result.check_type,
                    check_result.confidence,
                    evidence_json,
                    check_result.checked_at
                )
            )
            
        except Exception as e:
            logger.warning(f"상태 변경 로그 기록 실패: {e}")
    
    def get_status_statistics(self) -> Dict:
        """상태 통계 조회"""
        try:
            query = """
            SELECT 
                status,
                COUNT(*) as count,
                COUNT(CASE WHEN status_updated_at >= NOW() - INTERVAL '30 days' THEN 1 END) as recent_changes
            FROM refill_spots 
            GROUP BY status
            """
            
            results = self.db_manager.execute_query(query)
            
            stats = {}
            total_stores = 0
            
            for row in results:
                status, count, recent_changes = row
                stats[status] = {
                    'count': count,
                    'recent_changes': recent_changes
                }
                total_stores += count
            
            # 비율 계산
            for status_info in stats.values():
                status_info['percentage'] = (status_info['count'] / total_stores * 100) if total_stores > 0 else 0
            
            return {
                'total_stores': total_stores,
                'by_status': stats,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"상태 통계 조회 실패: {e}")
            return {}
    
    def run_periodic_status_check(self, batch_size: int = 100):
        """주기적 상태 확인 실행"""
        logger.info("=== 주기적 가게 상태 확인 시작 ===")
        
        # 모든 활성 가게 조회
        all_store_ids = self._get_all_active_store_ids()
        
        if not all_store_ids:
            logger.info("확인할 가게가 없습니다.")
            return
        
        logger.info(f"총 {len(all_store_ids)}개 가게 상태 확인")
        
        # 배치 단위로 처리
        total_checked = 0
        total_updated = 0
        
        for i in range(0, len(all_store_ids), batch_size):
            batch_ids = all_store_ids[i:i + batch_size]
            
            logger.info(f"배치 {i//batch_size + 1} 처리 중: {len(batch_ids)}개 가게")
            
            # 배치 확인
            check_results = self.batch_check_stores(batch_ids)
            
            # 상태 업데이트
            for result in check_results:
                total_checked += 1
                
                if self.update_store_status(result, auto_update=True):
                    if result.new_status != result.current_status:
                        total_updated += 1
            
            # 배치 간 휴식
            time.sleep(2)
        
        logger.info("=== 주기적 가게 상태 확인 완료 ===")
        logger.info(f"확인: {total_checked}개, 업데이트: {total_updated}개")
        
        # 통계 저장
        self._save_status_check_report(total_checked, total_updated)
    
    def _save_status_check_report(self, total_checked: int, total_updated: int):
        """상태 확인 리포트 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_checked': total_checked,
                'total_updated': total_updated,
                'update_rate': (total_updated / total_checked * 100) if total_checked > 0 else 0
            },
            'statistics': self.get_status_statistics()
        }
        
        with open(f'data/status_check_report_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"상태 확인 리포트 저장: data/status_check_report_{timestamp}.json")

    async def run_comprehensive_status_check(self):
        """포괄적 상태 확인 실행 (비동기)"""
        self.run_periodic_status_check()
        return type('StatusReport', (), {
            'newly_closed': 0,
            'total_checked': 0,
            'updated': 0
        })()

def run_store_status_check():
    """가게 상태 확인 실행 함수"""
    manager = StoreStatusManager()
    manager.run_periodic_status_check()

if __name__ == "__main__":
    run_store_status_check() 