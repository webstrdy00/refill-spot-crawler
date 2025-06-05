"""
간단한 다이닝코드 크롤링 테스트
"""

import time
import logging
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import config
from crawler import DiningCodeCrawler

# data 폴더 생성 (없으면)
os.makedirs('data', exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_simple_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_simple_crawling():
    """간단한 무한리필 검색 테스트"""
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("=== 간단한 무한리필 검색 테스트 ===")
        
        # 1. 무한리필 검색 (지역 제한 없음)
        print("\n1. 무한리필 검색...")
        search_url = "https://www.diningcode.com/list.dc?query=무한리필"
        driver.get(search_url)
        print(f"   URL: {search_url}")
        
        # 2. 충분한 시간 대기
        print("\n2. 페이지 로딩 대기...")
        time.sleep(15)  # 15초 대기
        
        print(f"   현재 URL: {driver.current_url}")
        print(f"   페이지 제목: {driver.title}")
        
        # 3. PoiBlock 요소 확인
        print("\n3. PoiBlock 요소 확인...")
        poi_elements = driver.find_elements(By.CLASS_NAME, "PoiBlock")
        print(f"   발견된 PoiBlock 수: {len(poi_elements)}")
        
        if poi_elements:
            print("   ✅ PoiBlock 요소 발견!")
            
            # 4. HTML 파싱으로 정보 추출
            print("\n4. 가게 정보 추출...")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            poi_blocks = soup.find_all('a', class_='PoiBlock')
            
            stores = []
            for i, block in enumerate(poi_blocks[:5]):  # 처음 5개만
                try:
                    store_info = {}
                    
                    # URL에서 rid 추출
                    href = block.get('href', '')
                    if 'rid=' in href:
                        rid = href.split('rid=')[1].split('&')[0]
                        store_info['id'] = rid
                        store_info['url'] = href
                    
                    # 가게 이름 추출
                    title_elem = block.find('h2')
                    if title_elem:
                        name_text = title_elem.get_text(strip=True)
                        if '. ' in name_text:
                            name_text = name_text.split('. ', 1)[1]
                        
                        # 지점명 분리
                        place_elem = title_elem.find('span', class_='Info__Title__Place')
                        if place_elem:
                            branch = place_elem.get_text(strip=True)
                            name = name_text.replace(branch, '').strip()
                            store_info['name'] = name
                            store_info['branch'] = branch
                        else:
                            store_info['name'] = name_text
                    
                    # 평점 정보 추출
                    score_elem = block.find('p', class_='Score')
                    if score_elem:
                        score_span = score_elem.find('span')
                        if score_span:
                            store_info['score'] = score_span.get_text(strip=True)
                    
                    # 사용자 평점 추출
                    user_score_elem = block.find('span', class_='score-text')
                    if user_score_elem:
                        store_info['user_rating'] = user_score_elem.get_text(strip=True)
                    
                    # 카테고리 정보 추출
                    categories = []
                    category_elems = block.find_all('span', class_='Category')
                    for cat_elem in category_elems:
                        cat_text = cat_elem.get_text(strip=True)
                        if cat_text:
                            categories.append(cat_text)
                    store_info['categories'] = categories
                    
                    stores.append(store_info)
                    print(f"   {i+1}. {store_info.get('name', 'Unknown')} {store_info.get('branch', '')}")
                    print(f"      ID: {store_info.get('id', 'N/A')}")
                    print(f"      점수: {store_info.get('score', 'N/A')}점")
                    print(f"      평점: {store_info.get('user_rating', 'N/A')}")
                    print(f"      카테고리: {', '.join(store_info.get('categories', []))}")
                    print()
                    
                except Exception as e:
                    print(f"   가게 {i+1} 정보 추출 오류: {e}")
            
            print(f"\n총 {len(stores)}개 가게 정보 추출 완료!")
            
            # 5. JSON으로 저장
            with open('data/simple_test_result.json', 'w', encoding='utf-8') as f:
                json.dump(stores, f, ensure_ascii=False, indent=2)
            print("결과를 data/simple_test_result.json에 저장했습니다.")
            
        else:
            print("   ❌ PoiBlock 요소를 찾을 수 없습니다.")
            
            # 페이지 소스 일부 확인
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            all_classes = set()
            for elem in soup.find_all(class_=True):
                if isinstance(elem.get('class'), list):
                    all_classes.update(elem.get('class'))
            
            poi_related = [cls for cls in all_classes if 'poi' in cls.lower() or 'block' in cls.lower()]
            print(f"   POI/Block 관련 클래스: {poi_related}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    
    finally:
        driver.quit()
        print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_simple_crawling() 