"""
지오코딩 및 좌표 검증 모듈
3단계: 좌표 완성도 90% → 98% 목표 (카카오 API 전용)
"""

import requests
import logging
import time
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import config

logger = logging.getLogger(__name__)

@dataclass
class GeocodingResult:
    """지오코딩 결과 데이터 클래스"""
    latitude: float
    longitude: float
    formatted_address: str
    confidence: float  # 0.0 ~ 1.0
    source: str  # 'kakao', 'estimated'
    is_valid: bool = True

class AddressNormalizer:
    """주소 정규화 및 전처리 클래스"""
    
    def __init__(self):
        # 주소 정제 패턴들
        self.address_patterns = {
            # 불필요한 문구 제거
            'remove_patterns': [
                r'\(.*?\)',  # 괄호 안 내용
                r'[0-9]+층',  # 층수 정보
                r'[0-9]+호',  # 호수 정보
                r'근처',
                r'앞',
                r'옆',
                r'건물',
                r'상가',
            ],
            # 주소 구성요소 패턴
            'address_components': {
                'sido': r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)',
                'sigungu': r'([가-힣]+시|[가-힣]+군|[가-힣]+구)',
                'dong': r'([가-힣]+동|[가-힣]+읍|[가-힣]+면)',
                'road': r'([가-힣]+로|[가-힣]+길)',
                'building_number': r'([0-9]+(-[0-9]+)?)'
            }
        }
    
    def normalize_address(self, address: str) -> str:
        """주소 정규화"""
        if not address:
            return ""
        
        # 기본 정제
        normalized = address.strip()
        
        # 불필요한 패턴 제거
        for pattern in self.address_patterns['remove_patterns']:
            normalized = re.sub(pattern, '', normalized)
        
        # 공백 정리
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def extract_address_components(self, address: str) -> Dict[str, str]:
        """주소 구성요소 추출"""
        components = {}
        
        for component, pattern in self.address_patterns['address_components'].items():
            match = re.search(pattern, address)
            if match:
                components[component] = match.group(1)
        
        return components
    
    def enhance_incomplete_address(self, address: str, nearby_stores: List[Dict] = None) -> str:
        """불완전한 주소 보완"""
        components = self.extract_address_components(address)
        
        # 시도 정보가 없는 경우 서울로 가정 (대부분의 데이터가 서울)
        if 'sido' not in components:
            if nearby_stores:
                # 근처 가게들의 주소에서 시도 정보 추출
                for store in nearby_stores:
                    store_components = self.extract_address_components(store.get('address', ''))
                    if 'sido' in store_components:
                        return f"{store_components['sido']} {address}"
            
            # 기본값으로 서울 추가
            return f"서울 {address}"
        
        return address

class KakaoGeocoder:
    """카카오 지오코딩 API 클래스"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dapi.kakao.com/v2/local/search/address.json"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'KakaoAK {api_key}'
        })
        self.request_count = 0
        self.daily_limit = 300000  # 일일 무료 한도
    
    def geocode(self, address: str) -> Optional[GeocodingResult]:
        """주소를 좌표로 변환"""
        if self.request_count >= self.daily_limit:
            logger.warning("카카오 API 일일 한도 초과")
            return None
        
        try:
            params = {
                'query': address,
                'analyze_type': 'similar'  # 유사한 주소도 검색
            }
            
            response = self.session.get(self.base_url, params=params)
            self.request_count += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if data['documents']:
                    doc = data['documents'][0]  # 첫 번째 결과 사용
                    
                    return GeocodingResult(
                        latitude=float(doc['y']),
                        longitude=float(doc['x']),
                        formatted_address=doc['address_name'],
                        confidence=self._calculate_confidence(address, doc),
                        source='kakao'
                    )
            
            elif response.status_code == 429:
                logger.warning("카카오 API 요청 한도 초과, 잠시 대기")
                time.sleep(1)
                return self.geocode(address)  # 재시도
            
            else:
                logger.warning(f"카카오 지오코딩 실패: {response.status_code}")
            
        except Exception as e:
            logger.error(f"카카오 지오코딩 오류: {e}")
        
        return None
    
    def _calculate_confidence(self, original: str, result: Dict) -> float:
        """지오코딩 결과 신뢰도 계산"""
        # 주소 유사도 기반 신뢰도 계산
        original_clean = re.sub(r'[^가-힣0-9]', '', original)
        result_clean = re.sub(r'[^가-힣0-9]', '', result['address_name'])
        
        # 간단한 문자열 유사도 계산
        common_chars = set(original_clean) & set(result_clean)
        total_chars = set(original_clean) | set(result_clean)
        
        if total_chars:
            similarity = len(common_chars) / len(total_chars)
            return min(similarity * 1.2, 1.0)  # 최대 1.0
        
        return 0.5  # 기본값

class CoordinateValidator:
    """좌표 유효성 검증 클래스"""
    
    def __init__(self):
        # 한국 영역 경계 (대략적)
        self.korea_bounds = {
            'min_lat': 33.0,
            'max_lat': 38.6,
            'min_lng': 124.5,
            'max_lng': 132.0
        }
        
        # 주요 도시 중심점 (이상치 감지용)
        self.city_centers = {
            '서울': (37.5665, 126.9780),
            '부산': (35.1796, 129.0756),
            '대구': (35.8714, 128.6014),
            '인천': (37.4563, 126.7052),
            '광주': (35.1595, 126.8526),
            '대전': (36.3504, 127.3845),
            '울산': (35.5384, 129.3114)
        }
    
    def validate_coordinates(self, lat: float, lng: float, address: str = "") -> bool:
        """좌표 유효성 검증"""
        # 1. 한국 영역 내부 확인
        if not self._is_within_korea(lat, lng):
            logger.warning(f"한국 영역 밖 좌표: {lat}, {lng}")
            return False
        
        # 2. 바다/산속 좌표 확인 (간단한 휴리스틱)
        if self._is_likely_invalid_location(lat, lng):
            logger.warning(f"의심스러운 위치 좌표: {lat}, {lng}")
            return False
        
        # 3. 주소와 좌표 일치성 확인
        if address and not self._address_coordinate_match(address, lat, lng):
            logger.warning(f"주소-좌표 불일치: {address} -> {lat}, {lng}")
            return False
        
        return True
    
    def _is_within_korea(self, lat: float, lng: float) -> bool:
        """한국 영역 내부 여부 확인"""
        return (self.korea_bounds['min_lat'] <= lat <= self.korea_bounds['max_lat'] and
                self.korea_bounds['min_lng'] <= lng <= self.korea_bounds['max_lng'])
    
    def _is_likely_invalid_location(self, lat: float, lng: float) -> bool:
        """명백히 잘못된 위치인지 확인"""
        # 공항, 항만, 산속 등의 좌표 패턴 확인
        # 실제로는 더 정교한 검증이 필요하지만 기본적인 체크만 구현
        
        # 인천공항 근처 (음식점이 있을 수 없는 활주로 등)
        if 37.44 <= lat <= 37.47 and 126.43 <= lng <= 126.46:
            return True
        
        # 기타 명백한 이상치들은 추후 데이터 분석을 통해 추가
        return False
    
    def _address_coordinate_match(self, address: str, lat: float, lng: float) -> bool:
        """주소와 좌표의 일치성 확인"""
        # 주소에서 시도 정보 추출
        for city, (city_lat, city_lng) in self.city_centers.items():
            if city in address:
                # 해당 도시 중심에서 50km 이내인지 확인
                distance = self._calculate_distance(lat, lng, city_lat, city_lng)
                if distance > 50:  # 50km 이상 떨어져 있으면 의심
                    return False
                break
        
        return True
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """두 좌표 간 거리 계산 (km)"""
        import math
        
        R = 6371  # 지구 반지름 (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

class GeocodingManager:
    """지오코딩 통합 관리 클래스 (카카오 API 전용)"""
    
    def __init__(self):
        self.address_normalizer = AddressNormalizer()
        self.coordinate_validator = CoordinateValidator()
        
        # 카카오 API 설정
        self.kakao_geocoder = None
        if hasattr(config, 'KAKAO_API_KEY') and config.KAKAO_API_KEY:
            self.kakao_geocoder = KakaoGeocoder(config.KAKAO_API_KEY)
        
        self.stats = {
            'total_requests': 0,
            'kakao_success': 0,
            'validation_failed': 0,
            'estimated_success': 0,
            'not_found': 0
        }
    
    def geocode_address(self, address: str, nearby_stores: List[Dict] = None) -> Optional[GeocodingResult]:
        """주소를 좌표로 변환 (카카오 API + 추정)"""
        self.stats['total_requests'] += 1
        
        if not address:
            return None
        
        # 1. 주소 정규화
        normalized_address = self.address_normalizer.normalize_address(address)
        enhanced_address = self.address_normalizer.enhance_incomplete_address(
            normalized_address, nearby_stores
        )
        
        logger.info(f"지오코딩 시도: {address} -> {enhanced_address}")
        
        # 2. 카카오 API 시도 (1순위)
        if self.kakao_geocoder:
            result = self.kakao_geocoder.geocode(enhanced_address)
            if result:
                # 좌표 유효성 검증
                if self.coordinate_validator.validate_coordinates(
                    result.latitude, result.longitude, enhanced_address
                ):
                    self.stats['kakao_success'] += 1
                    logger.info(f"카카오 지오코딩 성공: {result.latitude}, {result.longitude}")
                    return result
                else:
                    self.stats['validation_failed'] += 1
                    logger.warning("카카오 지오코딩 결과 검증 실패")
        
        # 3. 근처 가게 좌표 기반 추정 (2순위)
        if nearby_stores:
            estimated_result = self._estimate_from_nearby_stores(enhanced_address, nearby_stores)
            if estimated_result:
                self.stats['estimated_success'] += 1
                logger.info(f"근처 가게 기반 좌표 추정: {estimated_result.latitude}, {estimated_result.longitude}")
                return estimated_result
        
        self.stats['not_found'] += 1
        logger.warning(f"지오코딩 실패: {address}")
        return None
    
    def _estimate_from_nearby_stores(self, address: str, nearby_stores: List[Dict]) -> Optional[GeocodingResult]:
        """근처 가게들의 좌표를 기반으로 추정"""
        # 같은 건물이나 같은 도로의 가게들 찾기
        address_components = self.address_normalizer.extract_address_components(address)
        
        candidates = []
        for store in nearby_stores:
            store_address = store.get('address', '')
            store_components = self.address_normalizer.extract_address_components(store_address)
            
            # 같은 도로나 같은 동인 경우
            if (address_components.get('road') == store_components.get('road') or
                address_components.get('dong') == store_components.get('dong')):
                
                if store.get('position_lat') and store.get('position_lng'):
                    candidates.append({
                        'lat': store['position_lat'],
                        'lng': store['position_lng'],
                        'similarity': self._calculate_address_similarity(address, store_address)
                    })
        
        if candidates:
            # 가장 유사한 주소의 좌표 사용
            best_candidate = max(candidates, key=lambda x: x['similarity'])
            
            return GeocodingResult(
                latitude=best_candidate['lat'],
                longitude=best_candidate['lng'],
                formatted_address=address,
                confidence=0.6,  # 추정이므로 낮은 신뢰도
                source='estimated'
            )
        
        return None
    
    def _calculate_address_similarity(self, addr1: str, addr2: str) -> float:
        """주소 유사도 계산"""
        # 간단한 문자열 유사도 계산
        addr1_clean = re.sub(r'[^가-힣0-9]', '', addr1)
        addr2_clean = re.sub(r'[^가-힣0-9]', '', addr2)
        
        common_chars = set(addr1_clean) & set(addr2_clean)
        total_chars = set(addr1_clean) | set(addr2_clean)
        
        if total_chars:
            return len(common_chars) / len(total_chars)
        
        return 0.0
    
    def get_stats(self) -> Dict:
        """지오코딩 통계 반환"""
        total = self.stats['total_requests']
        if total == 0:
            return self.stats
        
        success_rate = (self.stats['kakao_success'] + self.stats['estimated_success']) / total * 100
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'kakao_rate': self.stats['kakao_success'] / total * 100,
            'estimated_rate': self.stats['estimated_success'] / total * 100,
            'validation_fail_rate': self.stats['validation_failed'] / total * 100,
            'not_found_rate': self.stats['not_found'] / total * 100
        }

def test_geocoding():
    """지오코딩 테스트 함수"""
    geocoding_manager = GeocodingManager()
    
    test_addresses = [
        "서울 강남구 테헤란로 123",
        "강남구 123번지",
        "강남역 근처",
        "서울특별시 종로구 종로 1",
        "부산 해운대구 해운대해변로 264"
    ]
    
    for address in test_addresses:
        print(f"\n테스트 주소: {address}")
        result = geocoding_manager.geocode_address(address)
        
        if result:
            print(f"결과: {result.latitude}, {result.longitude}")
            print(f"신뢰도: {result.confidence:.2f}")
            print(f"소스: {result.source}")
        else:
            print("지오코딩 실패")
    
    print(f"\n통계: {geocoding_manager.get_stats()}")

if __name__ == "__main__":
    test_geocoding() 