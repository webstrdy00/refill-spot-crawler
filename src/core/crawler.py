import logging
import time
import random
import re
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options

# config import 수정
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from config.config import USER_AGENTS, MIN_DELAY, MAX_DELAY, IMAGE_STORAGE_CONFIG
except ImportError:
    # 기본값 설정
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    MIN_DELAY = 1
    MAX_DELAY = 3
    IMAGE_STORAGE_CONFIG = {}

# 이미지 매니저 import
try:
    from src.core.image_manager import ImageManager
except ImportError:
    try:
        from .image_manager import ImageManager
    except ImportError:
        ImageManager = None


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# data 폴더 생성 (없으면)
os.makedirs('data', exist_ok=True)

class DiningCodeCrawler:
    def __init__(self, enable_image_download: bool = True):
        """
        다이닝코드 크롤러 초기화
        
        Args:
            enable_image_download: 이미지 다운로드 및 Storage 업로드 활성화 여부
        """
        self.driver = None
        self.current_url = ""
        self.session_start_time = time.time()
        
        # 이미지 매니저 초기화 (이미지 다운로드 및 Storage 업로드)
        self.enable_image_download = enable_image_download
        self.image_manager = None
        
        if enable_image_download and ImageManager:
            try:
                # config에서 이미지 스토리지 설정 가져오기
                self.image_manager = ImageManager(config=IMAGE_STORAGE_CONFIG)
                logger.info("이미지 매니저 초기화 완료 (스토리지 활성화)")
            except Exception as e:
                logger.warning(f"이미지 매니저 초기화 실패: {e}")
                self.enable_image_download = False
        elif enable_image_download:
            logger.warning("ImageManager 클래스를 찾을 수 없음. 이미지 다운로드가 비활성화됩니다.")
            self.enable_image_download = False
        
        # 성능 통계
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'images_processed': 0,
            'images_uploaded': 0
        }
        
        self.setup_driver()
        
    def setup_driver(self):
        """Selenium WebDriver 설정"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # 이미지 로딩 비활성화로 속도 향상
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 페이지 로드 전략 설정
        chrome_options.add_argument('--page-load-strategy=normal')
        
        # User-Agent 랜덤 설정
        user_agent = random.choice(USER_AGENTS)
        chrome_options.add_argument(f'--user-agent={user_agent}')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # 타임아웃 설정 최적화
            self.driver.set_page_load_timeout(20)  # 30초에서 20초로 단축
            self.driver.implicitly_wait(5)  # 10초에서 5초로 단축
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)  # 20초에서 10초로 단축
            logger.info("WebDriver 초기화 완료")
        except Exception as e:
            logger.error(f"WebDriver 초기화 실패: {e}")
            raise
    
    def random_delay(self, min_delay=None, max_delay=None):
        """랜덤 지연 (재시도 로직에서 사용할 수 있도록 파라미터 추가)"""
        min_d = min_delay or MIN_DELAY
        max_d = max_delay or MAX_DELAY
        delay = random.uniform(min_d, max_d)
        time.sleep(delay)
        
    def retry_on_failure(self, func, max_retries=3, delay_multiplier=1.5):
        """실패 시 재시도 로직"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"최대 재시도 횟수 초과: {e}")
                    raise
                else:
                    wait_time = (attempt + 1) * delay_multiplier
                    logger.warning(f"시도 {attempt + 1} 실패: {e}. {wait_time}초 후 재시도...")
                    time.sleep(wait_time)

    def get_store_list(self, keyword: str, rect: str) -> List[Dict]:
        """다이닝코드에서 가게 목록 수집 (두 번 시도 방식)"""
        stores = []
        
        try:
            logger.info(f"목록 페이지 크롤링 시작: {keyword}, {rect}")
            
            # 첫 번째 시도
            stores = self._search_stores(keyword, rect, attempt=1)
            
            # 첫 번째 시도에서 결과가 없으면 두 번째 시도
            if not stores:
                logger.info("첫 번째 검색에서 결과가 없음. 두 번째 시도 진행...")
                time.sleep(2)  # 3초에서 2초로 단축
                stores = self._search_stores(keyword, rect, attempt=2)
            
            if stores:
                logger.info(f"총 {len(stores)}개 가게 정보 수집 완료")
            else:
                logger.warning("두 번의 시도 모두에서 검색 결과를 찾을 수 없음")
            
        except Exception as e:
            logger.error(f"목록 크롤링 중 오류: {e}")
            try:
                logger.error(f"현재 URL: {self.driver.current_url}")
                logger.error(f"페이지 제목: {self.driver.title}")
            except:
                pass
            
        return stores
    
    def _search_stores(self, keyword: str, rect: str, attempt: int) -> List[Dict]:
        """실제 검색 수행 (단일 시도)"""
        stores = []
        
        try:
            logger.info(f"=== {attempt}번째 검색 시도 ===")
            
            # 1. 메인 페이지 먼저 접속 (안정성을 위해)
            logger.info("다이닝코드 메인 페이지 접속 중...")
            self.driver.get("https://www.diningcode.com")
            self.random_delay()
            
            # 2. 검색 페이지로 직접 이동
            if rect and rect != "":
                search_url = f"https://www.diningcode.com/list.dc?query={keyword}&rect={rect}"
                logger.info(f"지역 제한 검색 URL 접속: {search_url}")
            else:
                search_url = f"https://www.diningcode.com/list.dc?query={keyword}"
                logger.info(f"전국 검색 URL 접속: {search_url}")
            
            # 첫 번째 검색 시도
            stores = self._try_search_url(search_url, keyword, rect, "첫 번째")
            
            # 첫 번째 시도에서 결과가 없고 지역 제한 검색인 경우, 같은 검색을 한 번 더 시도
            if not stores and rect and rect != "":
                logger.info("첫 번째 지역 검색에서 결과가 없음. 잠시 대기 후 같은 검색 재시도...")
                time.sleep(3)  # 5초에서 3초로 단축
                stores = self._try_search_url(search_url, keyword, rect, "재시도")
                
                # 재시도에서도 결과가 없으면 전국 검색으로 시도
                if not stores:
                    logger.info("지역 제한 검색 재시도에서도 결과가 없음. 전국 검색으로 시도...")
                    fallback_url = f"https://www.diningcode.com/list.dc?query={keyword}"
                    stores = self._try_search_url(fallback_url, keyword, "", "전국 검색")
            
        except Exception as e:
            logger.error(f"{attempt}번째 검색 시도 중 오류: {e}")
            
        return stores
    
    def _try_search_url(self, search_url: str, keyword: str, rect: str, search_type: str) -> List[Dict]:
        """특정 URL로 검색 시도"""
        stores = []
        
        try:
            logger.info(f"=== {search_type} 검색 시도 ===")
            logger.info(f"URL: {search_url}")
            
            self.driver.get(search_url)
            self.random_delay()
            
            # 3. 페이지 로딩 대기 - React 앱이 로드될 때까지
            logger.info("React 앱 로딩 대기 중...")
            try:
                # PoiBlock 클래스를 가진 요소들이 나타날 때까지 대기 (시간 단축)
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "PoiBlock")))
                logger.info("가게 목록 로딩 완료")
            except TimeoutException:
                logger.warning("PoiBlock 요소를 찾을 수 없음. 추가 대기...")
                # 추가 대기 시간 단축
                time.sleep(3)  # 15초에서 3초로 단축
                
                # 다시 한 번 시도
                try:
                    poi_elements = self.driver.find_elements(By.CLASS_NAME, "PoiBlock")
                    if poi_elements:
                        logger.info(f"추가 대기 후 {len(poi_elements)}개 PoiBlock 발견")
                    else:
                        logger.warning(f"{search_type}에서 PoiBlock을 찾을 수 없음")
                        return stores
                except:
                    logger.warning(f"{search_type}에서 PoiBlock 검색 실패")
                    return stores
            
            # 4. 현재 페이지 정보 확인
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"현재 페이지 URL: {current_url}")
            logger.info(f"페이지 제목: {page_title}")
            
            # 5. JavaScript에서 데이터 추출 시도
            try:
                # 더보기 버튼 클릭으로 추가 결과 로드
                self._load_more_results()
                
                # 방법 1: localStorage에서 listData 추출
                list_data = self.driver.execute_script("return localStorage.getItem('listData');")
                if list_data:
                    import json
                    data = json.loads(list_data)
                    poi_list = data.get('poi_section', {}).get('list', [])
                    
                    logger.info(f"localStorage에서 {len(poi_list)}개 가게 데이터 추출")
                    
                    for poi in poi_list:
                        store_info = {
                            'diningcode_place_id': poi.get('v_rid', ''),
                            'detail_url': f"/profile.php?rid={poi.get('v_rid', '')}",
                            'name': poi.get('nm', ''),
                            'branch': poi.get('branch', ''),
                            'basic_address': poi.get('addr', ''),
                            'road_address': poi.get('road_addr', ''),
                            'phone_number': poi.get('phone', ''),
                            'distance': poi.get('distance', ''),
                            'category': poi.get('category', ''),
                            'keyword': keyword,
                            'rect_area': rect,
                            'position_lat': poi.get('lat'),
                            'position_lng': poi.get('lng'),
                            'diningcode_score': poi.get('score'),
                            'diningcode_rating': poi.get('user_score'),
                            'review_count': poi.get('review_cnt', 0),
                            'image_urls': poi.get('image_list', []),
                            'open_status': poi.get('open_status', ''),
                            'raw_categories_diningcode': poi.get('keyword', [])
                        }
                        
                        if store_info['diningcode_place_id'] and store_info['name']:
                            stores.append(store_info)
                            logger.info(f"가게 추가: {store_info['name']} {store_info['branch']} (ID: {store_info['diningcode_place_id']})")
                    
                    if stores:
                        logger.info(f"localStorage에서 총 {len(stores)}개 가게 정보 수집 완료")
                        return stores
                else:
                    logger.info("localStorage에 listData가 없음. 다른 방법 시도...")
                
                # 방법 2: 전역 JavaScript 변수에서 데이터 추출
                js_check_script = """
                    // window 객체에서 데이터 찾기
                    var data = null;
                    if (window.__INITIAL_STATE__) {
                        data = window.__INITIAL_STATE__;
                    } else if (window.__APP_DATA__) {
                        data = window.__APP_DATA__;
                    } else if (window.appData) {
                        data = window.appData;
                    }
                    return data;
                """
                
                js_data = self.driver.execute_script(js_check_script)
                if js_data:
                    logger.info("전역 JavaScript 변수에서 데이터 발견")
                    # 데이터 구조 분석 후 추출
                
                # 방법 3: 페이지 내 script 태그에서 JSON 데이터 추출
                scripts = self.driver.find_all('script')
                for script in scripts:
                    script_text = script.get_attribute('innerHTML')
                    if script_text and ('poi_list' in script_text or 'store_list' in script_text):
                        logger.info("script 태그에서 가게 데이터 발견")
                        # JSON 데이터 파싱 시도
                        
            except Exception as e:
                logger.warning(f"JavaScript 데이터 추출 실패: {e}")
            
            # 6. HTML 파싱으로 가게 정보 추출 (백업 방법)
            logger.info("HTML 파싱으로 가게 정보 추출 시도...")
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # PoiBlock 클래스를 가진 링크들 찾기
            poi_blocks = soup.find_all('a', class_='PoiBlock')
            logger.info(f"HTML에서 {len(poi_blocks)}개 PoiBlock 발견")
            
            for block in poi_blocks:
                try:
                    store_info = {
                        'diningcode_place_id': '',
                        'detail_url': '',
                        'name': '',
                        'branch': '',
                        'basic_address': '',
                        'keyword': keyword,
                        'rect_area': rect,
                        'position_lat': None,
                        'position_lng': None
                    }
                    
                    # URL에서 rid 추출
                    href = block.get('href', '')
                    if 'rid=' in href:
                        rid = href.split('rid=')[1].split('&')[0]
                        store_info['diningcode_place_id'] = rid
                        store_info['detail_url'] = href
                    
                    # 가게 이름 추출
                    title_elem = block.find('h2')
                    if title_elem:
                        # 번호 제거 (예: "1. 육미제당" -> "육미제당", "14.강남 돼지상회" -> "강남 돼지상회")
                        name_text = title_elem.get_text(strip=True)
                        
                        # 다양한 번호 패턴 제거
                        # 패턴 1: "1. 가게명", "14. 가게명"
                        if re.match(r'^\d+\.\s*', name_text):
                            name_text = re.sub(r'^\d+\.\s*', '', name_text)
                        
                        # 패턴 2: "1.가게명", "14.가게명" (공백 없음)
                        elif re.match(r'^\d+\.', name_text):
                            name_text = re.sub(r'^\d+\.', '', name_text)
                        
                        # 패턴 3: "1 가게명", "14 가게명" (점 없음)
                        elif re.match(r'^\d+\s+', name_text):
                            name_text = re.sub(r'^\d+\s+', '', name_text)
                        
                        # 지점명 분리 (하지만 가게명은 원본 그대로 저장)
                        place_elem = title_elem.find('span', class_='Info__Title__Place')
                        if place_elem:
                            store_info['branch'] = place_elem.get_text(strip=True)
                            # 가게명은 원본 그대로 저장 (지점명 포함)
                            store_info['name'] = name_text.strip()
                        else:
                            store_info['name'] = name_text.strip()
                            store_info['branch'] = ''
                    
                    # data 속성에서 위치정보 추출 시도
                    data_lat = block.get('data-lat') or block.get('data-latitude')
                    data_lng = block.get('data-lng') or block.get('data-longitude')
                    
                    if data_lat and data_lng:
                        try:
                            store_info['position_lat'] = float(data_lat)
                            store_info['position_lng'] = float(data_lng)
                            logger.info(f"HTML data 속성에서 좌표 추출: {store_info['name']} ({data_lat}, {data_lng})")
                        except:
                            pass
                    
                    # 평점 정보 추출
                    score_elem = block.find('p', class_='Score')
                    if score_elem:
                        score_span = score_elem.find('span')
                        if score_span:
                            try:
                                store_info['diningcode_score'] = int(score_span.get_text(strip=True))
                            except:
                                pass
                    
                    # 사용자 평점 추출
                    user_score_elem = block.find('span', class_='score-text')
                    if user_score_elem:
                        try:
                            store_info['diningcode_rating'] = float(user_score_elem.get_text(strip=True))
                        except:
                            pass
                    
                    # 카테고리 정보 추출
                    categories = []
                    category_elems = block.find_all('span', class_='Category')
                    for cat_elem in category_elems:
                        cat_text = cat_elem.get_text(strip=True)
                        if cat_text:
                            categories.append(cat_text)
                    store_info['raw_categories_diningcode'] = categories
                    
                    # 유효한 정보가 있는 경우만 추가
                    if store_info['diningcode_place_id'] and store_info['name']:
                        stores.append(store_info)
                        logger.info(f"가게 추가: {store_info['name']} {store_info['branch']} (ID: {store_info['diningcode_place_id']})")
                        
                except Exception as e:
                    logger.warning(f"가게 정보 추출 중 오류: {e}")
                    continue
            
            logger.info(f"{search_type}에서 총 {len(stores)}개 가게 정보 수집 완료")
            
        except Exception as e:
            logger.error(f"{search_type} 검색 중 오류: {e}")
            
        return stores
    
    def _load_more_results(self):
        """더보기 버튼을 클릭하여 추가 결과 로드"""
        try:
            max_attempts = 3  # 최대 3번까지 더보기 클릭
            
            for attempt in range(max_attempts):
                try:
                    # 더보기 버튼 찾기 (여러 가능한 셀렉터 시도)
                    more_button_selectors = [
                        "button[class*='more']",
                        "button[class*='More']", 
                        "a[class*='more']",
                        "div[class*='more']",
                        ".btn-more",
                        ".more-btn",
                        "[data-testid*='more']"
                    ]
                    
                    more_button = None
                    for selector in more_button_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                if element.is_displayed() and element.is_enabled():
                                    text = element.text.lower()
                                    if any(keyword in text for keyword in ['더보기', 'more', '더 보기', '추가']):
                                        more_button = element
                                        break
                            if more_button:
                                break
                        except:
                            continue
                    
                    if more_button:
                        logger.info(f"더보기 버튼 발견 (시도 {attempt + 1}): {more_button.text}")
                        
                        # 버튼이 보이도록 스크롤
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", more_button)
                        time.sleep(1)
                        
                        # 클릭
                        more_button.click()
                        logger.info("더보기 버튼 클릭 완료")
                        
                        # 로딩 대기
                        time.sleep(2)
                        
                        # 새로운 결과가 로드되었는지 확인
                        new_poi_count = len(self.driver.find_elements(By.CLASS_NAME, "PoiBlock"))
                        logger.info(f"더보기 후 총 {new_poi_count}개 가게 발견")
                        
                    else:
                        logger.info(f"더보기 버튼을 찾을 수 없음 (시도 {attempt + 1})")
                        break
                        
                except Exception as e:
                    logger.warning(f"더보기 버튼 클릭 실패 (시도 {attempt + 1}): {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"더보기 결과 로드 실패: {e}")

    def get_store_detail(self, store_info: Dict) -> Dict:
        """가게 상세 정보 수집 (강화된 파싱)"""
        def _get_detail():
            return self._extract_store_detail(store_info)
        
        return self.retry_on_failure(_get_detail, max_retries=3)

    def _extract_store_detail(self, store_info: Dict) -> Dict:
        """실제 상세 정보 추출 로직 (강화된 에러 핸들링)"""
        detail_info = store_info.copy()
        extraction_errors = []
        
        try:
            place_id = store_info.get('diningcode_place_id', '')
            if not place_id:
                logger.warning("place_id가 없어 상세 정보를 가져올 수 없습니다.")
                return detail_info
            
            # 상세 페이지 URL 생성
            detail_url = f"https://www.diningcode.com/profile.php?rid={place_id}"
            logger.info(f"상세 페이지 접속: {detail_url}")
            
            self.driver.get(detail_url)
            self.random_delay()
            
            # 페이지 로딩 대기 (더 유연한 조건)
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.find_elements(By.TAG_NAME, "body") and 
                    len(driver.page_source) > 1000 and
                    "diningcode" in driver.current_url.lower()
                )
                time.sleep(2)
            except TimeoutException:
                logger.warning("상세 페이지 로딩 타임아웃")
                time.sleep(3)
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 1. 메뉴 정보 추출 (에러 핸들링 강화)
            try:
                menu_info = self._extract_menu_info(soup)
                detail_info.update(menu_info)
                logger.debug("메뉴 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"메뉴 정보 추출 실패: {e}")
                logger.warning(f"메뉴 정보 추출 실패: {e}")
            
            # 2. 가격 정보 추출 (에러 핸들링 강화)
            try:
                price_info = self._extract_price_info(soup)
                detail_info.update(price_info)
                
                # 구조화된 메뉴 정보가 있으면 menu_items에 추가
                if 'structured_menu_items' in price_info and price_info['structured_menu_items']:
                    if 'menu_items' not in detail_info:
                        detail_info['menu_items'] = []
                    
                    # 기존 menu_items와 병합 (중복 제거)
                    existing_names = {item.get('name') for item in detail_info['menu_items'] if isinstance(item, dict)}
                    
                    for structured_item in price_info['structured_menu_items']:
                        if structured_item['name'] not in existing_names:
                            detail_info['menu_items'].append(structured_item)
                
                logger.debug("가격 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"가격 정보 추출 실패: {e}")
                logger.warning(f"가격 정보 추출 실패: {e}")
            
            # 3. 영업시간 정보 추출 (에러 핸들링 강화)
            try:
                hours_info = self._extract_hours_info(soup)
                detail_info.update(hours_info)
                logger.debug("영업시간 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"영업시간 정보 추출 실패: {e}")
                logger.warning(f"영업시간 정보 추출 실패: {e}")
            
            # 4. 이미지 정보 수집 및 다운로드 (에러 핸들링 강화)
            try:
                image_info = self._extract_image_info(soup)
                detail_info.update(image_info)
                
                # 이미지 다운로드 옵션이 활성화된 경우
                if self.enable_image_download and self.image_manager:
                    logger.info(f"이미지 다운로드 시작: {detail_info.get('name', 'Unknown')}")
                    download_result = self.image_manager.download_store_images(detail_info)
                    
                    # 다운로드된 로컬 경로로 업데이트 (대표 이미지만)
                    if download_result.get('main_image'):
                        detail_info['main_image_local'] = download_result['main_image']
                        logger.info(f"대표 이미지 로컬 저장: {os.path.basename(download_result['main_image'])}")
                        
                        # Supabase Storage에 업로드
                        try:
                            storage_url = self.image_manager.upload_to_supabase(
                                download_result['main_image'],
                                detail_info.get('name', 'unknown')
                            )
                            if storage_url:
                                detail_info['main_image_storage_url'] = storage_url
                                logger.info(f"✅ Supabase Storage 업로드 성공: {storage_url}")
                            else:
                                logger.warning("❌ Supabase Storage 업로드 실패")
                        except Exception as upload_error:
                            logger.error(f"Supabase 업로드 중 오류: {upload_error}")
                    
                    # 다운로드 통계
                    stats = download_result.get('download_stats', {})
                    if stats.get('successful', 0) > 0:
                        logger.info(f"이미지 다운로드 성공: {stats['successful']}/{stats['total_attempted']}")
                    else:
                        logger.warning(f"이미지 다운로드 실패")
                
                logger.debug("이미지 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"이미지 정보 추출 실패: {e}")
                logger.warning(f"이미지 정보 추출 실패: {e}")
            
            # 5. 리뷰 및 설명 정보 추출 (에러 핸들링 강화)
            try:
                review_info = self._extract_review_info(soup)
                detail_info.update(review_info)
                logger.debug("리뷰 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"리뷰 정보 추출 실패: {e}")
                logger.warning(f"리뷰 정보 추출 실패: {e}")
            
            # 6. 연락처 정보 추출 (에러 핸들링 강화)
            try:
                contact_info = self._extract_contact_info(soup)
                detail_info.update(contact_info)
                logger.debug("연락처 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"연락처 정보 추출 실패: {e}")
                logger.warning(f"연락처 정보 추출 실패: {e}")
            
            # 7. 좌표 및 주소 정보 추출 (에러 핸들링 강화)
            try:
                coordinate_info = self._extract_coordinate_info(soup)
                detail_info.update(coordinate_info)
                logger.debug("좌표 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"좌표 정보 추출 실패: {e}")
                logger.warning(f"좌표 정보 추출 실패: {e}")
            
            # 8. 주소 정보 추가 추출 (에러 핸들링 강화)
            try:
                address_info = self._extract_address_info(soup)
                # 주소가 없거나 coordinate_info의 주소가 더 상세한 경우 업데이트
                if address_info.get('address') and (not detail_info.get('address') or len(address_info['address']) > len(detail_info.get('address', ''))):
                    detail_info['address'] = address_info['address']
                if address_info.get('basic_address'):
                    detail_info['basic_address'] = address_info['basic_address']
                if address_info.get('road_address'):
                    detail_info['road_address'] = address_info['road_address']
                logger.debug("주소 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"주소 정보 추출 실패: {e}")
                logger.warning(f"주소 정보 추출 실패: {e}")
            
            # 9. 무한리필 관련 정보 추출 (에러 핸들링 강화)
            try:
                refill_info = self._extract_refill_info(soup)
                detail_info.update(refill_info)
                logger.debug("무한리필 정보 추출 성공")
            except Exception as e:
                extraction_errors.append(f"무한리필 정보 추출 실패: {e}")
                logger.warning(f"무한리필 정보 추출 실패: {e}")
            
            # 추출 오류 요약
            if extraction_errors:
                detail_info['extraction_errors'] = extraction_errors
                logger.warning(f"부분적 추출 오류 ({len(extraction_errors)}개): {'; '.join(extraction_errors[:3])}")
            
            # 데이터 품질 검증
            quality_score = self._calculate_data_quality(detail_info)
            detail_info['data_quality_score'] = quality_score
            
            logger.info(f"상세 정보 수집 완료: {detail_info.get('name', 'Unknown')} - 주소: {detail_info.get('address', 'N/A')[:50]}... (품질점수: {quality_score}%)")
            
        except Exception as e:
            logger.error(f"상세 정보 수집 중 치명적 오류: {e}")
            detail_info['fatal_error'] = str(e)
            # 기본 정보라도 반환
            
        return detail_info
    
    def _calculate_data_quality(self, store_info: Dict) -> int:
        """데이터 품질 점수 계산 (0-100점)"""
        try:
            score = 0
            max_score = 100
            
            # 필수 정보 (40점)
            if store_info.get('name'):
                score += 10
            if store_info.get('address'):
                score += 15
            if store_info.get('position_lat') and store_info.get('position_lng'):
                score += 15
            
            # 연락처 정보 (20점)
            if store_info.get('phone_number'):
                score += 20
            
            # 영업 정보 (20점)
            if store_info.get('open_hours'):
                score += 10
            if store_info.get('last_order') or store_info.get('break_time'):
                score += 5
            if store_info.get('holiday'):
                score += 5
            
            # 추가 정보 (20점)
            if store_info.get('price_range') or store_info.get('average_price'):
                score += 5
            if store_info.get('image_urls') and len(store_info.get('image_urls', [])) > 0:
                score += 5
            if store_info.get('refill_items') and len(store_info.get('refill_items', [])) > 0:
                score += 5
            if store_info.get('keywords') and len(store_info.get('keywords', [])) > 0:
                score += 5
            
            return min(score, max_score)
            
        except Exception as e:
            logger.debug(f"품질 점수 계산 실패: {e}")
            return 0

    def _extract_menu_info(self, soup: BeautifulSoup) -> Dict:
        """메뉴 정보 추출 (mcp-browserbase 기반 개선)"""
        menu_info = {
            'menu_items': [],
            'menu_categories': [],
            'signature_menu': [],
            'refill_menu_items': []  # 무한리필 메뉴 전용
        }
        
        try:
            logger.info("🍽️ 메뉴 정보 추출 시작...")
            
            # 1. 먼저 브라우저 기반 정확한 메뉴 추출 시도
            browser_menu_items = self._extract_menu_with_browser_verification(soup)
            if browser_menu_items:
                menu_info['refill_menu_items'] = browser_menu_items
                logger.info(f"브라우저 기반 메뉴 추출 성공: {len(browser_menu_items)}개")
            
            # 2. 기존 로직으로 폴백
            if not browser_menu_items:
                # 무한리필 메뉴 정보 추출 (운영 정보 섹션에서)
                refill_menu_items = self._extract_refill_menu_from_operation_info(soup)
                menu_info['refill_menu_items'] = refill_menu_items
                
                # 일반 메뉴 섹션에서 메뉴 추출
                general_menu_items = self._extract_general_menu_items(soup)
                menu_info['menu_items'] = general_menu_items
            else:
                # 브라우저 기반 메뉴를 무한리필 메뉴로 설정
                menu_info['refill_menu_items'] = browser_menu_items
                menu_info['menu_items'] = []
                
                # 구조화된 메뉴 정보를 menu_items 필드에 저장
                if browser_menu_items:
                    # 기존 menu_items가 없으면 초기화
                    if 'menu_items' not in detail_info:
                        detail_info['menu_items'] = []
                    
                    # 브라우저 기반 메뉴를 menu_items에 추가
                    for menu_item in browser_menu_items:
                        structured_item = {
                            'name': menu_item['name'],
                            'price': menu_item['price'],
                            'price_numeric': menu_item.get('price_numeric', 0),
                            'is_recommended': menu_item.get('is_recommended', False),
                            'type': 'browser_verified',
                            'order': menu_item.get('order', 0)
                        }
                        detail_info['menu_items'].append(structured_item)
            
            # 3. 대표 메뉴 추출
            signature_menu = self._extract_signature_menu(soup)
            menu_info['signature_menu'] = signature_menu
            
            # 4. 무한리필 관련 키워드 검색
            keywords = self._extract_menu_keywords(soup)
            menu_info['keywords'] = keywords
            
            total_menu_count = len(menu_info['menu_items']) + len(menu_info['refill_menu_items'])
            logger.info(f"메뉴 정보 추출 완료: 총 {total_menu_count}개 메뉴")
            
        except Exception as e:
            logger.error(f"메뉴 정보 추출 실패: {e}")
        
        return menu_info
    
    def _clean_menu_name(self, menu_name):
        """메뉴명에서 불필요한 텍스트 제거"""
        if not menu_name:
            return ""
        
        # 광고, 헤더 텍스트 제거
        unwanted_keywords = [
            'Advertisement', 'advertisement', '메뉴정보', '운영정보',
            '영업시간', '전화번호', '주소', '평점', '리뷰', '사진'
        ]
        
        # 줄바꿈 제거 및 정리
        cleaned = menu_name.replace('\n', ' ').strip()
        
        # 불필요한 키워드가 포함된 경우 제거 시도
        for keyword in unwanted_keywords:
            if keyword in cleaned:
                # 키워드 이후 부분만 추출
                parts = cleaned.split(keyword)
                if len(parts) > 1:
                    cleaned = parts[-1].strip()
        
        # 연속된 공백 제거
        import re
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()

    def _extract_menu_with_browser_verification(self, soup: BeautifulSoup) -> List[Dict]:
        """브라우저에서 확인한 구조를 바탕으로 정확한 메뉴 정보 추출"""
        menu_items = []
        
        try:
            logger.info("🔍 브라우저 기반 메뉴 정보 추출 시작...")
            
            # 다이닝코드 메뉴 정보 구조:
            # 1. "메뉴정보" 텍스트를 가진 paragraph
            # 2. 그 다음에 오는 ul 리스트
            # 3. 각 li 안에 두 개의 p 태그 (메뉴명, 가격)
            
            # Step 1: 메뉴정보 헤더 찾기
            menu_header_elem = soup.find('p', string=lambda text: text and '메뉴정보' in text.strip())
            
            if not menu_header_elem:
                # 다른 방법으로 메뉴정보 헤더 찾기
                menu_header_elem = soup.find(text=lambda text: text and '메뉴정보' in text.strip())
                if menu_header_elem:
                    menu_header_elem = menu_header_elem.parent
            
            if menu_header_elem:
                logger.info("✅ 메뉴정보 헤더 발견")
                
                # Step 2: 메뉴정보 헤더 다음에 오는 ul 리스트 찾기
                menu_list = menu_header_elem.find_next_sibling('ul')
                
                if menu_list:
                    logger.info("✅ 메뉴 리스트 발견")
                    
                    # Step 3: 각 li 아이템에서 메뉴 정보 추출
                    list_items = menu_list.find_all('li', recursive=False)  # 직접 자식만
                    
                    for i, item in enumerate(list_items):
                        try:
                            # 각 li 안의 p 태그들 찾기
                            paragraphs = item.find_all('p')
                            
                            if len(paragraphs) >= 2:
                                # 첫 번째 p: 메뉴명
                                menu_name_elem = paragraphs[0]
                                menu_name = menu_name_elem.get_text(strip=True)
                                # 광고 텍스트나 불필요한 텍스트 제거
                                menu_name = self._clean_menu_name(menu_name)
                                
                                # 두 번째 p: 가격
                                price_elem = paragraphs[1]
                                price_text = price_elem.get_text(strip=True)
                                
                                # 유효성 검사
                                if (menu_name and price_text and 
                                    len(menu_name) > 0 and len(menu_name) < 100 and
                                    ('원' in price_text or price_text == '0원')):
                                    
                                    # 가격에서 숫자 추출
                                    price_match = re.search(r'([\d,]+)\s*원', price_text)
                                    price_numeric = 0
                                    if price_match:
                                        price_numeric = int(price_match.group(1).replace(',', ''))
                                    
                                    # 추천 여부 확인
                                    is_recommended = '추천' in menu_name
                                    
                                    menu_item = {
                                        'name': menu_name,
                                        'price': price_text,
                                        'price_numeric': price_numeric,
                                        'is_recommended': is_recommended,
                                        'source': 'browser_verified',
                                        'order': i + 1
                                    }
                                    
                                    menu_items.append(menu_item)
                                    logger.debug(f"📋 메뉴 추출: {menu_name} - {price_text}")
                                    
                        except Exception as e:
                            logger.warning(f"메뉴 아이템 {i} 처리 중 오류: {e}")
                            continue
                    
                    # 가격순 정렬 (0원 제외하고)
                    paid_items = [item for item in menu_items if item['price_numeric'] > 0]
                    free_items = [item for item in menu_items if item['price_numeric'] == 0]
                    
                    paid_items.sort(key=lambda x: x['price_numeric'])
                    menu_items = paid_items + free_items
                    
                    logger.info(f"✅ 브라우저 기반 메뉴 추출 완료: {len(menu_items)}개")
                    
                else:
                    logger.warning("메뉴 리스트를 찾을 수 없음")
            else:
                logger.warning("메뉴정보 헤더를 찾을 수 없음")
                
        except Exception as e:
            logger.error(f"브라우저 기반 메뉴 추출 실패: {e}")
        
        return menu_items
    
    def _extract_general_menu_items(self, soup: BeautifulSoup) -> List[Dict]:
        """일반 메뉴 아이템 추출"""
        menu_items = []
        
        try:
            # 메뉴 섹션 찾기
            menu_sections = soup.find_all(['div', 'section', 'ul'], class_=re.compile(r'menu|Menu'))
            
            for section in menu_sections:
                # 리뷰 섹션 제외
                section_text = section.get_text().lower()
                if any(exclude in section_text for exclude in ['리뷰', '후기', '평점', '별점', '방문기', '블로그']):
                    continue
                
                # 메뉴 아이템 추출
                items = section.find_all(['div', 'li', 'tr'], class_=re.compile(r'menu-item|menuitem|item'))
                
                for item in items:
                    item_text = item.get_text()
                    
                    # 리뷰 관련 텍스트 제외
                    if any(exclude in item_text for exclude in ['리뷰', '후기', '평점', '별점', '방문', '예약', '블로그']):
                        continue
                    
                    menu_name = item.find(['span', 'div', 'h3', 'h4'], class_=re.compile(r'name|title'))
                    menu_price = item.find(['span', 'div'], class_=re.compile(r'price|cost|amount'))
                    
                    if menu_name:
                        menu_data = {
                            'name': menu_name.get_text(strip=True),
                            'price': menu_price.get_text(strip=True) if menu_price else '',
                        }
                        
                        # 가격 정보가 있고 유효한 메뉴인 경우만 추가
                        if menu_data['name'] and len(menu_data['name']) > 2:
                            menu_items.append(menu_data)
            
            # 테이블 형태의 메뉴 추출
            menu_tables = soup.find_all('table')
            for table in menu_tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        name_cell = cells[0].get_text(strip=True)
                        price_cell = cells[1].get_text(strip=True)
                        
                        # 리뷰 관련 텍스트 제외
                        if any(exclude in name_cell for exclude in ['리뷰', '후기', '평점', '별점']):
                            continue
                        
                        if name_cell and price_cell and '원' in price_cell:
                            menu_items.append({
                                'name': name_cell,
                                'price': price_cell
                            })
            
        except Exception as e:
            logger.error(f"일반 메뉴 추출 실패: {e}")
        
        return menu_items
    
    def _extract_signature_menu(self, soup: BeautifulSoup) -> List[str]:
        """대표 메뉴 추출"""
        signature_menu = []
        
        try:
            signature_elements = soup.find_all(['div', 'span'], class_=re.compile(r'signature|recommend|popular'))
            for elem in signature_elements:
                elem_text = elem.get_text()
                
                # 리뷰 관련 텍스트 제외
                if any(exclude in elem_text for exclude in ['리뷰', '후기', '평점', '별점', '방문기']):
                    continue
                
                text = elem.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 50:
                    signature_menu.append(text)
            
        except Exception as e:
            logger.error(f"대표 메뉴 추출 실패: {e}")
        
        return signature_menu
    
    def _extract_menu_keywords(self, soup: BeautifulSoup) -> List[str]:
        """메뉴 관련 키워드 추출"""
        keywords = []
        
        try:
            refill_keywords = ['무한리필', '무제한', '셀프바']
            food_keywords = ['고기', '삼겹살', '소고기', '돼지고기', '초밥', '회', '해산물', '야채']
            
            all_text = soup.get_text().lower()
            
            for keyword in refill_keywords + food_keywords:
                if keyword in all_text:
                    keywords.append(keyword)
            
            keywords = keywords[:10]  # 최대 10개
            
        except Exception as e:
            logger.error(f"메뉴 키워드 추출 실패: {e}")
        
        return keywords
    
    def _extract_refill_menu_from_operation_info(self, soup: BeautifulSoup) -> List[Dict]:
        """운영 정보 섹션에서 무한리필 메뉴 추출 (JSON 파싱 + HTML 파싱)"""
        menu_items = []
        
        try:
            logger.info("🔍 운영 정보에서 무한리필 메뉴 추출 시작...")
            
            # 1. 우선 JSON 데이터에서 메뉴 정보 추출
            menu_items = self._extract_menu_from_json_data(soup)
            
            if len(menu_items) > 0:
                logger.info(f"JSON 데이터에서 {len(menu_items)}개 메뉴 추출 성공")
                return menu_items
            
            # 2. JSON 추출 실패 시 HTML에서 추출 (브라우저 검증 기반 개선)
            logger.info("JSON 추출 실패, HTML 파싱으로 전환...")
            
            # 메뉴정보 헤더 정확히 찾기
            menu_header = soup.find(text=lambda text: text and '메뉴정보' in text.strip())
            
            if menu_header:
                logger.info(f"✅ 메뉴정보 헤더 발견: {menu_header.strip()}")
                
                # 헤더의 부모 요소에서 다음 형제 요소 찾기 (메뉴 리스트)
                header_parent = menu_header.parent
                if header_parent:
                    menu_list = header_parent.find_next_sibling(['ul', 'ol', 'div', 'section'])
                    
                    if menu_list:
                        logger.info(f"✅ 메뉴 리스트 컨테이너 발견: {menu_list.name}")
                        
                        # 리스트 아이템들에서 메뉴 추출
                        list_items = menu_list.find_all('li', recursive=True)
                        
                        for item in list_items:
                            paragraphs = item.find_all('p')
                            if len(paragraphs) >= 2:
                                # 첫 번째 p: 메뉴명, 두 번째 p: 가격
                                menu_name = paragraphs[0].get_text(strip=True)
                                price_text = paragraphs[1].get_text(strip=True)
                                
                                # 리뷰 내용 필터링 (짧고 명확한 메뉴 정보만)
                                if (menu_name and price_text and 
                                    len(menu_name) < 50 and  # 메뉴명이 너무 길지 않음
                                    '원' in price_text and  # 가격 정보 포함
                                    len(price_text) < 20):  # 가격 텍스트가 너무 길지 않음
                                    
                                    # 가격에서 숫자 추출
                                    price_match = re.search(r'([\d,]+)\s*원', price_text)
                                    price = price_match.group(1).replace(',', '') if price_match else ''
                                    
                                    menu_item = {
                                        'name': menu_name,
                                        'price': price_text,
                                        'price_numeric': int(price) if price.isdigit() else 0,
                                        'is_recommended': '추천' in menu_name,
                                        'source': 'html_parsing'
                                    }
                                    menu_items.append(menu_item)
                                    logger.info(f"📋 메뉴 추출: {menu_name} - {price_text}")
                        
                        if len(menu_items) > 0:
                            logger.info(f"✅ HTML에서 {len(menu_items)}개 메뉴 추출 완료")
                            return menu_items
            
            # 기존 로직으로 폴백
            menu_section = None
            
            # 메뉴정보 또는 가격정보 헤더 찾기 (폴백)
            menu_headers = soup.find_all(text=re.compile(r'(메뉴\s*정보|가격\s*정보|운영\s*정보)', re.IGNORECASE))
            for header in menu_headers:
                parent = header.parent
                if parent:
                    # 메뉴정보 섹션의 컨테이너 찾기
                    section_container = parent.find_parent(['div', 'section', 'article'])
                    if section_container:
                        # 리뷰 섹션이 아닌지 확인
                        section_text = section_container.get_text()[:200]
                        if not any(keyword in section_text for keyword in ['리뷰', '후기', '평점', '별점', '맛있', '좋았', '추천해요']):
                            menu_section = section_container
                            break
            
            # 메뉴정보 섹션이 없으면 더 구체적으로 찾기
            if not menu_section:
                # 가격이 포함된 요소들 중에서 메뉴 섹션 찾기
                price_elements = soup.find_all(text=re.compile(r'\d{1,3}(?:,\d{3})*\s*원'))
                for price_elem in price_elements:
                    container = price_elem.parent.find_parent(['div', 'section'])
                    if container:
                        container_text = container.get_text()
                        # 메뉴 관련 키워드가 있고 리뷰 키워드가 없는 섹션
                        if (any(keyword in container_text for keyword in ['무한리필', '추천', '할인', '세트']) and
                            not any(keyword in container_text for keyword in ['리뷰', '후기', '평점', '별점', '맛있다', '좋았', '방문했'])):
                            menu_section = container
                            break
            
            if not menu_section:
                logger.warning("메뉴 정보 섹션을 찾을 수 없음")
                return menu_items
            
            # 메뉴 정보만 정확히 추출
            section_text = menu_section.get_text()
            logger.debug(f"메뉴 섹션 텍스트 (일부): {section_text[:300]}...")
            
            # 리뷰 내용 제거 - 더 강력한 필터링
            cleaned_text = self._clean_text_for_menu_extraction(section_text)
            
            # 메뉴 정보 파싱
            menu_items = self._extract_clean_menu_from_text(cleaned_text)
            
            # HTML 구조에서 직접 추출 (백업)
            if len(menu_items) == 0:
                menu_items = self._extract_menu_from_html_structure(menu_section)
            
            logger.info(f"HTML에서 {len(menu_items)}개 무한리필 메뉴 추출")
            
            # 추출된 메뉴 정보 로깅
            for item in menu_items:
                logger.debug(f"메뉴: {item['name']} - {item['price']}")
            
        except Exception as e:
            logger.error(f"운영 정보에서 무한리필 메뉴 추출 실패: {e}")
        
        return menu_items
    
    def _extract_menu_from_json_data(self, soup: BeautifulSoup) -> List[Dict]:
        """JavaScript aData 변수에서 JSON 메뉴 데이터 추출"""
        menu_items = []
        
        try:
            # script 태그에서 aData 변수 찾기
            script_tags = soup.find_all('script', string=re.compile(r'aData\s*='))
            
            for script in script_tags:
                script_content = script.string
                if not script_content:
                    continue
                
                # aData 변수 값 추출
                aData_match = re.search(r'aData\s*=\s*(\[.*?\]);', script_content, re.DOTALL)
                
                if aData_match:
                    import json
                    json_str = aData_match.group(1)
                    
                    try:
                        # JSON 파싱
                        aData = json.loads(json_str)
                        logger.debug(f"aData 파싱 성공: {len(aData)}개 요소")
                        
                        # 첫 번째 요소에서 메뉴 정보 찾기
                        if len(aData) > 0 and isinstance(aData[0], dict):
                            first_item = aData[0]
                            
                            # 메뉴 정보 찾기
                            if 'menu' in first_item and isinstance(first_item['menu'], dict):
                                menu_data = first_item['menu']
                                
                                if 'list' in menu_data and isinstance(menu_data['list'], list):
                                    menu_list = menu_data['list']
                                    logger.info(f"JSON에서 {len(menu_list)}개 메뉴 발견")
                                    
                                    for menu_item in menu_list:
                                        if isinstance(menu_item, dict):
                                            menu_name = menu_item.get('menu', '').strip()
                                            price_str = menu_item.get('price', '').strip()
                                            is_best = menu_item.get('best', 0) == 1
                                            
                                            if menu_name and price_str:
                                                # 가격에서 숫자만 추출
                                                price_match = re.search(r'(\d{1,3}(?:,\d{3})*)', price_str)
                                                if price_match:
                                                    price_numeric = int(price_match.group(1).replace(',', ''))
                                                    
                                                    # 가격 범위 검증 (5,000원 ~ 100,000원)
                                                    if 5000 <= price_numeric <= 100000:
                                                        menu_items.append({
                                                            'name': menu_name,
                                                            'price': price_str,
                                                            'price_numeric': price_numeric,
                                                            'is_recommended': is_best,
                                                            'description': '추천' if is_best else ''
                                                        })
                                                        
                                                        logger.debug(f"JSON 메뉴 추가: {menu_name} - {price_str}")
                                    
                                    # 가격 순 정렬
                                    menu_items.sort(key=lambda x: x['price_numeric'])
                                    break
                                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 실패: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"JSON 메뉴 데이터 추출 실패: {e}")
        
        return menu_items
    
    def _clean_text_for_menu_extraction(self, text: str) -> str:
        """메뉴 추출을 위한 텍스트 정리 - 리뷰 내용 제거"""
        lines = text.split('\n')
        cleaned_lines = []
        
        # 리뷰성 키워드 패턴
        review_patterns = [
            r'.*[맛있|좋았|별로|추천해|후기|리뷰|평점|별점|다시|재방문|맛집|블로그].*',
            r'.*안녕하세요.*',
            r'.*소개해.*드릴게요.*',
            r'.*먹어보니.*',
            r'.*찾고 계신다면.*',
            r'.*~\s*오늘.*',
            r'.*제로에요.*',
            r'.*잇님들.*',
            r'.*ㄷㄷ.*',
            r'.*보이시죠.*',
            r'.*폐업신고.*',
            r'.*정보수정.*',
            r'.*유명하다는.*',
            r'.*느낌은 아니었지만.*',
            r'.*간절할때.*',
        ]
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:  # 너무 짧은 라인 제외
                continue
                
            # 리뷰성 내용 제외
            is_review = False
            for pattern in review_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_review = True
                    break
            
            if not is_review:
                # 메뉴나 가격 정보가 포함된 라인만 포함
                if (re.search(r'\d{1,3}(?:,\d{3})*\s*원', line) or
                    any(keyword in line for keyword in ['무한리필', '추천', '할인', '세트', '코스'])):
                    cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_clean_menu_from_text(self, text: str) -> List[Dict]:
        """정리된 텍스트에서 메뉴 정보만 정확히 추출"""
        menu_items = []
        
        try:
            # 메뉴 + 가격 패턴 (더 정확한 패턴)
            patterns = [
                # 패턴 1: "a 돼지모듬 무한리필 추천 17,900원" (다이닝코드 표준)
                r'([a-z])\s+([가-힣\s\w()]+?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?(?:추천|할인)?)\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 2: "돼지모듬 무한리필 추천 17,900원"
                r'([가-힣\s\w()]+?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?(?:추천|할인)?)\s+(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 3: "무한리필 추천\n17,900원" (줄바꿈 구분)
                r'([가-힣\s\w()]*?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?(?:추천|할인)?)\s*\n\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 4: "평일 점심 무한리필 15,900원" (시간대별)
                r'([가-힣\s\w()]*?(?:평일|주말|점심|저녁|오전|오후)[가-힣\s\w()]*?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?)\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 5: "성인 무한리필 19,900원" (연령대별)
                r'([가-힣\s\w()]*?(?:성인|어린이|초등|중등|고등|학생)[가-힣\s\w()]*?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?)\s*(\d{1,3}(?:,\d{3})*)\s*원'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    if len(match) == 3:  # 패턴 1
                        menu_name = match[1].strip()
                        price = match[2].strip()
                    else:  # 나머지 패턴
                        menu_name = match[0].strip()
                        price = match[1].strip()
                    
                    # 메뉴명 정리
                    menu_name = re.sub(r'^[a-z]\s+', '', menu_name)  # 앞의 알파벳 제거
                    menu_name = re.sub(r'\s+', ' ', menu_name)  # 공백 정리
                    
                    # 유효성 검사
                    if (len(menu_name) >= 3 and len(menu_name) <= 30 and 
                        price.replace(',', '').isdigit()):
                        
                        # 가격 범위 검증 (5,000원 ~ 50,000원)
                        price_num = int(price.replace(',', ''))
                        if 5000 <= price_num <= 50000:
                            # 중복 체크
                            if not any(item['name'] == menu_name for item in menu_items):
                                menu_items.append({
                                    'name': menu_name,
                                    'price': f"{price}원",
                                    'price_numeric': price_num,
                                    'description': ''
                                })
            
            # 가격 순 정렬
            menu_items.sort(key=lambda x: x['price_numeric'])
            
        except Exception as e:
            logger.error(f"정리된 텍스트에서 메뉴 추출 실패: {e}")
        
        return menu_items
    
    def _extract_menu_from_html_structure(self, menu_section: BeautifulSoup) -> List[Dict]:
        """HTML 구조에서 직접 메뉴 정보 추출"""
        menu_items = []
        
        try:
            # 가격이 포함된 요소들 찾기
            price_elements = menu_section.find_all(text=re.compile(r'\d{1,3}(?:,\d{3})*\s*원'))
            
            for price_elem in price_elements:
                price_text = price_elem.strip()
                price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', price_text)
                
                if price_match:
                    price = price_match.group(1)
                    price_num = int(price.replace(',', ''))
                    
                    # 가격 범위 검증
                    if 5000 <= price_num <= 50000:
                        # 가격 요소의 부모나 형제에서 메뉴명 찾기
                        parent = price_elem.parent
                        if parent:
                            parent_text = parent.get_text()
                            
                            # 메뉴명 추출 (가격 제외)
                            menu_text = re.sub(r'\d{1,3}(?:,\d{3})*\s*원', '', parent_text).strip()
                            
                            # 무한리필 관련 메뉴인지 확인
                            if (any(keyword in menu_text for keyword in ['무한리필', '뷔페', '셀프바', '추천', '할인']) and
                                len(menu_text) >= 3 and len(menu_text) <= 30 and
                                not any(keyword in menu_text for keyword in ['리뷰', '후기', '맛있', '좋았'])):
                                
                                # 중복 체크
                                if not any(item['name'] == menu_text for item in menu_items):
                                    menu_items.append({
                                        'name': menu_text,
                                        'price': f"{price}원",
                                        'price_numeric': price_num,
                                        'description': ''
                                    })
            
        except Exception as e:
            logger.error(f"HTML 구조에서 메뉴 추출 실패: {e}")
        
        return menu_items
    
    def _extract_price_info(self, soup: BeautifulSoup) -> Dict:
        """가격 정보 추출 (무한리필 메뉴 특화)"""
        price_info = {
            'price_range': '',
            'average_price': '',
            'price_details': [],
            'refill_prices': []  # 무한리필 가격 정보 전용
        }
        
        try:
            logger.info("💰 가격 정보 추출 시작...")
            
            # 1. 무한리필 메뉴 가격 정보 추출 (운영 정보에서)
            refill_prices = self._extract_refill_prices_from_operation_info(soup)
            price_info['refill_prices'] = refill_prices
            
            # 2. 일반 가격 정보 추출
            found_prices = []
            menu_prices = []
            
            # 가격 패턴 (리뷰 제외)
            price_patterns = [
                # 기본 가격 패턴
                r'(\d{1,3}(?:,\d{3})*)\s*원',
                # 메뉴명과 가격
                r'([가-힣\s\w()]+?)\s*[:：]\s*(\d{1,3}(?:,\d{3})*)\s*원',
                # 범위 가격
                r'(\d{1,3}(?:,\d{3})*)\s*원?\s*[-~]\s*(\d{1,3}(?:,\d{3})*)\s*원',
                # 만원 단위
                r'(\d{1,2})\s*만\s*(\d{1,3}(?:,\d{3})*)\s*원',
                r'(\d{1,2})\s*만원'
            ]
            
            # 3. 가격 관련 요소 찾기 (리뷰 섹션 제외)
            price_selectors = [
                '.menu-price', '.price', '.cost', '.amount',
                '[class*="price"]', '[class*="Price"]', '[class*="cost"]',
                '[class*="menu"]', '[class*="Menu"]'
            ]
            
            for selector in price_selectors:
                elements = soup.select(selector)
                
                for elem in elements:
                    # 리뷰 섹션인지 확인
                    elem_text = elem.get_text()
                    if any(exclude in elem_text for exclude in ['리뷰', '후기', '평점', '별점', '방문', '블로그']):
                        continue
                    
                    # 부모 요소도 체크
                    parent = elem.parent
                    if parent:
                        parent_text = parent.get_text()
                        if any(exclude in parent_text for exclude in ['리뷰', '후기', '평점', '별점', '방문기']):
                            continue
                    
                    text = elem.get_text(strip=True)
                    
                    # 가격과 관련 없는 텍스트 제외
                    if any(exclude in text for exclude in ['후기', '리뷰', '평점', '별점', '추천', '방문', '예약']):
                        continue
                    
                    for pattern in price_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if isinstance(match, tuple):
                                if len(match) == 2:
                                    # 메뉴명과 가격 또는 범위 가격
                                    if match[0].replace(',', '').isdigit() and match[1].replace(',', '').isdigit():
                                        # 범위 가격
                                        found_prices.extend([match[0], match[1]])
                                    else:
                                        # 메뉴명과 가격
                                        menu_name, price = match
                                        if price.replace(',', '').isdigit():
                                            found_prices.append(price)
                                            menu_prices.append(f"{menu_name}: {price}원")
                                else:
                                    found_prices.extend([m for m in match if m.replace(',', '').isdigit()])
                            else:
                                if match.replace(',', '').isdigit():
                                    found_prices.append(match)
            
            # 4. 테이블에서 가격 정보 추출
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text()
                
                # 리뷰 테이블 제외
                if any(exclude in table_text for exclude in ['리뷰', '후기', '평점', '별점']):
                    continue
                
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        
                        # 가격 패턴 찾기
                        price_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*원', cell_text)
                        for price in price_matches:
                            found_prices.append(price)
            
            # 5. 무한리필 가격이 있으면 우선 사용
            if refill_prices:
                # 무한리필 가격으로 price_details 구성 (구조화된 JSON)
                structured_menu_items = []
                for refill_price in refill_prices:
                    menu_item = {
                        'name': refill_price['name'],
                        'price': refill_price['price'],
                        'price_numeric': refill_price.get('price_numeric', 0),
                        'is_recommended': refill_price.get('is_recommended', False),
                        'type': 'refill'
                    }
                    structured_menu_items.append(menu_item)
                    
                    # 숫자 가격 추출
                    price_num = refill_price.get('price_numeric', 0)
                    if price_num > 0:
                        found_prices.append(str(price_num))
                
                # 구조화된 메뉴 정보를 menu_items에 저장 (detail_info가 있는 경우)
                # price_details는 기존 배열 형태 유지
                price_info['structured_menu_items'] = structured_menu_items
                
                logger.info(f"무한리필 가격 정보 {len(refill_prices)}개 사용")
            
            # 6. 가격 정보 정리 및 검증
            if found_prices:
                # 중복 제거 및 정리
                unique_prices = list(set(found_prices))
                
                # 숫자로 변환 가능한 가격만 필터링
                numeric_prices = []
                for price in unique_prices:
                    try:
                        # 만원 단위 처리
                        if '만' in price:
                            num = float(price.replace('만', '').replace(',', ''))
                            numeric_prices.append(int(num * 10000))
                        else:
                            num = int(price.replace(',', ''))
                            # 합리적인 가격 범위 필터링 (1,000원 ~ 100,000원)
                            if 1000 <= num <= 100000:
                                numeric_prices.append(num)
                    except:
                        continue
                
                if numeric_prices:
                    # 가격 통계 계산
                    min_price = min(numeric_prices)
                    max_price = max(numeric_prices)
                    avg_price = sum(numeric_prices) // len(numeric_prices)
                    
                    # 가격 정보 설정
                    price_info['price_range'] = f"{min_price:,}원 ~ {max_price:,}원"
                    price_info['average_price'] = f"{avg_price:,}원"
                    price_info['price_details'] = menu_prices[:10]  # 최대 10개
                    
                    logger.info(f"가격 정보 추출 성공: {len(numeric_prices)}개 가격, 평균 {avg_price:,}원")
                else:
                    logger.warning("유효한 가격 정보를 찾을 수 없음")
            
            # 7. 추가 가격 정보 검색 (Selenium 활용)
            if not price_info['price_details'] and self.driver:
                try:
                    # 메뉴 탭이나 가격 정보 버튼 클릭 시도
                    menu_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button, a, div')
                    
                    for button in menu_buttons:
                        button_text = button.text.lower()
                        if any(keyword in button_text for keyword in ['메뉴', '가격', 'menu', 'price', '운영정보']):
                            try:
                                logger.info(f"메뉴/가격 정보 버튼 클릭 시도: {button_text}")
                                self.driver.execute_script("arguments[0].scrollIntoView();", button)
                                time.sleep(1)
                                button.click()
                                time.sleep(3)
                                
                                # 업데이트된 페이지에서 가격 정보 재추출
                                updated_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                updated_price_info = self._extract_price_info_from_soup(updated_soup)
                                
                                if updated_price_info['price_details']:
                                    price_info.update(updated_price_info)
                                    logger.info("메뉴 클릭 후 가격 정보 수집 성공")
                                    break
                                    
                            except Exception as e:
                                logger.debug(f"메뉴 버튼 클릭 실패: {e}")
                                continue
                
                except Exception as e:
                    logger.debug(f"추가 가격 정보 검색 실패: {e}")
            
            logger.info(f"가격 정보 추출 완료: {len(price_info['price_details'])}개 일반가격, {len(price_info['refill_prices'])}개 무한리필가격")
            
        except Exception as e:
            logger.error(f"가격 정보 추출 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return price_info
    
    def _extract_price_info_from_soup(self, soup: BeautifulSoup) -> Dict:
        """BeautifulSoup 객체에서 가격 정보만 추출하는 헬퍼 함수"""
        price_info = {
            'price_range': '',
            'average_price': '',
            'price_details': []
        }
        
        try:
            # 간단한 가격 추출 로직 (재귀 호출 방지)
            price_elements = soup.find_all(['span', 'div', 'td'], string=re.compile(r'\d+.*원'))
            
            prices = []
            for elem in price_elements:
                text = elem.get_text(strip=True)
                price_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*원', text)
                prices.extend(price_matches)
            
            if prices:
                numeric_prices = []
                for price in prices:
                    try:
                        num = int(price.replace(',', ''))
                        if 1000 <= num <= 100000:
                            numeric_prices.append(num)
                    except:
                        continue
                
                if numeric_prices:
                    min_price = min(numeric_prices)
                    max_price = max(numeric_prices)
                    avg_price = sum(numeric_prices) // len(numeric_prices)
                    
                    price_info['price_range'] = f"{min_price:,}원 ~ {max_price:,}원"
                    price_info['average_price'] = f"{avg_price:,}원"
                    price_info['price_details'] = [f"{p}원" for p in prices[:10]]
            
        except Exception as e:
            logger.debug(f"헬퍼 가격 추출 실패: {e}")
        
        return price_info

    def _extract_hours_info(self, detail_soup: BeautifulSoup) -> Dict[str, Any]:
        """영업시간, 브레이크타임, 라스트오더 정보 추출 (개선된 버전)"""
        hours_info = {
            'open_hours': '',
            'holiday': '',
            'break_time': '',
            'last_order': ''
        }
        
        try:
            # 1단계: 영업시간이 포함된 리스트 아이템 찾기
            hours_section = None
            list_items = detail_soup.find_all('li')
            
            for li in list_items:
                li_text = li.get_text()
                if any(keyword in li_text for keyword in ['영업시간', '라스트 오더', '라스트오더', '휴무']):
                    hours_section = li
                    logger.info(f"영업시간 섹션 발견: {li_text[:150]}...")
                    break
            
            if not hours_section:
                logger.warning("영업시간 섹션을 찾을 수 없음")
                return hours_info
            
            # 2단계: Selenium으로 토글 버튼 클릭하여 상세 정보 수집 (개선된 버전)
            expanded_hours_text = ""
            if self.driver:
                try:
                    # 영업시간 토글 버튼 찾기 (더 정확한 방법)
                    toggle_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button')
                    
                    for button in toggle_buttons:
                        try:
                            # 버튼의 부모나 형제 요소에서 영업시간 관련 텍스트 확인
                            parent = button.find_element(By.XPATH, '..')
                            parent_text = parent.text
                            
                            if any(keyword in parent_text for keyword in ['영업시간', '라스트오더', '라스트 오더']):
                                # 토글 아이콘이 있는 버튼인지 확인
                                imgs = button.find_elements(By.TAG_NAME, 'img')
                                for img in imgs:
                                    alt_text = img.get_attribute('alt') or ''
                                    if '토글' in alt_text or 'toggle' in alt_text.lower():
                                        logger.info(f"영업시간 토글 버튼 클릭 시도")
                                        
                                        # 스크롤하여 버튼이 보이도록 조정
                                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                                        time.sleep(1)
                                        
                                        # 클릭
                                        self.driver.execute_script("arguments[0].click();", button)
                                        
                                        # 토글 애니메이션 및 데이터 로딩 대기 (개선된 대기 시간)
                                        logger.info("영업시간 상세 정보 로딩 대기 중...")
                                        time.sleep(5)  # 3초에서 5초로 증가
                                        
                                        # 추가 데이터 로딩 확인
                                        for wait_attempt in range(3):
                                            updated_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                            page_text = updated_soup.get_text()
                                            
                                            # 요일별 정보가 로드되었는지 확인
                                            weekday_count = sum(1 for day in ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일'] if day in page_text)
                                            if weekday_count >= 3:  # 최소 3개 요일 정보가 있으면 로딩 완료로 판단
                                                logger.info(f"요일별 정보 로딩 완료: {weekday_count}개 요일 감지")
                                                break
                                            
                                            logger.info(f"추가 로딩 대기 중... (시도 {wait_attempt + 1}/3)")
                                            time.sleep(2)
                                        
                                        # 확장된 영업시간 정보 찾기 (개선된 방법)
                                        updated_list_items = updated_soup.find_all('li')
                                        
                                        for updated_li in updated_list_items:
                                            updated_text = updated_li.get_text()
                                            
                                            # 날짜별 영업시간 패턴이 있는지 확인
                                            if re.search(r'\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)', updated_text):
                                                # 실제 영업시간 정보인지 확인 (리뷰나 기타 내용 제외)
                                                if not any(word in updated_text for word in ['블로그', '후기', '리뷰', '방문', '추천', '맛집']):
                                                    if any(keyword in updated_text for keyword in ['영업시간', '라스트오더', '휴무일', '휴무']):
                                                        expanded_hours_text = updated_text
                                                        logger.info(f"확장된 영업시간 정보 수집: {expanded_hours_text[:200]}...")
                                                        break
                                        
                                        # 패턴 매칭으로 추가 시도
                                        if not expanded_hours_text:
                                            page_text = updated_soup.get_text()
                                            
                                            # 개선된 날짜별 영업시간 패턴
                                            date_patterns = [
                                                r'(\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)\s*[^\n]*?영업시간[^\n]*?\d{1,2}:\d{2}[^\n]*)',
                                                r'(\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)\s*[^\n]*?휴무[^\n]*)',
                                                r'([월화수목금토일]요일[^\n]*?영업시간[^\n]*?\d{1,2}:\d{2}[^\n]*)',
                                                r'([월화수목금토일]요일[^\n]*?휴무[^\n]*)'
                                            ]
                                            
                                            found_dates = []
                                            for pattern in date_patterns:
                                                matches = re.findall(pattern, page_text)
                                                found_dates.extend(matches)
                                            
                                            if found_dates:
                                                expanded_hours_text = ' '.join(found_dates)
                                                logger.info(f"패턴 매칭으로 영업시간 정보 수집: {len(found_dates)}개 항목")
                                        
                                        break
                                break
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    logger.warning(f"토글 버튼 클릭 실패: {e}")
            
            # 3단계: 개선된 영업시간 파싱 로직 적용
            hours_text = expanded_hours_text if expanded_hours_text else hours_section.get_text(strip=True)
            logger.info(f"파싱할 영업시간 텍스트: {hours_text[:300]}...")
            
            # 개선된 파싱 함수 사용
            parsed_hours = self._parse_hours_info_improved(hours_text)
            
            # 결과 병합
            hours_info.update(parsed_hours)
            
            logger.info(f"최종 영업시간: {hours_info['open_hours']}")
            logger.info(f"휴무일: {hours_info['holiday']}")
            logger.info(f"브레이크타임: {hours_info['break_time']}")
            logger.info(f"라스트오더: {hours_info['last_order']}")
            
        except Exception as e:
            logger.error(f"영업시간 정보 추출 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return hours_info

    def _parse_hours_info_improved(self, hours_text: str) -> Dict[str, Any]:
        """
        개선된 영업시간 정보 파싱
        
        Args:
            hours_text: 영업시간 관련 텍스트
            
        Returns:
            Dict: 파싱된 영업시간 정보
        """
        hours_info = {
            'open_hours': '',
            'holiday': '',
            'break_time': '',
            'last_order': ''
        }
        
        try:
            # 1단계: 라스트오더 정보 추출
            last_order_patterns = [
                r'라스트\s*오더\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'라스트오더\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'L\.?O\.?\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'주문\s*마감\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'마지막\s*주문\s*[:：]?\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in last_order_patterns:
                matches = re.findall(pattern, hours_text, re.IGNORECASE)
                if matches:
                    hours_info['last_order'] = matches[0]
                    logger.info(f"라스트오더 추출: {hours_info['last_order']}")
                    break
            
            # 2단계: 브레이크타임 정보 추출
            break_patterns = [
                r'브레이크\s*타임?\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                r'브레이크\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                r'휴게시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                r'쉬는시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                r'중간휴식\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in break_patterns:
                matches = re.findall(pattern, hours_text, re.IGNORECASE)
                if matches:
                    start_time, end_time = matches[0]
                    hours_info['break_time'] = f"{start_time}-{end_time}"
                    logger.info(f"브레이크타임 추출: {hours_info['break_time']}")
                    break
            
            # 3단계: 요일별 영업시간 추출
            day_hours = {}
            holiday_days = []
            
            # 한국어 요일 매핑
            day_mapping = {
                '월': '월', '화': '화', '수': '수', '목': '목', '금': '금', '토': '토', '일': '일',
                '월요일': '월', '화요일': '화', '수요일': '수', '목요일': '목', 
                '금요일': '금', '토요일': '토', '일요일': '일'
            }
            
            # 영업시간 패턴들 (우선순위 순)
            hour_patterns = [
                # 패턴 1: "영업시간: 11:00 - 23:00" 형태
                r'영업시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                
                # 패턴 2: "11:00 - 23:00" 단순 형태
                r'(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
                
                # 패턴 3: "오전 11시 - 오후 11시" 형태
                r'오전\s*(\d{1,2})시?\s*[-~]\s*오후\s*(\d{1,2})시?',
                
                # 패턴 4: "11시 - 23시" 형태
                r'(\d{1,2})시\s*[-~]\s*(\d{1,2})시'
            ]
            
            # 휴무 패턴들
            holiday_patterns = [
                r'([월화수목금토일])요일\s*휴무',
                r'([월화수목금토일])\s*[:：]?\s*휴무',
                r'매주\s*([월화수목금토일])요일\s*휴무',
                r'휴무일?\s*[:：]?\s*([월화수목금토일])요일?'
            ]
            
            # 텍스트를 줄 단위로 분할하여 처리
            lines = hours_text.split('\n')
            
            current_day = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 요일 감지 (날짜 형태에서 요일 추출)
                date_day_match = re.search(r'\d{1,2}월\s*\d{1,2}일\s*\(([월화수목금토일])\)', line)
                if date_day_match:
                    current_day = date_day_match.group(1)
                else:
                    # 일반 요일 감지
                    for day_text, day_short in day_mapping.items():
                        if day_text in line:
                            current_day = day_short
                            break
                
                # 휴무일 확인
                for pattern in holiday_patterns:
                    matches = re.findall(pattern, line)
                    if matches:
                        for match in matches:
                            day = day_mapping.get(match, match)
                            if day and day not in holiday_days:
                                holiday_days.append(day)
                                logger.info(f"휴무일 발견: {day}요일")
                
                # 영업시간 추출
                for pattern in hour_patterns:
                    matches = re.findall(pattern, line)
                    if matches and current_day:
                        start_time, end_time = matches[0]
                        
                        # 시간 형식 정규화
                        if ':' not in start_time:  # "11시" 형태
                            start_time = f"{start_time.zfill(2)}:00"
                        if ':' not in end_time:    # "23시" 형태
                            end_time = f"{end_time.zfill(2)}:00"
                        
                        # 오전/오후 처리
                        if '오전' in line and '오후' in line:
                            end_hour = int(end_time.split(':')[0])
                            if end_hour != 12:
                                end_hour += 12
                            end_time = f"{end_hour:02d}:{end_time.split(':')[1]}"
                        
                        hours_str = f"{start_time}-{end_time}"
                        day_hours[current_day] = hours_str
                        logger.info(f"영업시간 발견: {current_day}요일 {hours_str}")
                        break
            
            # 4단계: 패턴 분석으로 누락된 요일 보완
            all_days = ['월', '화', '수', '목', '금', '토', '일']
            collected_days = set(day_hours.keys())
            missing_days = [d for d in all_days if d not in collected_days and d not in holiday_days]
            
            logger.info(f"수집된 요일: {list(collected_days)}")
            logger.info(f"휴무일: {holiday_days}")
            logger.info(f"누락된 요일: {missing_days}")
            
            # 패턴 분석하여 누락된 요일 보완
            if len(day_hours) >= 1 and missing_days:
                # 주중/주말 패턴 분석
                weekday_hours = []
                weekend_hours = []
                
                for day in ['월', '화', '수', '목', '금']:
                    if day in day_hours:
                        weekday_hours.append(day_hours[day])
                
                for day in ['토', '일']:
                    if day in day_hours:
                        weekend_hours.append(day_hours[day])
                
                # 주중 패턴 적용 (2개 이상 동일한 시간이면 패턴으로 인정)
                if weekday_hours and len(weekday_hours) >= 2:
                    most_common_weekday = max(set(weekday_hours), key=weekday_hours.count)
                    if weekday_hours.count(most_common_weekday) >= 2:
                        for day in ['월', '화', '수', '목', '금']:
                            if day in missing_days:
                                day_hours[day] = most_common_weekday
                                logger.info(f"{day}요일에 주중 패턴 적용: {most_common_weekday}")
                
                # 주말 패턴 적용
                if weekend_hours and len(weekend_hours) >= 1:
                    most_common_weekend = max(set(weekend_hours), key=weekend_hours.count)
                    for day in ['토', '일']:
                        if day in missing_days and day not in holiday_days:
                            day_hours[day] = most_common_weekend
                            logger.info(f"{day}요일에 주말 패턴 적용: {most_common_weekend}")
                
                # 전체 동일 패턴 적용 (모든 요일이 같은 시간인 경우)
                if len(day_hours) == 1:
                    common_hours = list(day_hours.values())[0]
                    for day in missing_days:
                        if day not in holiday_days:
                            day_hours[day] = common_hours
                            logger.info(f"{day}요일에 전체 패턴 적용: {common_hours}")
            
            # 5단계: 최종 영업시간 문자열 생성
            if day_hours:
                hours_parts = []
                days_order = ['월', '화', '수', '목', '금', '토', '일']
                
                for day in days_order:
                    if day in day_hours:
                        hours_parts.append(f"{day}: {day_hours[day]}")
                    elif day in holiday_days:
                        hours_parts.append(f"{day}: 휴무")
                
                # 기본 영업시간 설정
                hours_info['open_hours'] = ', '.join(hours_parts)
                
                # 라스트오더가 있으면 맨 마지막에 추가
                if hours_info['last_order']:
                    hours_info['open_hours'] += f" / 라스트오더: {hours_info['last_order']}"
            
            # 6단계: 휴무일 설정
            if holiday_days:
                unique_holidays = list(set(holiday_days))
                if len(unique_holidays) == 1:
                    hours_info['holiday'] = f"매주 {unique_holidays[0]}요일 휴무"
                else:
                    hours_info['holiday'] = f"매주 {', '.join(unique_holidays)}요일 휴무"
            
        except Exception as e:
            logger.error(f"영업시간 정보 파싱 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return hours_info

    def _extract_image_info(self, soup: BeautifulSoup) -> Dict:
        """이미지 정보 추출 및 Storage 업로드 (기존 스키마 활용)"""
        image_info = {
            'main_image': '',
            'image_urls': []
        }
        
        try:
            logger.info("🖼️ 이미지 정보 추출 시작...")
            
            main_image_found = False
            original_image_url = None
            
            # 방법 1: 특정 클래스나 ID를 가진 대표 이미지 찾기
            main_image_selectors = [
                '.restaurant-image img',
                '.main-image img', 
                '.hero-image img',
                '.restaurant-photo img',
                '.poi-image img',
                '.store-image img',
                '#main-image',
                '.photo-main img',
                'img[alt*="대표"]',
                'img[alt*="메인"]',
                'img[alt*="main"]'
            ]
            
            for selector in main_image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
                    if src and src.startswith('http'):
                        original_image_url = src
                        main_image_found = True
                        logger.info(f"대표 이미지 발견 (방법1): {selector}")
                        break
            
            # 방법 2: 페이지 상단의 첫 번째 큰 이미지 찾기
            if not main_image_found:
                all_images = soup.find_all('img')
                for img in all_images[:10]:  # 상위 10개 이미지만 체크
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if src and src.startswith('http'):
                        # 작은 아이콘이나 UI 요소 제외
                        if not any(keyword in src.lower() for keyword in [
                            'icon', 'logo', 'btn', 'button', 'arrow', 'close', 
                            'addphoto', 'placeholder', 'default', 'loading'
                        ]):
                            # alt 텍스트나 클래스에서 대표 이미지 힌트 찾기
                            alt_text = img.get('alt', '').lower()
                            class_name = ' '.join(img.get('class', [])).lower()
                            
                            if (any(keyword in alt_text for keyword in ['대표', 'main', '가게', '매장']) or
                                any(keyword in class_name for keyword in ['main', 'hero', 'banner', 'primary'])):
                                original_image_url = src
                                main_image_found = True
                                logger.info(f"대표 이미지 발견 (방법2): alt='{alt_text}', class='{class_name}'")
                                break
            
            # 방법 3: JavaScript로 동적으로 로드된 이미지 찾기
            if not main_image_found and self.driver:
                try:
                    js_script = """
                    var images = document.querySelectorAll('img');
                    var largestImage = null;
                    var maxArea = 0;
                    
                    for (var i = 0; i < Math.min(images.length, 10); i++) {
                        var img = images[i];
                        var rect = img.getBoundingClientRect();
                        var area = rect.width * rect.height;
                        
                        if (rect.top < window.innerHeight / 2 && area > 10000) {
                            var src = img.src || img.getAttribute('data-src') || img.getAttribute('data-lazy');
                            if (src && src.startsWith('http') && 
                                !src.includes('icon') && !src.includes('logo') && 
                                !src.includes('btn') && !src.includes('addphoto')) {
                                if (area > maxArea) {
                                    maxArea = area;
                                    largestImage = src;
                                }
                            }
                        }
                    }
                    return largestImage;
                    """
                    
                    js_main_image = self.driver.execute_script(js_script)
                    if js_main_image:
                        original_image_url = js_main_image
                        main_image_found = True
                        logger.info(f"대표 이미지 발견 (방법3-JS): 가장 큰 이미지")
                        
                except Exception as js_error:
                    logger.warning(f"JavaScript 이미지 검색 실패: {js_error}")
            
            # 방법 4: 백업 - 첫 번째 유효한 이미지
            if not main_image_found:
                all_images = soup.find_all('img')
                for img in all_images[:15]:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if src and src.startswith('http'):
                        if not any(keyword in src.lower() for keyword in [
                            'icon', 'logo', 'btn', 'button', 'arrow', 'close', 
                            'addphoto', 'placeholder', 'default', 'loading',
                            'common', 'ui', 'sprite'
                        ]):
                            original_image_url = src
                            main_image_found = True
                            logger.info(f"대표 이미지 발견 (방법4-백업): 첫 번째 유효 이미지")
                            break
            
            # 이미지 처리 및 Storage 업로드
            if main_image_found and original_image_url:
                logger.info(f"📸 원본 이미지 URL: {original_image_url[:100]}...")
                
                # 기본적으로 원본 URL을 저장
                image_info['main_image'] = original_image_url
                image_info['image_urls'] = [original_image_url]
                
                # 이미지 매니저가 활성화된 경우 Storage 업로드 시도
                if self.enable_image_download and self.image_manager:
                    try:
                        self.stats['images_processed'] += 1
                        
                        # 가게명 추출 (파일명 생성용)
                        store_name = soup.find('h1')
                        if store_name:
                            store_name = store_name.get_text(strip=True)
                        else:
                            store_name = "unknown_store"
                        
                        logger.info(f"🔄 이미지 다운로드 및 Storage 업로드 시작: {store_name}")
                        
                        # 이미지 다운로드 → 처리 → Storage 업로드
                        result = self.image_manager.process_and_upload_image(
                            original_image_url, 
                            store_name
                        )
                        
                        if result.get('storage_url'):
                            # Storage URL을 main_image로 설정 (우선 사용)
                            image_info['main_image'] = result['storage_url']
                            # image_urls에는 원본과 Storage URL 모두 저장
                            image_info['image_urls'] = [original_image_url, result['storage_url']]
                            
                            self.stats['images_uploaded'] += 1
                            logger.info(f"✅ 이미지 Storage 업로드 성공!")
                            logger.info(f"🔗 Storage URL: {result['storage_url']}")
                        else:
                            logger.warning(f"⚠️ Storage 업로드 실패: {result.get('error', '알 수 없는 오류')}")
                            logger.info("📌 원본 URL을 사용합니다.")
                            
                    except Exception as upload_error:
                        logger.error(f"이미지 업로드 처리 실패: {upload_error}")
                        # 실패해도 원본 URL은 유지
                
                logger.info(f"✅ 이미지 정보 처리 완료")
                logger.info(f"📸 최종 main_image: {image_info['main_image'][:100]}...")
                logger.info(f"📸 image_urls 개수: {len(image_info['image_urls'])}")
            else:
                logger.warning("❌ 가게 대표 이미지를 찾을 수 없음")
            
        except Exception as e:
            logger.error(f"이미지 정보 추출 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return image_info

    def _extract_review_info(self, soup: BeautifulSoup) -> Dict:
        """리뷰 및 설명 정보 추출 (강화)"""
        review_info = {
            'description': '',
            'review_summary': '',
            'keywords': [],
            'atmosphere': ''
        }
        
        try:
            # 설명 텍스트 추출
            desc_elements = soup.find_all(['div', 'p'], class_=re.compile(r'desc|description|intro|summary'))
            descriptions = []
            
            for elem in desc_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 10:
                    descriptions.append(text)
            
            if descriptions:
                review_info['description'] = ' '.join(descriptions[:3])  # 최대 3개 합치기
            
            # 키워드 추출 (무한리필 관련)
            refill_keywords = ['무한리필', '무제한', '셀프바', '리필가능', '무료리필']
            food_keywords = ['고기', '삼겹살', '소고기', '돼지고기', '초밥', '회', '해산물', '야채']
            
            all_text = soup.get_text().lower()
            found_keywords = []
            
            for keyword in refill_keywords + food_keywords:
                if keyword in all_text:
                    found_keywords.append(keyword)
            
            review_info['keywords'] = found_keywords[:10]  # 최대 10개
            
            logger.info(f"리뷰 정보 추출: {len(found_keywords)}개 키워드")
            
        except Exception as e:
            logger.error(f"리뷰 정보 추출 실패: {e}")
        
        return review_info

    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict:
        """연락처 정보 추출 (강화)"""
        contact_info = {
            'phone_number': '',
            'website': '',
            'social_media': []
        }
        
        try:
            # 전화번호 패턴 매칭
            all_text = soup.get_text()
            phone_patterns = [
                r'0\d{1,2}-\d{3,4}-\d{4}',  # 02-1234-5678
                r'0\d{9,10}',               # 0212345678
                r'\d{3}-\d{3,4}-\d{4}'      # 010-1234-5678
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, all_text)
                if matches:
                    raw_phone = matches[0]
                    # 전화번호 정규화 (0507 → 07 문제 해결)
                    contact_info['phone_number'] = self._normalize_phone_number(raw_phone)
                    break
            
            # 웹사이트 링크 찾기
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if href.startswith('http') and 'diningcode.com' not in href:
                    contact_info['website'] = href
                    break
            
            logger.info(f"연락처 정보 추출 완료")
            
        except Exception as e:
            logger.error(f"연락처 정보 추출 실패: {e}")
        
        return contact_info
    
    def _normalize_phone_number(self, phone: str) -> str:
        """전화번호 정규화 (0507 → 07 문제 해결)"""
        if not phone:
            return phone
        
        # 하이픈 제거
        clean_phone = phone.replace('-', '')
        
        # 0507, 0508 등의 인터넷 전화번호 정규화
        # 0507-1234-5678 → 0507-1234-5678 (그대로 유지)
        # 잘못 파싱된 07-1234-5678 → 0507-1234-5678 (복원)
        
        # 패턴 1: 07-XXXX-XXXX 형태 (0507에서 05가 누락된 경우)
        if re.match(r'^07\d{8}$', clean_phone):
            # 07XXXXXXXX → 0507XXXXXXXX
            clean_phone = '0507' + clean_phone[2:]
        elif re.match(r'^08\d{8}$', clean_phone):
            # 08XXXXXXXX → 0508XXXXXXXX  
            clean_phone = '0508' + clean_phone[2:]
        
        # 하이픈 추가하여 표준 형식으로 변환
        if len(clean_phone) == 11:
            if clean_phone.startswith('010'):
                # 010-XXXX-XXXX
                return f"{clean_phone[:3]}-{clean_phone[3:7]}-{clean_phone[7:]}"
            elif clean_phone.startswith(('0507', '0508', '070')):
                # 0507-XXXX-XXXX, 0508-XXXX-XXXX, 070-XXXX-XXXX
                return f"{clean_phone[:4]}-{clean_phone[4:8]}-{clean_phone[8:]}"
        elif len(clean_phone) == 10:
            if clean_phone.startswith('02'):
                # 02-XXXX-XXXX
                return f"{clean_phone[:2]}-{clean_phone[2:6]}-{clean_phone[6:]}"
            else:
                # 기타 지역번호 0XX-XXX-XXXX
                return f"{clean_phone[:3]}-{clean_phone[3:6]}-{clean_phone[6:]}"
        elif len(clean_phone) == 9 and clean_phone.startswith('02'):
            # 02-XXX-XXXX
            return f"{clean_phone[:2]}-{clean_phone[2:5]}-{clean_phone[5:]}"
        
        # 기본적으로 원래 번호 반환
        return phone

    def _extract_refill_info(self, soup: BeautifulSoup) -> Dict:
        """무한리필 관련 정보 추출 (개선된 버전 - 리뷰 제외)"""
        refill_info = {
            'refill_items': [],
            'refill_type': '',
            'refill_conditions': '',
            'is_confirmed_refill': False,
            'refill_menu_summary': []  # 메뉴 정보와 통합된 요약
        }
        
        try:
            logger.info("🔄 무한리필 정보 추출 시작...")
            
            # 1. 메뉴/운영 정보 섹션만 추출 (리뷰 섹션 제외)
            operation_text = self._extract_operation_section_text(soup)
            
            # 2. 무한리필 확인
            refill_keywords = ['무한리필', '무제한', '셀프바', '뷔페']
            for keyword in refill_keywords:
                if keyword in operation_text:
                    refill_info['is_confirmed_refill'] = True
                    break
            
            # 3. 무한리필 아이템 추출 (더 정확한 패턴)
            refill_items = self._extract_clean_refill_items(operation_text)
            refill_info['refill_items'] = refill_items
            
            # 4. 리필 타입 추정
            if '고기' in operation_text or '삼겹살' in operation_text or '소고기' in operation_text:
                refill_info['refill_type'] = '고기무한리필'
            elif '초밥' in operation_text or '회' in operation_text:
                refill_info['refill_type'] = '초밥뷔페'
            elif '뷔페' in operation_text:
                refill_info['refill_type'] = '뷔페'
            elif '셀프바' in operation_text:
                refill_info['refill_type'] = '셀프바'
            else:
                refill_info['refill_type'] = '무한리필'
            
            # 5. 무한리필 조건 추출
            conditions = self._extract_refill_conditions(operation_text)
            refill_info['refill_conditions'] = '; '.join(conditions[:5])
            
            # 5. 메뉴 정보와 가격 정보를 통합한 요약 생성
            # (메뉴 추출에서 얻은 refill_menu_items 활용)
            menu_info = self._extract_menu_info(soup)
            price_info = self._extract_price_info(soup)
            
            # 무한리필 메뉴 요약 생성
            refill_summary = []
            
            # 가격 정보가 있는 경우
            if price_info.get('refill_prices'):
                for price_item in price_info['refill_prices']:
                    refill_summary.append({
                        'name': price_item['name'],
                        'price': price_item['price'],
                        'type': 'price_menu'
                    })
            
            # 메뉴 정보가 있는 경우
            if menu_info.get('refill_menu_items'):
                for menu_item in menu_info['refill_menu_items']:
                    # 중복 체크 (이름이 같은 경우 제외)
                    if not any(item['name'] == menu_item['name'] for item in refill_summary):
                        refill_summary.append({
                            'name': menu_item['name'],
                            'price': menu_item.get('price', ''),
                            'type': 'menu_item'
                        })
            
            # 일반 무한리필 아이템 추가
            for item in refill_info['refill_items']:
                if not any(summary_item['name'] == item for summary_item in refill_summary):
                    refill_summary.append({
                        'name': item,
                        'price': '',
                        'type': 'general_item'
                    })
            
            refill_info['refill_menu_summary'] = refill_summary[:10]  # 최대 10개
            
            logger.info(f"무한리필 정보 추출 완료: {len(refill_info['refill_items'])}개 아이템, {len(refill_summary)}개 요약")
            
        except Exception as e:
            logger.error(f"무한리필 정보 추출 실패: {e}")
        
        return refill_info
    
    def _extract_coordinate_info(self, soup: BeautifulSoup) -> Dict:
        """좌표 정보 추출 (다이닝코드 상세 페이지에서) - 개선된 버전"""
        coordinate_info = {
            'position_lat': None,
            'position_lng': None,
            'address': None
        }
        
        try:
            # 1. Selenium을 통한 JavaScript 변수 추출 (가장 확실한 방법)
            if self.driver:
                try:
                    # JavaScript 실행으로 좌표 정보 추출
                    lat_script = r"""
                    var lat = null;
                    try {
                        // 전역 변수에서 찾기
                        if (typeof lat !== 'undefined' && lat) lat = lat;
                        else if (typeof latitude !== 'undefined' && latitude) lat = latitude;
                        else if (typeof poi_lat !== 'undefined' && poi_lat) lat = poi_lat;
                        else if (typeof mapLat !== 'undefined' && mapLat) lat = mapLat;
                        else if (typeof window.lat !== 'undefined' && window.lat) lat = window.lat;
                        else if (typeof window.latitude !== 'undefined' && window.latitude) lat = window.latitude;
                        
                        // 객체 안에서 찾기
                        if (!lat && typeof window.poi !== 'undefined' && window.poi && window.poi.lat) lat = window.poi.lat;
                        if (!lat && typeof window.store !== 'undefined' && window.store && window.store.lat) lat = window.store.lat;
                        if (!lat && typeof window.restaurant !== 'undefined' && window.restaurant && window.restaurant.lat) lat = window.restaurant.lat;
                        
                        // 페이지 소스에서 정규식으로 찾기
                        if (!lat) {
                            var pageSource = document.documentElement.outerHTML;
                            var latMatch = pageSource.match(/(?:latitude|lat)["']?\s*[:=]\s*([0-9]+\.?[0-9]*)/i);
                            if (latMatch) lat = parseFloat(latMatch[1]);
                        }
                    } catch(e) {
                        console.log('위도 추출 오류:', e);
                    }
                    return lat;
                    """
                    
                    lng_script = r"""
                    var lng = null;
                    try {
                        // 전역 변수에서 찾기
                        if (typeof lng !== 'undefined' && lng) lng = lng;
                        else if (typeof longitude !== 'undefined' && longitude) lng = longitude;
                        else if (typeof poi_lng !== 'undefined' && poi_lng) lng = poi_lng;
                        else if (typeof mapLng !== 'undefined' && mapLng) lng = mapLng;
                        else if (typeof window.lng !== 'undefined' && window.lng) lng = window.lng;
                        else if (typeof window.longitude !== 'undefined' && window.longitude) lng = window.longitude;
                        
                        // 객체 안에서 찾기
                        if (!lng && typeof window.poi !== 'undefined' && window.poi && window.poi.lng) lng = window.poi.lng;
                        if (!lng && typeof window.store !== 'undefined' && window.store && window.store.lng) lng = window.store.lng;
                        if (!lng && typeof window.restaurant !== 'undefined' && window.restaurant && window.restaurant.lng) lng = window.restaurant.lng;
                        
                        // 페이지 소스에서 정규식으로 찾기
                        if (!lng) {
                            var pageSource = document.documentElement.outerHTML;
                            var lngMatch = pageSource.match(/(?:longitude|lng)["']?\s*[:=]\s*([0-9]+\.?[0-9]*)/i);
                            if (lngMatch) lng = parseFloat(lngMatch[1]);
                        }
                    } catch(e) {
                        console.log('경도 추출 오류:', e);
                    }
                    return lng;
                    """
                    
                    lat = self.driver.execute_script(lat_script)
                    lng = self.driver.execute_script(lng_script)
                    
                    if lat and lng:
                        coordinate_info['position_lat'] = float(lat)
                        coordinate_info['position_lng'] = float(lng)
                        logger.info(f"JavaScript에서 좌표 추출 성공: ({lat}, {lng})")
                    else:
                        logger.warning("JavaScript에서 좌표 추출 실패")
                        
                except Exception as js_error:
                    logger.error(f"JavaScript 좌표 추출 오류: {js_error}")
            
            # 2. JavaScript 실행이 실패한 경우 HTML 파싱으로 대체
            if not coordinate_info['position_lat']:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        script_content = script.string
                        
                        # 다양한 패턴으로 좌표 검색
                        patterns = [
                            (r'latitude["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)', r'longitude["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)'),
                            (r'lat["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)', r'lng["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)'),
                            (r'poi_lat["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)', r'poi_lng["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)'),
                            (r'mapLat["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)', r'mapLng["\']?\s*[:=]\s*([0-9]+\.?[0-9]*)')
                        ]
                        
                        for lat_pattern, lng_pattern in patterns:
                            lat_match = re.search(lat_pattern, script_content, re.IGNORECASE)
                            lng_match = re.search(lng_pattern, script_content, re.IGNORECASE)
                            
                            if lat_match and lng_match:
                                coordinate_info['position_lat'] = float(lat_match.group(1))
                                coordinate_info['position_lng'] = float(lng_match.group(1))
                                logger.info(f"HTML 파싱으로 좌표 추출: ({coordinate_info['position_lat']}, {coordinate_info['position_lng']})")
                                break
                        
                        if coordinate_info['position_lat']:
                            break
            
            # 3. 주소 정보 추출 (지오코딩용)
            address_selectors = [
                '.address',
                '.location',
                '[class*="addr"]',
                '[class*="address"]',
                '.info-address',
                '.restaurant-address',
                '.store-address',
                '.poi-address'
            ]
            
            for selector in address_selectors:
                address_elem = soup.select_one(selector)
                if address_elem:
                    address_text = address_elem.get_text(strip=True)
                    if address_text and len(address_text) > 5:
                        coordinate_info['address'] = address_text
                        logger.info(f"주소 정보 추출: {address_text}")
                        break
            
            # 4. 좌표 유효성 검증 (한국 영역 내)
            if coordinate_info['position_lat'] and coordinate_info['position_lng']:
                lat = coordinate_info['position_lat']
                lng = coordinate_info['position_lng']
                
                # 한국 영역 체크 (대략적인 범위)
                if not (33.0 <= lat <= 38.5 and 124.0 <= lng <= 132.0):
                    logger.warning(f"좌표가 한국 영역을 벗어남: ({lat}, {lng})")
                    coordinate_info['position_lat'] = None
                    coordinate_info['position_lng'] = None
                else:
                    logger.info(f"좌표 유효성 검증 통과: ({lat}, {lng})")
            
            # 5. 좌표가 없으면 주소로 지오코딩 필요 표시
            if not coordinate_info['position_lat'] and coordinate_info['address']:
                logger.info(f"주소 기반 지오코딩 필요: {coordinate_info['address']}")
                
        except Exception as e:
            logger.error(f"좌표 정보 추출 실패: {e}")
        
        return coordinate_info
    
    def _extract_address_info(self, soup: BeautifulSoup) -> Dict:
        """주소 정보 추출 (다이닝코드 구조에 맞게 개선)"""
        address_info = {
            'address': '',
            'basic_address': '',
            'road_address': ''
        }
        
        try:
            # 다이닝코드의 주소는 주로 링크 형태로 되어 있음
            # 예: <a href="/list.dc?query=서울특별시">서울특별시</a> <a href="/list.dc?query=서울특별시 강남구">강남구</a>
            
            # 1. 주소 링크들을 찾기
            address_parts = []
            
            # list.dc?query= 패턴을 가진 링크들 찾기
            address_links = soup.find_all('a', href=re.compile(r'/list\.dc\?query='))
            
            # 주소 부분만 추출
            for link in address_links:
                text = link.get_text(strip=True)
                
                # 주소 관련 키워드가 있는 경우만
                if any(keyword in text for keyword in ['서울', '특별시', '광역시', '시', '구', '동', '로', '길', '번지']):
                    # 맛집, 검색하기 등의 키워드가 포함된 경우 제외
                    if not any(exclude in text for exclude in ['맛집', '검색', '음식', '랭킹', '추천']):
                        address_parts.append(text)
            
            # 2. 중복 제거하면서 순서대로 주소 조합
            if address_parts:
                # 중복 제거 (순서 유지)
                seen = set()
                unique_parts = []
                for part in address_parts:
                    if part not in seen and len(part) > 1:
                        seen.add(part)
                        unique_parts.append(part)
                
                # 주소 부분들을 합쳐서 완전한 주소 만들기
                # 서울특별시, 강남구, 테헤란로 -> 서울특별시 강남구 테헤란로
                full_address = ""
                
                # 시/도 찾기
                for part in unique_parts:
                    if any(keyword in part for keyword in ['서울특별시', '서울시', '서울', '경기도', '인천광역시']):
                        full_address = part
                        break
                
                # 구 찾기
                for part in unique_parts:
                    if '구' in part and part not in full_address:
                        if full_address:
                            full_address += " " + part
                        else:
                            full_address = part
                
                # 동/로/길 찾기
                for part in unique_parts:
                    if any(keyword in part for keyword in ['동', '로', '길']) and part not in full_address:
                        if full_address:
                            full_address += " " + part
                        else:
                            full_address = part
                
                # 번지/번호 찾기
                for part in unique_parts:
                    if re.search(r'\d+', part) and part not in full_address:
                        if full_address:
                            full_address += " " + part
                
                address_info['address'] = full_address.strip()
            
            # 3. 주소가 없거나 불완전한 경우 백업 방법 시도
            if not address_info['address'] or len(address_info['address']) < 10:
                # 주소 관련 요소 직접 찾기
                address_selectors = [
                    '.BasicInfo__Address',
                    '.Info__Address', 
                    '.address',
                    '.location',
                    '[class*="addr"]',
                    '[class*="address"]'
                ]
                
                for selector in address_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        text = elem.get_text(strip=True)
                        # HTML 태그 제거
                        text = re.sub(r'<[^>]+>', '', text)
                        # 주소 패턴 확인
                        if text and any(keyword in text for keyword in ['서울', '구', '동', '로', '길']):
                            # 불필요한 텍스트 제거
                            text = re.sub(r'(맛집|검색하기|음식|랭킹|추천).*', '', text)
                            text = text.strip()
                            if len(text) > len(address_info.get('address', '')):
                                address_info['address'] = text
                                break
            
            # 4. 주소 최종 정리
            if address_info['address']:
                # 연속된 공백 제거
                address_info['address'] = ' '.join(address_info['address'].split())
                
                # HTML 엔티티 제거
                address_info['address'] = address_info['address'].replace('&nbsp;', ' ')
                address_info['address'] = address_info['address'].replace('&amp;', '&')
                
                # 도로명 주소인지 확인
                if any(keyword in address_info['address'] for keyword in ['로', '길']):
                    address_info['road_address'] = address_info['address']
                else:
                    address_info['basic_address'] = address_info['address']
            
            logger.info(f"최종 주소: {address_info['address']}")
            
        except Exception as e:
            logger.error(f"주소 정보 추출 실패: {e}")
        
        return address_info
    
    def _extract_refill_prices_from_operation_info(self, soup: BeautifulSoup) -> List[Dict]:
        """운영 정보에서 무한리필 가격 정보 추출 (개선된 버전)"""
        price_items = []
        
        try:
            logger.info("🔍 운영 정보에서 무한리필 가격 추출 시작...")
            
            # 1. 메뉴정보 섹션 직접 찾기
            menu_section = None
            
            # 메뉴정보 텍스트가 포함된 요소 찾기
            menu_headers = soup.find_all(text=re.compile(r'메뉴\s*정보', re.IGNORECASE))
            for header in menu_headers:
                parent = header.parent
                if parent:
                    # 메뉴정보 섹션의 부모 요소 찾기
                    menu_section = parent.find_parent(['div', 'section', 'article'])
                    if menu_section:
                        break
            
            # 2. 메뉴정보 섹션이 없으면 전체 페이지에서 검색
            if not menu_section:
                menu_section = soup
            
            # 3. 가격 정보 추출
            all_text = menu_section.get_text()
            
            # 4. 가격 정보 파싱
            price_items = self._extract_refill_prices_from_text(all_text)
            
            # 5. 추가로 HTML 구조에서 직접 추출 시도
            if len(price_items) == 0:
                # 가격 요소를 포함하는 요소들 찾기
                price_elements = menu_section.find_all(['div', 'span', 'p'], 
                                                     text=re.compile(r'\d{1,3}(?:,\d{3})*\s*원'))
                
                for element in price_elements:
                    price_text = element.get_text()
                    price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', price_text)
                    
                    if price_match:
                        price = price_match.group(1)
                        
                        # 이전 형제 요소에서 메뉴명 찾기
                        prev_sibling = element.find_previous_sibling()
                        if prev_sibling:
                            menu_text = prev_sibling.get_text()
                            if '무한리필' in menu_text or '추천' in menu_text:
                                menu_name = re.sub(r'^[a-z]\s+', '', menu_text.strip())
                                
                                if len(menu_name) >= 3:
                                    price_num = int(price.replace(',', ''))
                                    if 5000 <= price_num <= 50000:
                                        price_items.append({
                                            'name': menu_name,
                                            'price': f"{price}원",
                                            'price_numeric': price_num
                                        })
            
            # 6. 정렬 및 중복 제거
            if price_items:
                # 가격 순 정렬
                price_items.sort(key=lambda x: x['price_numeric'])
                
                # 중복 제거 (이름 기준)
                unique_items = []
                seen_names = set()
                for item in price_items:
                    if item['name'] not in seen_names:
                        unique_items.append(item)
                        seen_names.add(item['name'])
                price_items = unique_items
            
            logger.info(f"텍스트에서 {len(price_items)}개 무한리필 가격 추출")
            
            # 추출된 가격 정보 로깅
            for item in price_items:
                logger.debug(f"가격: {item['name']} - {item['price']}")
            
        except Exception as e:
            logger.error(f"운영 정보에서 무한리필 가격 추출 실패: {e}")
        
        return price_items
    
    def _extract_refill_prices_from_text(self, text: str) -> List[Dict]:
        """텍스트에서 무한리필 가격 패턴 추출"""
        price_items = []
        
        try:
            # 실제 다이닝코드 페이지의 메뉴 정보 패턴에 맞는 정규식
            patterns = [
                # 패턴 1: 다이닝코드 메뉴 정보 형식 (예: "a 돼지모듬 무한리필 추천\n17,900원")
                r'([a-z]\s+[가-힣\s\w()]+?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?(?:추천|할인)?)\s*\n?\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 2: 시간대별 가격 (예: "평일 15:00 이전 입장기준 추천 17,900원")
                r'([가-힣\s\w()]+?(?:평일|주말|공휴일|이전|이후|저녁|점심|오전|오후)[가-힣\s\w()]*?(?:추천|할인|무한리필|입장기준))\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 3: 연령대별 가격 (예: "무한리필 초등할인(4~6학년) 추천 16,000원")
                r'([가-힣\s\w()]+?(?:초등|미취학|성인|어린이|학생)[가-힣\s\w()]*?(?:추천|할인|무한리필))\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 4: 기본 무한리필 가격
                r'([가-힣\s\w()]+?(?:무한리필|뷔페|셀프바)[가-힣\s\w()]*?(?:추천|할인)?)\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 5: 메뉴명 + 가격 (콜론 구분)
                r'([가-힣\s\w()]+?(?:추천|할인|무한리필|입장기준))\s*[:：]\s*(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 패턴 6: 줄바꿈으로 구분된 가격
                r'([가-힣\s\w()]+?(?:추천|할인|무한리필|입장기준))\s*\n\s*(\d{1,3}(?:,\d{3})*)\s*원'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    menu_name = match[0].strip()
                    price = match[1].strip()
                    
                    # 메뉴명 정리 (앞의 알파벳 제거)
                    menu_name = re.sub(r'^[a-z]\s+', '', menu_name)
                    
                    # 유효성 검사
                    if (len(menu_name) >= 3 and len(menu_name) <= 50 and 
                        price.replace(',', '').isdigit()):
                        
                        # 리뷰나 기타 정보 제외
                        if any(exclude in menu_name for exclude in ['리뷰', '후기', '평점', '별점', '방문', '블로그']):
                            continue
                        
                        # 가격 범위 검증 (5,000원 ~ 50,000원)
                        price_num = int(price.replace(',', ''))
                        if 5000 <= price_num <= 50000:
                            price_items.append({
                                'name': menu_name,
                                'price': f"{price}원",
                                'price_numeric': price_num
                            })
            
            # 추가 패턴: 테이블 형태의 가격 정보
            table_patterns = [
                # 탭으로 구분된 형태
                r'([가-힣\s\w()]+?(?:추천|할인|무한리필|입장기준))\s+(\d{1,3}(?:,\d{3})*)\s*원',
                
                # 대시로 구분된 형태
                r'([가-힣\s\w()]+?(?:추천|할인|무한리필|입장기준))\s*-\s*(\d{1,3}(?:,\d{3})*)\s*원'
            ]
            
            for pattern in table_patterns:
                matches = re.findall(pattern, text, re.MULTILINE)
                
                for match in matches:
                    menu_name = match[0].strip()
                    price = match[1].strip()
                    
                    # 메뉴명 정리
                    menu_name = re.sub(r'^[a-z]\s+', '', menu_name)
                    
                    if (len(menu_name) >= 3 and len(menu_name) <= 50 and 
                        price.replace(',', '').isdigit()):
                        
                        # 중복 체크
                        if not any(item['name'] == menu_name for item in price_items):
                            price_num = int(price.replace(',', ''))
                            if 5000 <= price_num <= 50000:
                                price_items.append({
                                    'name': menu_name,
                                    'price': f"{price}원",
                                    'price_numeric': price_num
                                })
            
            # 정렬 (가격 순)
            price_items.sort(key=lambda x: x['price_numeric'])
            
            logger.info(f"텍스트에서 {len(price_items)}개 무한리필 가격 추출")
            
        except Exception as e:
            logger.error(f"텍스트에서 무한리필 가격 추출 실패: {e}")
        
        return price_items

    def get_stats(self) -> Dict:
        """크롤링 및 이미지 처리 통계 반환"""
        return self.stats.copy()
    
    def print_stats(self):
        """크롤링 통계 출력"""
        print("\n📊 크롤링 통계:")
        print(f"   전체 요청: {self.stats['total_requests']}")
        print(f"   성공 요청: {self.stats['successful_requests']}")
        print(f"   실패 요청: {self.stats['failed_requests']}")
        print(f"   이미지 처리: {self.stats['images_processed']}")
        print(f"   Storage 업로드: {self.stats['images_uploaded']}")
        
        if self.stats['images_processed'] > 0:
            upload_rate = (self.stats['images_uploaded'] / self.stats['images_processed']) * 100
            print(f"   업로드 성공률: {upload_rate:.1f}%")
    
    def close(self):
        """리소스 정리 및 통계 출력"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver 종료 완료")
            except Exception as e:
                logger.error(f"WebDriver 종료 중 오류: {e}")
        
        # 이미지 매니저 통계 출력
        if self.image_manager:
            try:
                storage_stats = self.image_manager.get_storage_stats()
                print("\n📈 이미지 저장소 통계:")
                for key, value in storage_stats.items():
                    print(f"   {key}: {value}")
            except Exception as e:
                logger.warning(f"저장소 통계 조회 실패: {e}")
        
        # 크롤링 통계 출력
        self.print_stats()

# 테스트 실행 함수
def test_crawling():
    """기본 크롤링 테스트 (지역명 포함 키워드 사용)"""
    crawler = DiningCodeCrawler()
    
    try:
        # 1. 목록 수집 테스트 (지역명 포함 키워드 사용)
        region_name = config.REGIONS[config.TEST_REGION]["name"]
        test_keyword = f"{region_name} 무한리필"  # 지역명 포함
        logger.info(f"테스트 키워드: {test_keyword}")
        
        stores = crawler.get_store_list(test_keyword, config.TEST_RECT)
        logger.info(f"총 {len(stores)}개 가게 발견")
        
        if stores:
            # 2. 첫 번째 가게 상세 정보 수집 테스트
            first_store = stores[0]
            logger.info(f"테스트 대상 가게: {first_store.get('name')}")
            logger.info(f"가게 ID: {first_store.get('diningcode_place_id')}")
            
            detailed_store = crawler.get_store_detail(first_store)
            
            logger.info("=== 테스트 결과 ===")
            for key, value in detailed_store.items():
                logger.info(f"{key}: {value}")
                
            # CSV로 저장
            df = pd.DataFrame([detailed_store])
            df.to_csv('data/test_crawling_result.csv', index=False, encoding='utf-8-sig')
            logger.info("테스트 결과를 data/test_crawling_result.csv에 저장")
            
        else:
            logger.warning(f"'{test_keyword}' 키워드로 검색된 가게가 없습니다.")
            logger.info("다른 키워드를 시도해보겠습니다...")
            
            # 백업 키워드로 재시도
            backup_keyword = "강남 고기무한리필"
            logger.info(f"백업 키워드: {backup_keyword}")
            stores = crawler.get_store_list(backup_keyword, config.TEST_RECT)
            
            if stores:
                first_store = stores[0]
                detailed_store = crawler.get_store_detail(first_store)
                logger.info(f"백업 키워드로 {len(stores)}개 가게 발견")
            else:
                logger.warning("백업 키워드로도 가게를 찾을 수 없습니다.")
            
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    test_crawling()