
import time
import random
import logging
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
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User-Agent 랜덤 설정
        user_agent = random.choice(config.USER_AGENTS)
        chrome_options.add_argument(f'--user-agent={user_agent}')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("WebDriver 초기화 완료")
        except Exception as e:
            logger.error(f"WebDriver 초기화 실패: {e}")
            raise
    
    def random_delay(self):
        """랜덤 지연"""
        delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
        time.sleep(delay)
        
    def get_store_list(self, keyword: str, rect: str) -> List[Dict]:
        """다이닝코드에서 가게 목록 수집"""
        stores = []
        url = f"https://www.diningcode.com/list.dc?query={keyword}&rect={rect}"
        
        try:
            logger.info(f"목록 페이지 크롤링 시작: {keyword}, {rect}")
            self.driver.get(url)
            self.random_delay()
            
            # 페이지 로딩 대기
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dc-card")))
            
            # "더보기" 버튼 처리
            more_count = 0
            max_more_clicks = 5  # 최대 5회까지만
            
            while more_count < max_more_clicks:
                try:
                    # "더보기" 버튼 찾기
                    more_button = self.driver.find_element(By.CSS_SELECTOR, ".btn-more, .more-btn, [data-more]")
                    if more_button.is_displayed() and more_button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", more_button)
                        logger.info(f"더보기 버튼 클릭 ({more_count + 1})")
                        time.sleep(2)  # 로딩 대기
                        more_count += 1
                    else:
                        break
                except NoSuchElementException:
                    logger.info("더보기 버튼 없음 - 모든 결과 로드 완료")
                    break
                except Exception as e:
                    logger.warning(f"더보기 버튼 처리 중 오류: {e}")
                    break
            
            # 가게 정보 추출
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            store_cards = soup.find_all('a', {'data-rid': True})
            
            for card in store_cards:
                try:
                    store_info = {
                        'diningcode_place_id': card.get('data-rid'),
                        'detail_url': card.get('href', ''),
                        'name': '',
                        'basic_address': '',
                        'keyword': keyword,
                        'rect_area': rect
                    }
                    
                    # 가게 이름 추출
                    name_elem = card.find(class_='dc-card-title') or card.find('h3') or card.find(class_='tit')
                    if name_elem:
                        store_info['name'] = name_elem.get_text(strip=True)
                    
                    # 주소 추출  
                    addr_elem = card.find(class_='dc-card-addr') or card.find(class_='addr')
                    if addr_elem:
                        store_info['basic_address'] = addr_elem.get_text(strip=True)
                    
                    if store_info['diningcode_place_id'] and store_info['name']:
                        stores.append(store_info)
                        
                except Exception as e:
                    logger.warning(f"가게 정보 추출 중 오류: {e}")
                    continue
            
            logger.info(f"목록에서 {len(stores)}개 가게 정보 수집 완료")
            
        except Exception as e:
            logger.error(f"목록 크롤링 중 오류: {e}")
            
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
            
            # JavaScript에서 좌표 추출 시도
            try:
                lat = self.driver.execute_script("return window.lat || window.latitude || null;")
                lng = self.driver.execute_script("return window.lng || window.longitude || null;")
                
                if not lat or not lng:
                    # 다른 변수명으로 시도
                    coords = self.driver.execute_script("""
                        return window.PLACE_INFO || 
                               window.placeInfo || 
                               window.storeInfo || 
                               null;
                    """)
                    if coords and isinstance(coords, dict):
                        lat = coords.get('lat') or coords.get('latitude')
                        lng = coords.get('lng') or coords.get('longitude')
                        
            except Exception as e:
                logger.warning(f"JavaScript 좌표 추출 실패: {e}")
                lat = lng = None
            
            # HTML에서 추가 정보 추출
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 전화번호
            phone = ""
            phone_elem = soup.find('a', href=lambda x: x and x.startswith('tel:'))
            if phone_elem:
                phone = phone_elem.get_text(strip=True)
            
            # 주소
            address = store_info.get('basic_address', '')
            addr_elem = soup.find(class_='addr') or soup.find(class_='address')
            if addr_elem:
                address = addr_elem.get_text(strip=True)
            
            # 태그 정보
            tags = []
            tag_list = soup.find('ul', class_='dc-tag-list')
            if tag_list:
                for tag in tag_list.find_all('li'):
                    tag_text = tag.get_text(strip=True).replace('#', '')
                    if tag_text:
                        tags.append(tag_text)
            
            # 평점
            rating = None
            rating_elem = soup.find(class_='rating') or soup.find(class_='score')
            if rating_elem:
                try:
                    rating_text = rating_elem.get_text(strip=True)
                    rating = float(rating_text.replace('점', '').strip())
                except:
                    pass
            
            # 상세 정보 업데이트
            store_info.update({
                'position_lat': lat,
                'position_lng': lng,
                'address': address,
                'phone_number': phone,
                'raw_categories_diningcode': tags,
                'diningcode_rating': rating,
                'description': '',  # 나중에 추가
                'open_hours_raw': '',  # 나중에 추가
                'price': None,  # 나중에 추가
                'refill_items': [],  # 나중에 추가
                'image_urls': []  # 나중에 추가
            })
            
            logger.info(f"상세 정보 수집 완료: {store_info['name']}")
            
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
            df.to_csv('test_crawling_result.csv', index=False, encoding='utf-8-sig')
            logger.info("테스트 결과를 test_crawling_result.csv에 저장")
            
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    test_crawling()