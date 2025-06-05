"""
6단계: 예외 상황 처리 시스템
웹사이트 구조 변경 감지, IP 차단 대응, 자동 복구 시스템
"""

import logging
import time
import random
import json
import requests
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ..core.database import DatabaseManager

logger = logging.getLogger(__name__)

@dataclass
class ExceptionConfig:
    """예외 처리 설정"""
    failure_rate_threshold: float = 0.15
    structure_change_threshold: float = 0.3
    ip_block_detection_enabled: bool = True
    proxy_rotation_enabled: bool = True
    backup_strategy_enabled: bool = True
    max_retries: int = 3
    retry_delay: int = 5

@dataclass
class CrawlingFailure:
    """크롤링 실패 정보"""
    url: str
    error_type: str
    error_message: str
    timestamp: datetime
    retry_count: int = 0
    user_agent: str = ""
    proxy: str = ""

@dataclass
class StructureChange:
    """웹사이트 구조 변경 정보"""
    url: str
    change_type: str  # 'selector_missing', 'new_element', 'layout_change'
    old_selector: str
    detected_at: datetime
    new_selector: str = ""
    confidence: float = 0.0

@dataclass
class ProxyInfo:
    """프록시 정보"""
    host: str
    port: int
    username: str = ""
    password: str = ""
    protocol: str = "http"
    is_active: bool = True
    failure_count: int = 0
    last_used: Optional[datetime] = None
    success_rate: float = 100.0

class WebsiteStructureMonitor:
    """웹사이트 구조 변경 감지"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.failure_threshold = 0.7  # 70% 이상 실패 시 구조 변경 의심
        self.time_window = timedelta(hours=1)  # 1시간 윈도우
        self.known_selectors = {
            'diningcode': {
                'store_list': '.Restaurant_ListItem',
                'store_name': '.Restaurant_Name',
                'store_rating': '.Restaurant_Rating',
                'store_address': '.Restaurant_Address',
                'detail_info': '.Restaurant_DetailInfo',
                'business_hours': '.busi-hours',
                'menu_info': '.menu-info',
                'price_info': '.Restaurant_MenuPrice'
            }
        }
    
    def detect_structure_changes(self, failures: List[CrawlingFailure]) -> List[StructureChange]:
        """크롤링 실패율 급증 시 구조 변경 감지"""
        changes = []
        
        # 시간대별 실패율 분석
        recent_failures = self._filter_recent_failures(failures)
        failure_rate = self._calculate_failure_rate(recent_failures)
        
        logger.info(f"최근 1시간 크롤링 실패율: {failure_rate:.1%}")
        
        if failure_rate > self.failure_threshold:
            logger.warning(f"크롤링 실패율 급증 감지: {failure_rate:.1%}")
            
            # 실패 패턴 분석
            error_patterns = self._analyze_error_patterns(recent_failures)
            
            for pattern, count in error_patterns.items():
                if count > len(recent_failures) * 0.3:  # 30% 이상의 실패가 같은 패턴
                    change = self._identify_structure_change(pattern, recent_failures)
                    if change:
                        changes.append(change)
        
        return changes
    
    def _filter_recent_failures(self, failures: List[CrawlingFailure]) -> List[CrawlingFailure]:
        """최근 시간 윈도우 내 실패만 필터링"""
        cutoff_time = datetime.now() - self.time_window
        return [f for f in failures if f.timestamp >= cutoff_time]
    
    def _calculate_failure_rate(self, failures: List[CrawlingFailure]) -> float:
        """실패율 계산"""
        if not failures:
            return 0.0
        
        # 총 시도 횟수 추정 (실패 + 성공)
        # 실제로는 성공 로그도 필요하지만, 여기서는 실패 기반으로 추정
        total_attempts = len(failures) * 2  # 간단한 추정
        return len(failures) / total_attempts
    
    def _analyze_error_patterns(self, failures: List[CrawlingFailure]) -> Dict[str, int]:
        """에러 패턴 분석"""
        patterns = defaultdict(int)
        
        for failure in failures:
            # 에러 메시지에서 패턴 추출
            error_msg = failure.error_message.lower()
            
            if 'element not found' in error_msg or 'no such element' in error_msg:
                patterns['selector_missing'] += 1
            elif 'timeout' in error_msg:
                patterns['timeout'] += 1
            elif 'blocked' in error_msg or 'forbidden' in error_msg:
                patterns['ip_blocked'] += 1
            elif 'rate limit' in error_msg:
                patterns['rate_limit'] += 1
            else:
                patterns['unknown'] += 1
        
        return dict(patterns)
    
    def _identify_structure_change(self, pattern: str, failures: List[CrawlingFailure]) -> Optional[StructureChange]:
        """구조 변경 식별"""
        if pattern == 'selector_missing':
            # 가장 많이 실패한 셀렉터 찾기
            selector_failures = defaultdict(int)
            
            for failure in failures:
                # URL에서 셀렉터 정보 추출 (로그에 포함되어 있다고 가정)
                if 'selector:' in failure.error_message:
                    selector = failure.error_message.split('selector:')[1].split()[0]
                    selector_failures[selector] += 1
            
            if selector_failures:
                most_failed_selector = max(selector_failures, key=selector_failures.get)
                
                return StructureChange(
                    url=failures[0].url,
                    change_type='selector_missing',
                    old_selector=most_failed_selector,
                    detected_at=datetime.now(),
                    confidence=selector_failures[most_failed_selector] / len(failures)
                )
        
        return None
    
    def auto_detect_new_selectors(self, url: str, old_selector: str) -> Optional[str]:
        """새로운 셀렉터 자동 감지"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 기존 셀렉터와 유사한 새로운 셀렉터 찾기
            new_selector = self._find_similar_selector(soup, old_selector)
            
            if new_selector:
                logger.info(f"새로운 셀렉터 발견: {old_selector} -> {new_selector}")
                return new_selector
            
        except Exception as e:
            logger.warning(f"새로운 셀렉터 자동 감지 실패: {e}")
        
        return None
    
    def _find_similar_selector(self, soup: BeautifulSoup, old_selector: str) -> Optional[str]:
        """유사한 셀렉터 찾기"""
        # 클래스명에서 키워드 추출
        if '.' in old_selector:
            old_class = old_selector.replace('.', '')
            keywords = re.findall(r'[A-Z][a-z]*|[a-z]+', old_class)
            
            # 유사한 클래스명 찾기
            for element in soup.find_all(class_=True):
                for class_name in element.get('class', []):
                    if any(keyword.lower() in class_name.lower() for keyword in keywords):
                        return f'.{class_name}'
        
        return None

class IPBlockDetector:
    """IP 차단 감지 및 대응"""
    
    def __init__(self):
        self.block_indicators = [
            'blocked', 'forbidden', '403', '429', 'rate limit',
            'too many requests', 'access denied', 'captcha'
        ]
        self.consecutive_failures = deque(maxlen=10)
        self.block_threshold = 5  # 연속 5회 실패 시 차단 의심
    
    def is_ip_blocked(self, error_message: str, status_code: int = None) -> bool:
        """IP 차단 여부 확인"""
        error_lower = error_message.lower()
        
        # 에러 메시지 기반 확인
        for indicator in self.block_indicators:
            if indicator in error_lower:
                return True
        
        # HTTP 상태 코드 기반 확인
        if status_code in [403, 429, 503]:
            return True
        
        # 연속 실패 패턴 확인
        self.consecutive_failures.append(datetime.now())
        if len(self.consecutive_failures) >= self.block_threshold:
            time_span = self.consecutive_failures[-1] - self.consecutive_failures[0]
            if time_span < timedelta(minutes=5):  # 5분 내 연속 실패
                return True
        
        return False
    
    def get_block_recovery_strategy(self, block_type: str) -> Dict:
        """차단 유형별 복구 전략"""
        strategies = {
            'rate_limit': {
                'wait_time': 300,  # 5분 대기
                'use_proxy': True,
                'change_user_agent': True,
                'reduce_request_rate': True
            },
            'ip_block': {
                'wait_time': 1800,  # 30분 대기
                'use_proxy': True,
                'change_user_agent': True,
                'use_different_endpoint': True
            },
            'captcha': {
                'wait_time': 3600,  # 1시간 대기
                'use_proxy': True,
                'manual_intervention': True
            }
        }
        
        return strategies.get(block_type, strategies['ip_block'])

class ProxyRotationManager:
    """프록시 로테이션 관리"""
    
    def __init__(self):
        self.proxies: List[ProxyInfo] = []
        self.current_proxy_index = 0
        self.load_proxy_list()
        
    def load_proxy_list(self):
        """프록시 목록 로드"""
        # 환경변수나 설정 파일에서 프록시 목록 로드
        proxy_config = []  # config.get('PROXY_LIST', [])
        
        for proxy_data in proxy_config:
            proxy = ProxyInfo(
                host=proxy_data.get('host'),
                port=proxy_data.get('port'),
                username=proxy_data.get('username', ''),
                password=proxy_data.get('password', ''),
                protocol=proxy_data.get('protocol', 'http')
            )
            self.proxies.append(proxy)
        
        # 기본 프록시가 없으면 무료 프록시 서비스 사용
        if not self.proxies:
            self._load_free_proxies()
    
    def _load_free_proxies(self):
        """무료 프록시 목록 로드 (예시)"""
        # 실제로는 신뢰할 수 있는 프록시 서비스를 사용해야 함
        free_proxies = [
            {'host': '8.8.8.8', 'port': 8080},
            {'host': '1.1.1.1', 'port': 8080},
        ]
        
        for proxy_data in free_proxies:
            proxy = ProxyInfo(
                host=proxy_data['host'],
                port=proxy_data['port']
            )
            self.proxies.append(proxy)
    
    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """다음 사용 가능한 프록시 반환"""
        if not self.proxies:
            return None
        
        # 활성 프록시만 필터링
        active_proxies = [p for p in self.proxies if p.is_active]
        
        if not active_proxies:
            # 모든 프록시가 비활성화된 경우 재활성화
            self._reactivate_proxies()
            active_proxies = [p for p in self.proxies if p.is_active]
        
        if not active_proxies:
            return None
        
        # 성공률 기반 선택
        best_proxy = max(active_proxies, key=lambda p: p.success_rate)
        best_proxy.last_used = datetime.now()
        
        return best_proxy
    
    def _reactivate_proxies(self):
        """비활성화된 프록시 재활성화"""
        for proxy in self.proxies:
            if not proxy.is_active:
                # 일정 시간 후 재활성화
                if proxy.last_used and datetime.now() - proxy.last_used > timedelta(hours=1):
                    proxy.is_active = True
                    proxy.failure_count = 0
                    logger.info(f"프록시 재활성화: {proxy.host}:{proxy.port}")
    
    def report_proxy_failure(self, proxy: ProxyInfo):
        """프록시 실패 보고"""
        proxy.failure_count += 1
        proxy.success_rate = max(0, proxy.success_rate - 10)
        
        if proxy.failure_count >= 3:
            proxy.is_active = False
            logger.warning(f"프록시 비활성화: {proxy.host}:{proxy.port}")
    
    def report_proxy_success(self, proxy: ProxyInfo):
        """프록시 성공 보고"""
        proxy.success_rate = min(100, proxy.success_rate + 5)
        proxy.failure_count = max(0, proxy.failure_count - 1)
    
    def get_proxy_dict(self, proxy: ProxyInfo) -> Dict:
        """requests 라이브러리용 프록시 딕셔너리 생성"""
        if proxy.username and proxy.password:
            proxy_url = f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            proxy_url = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }

class UserAgentRotator:
    """User-Agent 자동 변경"""
    
    def __init__(self):
        self.user_agents = [
            # Chrome
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
            
            # Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            
            # Edge
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        ]
        self.current_index = 0
    
    def get_random_user_agent(self) -> str:
        """랜덤 User-Agent 반환"""
        return random.choice(self.user_agents)
    
    def get_next_user_agent(self) -> str:
        """순차적 User-Agent 반환"""
        user_agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return user_agent

class RequestRateController:
    """요청 간격 동적 조정"""
    
    def __init__(self):
        self.base_delay = 2.0  # 기본 지연 시간 (초)
        self.current_delay = self.base_delay
        self.max_delay = 30.0  # 최대 지연 시간
        self.min_delay = 0.5   # 최소 지연 시간
        self.success_count = 0
        self.failure_count = 0
        
    def adjust_delay(self, success: bool):
        """성공/실패에 따른 지연 시간 조정"""
        if success:
            self.success_count += 1
            self.failure_count = 0
            
            # 연속 성공 시 지연 시간 감소
            if self.success_count >= 5:
                self.current_delay = max(self.min_delay, self.current_delay * 0.9)
                self.success_count = 0
        else:
            self.failure_count += 1
            self.success_count = 0
            
            # 실패 시 지연 시간 증가
            multiplier = 1.5 + (self.failure_count * 0.2)
            self.current_delay = min(self.max_delay, self.current_delay * multiplier)
    
    def get_delay(self) -> float:
        """현재 지연 시간 반환"""
        # 약간의 랜덤성 추가
        jitter = random.uniform(0.8, 1.2)
        return self.current_delay * jitter
    
    def reset(self):
        """지연 시간 초기화"""
        self.current_delay = self.base_delay
        self.success_count = 0
        self.failure_count = 0

class BackupCrawlingStrategy:
    """백업 크롤링 전략"""
    
    def __init__(self):
        self.strategies = {
            'alternative_endpoints': [
                'https://www.diningcode.com/list.php',
                'https://m.diningcode.com/list.php',  # 모바일 버전
            ],
            'alternative_methods': [
                'selenium_headless',
                'requests_session',
                'api_endpoint'
            ]
        }
    
    def execute_backup_strategy(self, original_url: str, error_type: str) -> Optional[Dict]:
        """백업 전략 실행"""
        if error_type == 'structure_change':
            return self._try_alternative_endpoints(original_url)
        elif error_type == 'ip_block':
            return self._try_alternative_methods(original_url)
        else:
            return self._try_all_alternatives(original_url)
    
    def _try_alternative_endpoints(self, original_url: str) -> Optional[Dict]:
        """대체 엔드포인트 시도"""
        for endpoint in self.strategies['alternative_endpoints']:
            try:
                # URL 파라미터 추출 및 대체 엔드포인트에 적용
                parsed_original = urlparse(original_url)
                parsed_alternative = urlparse(endpoint)
                
                alternative_url = f"{parsed_alternative.scheme}://{parsed_alternative.netloc}{parsed_alternative.path}?{parsed_original.query}"
                
                response = requests.get(alternative_url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"대체 엔드포인트 성공: {alternative_url}")
                    return {'url': alternative_url, 'content': response.content}
                    
            except Exception as e:
                logger.warning(f"대체 엔드포인트 실패: {endpoint} - {e}")
        
        return None
    
    def _try_alternative_methods(self, original_url: str) -> Optional[Dict]:
        """대체 크롤링 방법 시도"""
        for method in self.strategies['alternative_methods']:
            try:
                if method == 'selenium_headless':
                    result = self._try_selenium_headless(original_url)
                elif method == 'requests_session':
                    result = self._try_requests_session(original_url)
                elif method == 'api_endpoint':
                    result = self._try_api_endpoint(original_url)
                else:
                    continue
                
                if result:
                    logger.info(f"대체 방법 성공: {method}")
                    return result
                    
            except Exception as e:
                logger.warning(f"대체 방법 실패: {method} - {e}")
        
        return None
    
    def _try_selenium_headless(self, url: str) -> Optional[Dict]:
        """Selenium 헤드리스 모드 시도"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            
            content = driver.page_source
            driver.quit()
            
            return {'url': url, 'content': content.encode()}
            
        except Exception as e:
            logger.warning(f"Selenium 헤드리스 실패: {e}")
            return None
    
    def _try_requests_session(self, url: str) -> Optional[Dict]:
        """requests 세션 시도"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            })
            
            response = session.get(url, timeout=15)
            response.raise_for_status()
            
            return {'url': url, 'content': response.content}
            
        except Exception as e:
            logger.warning(f"requests 세션 실패: {e}")
            return None
    
    def _try_api_endpoint(self, url: str) -> Optional[Dict]:
        """API 엔드포인트 시도"""
        # 실제 API 엔드포인트가 있다면 시도
        # 여기서는 예시로만 구현
        return None
    
    def _try_all_alternatives(self, original_url: str) -> Optional[Dict]:
        """모든 대체 방법 시도"""
        # 엔드포인트 먼저 시도
        result = self._try_alternative_endpoints(original_url)
        if result:
            return result
        
        # 방법론 시도
        return self._try_alternative_methods(original_url)

class ExceptionHandler:
    """예외 상황 처리 통합 시스템"""
    
    def __init__(self, config: ExceptionConfig):
        self.config = config
        self.structure_monitor = WebsiteStructureMonitor()
        self.ip_detector = IPBlockDetector()
        self.proxy_manager = ProxyRotationManager()
        self.user_agent_rotator = UserAgentRotator()
        self.rate_controller = RequestRateController()
        self.backup_strategy = BackupCrawlingStrategy()
        
        self.failure_log: List[CrawlingFailure] = []
        self.db_manager = DatabaseManager()
    
    async def execute_with_exception_handling(self, func, task_name: str) -> bool:
        """예외 처리와 함께 함수 실행"""
        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
            return True
        except Exception as e:
            logger.error(f"작업 실행 실패 ({task_name}): {e}")
            return False
    
    def handle_crawling_exception(self, url: str, error: Exception, 
                                context: Dict = None) -> Dict:
        """크롤링 예외 통합 처리"""
        error_message = str(error)
        error_type = type(error).__name__
        
        # 실패 로그 기록
        failure = CrawlingFailure(
            url=url,
            error_type=error_type,
            error_message=error_message,
            timestamp=datetime.now(),
            user_agent=context.get('user_agent', '') if context else '',
            proxy=context.get('proxy', '') if context else ''
        )
        self.failure_log.append(failure)
        
        logger.warning(f"크롤링 예외 발생: {url} - {error_type}: {error_message}")
        
        # 예외 유형별 처리
        recovery_plan = self._create_recovery_plan(failure)
        
        # 복구 시도
        recovery_result = self._execute_recovery_plan(recovery_plan)
        
        return {
            'success': recovery_result.get('success', False),
            'recovery_plan': recovery_plan,
            'result': recovery_result,
            'failure_info': asdict(failure)
        }
    
    def _create_recovery_plan(self, failure: CrawlingFailure) -> Dict:
        """복구 계획 생성"""
        plan = {
            'actions': [],
            'estimated_delay': 0,
            'use_proxy': False,
            'change_user_agent': False,
            'use_backup_strategy': False
        }
        
        # IP 차단 확인
        if self.ip_detector.is_ip_blocked(failure.error_message):
            logger.warning("IP 차단 감지")
            block_strategy = self.ip_detector.get_block_recovery_strategy('ip_block')
            
            plan['actions'].append('wait_for_unblock')
            plan['actions'].append('use_proxy')
            plan['actions'].append('change_user_agent')
            plan['estimated_delay'] = block_strategy['wait_time']
            plan['use_proxy'] = True
            plan['change_user_agent'] = True
        
        # 구조 변경 확인
        structure_changes = self.structure_monitor.detect_structure_changes(self.failure_log)
        if structure_changes:
            logger.warning(f"웹사이트 구조 변경 감지: {len(structure_changes)}개")
            
            plan['actions'].append('detect_new_selectors')
            plan['actions'].append('use_backup_strategy')
            plan['use_backup_strategy'] = True
        
        # 일반적인 네트워크 오류
        if 'timeout' in failure.error_message.lower():
            plan['actions'].append('increase_delay')
            plan['actions'].append('retry_with_longer_timeout')
            plan['estimated_delay'] = max(plan['estimated_delay'], 10)
        
        # 요청 간격 조정
        self.rate_controller.adjust_delay(success=False)
        plan['estimated_delay'] = max(plan['estimated_delay'], self.rate_controller.get_delay())
        
        return plan
    
    def _execute_recovery_plan(self, plan: Dict) -> Dict:
        """복구 계획 실행"""
        result = {
            'success': False,
            'actions_taken': [],
            'new_config': {}
        }
        
        # 대기 시간
        if plan['estimated_delay'] > 0:
            logger.info(f"복구를 위해 {plan['estimated_delay']:.1f}초 대기")
            time.sleep(plan['estimated_delay'])
            result['actions_taken'].append(f"waited_{plan['estimated_delay']:.1f}s")
        
        # 프록시 변경
        if plan['use_proxy']:
            proxy = self.proxy_manager.get_next_proxy()
            if proxy:
                result['new_config']['proxy'] = self.proxy_manager.get_proxy_dict(proxy)
                result['actions_taken'].append('proxy_changed')
                logger.info(f"프록시 변경: {proxy.host}:{proxy.port}")
        
        # User-Agent 변경
        if plan['change_user_agent']:
            new_ua = self.user_agent_rotator.get_random_user_agent()
            result['new_config']['user_agent'] = new_ua
            result['actions_taken'].append('user_agent_changed')
            logger.info("User-Agent 변경됨")
        
        # 백업 전략 사용
        if plan['use_backup_strategy']:
            # 실제 백업 크롤링은 호출자가 수행
            result['actions_taken'].append('backup_strategy_prepared')
            result['new_config']['use_backup'] = True
        
        # 요청 간격 조정
        new_delay = self.rate_controller.get_delay()
        result['new_config']['request_delay'] = new_delay
        result['actions_taken'].append('delay_adjusted')
        
        result['success'] = True
        return result
    
    def get_failure_statistics(self) -> Dict:
        """실패 통계 조회"""
        if not self.failure_log:
            return {}
        
        recent_failures = self.structure_monitor._filter_recent_failures(self.failure_log)
        
        error_types = defaultdict(int)
        hourly_failures = defaultdict(int)
        
        for failure in recent_failures:
            error_types[failure.error_type] += 1
            hour = failure.timestamp.strftime('%Y-%m-%d %H:00')
            hourly_failures[hour] += 1
        
        return {
            'total_failures': len(self.failure_log),
            'recent_failures': len(recent_failures),
            'failure_rate': self.structure_monitor._calculate_failure_rate(recent_failures),
            'error_types': dict(error_types),
            'hourly_failures': dict(hourly_failures),
            'active_proxies': len([p for p in self.proxy_manager.proxies if p.is_active]),
            'current_delay': self.rate_controller.current_delay
        }
    
    def save_failure_log(self):
        """실패 로그 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'failures': [asdict(f) for f in self.failure_log],
            'statistics': self.get_failure_statistics()
        }
        
        with open(f'data/failure_log_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"실패 로그 저장: data/failure_log_{timestamp}.json")

def create_resilient_crawler_session() -> requests.Session:
    """복원력 있는 크롤러 세션 생성"""
    session = requests.Session()
    
    # 기본 헤더 설정
    user_agent_rotator = UserAgentRotator()
    session.headers.update({
        'User-Agent': user_agent_rotator.get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    # 재시도 설정
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

if __name__ == "__main__":
    # 테스트 코드
    handler = ExceptionHandler()
    
    # 모의 예외 처리
    try:
        raise requests.exceptions.Timeout("Connection timeout")
    except Exception as e:
        result = handler.handle_crawling_exception(
            "https://www.diningcode.com/list.php",
            e,
            {'user_agent': 'test', 'proxy': 'none'}
        )
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False)) 