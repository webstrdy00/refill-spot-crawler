import time
import random
import logging
import os
import re
import json
import urllib.parse
from typing import List, Dict, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
import config


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
    def __init__(self):
        self.driver = None
        self.wait = None
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
        user_agent = random.choice(config.USER_AGENTS)
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
        min_d = min_delay or config.MIN_DELAY
        max_d = max_delay or config.MAX_DELAY
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
                        
                        # 지점명 분리
                        place_elem = title_elem.find('span', class_='Info__Title__Place')
                        if place_elem:
                            store_info['branch'] = place_elem.get_text(strip=True)
                            # 지점명 제거하여 순수 가게명 추출
                            store_info['name'] = name_text.replace(store_info['branch'], '').strip()
                        else:
                            store_info['name'] = name_text.strip()
                    
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
        """실제 상세 정보 추출 로직"""
        detail_info = store_info.copy()
        
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
                # 여러 가능한 요소 중 하나라도 로드되면 계속 진행
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.find_elements(By.TAG_NAME, "body") and 
                    len(driver.page_source) > 1000 and
                    "diningcode" in driver.current_url.lower()
                )
                # 추가 로딩 시간
                time.sleep(2)
            except TimeoutException:
                logger.warning("상세 페이지 로딩 타임아웃")
                time.sleep(3)
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 1. 메뉴 정보 추출 (강화)
            menu_info = self._extract_menu_info(soup)
            detail_info.update(menu_info)
            
            # 2. 가격 정보 추출 (강화)
            price_info = self._extract_price_info(soup)
            detail_info.update(price_info)
            
            # 3. 영업시간 정보 추출 (날짜별을 요일별로 변환)
            hours_info = self._extract_hours_info(soup)
            detail_info.update(hours_info)
            
            # 4. 이미지 URL 수집 (강화)
            image_info = self._extract_image_info(soup)
            detail_info.update(image_info)
            
            # 5. 리뷰 및 설명 정보 추출 (강화)
            review_info = self._extract_review_info(soup)
            detail_info.update(review_info)
            
            # 6. 연락처 정보 추출 (강화)
            contact_info = self._extract_contact_info(soup)
            detail_info.update(contact_info)
            
            # 7. 좌표 및 주소 정보 추출 (중요!)
            coordinate_info = self._extract_coordinate_info(soup)
            detail_info.update(coordinate_info)
            
            # 8. 주소 정보 추가 추출 (개선)
            address_info = self._extract_address_info(soup)
            # 주소가 없거나 coordinate_info의 주소가 더 상세한 경우 업데이트
            if address_info.get('address') and (not detail_info.get('address') or len(address_info['address']) > len(detail_info.get('address', ''))):
                detail_info['address'] = address_info['address']
            if address_info.get('basic_address'):
                detail_info['basic_address'] = address_info['basic_address']
            if address_info.get('road_address'):
                detail_info['road_address'] = address_info['road_address']
            
            # 9. 무한리필 관련 정보 추출 (강화)
            refill_info = self._extract_refill_info(soup)
            detail_info.update(refill_info)
            
            logger.info(f"상세 정보 수집 완료: {detail_info.get('name', 'Unknown')} - 주소: {detail_info.get('address', 'N/A')}")
            
        except Exception as e:
            logger.error(f"상세 정보 수집 중 오류: {e}")
            # 기본 정보라도 반환
            
        return detail_info

    def _extract_menu_info(self, soup: BeautifulSoup) -> Dict:
        """메뉴 정보 추출 (강화)"""
        menu_info = {
            'menu_items': [],
            'menu_categories': [],
            'signature_menu': []
        }
        
        try:
            # 메뉴 섹션 찾기
            menu_sections = soup.find_all(['div', 'section'], class_=re.compile(r'menu|Menu'))
            
            for section in menu_sections:
                # 메뉴 아이템 추출
                menu_items = section.find_all(['div', 'li'], class_=re.compile(r'menu-item|menuitem|item'))
                
                for item in menu_items:
                    menu_name = item.find(['span', 'div', 'h3', 'h4'], class_=re.compile(r'name|title'))
                    menu_price = item.find(['span', 'div'], class_=re.compile(r'price|cost|amount'))
                    
                    if menu_name:
                        menu_data = {
                            'name': menu_name.get_text(strip=True),
                            'price': menu_price.get_text(strip=True) if menu_price else '',
                        }
                        menu_info['menu_items'].append(menu_data)
            
            # 대표 메뉴 추출
            signature_elements = soup.find_all(['div', 'span'], class_=re.compile(r'signature|recommend|popular'))
            for elem in signature_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 2:
                    menu_info['signature_menu'].append(text)
            
            # 무한리필 관련 메뉴 키워드 검색
            refill_keywords = ['무한리필', '무제한', '셀프바']
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
        
        return menu_info

    def _extract_price_info(self, soup: BeautifulSoup) -> Dict:
        """가격 정보 추출 (강화)"""
        price_info = {
            'price_range': '',
            'average_price': '',
            'price_details': []
        }
        
        try:
            # 가격 관련 요소 찾기
            price_elements = soup.find_all(['span', 'div', 'td'], class_=re.compile(r'price|cost|amount|won'))
            
            prices = []
            for elem in price_elements:
                text = elem.get_text(strip=True)
                # 가격 패턴 매칭 (원, 만원 등)
                price_matches = re.findall(r'[\d,]+\s*[만]?원', text)
                prices.extend(price_matches)
            
            if prices:
                # 중복 제거 및 정리
                unique_prices = list(set(prices))
                price_info['price_details'] = unique_prices[:10]  # 최대 10개
                
                # 가격 범위 추정
                numeric_prices = []
                for price in unique_prices:
                    try:
                        # 숫자만 추출하여 변환
                        num_str = re.sub(r'[^\d,]', '', price).replace(',', '')
                        if num_str:
                            num = int(num_str)
                            if '만원' in price:
                                num *= 10000
                            numeric_prices.append(num)
                    except:
                        continue
                
                if numeric_prices:
                    min_price = min(numeric_prices)
                    max_price = max(numeric_prices)
                    avg_price = sum(numeric_prices) // len(numeric_prices)
                    
                    price_info['price_range'] = f"{min_price:,}원 ~ {max_price:,}원"
                    price_info['average_price'] = f"{avg_price:,}원"
            
            logger.info(f"가격 정보 추출: {len(price_info['price_details'])}개 가격 정보")
            
        except Exception as e:
            logger.error(f"가격 정보 추출 실패: {e}")
        
        return price_info

    def _extract_hours_info(self, detail_soup: BeautifulSoup) -> Dict[str, Any]:
        """영업시간, 브레이크타임, 라스트오더 정보 추출 (다이닝코드 구조 맞춤)"""
        hours_info = {
            'open_hours': '',
            'holiday': '',
            'break_time': '',
            'last_order': ''
        }
        
        try:
            # 1단계: 영업시간이 포함된 리스트 아이템 찾기 (다이닝코드 구조)
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
            
            # 2단계: Selenium으로 토글 버튼 클릭하여 상세 정보 수집
            expanded_hours_text = ""
            if self.driver:
                try:
                    # 영업시간 토글 버튼 찾기
                    toggle_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button')
                    
                    for button in toggle_buttons:
                        try:
                            # 버튼 근처에 영업시간 관련 텍스트가 있는지 확인
                            parent = button.find_element(By.XPATH, '..')
                            parent_text = parent.text
                            
                            if any(keyword in parent_text for keyword in ['영업시간', '라스트오더', '라스트 오더']):
                                # 토글 아이콘이 있는 버튼인지 확인
                                imgs = button.find_elements(By.TAG_NAME, 'img')
                                for img in imgs:
                                    alt_text = img.get_attribute('alt') or ''
                                    if '토글' in alt_text or 'toggle' in alt_text.lower():
                                        logger.info(f"영업시간 토글 버튼 클릭 시도")
                                        self.driver.execute_script("arguments[0].click();", button)
                                        time.sleep(2)  # 토글 애니메이션 대기
                                        
                                        # 업데이트된 페이지 소스로 다시 파싱
                                        updated_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                        
                                        # 확장된 영업시간 정보 찾기 (개선된 방법)
                                        # 1차: 원래 영업시간 섹션에서 확장된 내용 찾기
                                        updated_list_items = updated_soup.find_all('li')
                                        
                                        for updated_li in updated_list_items:
                                            updated_text = updated_li.get_text()
                                            # 날짜별 영업시간 패턴이 있는지 확인
                                            if re.search(r'\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)', updated_text):
                                                # 블로그 리뷰나 기타 내용이 아닌 실제 영업시간 정보인지 확인
                                                if not any(word in updated_text for word in ['블로그', '후기', '리뷰', '방문', '추천', '맛집', '오픈런', '웨이팅', '테이블링']):
                                                    # 영업시간 관련 키워드가 포함되어 있는지 확인
                                                    if any(keyword in updated_text for keyword in ['영업시간', '라스트오더', '휴무일', '휴무']):
                                                        expanded_hours_text = updated_text
                                                        logger.info(f"확장된 영업시간 정보 수집: {expanded_hours_text[:200]}...")
                                                        break
                                        
                                        # 2차: 직접 영업시간 패턴 검색
                                        if not expanded_hours_text:
                                            # 페이지 전체에서 날짜별 영업시간 패턴 추출
                                            page_text = updated_soup.get_text()
                                            
                                            # 날짜별 영업시간/휴무 패턴 찾기
                                            date_patterns = [
                                                r'(\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)\s*영업시간:\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}[^가-힣]*?라스트오더:\s*\d{1,2}:\d{2})',
                                                r'(\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)\s*휴무일?)',
                                                r'(\d{1,2}월\s*\d{1,2}일\s*\([월화수목금토일]\)\s*영업시간:\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})'
                                            ]
                                            
                                            found_dates = []
                                            for pattern in date_patterns:
                                                matches = re.findall(pattern, page_text)
                                                found_dates.extend(matches)
                                            
                                            if found_dates:
                                                expanded_hours_text = ' '.join(found_dates)
                                                logger.info(f"패턴 매칭으로 영업시간 정보 수집: {expanded_hours_text[:200]}...")
                                        
                                        break
                                break
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    logger.warning(f"토글 버튼 클릭 실패: {e}")
            
            # 3단계: 텍스트 파싱
            hours_text = expanded_hours_text if expanded_hours_text else hours_section.get_text(strip=True)
            logger.info(f"파싱할 영업시간 텍스트: {hours_text[:300]}...")
            
            # 날짜별 영업시간을 요일별로 변환
            day_hours = {}
            holiday_days = []
            
            # 라스트오더 정보 추출 (전체적으로 적용되는 것)
            last_order_patterns = [
                r'라스트\s*오더\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'라스트오더\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'L\.?O\.?\s*[:：]?\s*(\d{1,2}:\d{2})',
                r'주문\s*마감\s*[:：]?\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in last_order_patterns:
                matches = re.findall(pattern, hours_text)
                if matches:
                    hours_info['last_order'] = matches[0]
                    logger.info(f"라스트오더 추출: {hours_info['last_order']}")
                    break
            
            # 브레이크타임 정보 추출
            break_patterns = [
                r'브레이크\s*타임?\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
                r'브레이크\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
                r'휴게시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in break_patterns:
                matches = re.findall(pattern, hours_text)
                if matches:
                    start_time, end_time = matches[0]
                    hours_info['break_time'] = f"{start_time}-{end_time}"
                    logger.info(f"브레이크타임 추출: {hours_info['break_time']}")
                    break
            
            # 날짜별 영업시간 패턴 매칭
            # 예: "6월 29일(일) 휴무일", "6월 30일(월) 영업시간: 11:30 - 21:00 라스트오더: 20:20"
            date_patterns = [
                # 휴무일 패턴
                r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*휴무',
                # 영업시간 패턴 (라스트오더 포함)
                r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*영업시간:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})(?:\s*라스트오더:\s*(\d{1,2}:\d{2}))?',
                # 간단한 영업시간 패턴
                r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, hours_text)
                for match in matches:
                    if len(match) == 2:  # 휴무일
                        date, day = match
                        holiday_days.append(day)
                        logger.info(f"휴무일 발견: {day}요일")
                    elif len(match) >= 4:  # 영업시간
                        if len(match) == 5:  # 라스트오더 포함
                            date, day, start_time, end_time, last_order = match
                            if last_order:
                                day_hours[day] = f"{start_time}-{end_time} (L.O: {last_order})"
                            else:
                                day_hours[day] = f"{start_time}-{end_time}"
                        else:  # 기본 영업시간
                            date, day, start_time, end_time = match[:4]
                            day_hours[day] = f"{start_time}-{end_time}"
                        logger.info(f"영업시간 발견: {day}요일 {day_hours[day]}")
            
            # 기본 영업시간 패턴도 확인 (토글되지 않은 경우)
            basic_patterns = [
                r'영업시간:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
                r'오늘.*?영업시간:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
            ]
            
            for pattern in basic_patterns:
                matches = re.findall(pattern, hours_text)
                if matches and not day_hours:  # 요일별 정보가 없을 때만
                    start_time, end_time = matches[0]
                    # 오늘 요일 추정 (실제로는 현재 날짜 기준)
                    import datetime
                    today = datetime.datetime.now()
                    weekdays = ['월', '화', '수', '목', '금', '토', '일']
                    today_korean = weekdays[today.weekday()]
                    
                    basic_hours = f"{start_time}-{end_time}"
                    if hours_info['last_order']:
                        basic_hours += f" (L.O: {hours_info['last_order']})"
                    
                    day_hours[today_korean] = basic_hours
                    logger.info(f"기본 영업시간 적용: {today_korean}요일 {basic_hours}")
                    break
            
            # 패턴 분석 및 누락된 요일 보완
            all_days = ['월', '화', '수', '목', '금', '토', '일']
            collected_days = set(day_hours.keys())
            missing_days = [d for d in all_days if d not in collected_days and d not in holiday_days]
            
            logger.info(f"수집된 요일: {list(collected_days)}, 휴무일: {holiday_days}, 누락: {missing_days}")
            
            # 패턴 분석하여 누락된 요일 보완
            if len(day_hours) > 0 and missing_days:
                # 주중/주말 패턴 분석
                weekday_hours = []
                weekend_hours = []
                
                for day in ['월', '화', '수', '목', '금']:
                    if day in day_hours:
                        weekday_hours.append(day_hours[day])
                
                for day in ['토', '일']:
                    if day in day_hours:
                        weekend_hours.append(day_hours[day])
                
                # 주중 패턴 적용
                if weekday_hours and len(set(weekday_hours)) == 1:  # 모든 주중이 같은 시간
                    common_weekday = weekday_hours[0]
                    for day in ['월', '화', '수', '목', '금']:
                        if day in missing_days:
                            day_hours[day] = common_weekday
                            logger.info(f"{day}요일에 주중 패턴 적용: {common_weekday}")
                
                # 주말 패턴 적용
                if weekend_hours and len(set(weekend_hours)) == 1:  # 모든 주말이 같은 시간
                    common_weekend = weekend_hours[0]
                    for day in ['토', '일']:
                        if day in missing_days and day not in holiday_days:
                            day_hours[day] = common_weekend
                            logger.info(f"{day}요일에 주말 패턴 적용: {common_weekend}")
            
            # 최종 영업시간 문자열 생성
            if day_hours:
                hours_parts = []
                days_order = ['월', '화', '수', '목', '금', '토', '일']
                
                for day in days_order:
                    if day in day_hours:
                        hours_parts.append(f"{day}: {day_hours[day]}")
                    elif day in holiday_days:
                        hours_parts.append(f"{day}: 휴무")
                
                hours_info['open_hours'] = ', '.join(hours_parts)
            
            # 휴무일 설정
            if holiday_days:
                unique_holidays = list(set(holiday_days))
                if len(unique_holidays) == 1:
                    hours_info['holiday'] = f"매주 {unique_holidays[0]} 휴무"
                else:
                    hours_info['holiday'] = ', '.join(unique_holidays) + ' 휴무'
            elif len(day_hours) == 7:
                hours_info['holiday'] = '연중무휴'
            
            # 24시간 영업 체크
            if any(keyword in hours_text for keyword in ['24시간', '24시', '24HOUR', '24H']):
                hours_info['open_hours'] = '24시간 영업'
                hours_info['holiday'] = '연중무휴'
            
            logger.info(f"최종 영업시간: {hours_info['open_hours']}")
            logger.info(f"휴무일: {hours_info['holiday']}")
            logger.info(f"브레이크타임: {hours_info['break_time']}")
            logger.info(f"라스트오더: {hours_info['last_order']}")
            
        except Exception as e:
            logger.error(f"영업시간 추출 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return hours_info

    def _extract_image_info(self, soup: BeautifulSoup) -> Dict:
        """이미지 URL 수집 (강화)"""
        image_info = {
            'image_urls': [],
            'main_image': '',
            'menu_images': [],
            'interior_images': []
        }
        
        try:
            # 모든 이미지 요소 찾기
            img_elements = soup.find_all('img')
            
            for img in img_elements:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src and src.startswith('http'):
                    # 이미지 분류
                    alt_text = img.get('alt', '').lower()
                    class_name = ' '.join(img.get('class', [])).lower()
                    
                    if any(keyword in alt_text + class_name for keyword in ['menu', '메뉴']):
                        image_info['menu_images'].append(src)
                    elif any(keyword in alt_text + class_name for keyword in ['interior', '내부', '인테리어']):
                        image_info['interior_images'].append(src)
                    elif any(keyword in alt_text + class_name for keyword in ['main', '대표', 'logo']):
                        if not image_info['main_image']:
                            image_info['main_image'] = src
                    
                    image_info['image_urls'].append(src)
            
            # 중복 제거
            image_info['image_urls'] = list(set(image_info['image_urls']))[:20]  # 최대 20개
            image_info['menu_images'] = list(set(image_info['menu_images']))[:10]
            image_info['interior_images'] = list(set(image_info['interior_images']))[:10]
            
            logger.info(f"이미지 정보 추출: 총 {len(image_info['image_urls'])}개")
            
        except Exception as e:
            logger.error(f"이미지 정보 추출 실패: {e}")
        
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
        """무한리필 관련 정보 추출 (강화)"""
        refill_info = {
            'refill_items': [],
            'refill_type': '',
            'refill_conditions': '',
            'is_confirmed_refill': False
        }
        
        try:
            all_text = soup.get_text()
            
            # 무한리필 아이템 추출
            refill_patterns = [
                r'무한리필\s*[:：]?\s*([^.\n]{1,30})',
                r'무제한\s*[:：]?\s*([^.\n]{1,30})',
                r'리필\s*가능\s*[:：]?\s*([^.\n]{1,30})'
            ]
            
            items = []
            for pattern in refill_patterns:
                matches = re.findall(pattern, all_text)
                items.extend(matches)
            
            # 정리 및 필터링
            cleaned_items = []
            for item in items:
                item = item.strip()
                if item and len(item) > 2 and len(item) < 50:
                    cleaned_items.append(item)
            
            refill_info['refill_items'] = list(set(cleaned_items))[:10]
            
            # 무한리필 확인
            refill_keywords = ['무한리필', '무제한', '셀프바']
            for keyword in refill_keywords:
                if keyword in all_text:
                    refill_info['is_confirmed_refill'] = True
                    break
            
            # 리필 타입 추정
            if '고기' in all_text:
                refill_info['refill_type'] = '고기무한리필'
            elif '초밥' in all_text or '회' in all_text:
                refill_info['refill_type'] = '초밥뷔페'
            elif '뷔페' in all_text:
                refill_info['refill_type'] = '뷔페'
            else:
                refill_info['refill_type'] = '무한리필'
            
            logger.info(f"무한리필 정보 추출: {len(refill_info['refill_items'])}개 아이템")
            
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
    
    def close(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver 종료")

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