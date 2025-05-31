import time
import random
import logging
import os
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
import config
import re

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
    
    def random_delay(self):
        """랜덤 지연"""
        delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
        time.sleep(delay)
        
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
                # localStorage에서 listData 추출
                list_data = self.driver.execute_script("return localStorage.getItem('listData');")
                if list_data:
                    import json
                    data = json.loads(list_data)
                    poi_list = data.get('poi_section', {}).get('list', [])
                    
                    logger.info(f"JavaScript에서 {len(poi_list)}개 가게 데이터 추출")
                    
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
                        logger.info(f"JavaScript에서 총 {len(stores)}개 가게 정보 수집 완료")
                        return stores
                        
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
                        'rect_area': rect
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
    
    def get_store_detail(self, store_info: Dict) -> Dict:
        """가게 상세 정보 수집"""
        detail_url = store_info['detail_url']
        if not detail_url.startswith('http'):
            detail_url = f"https://www.diningcode.com{detail_url}"
            
        try:
            logger.info(f"상세 페이지 크롤링: {store_info['name']}")
            self.driver.get(detail_url)
            self.random_delay()
            
            # 페이지 로딩 대기
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(5)  # 추가 로딩 시간
            
            # 페이지 소스에서 좌표 정보 추출
            page_source = self.driver.page_source
            
            lat = lng = None
            
            # 좌표 패턴 매칭
            lat_patterns = [
                r'"lat":\s*([0-9.]+)',
                r'"latitude":\s*([0-9.]+)',
                r'lat:\s*([0-9.]+)',
                r'latitude:\s*([0-9.]+)'
            ]
            
            lng_patterns = [
                r'"lng":\s*([0-9.]+)',
                r'"longitude":\s*([0-9.]+)',
                r'lng:\s*([0-9.]+)',
                r'longitude:\s*([0-9.]+)'
            ]
            
            # 위도 찾기
            for pattern in lat_patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    for match in matches:
                        coord_val = float(match)
                        if 37.0 <= coord_val <= 38.0:  # 서울 위도 범위
                            lat = coord_val
                            break
                if lat:
                    break
            
            # 경도 찾기
            for pattern in lng_patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    for match in matches:
                        coord_val = float(match)
                        if 126.0 <= coord_val <= 128.0:  # 서울 경도 범위
                            lng = coord_val
                            break
                if lng:
                    break
            
            # HTML에서 추가 정보 추출
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 전화번호 추출
            phone = ""
            # tel 클래스 확인
            tel_elem = soup.find(class_='tel')
            if tel_elem:
                phone = tel_elem.get_text(strip=True)
            else:
                # tel: 링크 확인
                tel_link = soup.find('a', href=lambda x: x and x.startswith('tel:'))
                if tel_link:
                    phone = tel_link.get_text(strip=True)
            
            # 주소 추출
            address = store_info.get('basic_address', '')
            # basic-info 클래스에서 주소 찾기
            basic_info = soup.find(class_='basic-info')
            if basic_info:
                addr_text = basic_info.get_text()
                # 주소 패턴 찾기 (서울, 경기 등으로 시작하는 주소)
                addr_match = re.search(r'(서울[^0-9]*|경기[^0-9]*|인천[^0-9]*)[^\n]*', addr_text)
                if addr_match:
                    address = addr_match.group().strip()
            
            # 영업시간 추출
            open_hours = ""
            busi_hours = soup.find(class_='busi-hours') or soup.find(class_='busi-hours-today')
            if busi_hours:
                open_hours = busi_hours.get_text(strip=True)
            
            # 태그 정보 추출 (맛 태그, 일반 태그)
            tags = []
            
            # taste-tag 클래스
            taste_tags = soup.find_all(class_='taste-tag')
            for tag in taste_tags:
                tag_text = tag.get_text(strip=True).replace('#', '')
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
            
            # tag, tags 클래스
            tag_elems = soup.find_all(class_=['tag', 'tags'])
            for tag in tag_elems:
                tag_text = tag.get_text(strip=True).replace('#', '')
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
            
            # 메뉴 가격 정보 추출
            price_info = None
            menu_price = soup.find(class_='Restaurant_MenuPrice')
            if menu_price:
                price_text = menu_price.get_text(strip=True)
                # 숫자와 원 패턴 찾기
                price_match = re.search(r'([0-9,]+)원', price_text)
                if price_match:
                    try:
                        price_info = int(price_match.group(1).replace(',', ''))
                    except:
                        pass
            
            # 평점 정보 재추출 (더 정확하게)
            rating = store_info.get('diningcode_rating')
            score = store_info.get('diningcode_score')
            
            # avg_score 클래스에서 사용자 평점
            avg_score_elem = soup.find(class_='avg_score')
            if avg_score_elem:
                try:
                    rating_text = avg_score_elem.get_text(strip=True)
                    rating_match = re.search(r'([0-9.]+)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))
                except:
                    pass
            
            # highlight-score 클래스에서 다이닝코드 점수
            highlight_score = soup.find(class_='highlight-score')
            if highlight_score:
                try:
                    score_text = highlight_score.get_text(strip=True)
                    score_match = re.search(r'([0-9]+)', score_text)
                    if score_match:
                        score = int(score_match.group(1))
                except:
                    pass
            
            # 이미지 URL 추출
            image_urls = []
            # 다이닝코드 이미지 패턴
            img_elements = soup.find_all('img')
            for img in img_elements:
                src = img.get('src', '')
                if src and ('diningcode' in src or 'restaurant' in src or 'food' in src):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://www.diningcode.com' + src
                    
                    if src not in image_urls:
                        image_urls.append(src)
            
            # 설명 정보 추출
            description = ""
            detail_info = soup.find(class_='detail-info')
            if detail_info:
                description = detail_info.get_text(strip=True)[:500]  # 최대 500자
            
            # 상세 정보 업데이트
            store_info.update({
                'position_lat': lat,
                'position_lng': lng,
                'address': address,
                'phone_number': phone,
                'raw_categories_diningcode': tags,
                'diningcode_rating': rating,
                'diningcode_score': score,
                'description': description,
                'open_hours_raw': open_hours,
                'price': price_info,
                'refill_items': [],  # 무한리필 항목은 별도 로직 필요
                'image_urls': image_urls[:10]  # 최대 10개 이미지
            })
            
            logger.info(f"상세 정보 수집 완료: {store_info['name']}")
            logger.info(f"  좌표: ({lat}, {lng})")
            logger.info(f"  전화번호: {phone}")
            logger.info(f"  주소: {address}")
            logger.info(f"  태그: {len(tags)}개")
            logger.info(f"  이미지: {len(image_urls)}개")
            
        except Exception as e:
            logger.error(f"상세 정보 수집 중 오류: {e}")
            
        return store_info
    
    def close(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver 종료")

# 테스트 실행 함수
def test_crawling():
    """기본 크롤링 테스트"""
    crawler = DiningCodeCrawler()
    
    try:
        # 1. 목록 수집 테스트
        stores = crawler.get_store_list("무한리필", config.TEST_RECT)
        logger.info(f"총 {len(stores)}개 가게 발견")
        
        if stores:
            # 2. 첫 번째 가게 상세 정보 수집 테스트
            first_store = stores[0]
            detailed_store = crawler.get_store_detail(first_store)
            
            logger.info("=== 테스트 결과 ===")
            for key, value in detailed_store.items():
                logger.info(f"{key}: {value}")
                
            # CSV로 저장
            df = pd.DataFrame([detailed_store])
            df.to_csv('data/test_crawling_result.csv', index=False, encoding='utf-8-sig')
            logger.info("테스트 결과를 data/test_crawling_result.csv에 저장")
            
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    test_crawling()