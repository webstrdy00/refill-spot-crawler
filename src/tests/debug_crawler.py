"""
다이닝코드 사이트 구조 분석용 디버깅 스크립트
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def debug_diningcode():
    """다이닝코드 사이트 구조 분석"""
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("=== 다이닝코드 사이트 구조 분석 ===")
        
        # 1. 메인 페이지 접속
        print("\n1. 메인 페이지 접속...")
        driver.get("https://www.diningcode.com")
        time.sleep(3)
        print(f"   현재 URL: {driver.current_url}")
        print(f"   페이지 제목: {driver.title}")
        
        # 2. 검색 기능 확인
        print("\n2. 검색 기능 확인...")
        try:
            # 검색창 찾기
            search_selectors = [
                'input[name="query"]',
                'input[placeholder*="검색"]',
                '.search-input',
                '#search',
                'input[type="search"]'
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"   검색창 발견: {selector}")
                    break
                except:
                    continue
            
            if search_box:
                # 검색어 입력
                search_box.clear()
                search_box.send_keys("무한리필")
                time.sleep(1)
                
                # 검색 버튼 찾기
                search_btn_selectors = [
                    'button[type="submit"]',
                    '.search-btn',
                    '.btn-search',
                    'input[type="submit"]'
                ]
                
                for selector in search_btn_selectors:
                    try:
                        search_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        search_btn.click()
                        print(f"   검색 버튼 클릭: {selector}")
                        break
                    except:
                        continue
                
                time.sleep(3)
                print(f"   검색 후 URL: {driver.current_url}")
                
        except Exception as e:
            print(f"   검색 기능 오류: {e}")
        
        # 3. 직접 검색 URL 접속
        print("\n3. 직접 검색 URL 접속...")
        search_url = "https://www.diningcode.com/list.dc?query=무한리필"
        driver.get(search_url)
        time.sleep(5)
        print(f"   현재 URL: {driver.current_url}")
        print(f"   페이지 제목: {driver.title}")
        
        # 3-2. 더 긴 시간 대기 후 다시 확인
        print("\n3-2. 추가 대기 후 재확인...")
        time.sleep(10)  # 더 긴 시간 대기
        
        # 4. 페이지 구조 분석
        print("\n4. 페이지 구조 분석...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # PoiBlock 클래스 확인
        poi_blocks = soup.find_all('a', class_='PoiBlock')
        print(f"   PoiBlock 요소 수: {len(poi_blocks)}")
        
        if poi_blocks:
            print("   첫 번째 PoiBlock 내용:")
            print(f"   {str(poi_blocks[0])[:500]}...")
        
        # 주요 요소들 확인
        elements_to_check = [
            ('PoiBlock', 'class'),
            ('sc-sLsrZ', 'class'),
            ('kELyrO', 'class'),
            ('RHeader', 'class'),
            ('Info', 'class'),
            ('data-rid', 'attribute'),
            ('data-store-id', 'attribute'),
            ('search-result', 'class'),
            ('list-wrap', 'class')
        ]
        
        for element, check_type in elements_to_check:
            if check_type == 'class':
                found = soup.find_all(class_=element)
            else:  # attribute
                found = soup.find_all(attrs={element: True})
            
            if found:
                print(f"   ✅ {element}: {len(found)}개 발견")
                if len(found) > 0 and element in ['PoiBlock', 'sc-sLsrZ']:
                    print(f"      첫 번째 요소: {str(found[0])[:200]}...")
            else:
                print(f"   ❌ {element}: 없음")
        
        # 5. 모든 링크 확인
        print("\n5. 페이지 내 링크 분석...")
        all_links = soup.find_all('a', href=True)
        print(f"   전체 링크 수: {len(all_links)}")
        
        # 가게 관련 링크 찾기
        store_links = []
        for link in all_links:
            href = link.get('href', '')
            if any(keyword in href for keyword in ['/list', '/store', '/restaurant', '/place']):
                store_links.append(href)
        
        print(f"   가게 관련 링크 수: {len(store_links)}")
        if store_links:
            print("   예시 링크들:")
            for i, link in enumerate(store_links[:5]):
                print(f"     {i+1}. {link}")
        
        # 6. 페이지 소스 일부 저장
        print("\n6. 페이지 소스 저장...")
        with open('debug_page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("   페이지 소스를 debug_page_source.html에 저장")
        
        # 7. 스크린샷 저장
        print("\n7. 스크린샷 저장...")
        driver.save_screenshot('debug_screenshot.png')
        print("   스크린샷을 debug_screenshot.png에 저장")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    
    finally:
        driver.quit()
        print("\n=== 분석 완료 ===")

if __name__ == "__main__":
    debug_diningcode() 