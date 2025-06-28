import time
import random
import logging
import os
import re
import json
from typing import List, Dict, Optional
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
                        # 번호 제거 (예: "1. 육미제당" -> "육미제당")
                        name_text = title_elem.get_text(strip=True)
                        if '. ' in name_text:
                            name_text = name_text.split('. ', 1)[1]
                        
                        # 지점명 분리
                        place_elem = title_elem.find('span', class_='Info__Title__Place')
                        if place_elem:
                            store_info['branch'] = place_elem.get_text(strip=True)
                            # 지점명 제거하여 순수 가게명 추출
                            store_info['name'] = name_text.replace(store_info['branch'], '').strip()
                        else:
                            store_info['name'] = name_text
                    
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
            
            # 3. 영업시간 정보 추출 (강화)
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
            
            # 7. 좌표 정보 추출 (중요!)
            coordinate_info = self._extract_coordinate_info(soup)
            detail_info.update(coordinate_info)
            
            # 8. 무한리필 관련 정보 추출 (강화)
            refill_info = self._extract_refill_info(soup)
            detail_info.update(refill_info)
            
            logger.info(f"상세 정보 수집 완료: {detail_info.get('name', 'Unknown')}")
            
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
            refill_keywords = ['무한리필', '무제한', '리필', '셀프바']
            all_text = soup.get_text()
            
            for keyword in refill_keywords:
                if keyword in all_text:
                    # 키워드 주변 텍스트 추출
                    pattern = rf'.{{0,20}}{keyword}.{{0,20}}'
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    for match in matches[:3]:  # 최대 3개까지
                        clean_match = re.sub(r'\s+', ' ', match.strip())
                        if clean_match not in menu_info['signature_menu']:
                            menu_info['signature_menu'].append(clean_match)
            
            logger.info(f"메뉴 정보 추출: {len(menu_info['menu_items'])}개 메뉴, {len(menu_info['signature_menu'])}개 대표메뉴")
            
        except Exception as e:
            logger.error(f"메뉴 정보 추출 실패: {e}")
        
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

    def _extract_hours_info(self, soup: BeautifulSoup) -> Dict:
        """영업시간 정보 추출 (강화)"""
        hours_info = {
            'open_hours': '',
            'open_hours_raw': '',
            'break_time': '',
            'last_order': '',
            'holiday': ''
        }
        
        try:
            # 영업시간 관련 요소 찾기
            time_elements = soup.find_all(['div', 'span', 'td'], class_=re.compile(r'time|hour|open|close'))
            
            time_texts = []
            for elem in time_elements:
                text = elem.get_text(strip=True)
                if text and any(keyword in text for keyword in ['시', ':', '영업', '휴무', '브레이크']):
                    time_texts.append(text)
            
            # 영업시간 패턴 매칭
            for text in time_texts:
                # 영업시간 패턴
                if re.search(r'\d{1,2}:\d{2}.*\d{1,2}:\d{2}', text):
                    if not hours_info['open_hours']:
                        hours_info['open_hours'] = text
                    hours_info['open_hours_raw'] += text + ' | '
                
                # 브레이크타임 패턴
                if '브레이크' in text or 'break' in text.lower():
                    hours_info['break_time'] = text
                
                # 라스트오더 패턴
                if '라스트' in text or 'last' in text.lower() or '주문마감' in text:
                    hours_info['last_order'] = text
                
                # 휴무일 패턴
                if '휴무' in text or '정기휴일' in text:
                    hours_info['holiday'] = text
            
            # 정리
            hours_info['open_hours_raw'] = hours_info['open_hours_raw'].rstrip(' | ')
            
            logger.info(f"영업시간 정보 추출 완료")
            
        except Exception as e:
            logger.error(f"영업시간 정보 추출 실패: {e}")
        
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
                    contact_info['phone_number'] = matches[0]
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