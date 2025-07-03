"""
데이터 강화 모듈 (3단계 고도화)
크롤링된 데이터의 품질을 향상시키는 통합 모듈
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import re
from collections import defaultdict

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
sys.path.append(os.path.dirname(__file__))

from geocoding import GeocodingManager, GeocodingResult
from price_normalizer import PriceNormalizer, PriceInfo

logger = logging.getLogger(__name__)

@dataclass
class EnhancementStats:
    """데이터 강화 통계"""
    total_stores: int = 0
    geocoding_success: int = 0
    price_normalized: int = 0
    categories_mapped: int = 0
    duplicates_removed: int = 0
    processing_time: float = 0.0

class CategoryMapper:
    """카테고리 매핑 시스템 (7개 카테고리로 제한)"""
    
    def __init__(self):
        # 표준 카테고리 (7개로 제한)
        self.standard_categories = ["고기", "해산물", "양식", "한식", "중식", "일식", "디저트"]
        
        # 키워드 매핑 규칙 (7개 카테고리로만 매핑)
        self.mapping_rules = {
            # 고기
            "삼겹살": ["고기"],
            "갈비": ["고기"],
            "소고기": ["고기"],
            "돼지고기": ["고기"],
            "닭고기": ["고기"],
            "양고기": ["고기"],
            "오리고기": ["고기"],
            "고기무한리필": ["고기"],
            "소고기무한리필": ["고기"],
            "삼겹살무한리필": ["고기"],
            "스테이크": ["고기"],
            "바베큐": ["고기"],
            "BBQ": ["고기"],
            "구이": ["고기"],
            "육류": ["고기"],
            
            # 해산물
            "초밥": ["해산물"],
            "사시미": ["해산물"],
            "스시": ["해산물"],
            "회": ["해산물"],
            "해산물": ["해산물"],
            "해산물무한리필": ["해산물"],
            "수산물": ["해산물"],
            "생선": ["해산물"],
            "조개": ["해산물"],
            "새우": ["해산물"],
            "게": ["해산물"],
            "오징어": ["해산물"],
            "문어": ["해산물"],
            
            # 양식
            "파스타": ["양식"],
            "피자": ["양식"],
            "스테이크": ["양식"],
            "이탈리안": ["양식"],
            "서양음식": ["양식"],
            "양식": ["양식"],
            "브런치": ["양식"],
            "샐러드": ["양식"],
            "버거": ["양식"],
            "햄버거": ["양식"],
            
            # 한식
            "한식": ["한식"],
            "한국음식": ["한식"],
            "김치": ["한식"],
            "된장": ["한식"],
            "고추장": ["한식"],
            "비빔밥": ["한식"],
            "냉면": ["한식"],
            "불고기": ["한식"],
            "떡볶이": ["한식"],
            "순대": ["한식"],
            "족발": ["한식"],
            "보쌈": ["한식"],
            "곱창": ["한식"],
            "막창": ["한식"],
            "찜닭": ["한식"],
            "치킨": ["한식"],
            "분식": ["한식"],
            
            # 중식
            "중식": ["중식"],
            "중국음식": ["중식"],
            "차이니즈": ["중식"],
            "짜장면": ["중식"],
            "짬뽕": ["중식"],
            "탕수육": ["중식"],
            "마파두부": ["중식"],
            "깐풍기": ["중식"],
            "양장피": ["중식"],
            
            # 일식
            "일식": ["일식"],
            "일본음식": ["일식"],
            "초밥뷔페": ["일식"],
            "돈까스": ["일식"],
            "우동": ["일식"],
            "라멘": ["일식"],
            "소바": ["일식"],
            "야키토리": ["일식"],
            "가라아게": ["일식"],
            "덴푸라": ["일식"],
            "규동": ["일식"],
            
            # 디저트
            "디저트": ["디저트"],
            "케이크": ["디저트"],
            "아이스크림": ["디저트"],
            "빵": ["디저트"],
            "베이커리": ["디저트"],
            "쿠키": ["디저트"],
            "마카롱": ["디저트"],
            "타르트": ["디저트"],
            "푸딩": ["디저트"],
            "젤라토": ["디저트"],
            "와플": ["디저트"],
            "팬케이크": ["디저트"],
            "카페": ["디저트"],
            "커피": ["디저트"]
        }
        
        # 제외할 태그들
        self.exclude_patterns = [
            r'.*맛집$',  # 지역맛집
            r'.*역$',    # 지하철역
            r'.*구$',    # 행정구역
            r'할인',
            r'이벤트',
            r'오픈',
            r'신규',
            r'인기',
            r'유명',
            r'맛있는',
            r'좋은'
        ]
    
    def map_categories(self, raw_categories: List[str], store_info: Dict = None) -> List[str]:
        """원본 카테고리를 7개 표준 카테고리로 매핑"""
        if not raw_categories:
            return ["한식"]  # 기본 카테고리
        
        mapped_categories = set()
        
        # 1. 원본 카테고리에서 매핑
        for category in raw_categories:
            category_clean = self._clean_category(category)
            
            # 제외 패턴 확인
            if self._should_exclude(category_clean):
                continue
            
            # 매핑 규칙 적용
            for keyword, standard_cats in self.mapping_rules.items():
                if keyword in category_clean:
                    mapped_categories.update(standard_cats)
        
        # 2. 가게 이름에서 추가 매핑
        if store_info and store_info.get('name'):
            name = store_info['name']
            for keyword, standard_cats in self.mapping_rules.items():
                if keyword in name:
                    mapped_categories.update(standard_cats)
        
        # 3. 메뉴 정보에서 추가 매핑
        if store_info and store_info.get('menu_items'):
            menu_items = store_info['menu_items']
            for menu in menu_items[:5]:  # 상위 5개 메뉴만 확인
                menu_text = str(menu) if isinstance(menu, str) else menu.get('name', '') if isinstance(menu, dict) else ''
                for keyword, standard_cats in self.mapping_rules.items():
                    if keyword in menu_text:
                        mapped_categories.update(standard_cats)
        
        # 4. 표준 카테고리만 유지
        final_categories = [cat for cat in mapped_categories if cat in self.standard_categories]
        
        # 카테고리가 없으면 기본 카테고리 추가
        if not final_categories:
            final_categories = ["한식"]
        
        return final_categories
    
    def _clean_category(self, category: str) -> str:
        """카테고리 정제"""
        if not category:
            return ""
        
        # # 제거
        cleaned = category.replace('#', '').strip()
        
        # 소문자 변환
        cleaned = cleaned.lower()
        
        return cleaned
    
    def _should_exclude(self, category: str) -> bool:
        """제외해야 할 카테고리인지 확인"""
        for pattern in self.exclude_patterns:
            if re.search(pattern, category):
                return True
        return False

class DuplicateDetector:
    """중복 가게 감지 및 제거"""
    
    def __init__(self):
        self.similarity_threshold = 0.85
        self.distance_threshold = 200  # 200m
    
    def find_duplicates(self, stores: List[Dict]) -> List[List[int]]:
        """중복 가게 그룹 찾기"""
        duplicate_groups = []
        processed = set()
        
        for i, store1 in enumerate(stores):
            if i in processed:
                continue
            
            current_group = [i]
            
            for j, store2 in enumerate(stores[i+1:], i+1):
                if j in processed:
                    continue
                
                if self._is_duplicate(store1, store2):
                    current_group.append(j)
                    processed.add(j)
            
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                processed.update(current_group)
        
        return duplicate_groups
    
    def _is_duplicate(self, store1: Dict, store2: Dict) -> bool:
        """두 가게가 중복인지 판단"""
        # 1. 이름 유사도 확인
        name_similarity = self._calculate_name_similarity(
            store1.get('name', ''), 
            store2.get('name', '')
        )
        
        # 2. 위치 거리 확인
        distance = self._calculate_distance(store1, store2)
        
        # 3. 전화번호 확인
        phone_match = self._phone_numbers_match(
            store1.get('phone_number', ''),
            store2.get('phone_number', '')
        )
        
        # 4. 종합 판단
        if phone_match and phone_match != '':
            return True  # 전화번호가 같으면 확실한 중복
        
        if name_similarity > 0.9 and distance < 50:
            return True  # 이름 매우 유사 + 50m 이내
        
        if name_similarity > 0.85 and distance < 200:
            return True  # 이름 유사 + 200m 이내
        
        return False
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """이름 유사도 계산 (Jaccard similarity)"""
        if not name1 or not name2:
            return 0.0
        
        # 정규화
        name1_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', name1.lower())
        name2_clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', name2.lower())
        
        if name1_clean == name2_clean:
            return 1.0
        
        # 문자 단위 Jaccard similarity
        set1 = set(name1_clean)
        set2 = set(name2_clean)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _calculate_distance(self, store1: Dict, store2: Dict) -> float:
        """두 가게 간 거리 계산 (미터)"""
        lat1 = store1.get('position_lat')
        lng1 = store1.get('position_lng')
        lat2 = store2.get('position_lat')
        lng2 = store2.get('position_lng')
        
        if not all([lat1, lng1, lat2, lng2]):
            return float('inf')  # 좌표가 없으면 무한대 거리
        
        import math
        
        R = 6371000  # 지구 반지름 (미터)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _phone_numbers_match(self, phone1: str, phone2: str) -> bool:
        """전화번호 일치 확인"""
        if not phone1 or not phone2:
            return False
        
        # 숫자만 추출
        phone1_clean = re.sub(r'[^0-9]', '', phone1)
        phone2_clean = re.sub(r'[^0-9]', '', phone2)
        
        if len(phone1_clean) < 8 or len(phone2_clean) < 8:
            return False
        
        return phone1_clean == phone2_clean
    
    def merge_duplicates(self, stores: List[Dict], duplicate_groups: List[List[int]]) -> List[Dict]:
        """중복 가게들을 통합"""
        merged_stores = []
        merged_indices = set()
        
        # 중복 그룹 처리
        for group in duplicate_groups:
            if not group:
                continue
            
            # 가장 완성도 높은 가게를 기준으로 통합
            best_store_idx = self._select_best_store(stores, group)
            best_store = stores[best_store_idx].copy()
            
            # 다른 가게들의 정보를 통합
            for idx in group:
                if idx != best_store_idx:
                    self._merge_store_info(best_store, stores[idx])
                merged_indices.add(idx)
            
            merged_stores.append(best_store)
        
        # 중복되지 않은 가게들 추가
        for i, store in enumerate(stores):
            if i not in merged_indices:
                merged_stores.append(store)
        
        return merged_stores
    
    def _select_best_store(self, stores: List[Dict], group: List[int]) -> int:
        """그룹에서 가장 완성도 높은 가게 선택"""
        best_idx = group[0]
        best_score = self._calculate_completeness_score(stores[best_idx])
        
        for idx in group[1:]:
            score = self._calculate_completeness_score(stores[idx])
            if score > best_score:
                best_score = score
                best_idx = idx
        
        return best_idx
    
    def _calculate_completeness_score(self, store: Dict) -> float:
        """가게 정보 완성도 점수 계산"""
        score = 0.0
        
        # 필수 정보
        if store.get('name'):
            score += 1.0
        if store.get('address'):
            score += 1.0
        if store.get('position_lat') and store.get('position_lng'):
            score += 2.0
        
        # 추가 정보
        if store.get('phone_number'):
            score += 0.5
        if store.get('open_hours'):
            score += 0.5
        if store.get('price'):
            score += 0.5
        if store.get('image_urls'):
            score += 0.3
        if store.get('menu_items'):
            score += 0.3
        if store.get('description'):
            score += 0.2
        
        return score
    
    def _merge_store_info(self, target: Dict, source: Dict):
        """소스 가게 정보를 타겟에 통합"""
        # 빈 필드 채우기
        for key, value in source.items():
            if not target.get(key) and value:
                target[key] = value
        
        # 리스트 필드 통합
        list_fields = ['image_urls', 'menu_items', 'raw_categories_diningcode']
        for field in list_fields:
            if field in target and field in source:
                target_list = target[field] if isinstance(target[field], list) else []
                source_list = source[field] if isinstance(source[field], list) else []
                
                # 중복 제거하여 통합
                combined = list(set(target_list + source_list))
                target[field] = combined

class DataEnhancer:
    """데이터 강화 통합 클래스"""
    
    def __init__(self):
        self.geocoding_manager = GeocodingManager()
        self.price_normalizer = PriceNormalizer()
        self.category_mapper = CategoryMapper()
        self.duplicate_detector = DuplicateDetector()
        
        self.stats = EnhancementStats()
    
    def enhance_stores_data(self, stores_data: List[Dict]) -> Tuple[List[Dict], EnhancementStats]:
        """가게 데이터 종합 강화"""
        start_time = time.time()
        
        logger.info(f"=== 데이터 강화 시작: {len(stores_data)}개 가게 ===")
        
        self.stats = EnhancementStats()
        self.stats.total_stores = len(stores_data)
        
        enhanced_stores = []
        
        # 1단계: 개별 가게 데이터 강화
        for i, store in enumerate(stores_data):
            logger.info(f"가게 강화 중: {i+1}/{len(stores_data)} - {store.get('name', 'Unknown')}")
            
            enhanced_store = self._enhance_single_store(store, stores_data)
            enhanced_stores.append(enhanced_store)
        
        # 2단계: 중복 제거
        logger.info("중복 가게 감지 및 제거 중...")
        duplicate_groups = self.duplicate_detector.find_duplicates(enhanced_stores)
        
        if duplicate_groups:
            logger.info(f"중복 그룹 발견: {len(duplicate_groups)}개")
            enhanced_stores = self.duplicate_detector.merge_duplicates(enhanced_stores, duplicate_groups)
            self.stats.duplicates_removed = self.stats.total_stores - len(enhanced_stores)
        
        # 통계 완료
        self.stats.processing_time = time.time() - start_time
        
        logger.info(f"=== 데이터 강화 완료 ===")
        logger.info(f"처리 시간: {self.stats.processing_time:.2f}초")
        logger.info(f"지오코딩 성공: {self.stats.geocoding_success}/{self.stats.total_stores}")
        logger.info(f"가격 정규화: {self.stats.price_normalized}/{self.stats.total_stores}")
        logger.info(f"카테고리 매핑: {self.stats.categories_mapped}/{self.stats.total_stores}")
        logger.info(f"중복 제거: {self.stats.duplicates_removed}개")
        logger.info(f"최종 가게 수: {len(enhanced_stores)}개")
        
        return enhanced_stores, self.stats
    
    def _enhance_single_store(self, store: Dict, all_stores: List[Dict]) -> Dict:
        """단일 가게 데이터 강화"""
        enhanced = store.copy()
        
        # 1. 지오코딩 (좌표가 없는 경우)
        if not store.get('position_lat') or not store.get('position_lng'):
            address = store.get('address', '')
            if address:
                # 근처 가게들 정보 제공 (같은 지역의 가게들)
                nearby_stores = self._get_nearby_stores_by_address(address, all_stores)
                
                geocoding_result = self.geocoding_manager.geocode_address(address, nearby_stores)
                if geocoding_result:
                    enhanced['position_lat'] = geocoding_result.latitude
                    enhanced['position_lng'] = geocoding_result.longitude
                    enhanced['geocoding_source'] = geocoding_result.source
                    enhanced['geocoding_confidence'] = geocoding_result.confidence
                    self.stats.geocoding_success += 1
        else:
            self.stats.geocoding_success += 1
        
        # 2. 가격 정규화
        price_text = store.get('price', '') or store.get('price_range', '')
        if price_text:
            additional_info = {
                'menu_items': store.get('menu_items', []),
                'refill_items': store.get('refill_items', [])
            }
            
            price_info = self.price_normalizer.normalize_price(price_text, additional_info)
            enhanced['normalized_price'] = {
                'price_type': price_info.price_type,
                'min_price': price_info.min_price,
                'max_price': price_info.max_price,
                'time_based': price_info.time_based,
                'conditions': price_info.conditions,
                'confidence': price_info.confidence
            }
            self.stats.price_normalized += 1
        
        # 3. 카테고리 매핑
        raw_categories = store.get('raw_categories_diningcode', [])
        if raw_categories:
            mapped_categories = self.category_mapper.map_categories(raw_categories, store)
            enhanced['standard_categories'] = mapped_categories
            self.stats.categories_mapped += 1
        
        return enhanced
    
    def _get_nearby_stores_by_address(self, address: str, all_stores: List[Dict]) -> List[Dict]:
        """주소 기반으로 근처 가게들 찾기"""
        # 간단한 주소 매칭 (같은 구/동)
        address_parts = address.split()
        nearby_stores = []
        
        for store in all_stores:
            store_address = store.get('address', '')
            if store_address:
                # 공통 주소 구성요소가 있는지 확인
                store_parts = store_address.split()
                common_parts = set(address_parts) & set(store_parts)
                
                if len(common_parts) >= 2:  # 최소 2개 이상 공통 요소
                    nearby_stores.append(store)
        
        return nearby_stores[:10]  # 최대 10개만 반환
    
    def get_enhancement_summary(self) -> Dict:
        """강화 작업 요약 정보"""
        total = self.stats.total_stores
        if total == 0:
            return {}
        
        return {
            'total_stores': total,
            'final_stores': total - self.stats.duplicates_removed,
            'geocoding_rate': (self.stats.geocoding_success / total) * 100,
            'price_normalization_rate': (self.stats.price_normalized / total) * 100,
            'category_mapping_rate': (self.stats.categories_mapped / total) * 100,
            'duplicate_removal_rate': (self.stats.duplicates_removed / total) * 100,
            'processing_time': self.stats.processing_time,
            'geocoding_stats': self.geocoding_manager.get_stats(),
            'price_stats': self.price_normalizer.get_stats()
        }

def test_data_enhancement():
    """데이터 강화 테스트"""
    # 테스트 데이터
    test_stores = [
        {
            'name': '맛있는 삼겹살집',
            'address': '서울 강남구 테헤란로 123',
            'price': '1만5천원',
            'raw_categories_diningcode': ['#삼겹살무한리필', '#고기', '#강남맛집'],
            'diningcode_place_id': 'test1'
        },
        {
            'name': '맛있는삼겹살집',  # 중복 (띄어쓰기 차이)
            'address': '서울 강남구 테헤란로 125',
            'price': '15000원',
            'raw_categories_diningcode': ['#무한리필', '#삼겹살'],
            'diningcode_place_id': 'test2'
        },
        {
            'name': '초밥뷔페 스시로',
            'address': '서울 강남구 역삼동',  # 좌표 없음
            'price': '런치 2만원, 디너 3만원',
            'raw_categories_diningcode': ['#초밥뷔페', '#일식', '#뷔페'],
            'diningcode_place_id': 'test3'
        }
    ]
    
    enhancer = DataEnhancer()
    enhanced_stores, stats = enhancer.enhance_stores_data(test_stores)
    
    print("=== 데이터 강화 테스트 결과 ===")
    print(f"원본 가게 수: {len(test_stores)}")
    print(f"강화 후 가게 수: {len(enhanced_stores)}")
    print(f"강화 통계: {enhancer.get_enhancement_summary()}")
    
    for i, store in enumerate(enhanced_stores):
        print(f"\n가게 {i+1}: {store.get('name')}")
        print(f"좌표: {store.get('position_lat')}, {store.get('position_lng')}")
        print(f"정규화된 가격: {store.get('normalized_price')}")
        print(f"표준 카테고리: {store.get('standard_categories')}")

if __name__ == "__main__":
    test_data_enhancement() 