"""
다이닝코드 상세 페이지 구조 분석
"""

import time
import logging
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re

# data 폴더 생성 (없으면)
os.makedirs('data', exist_ok=True)

def debug_detail_page():
    """다이닝코드 상세 페이지 구조 분석"""
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("=== 다이닝코드 상세 페이지 구조 분석 ===")
        
        # 1. 강남 돼지상회 무한리필 상세 페이지 접속
        detail_url = "https://www.diningcode.com/profile.php?rid=sJL6OuwQfW9a"
        print(f"\n1. 상세 페이지 접속: {detail_url}")
        driver.get(detail_url)
        time.sleep(10)  # 충분한 로딩 시간
        
        print(f"   현재 URL: {driver.current_url}")
        print(f"   페이지 제목: {driver.title}")
        
        # 2. JavaScript 변수 확인
        print("\n2. JavaScript 변수 확인...")
        js_variables = [
            "window.lat",
            "window.lng", 
            "window.latitude",
            "window.longitude",
            "window.PLACE_INFO",
            "window.placeInfo",
            "window.storeInfo",
            "window.restaurantInfo",
            "window.poi",
            "window.poiData"
        ]
        
        for var in js_variables:
            try:
                value = driver.execute_script(f"return {var};")
                if value is not None:
                    print(f"   ✅ {var}: {value}")
                else:
                    print(f"   ❌ {var}: None")
            except Exception as e:
                print(f"   ❌ {var}: Error - {e}")
        
        # 3. 페이지 소스에서 좌표 정보 찾기
        print("\n3. 페이지 소스에서 좌표 정보 찾기...")
        page_source = driver.page_source
        
        # 좌표 관련 패턴 찾기
        import re
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
        
        found_coords = []
        for pattern in lat_patterns:
            matches = re.findall(pattern, page_source)
            if matches:
                for match in matches:
                    if 37.0 <= float(match) <= 38.0:  # 서울 위도 범위
                        found_coords.append(f"위도: {match}")
        
        for pattern in lng_patterns:
            matches = re.findall(pattern, page_source)
            if matches:
                for match in matches:
                    if 126.0 <= float(match) <= 128.0:  # 서울 경도 범위
                        found_coords.append(f"경도: {match}")
        
        if found_coords:
            print("   발견된 좌표:")
            for coord in found_coords[:10]:  # 처음 10개만
                print(f"      {coord}")
        else:
            print("   좌표 정보를 찾을 수 없음")
        
        # 4. HTML 구조 분석
        print("\n4. HTML 구조 분석...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 주요 정보 요소들 확인
        info_elements = [
            ('전화번호', 'a[href^="tel:"]'),
            ('주소', '.addr, .address, .location'),
            ('태그', '.dc-tag-list li, .tag-list li, .hashtag'),
            ('평점', '.rating, .score, .point'),
            ('영업시간', '.hours, .time, .open-time'),
            ('가격', '.price, .cost, .menu-price'),
            ('설명', '.description, .intro, .summary'),
            ('이미지', 'img[src*="diningcode"], img[src*="restaurant"]')
        ]
        
        extracted_info = {}
        for name, selector in info_elements:
            try:
                elements = soup.select(selector)
                if elements:
                    values = []
                    for elem in elements[:5]:  # 처음 5개만
                        if elem.name == 'img':
                            values.append(elem.get('src', ''))
                        else:
                            text = elem.get_text(strip=True)
                            if text:
                                values.append(text)
                    
                    if values:
                        extracted_info[name] = values
                        print(f"   ✅ {name}: {len(values)}개 발견")
                        for i, value in enumerate(values[:3]):
                            print(f"      {i+1}. {value[:100]}...")
                    else:
                        print(f"   ❌ {name}: 텍스트 없음")
                else:
                    print(f"   ❌ {name}: 요소 없음")
            except Exception as e:
                print(f"   ❌ {name}: 오류 - {e}")
        
        # 5. 모든 클래스명 수집
        print("\n5. 주요 클래스명 분석...")
        all_classes = set()
        for elem in soup.find_all(class_=True):
            if isinstance(elem.get('class'), list):
                all_classes.update(elem.get('class'))
        
        # 정보 관련 클래스 필터링
        info_classes = [cls for cls in all_classes if any(keyword in cls.lower() for keyword in 
                       ['info', 'detail', 'addr', 'phone', 'tel', 'time', 'hour', 'price', 'tag', 'rating', 'score'])]
        
        print(f"   정보 관련 클래스 ({len(info_classes)}개):")
        for cls in sorted(info_classes)[:20]:  # 처음 20개만
            print(f"      {cls}")
        
        # 6. 결과 저장
        print("\n6. 결과 저장...")
        result = {
            'url': detail_url,
            'title': driver.title,
            'extracted_info': extracted_info,
            'found_coordinates': found_coords,
            'info_classes': sorted(info_classes)
        }
        
        with open('data/detail_page_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 페이지 소스 저장
        with open('data/detail_page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        print("   data/detail_page_analysis.json에 분석 결과 저장")
        print("   data/detail_page_source.html에 페이지 소스 저장")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    
    finally:
        driver.quit()
        print("\n=== 분석 완료 ===")

if __name__ == "__main__":
    debug_detail_page() 