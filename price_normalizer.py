"""
가격 정보 정규화 모듈
3단계: 가격 정보 활용 30% → 80% 목표
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class PriceInfo:
    """정규화된 가격 정보 데이터 클래스"""
    price_type: str  # 'single', 'range', 'time_based', 'conditional'
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    currency: str = 'KRW'
    time_based: Dict[str, Dict[str, int]] = None
    conditions: str = ''
    original_text: str = ''
    confidence: float = 0.0  # 0.0 ~ 1.0
    
    def __post_init__(self):
        if self.time_based is None:
            self.time_based = {}

class KoreanNumberConverter:
    """한국어 숫자 표현 변환 클래스"""
    
    def __init__(self):
        # 한국어 숫자 매핑
        self.korean_numbers = {
            '영': 0, '일': 1, '이': 2, '삼': 3, '사': 4, '오': 5,
            '육': 6, '칠': 7, '팔': 8, '구': 9, '십': 10,
            '백': 100, '천': 1000, '만': 10000, '억': 100000000
        }
        
        # 단위 매핑
        self.units = {
            '원': 1,
            '천원': 1000,
            '만원': 10000,
            '십만원': 100000,
            '백만원': 1000000
        }
        
        # 숫자 패턴들
        self.patterns = {
            # "1만원", "2만5천원" 등
            'korean_mixed': r'([0-9]+)만([0-9]+)?천?원?',
            # "십만원", "이만원" 등
            'korean_pure': r'([일이삼사오육칠팔구십백천만억]+)원?',
            # "10,000원", "15000원" 등
            'arabic_with_comma': r'([0-9,]+)원?',
            # "1만원대", "2만원대" 등
            'range_suffix': r'([0-9]+)만?원?대',
            # "천원", "만원" 등 단위만
            'unit_only': r'(천|만|십만|백만)원'
        }
    
    def convert_korean_to_number(self, text: str) -> Optional[int]:
        """한국어 숫자 표현을 숫자로 변환"""
        if not text:
            return None
        
        text = text.strip()
        
        # 1. 혼합형 패턴 (1만2천원)
        match = re.search(self.patterns['korean_mixed'], text)
        if match:
            man = int(match.group(1)) * 10000
            cheon = int(match.group(2)) * 1000 if match.group(2) else 0
            return man + cheon
        
        # 2. 순수 한국어 패턴 (이만원)
        match = re.search(self.patterns['korean_pure'], text)
        if match:
            korean_text = match.group(1)
            return self._parse_pure_korean(korean_text)
        
        # 3. 아라비아 숫자 + 콤마 패턴 (10,000원)
        match = re.search(self.patterns['arabic_with_comma'], text)
        if match:
            number_text = match.group(1).replace(',', '')
            try:
                return int(number_text)
            except ValueError:
                pass
        
        # 4. 범위 표현 (2만원대)
        match = re.search(self.patterns['range_suffix'], text)
        if match:
            base = int(match.group(1))
            if '만' in text:
                min_price = base * 10000
                max_price = (base + 1) * 10000 - 1
            else:
                min_price = base * 1000
                max_price = (base + 1) * 1000 - 1
            
            return PriceInfo(
                price_type='range',
                min_price=min_price,
                max_price=max_price,
                original_text=text,
                confidence=0.8
            )
        
        # 5. 단위만 있는 경우 (만원)
        match = re.search(self.patterns['unit_only'], text)
        if match:
            unit = match.group(1)
            return self.units.get(unit + '원', None)
        
        return None
    
    def _parse_pure_korean(self, korean_text: str) -> Optional[int]:
        """순수 한국어 숫자 파싱"""
        try:
            result = 0
            current = 0
            
            i = 0
            while i < len(korean_text):
                char = korean_text[i]
                
                if char in self.korean_numbers:
                    num = self.korean_numbers[char]
                    
                    if num < 10:  # 기본 숫자
                        current = current * 10 + num
                    elif num == 10:  # 십
                        if current == 0:
                            current = 10
                        else:
                            current *= 10
                    elif num == 100:  # 백
                        if current == 0:
                            current = 100
                        else:
                            current *= 100
                    elif num == 1000:  # 천
                        if current == 0:
                            current = 1000
                        else:
                            result += current * 1000
                            current = 0
                    elif num == 10000:  # 만
                        if current == 0:
                            current = 10000
                        else:
                            result += current * 10000
                            current = 0
                    elif num == 100000000:  # 억
                        if current == 0:
                            current = 100000000
                        else:
                            result += current * 100000000
                            current = 0
                
                i += 1
            
            return result + current
        
        except Exception as e:
            logger.warning(f"한국어 숫자 파싱 실패: {korean_text}, {e}")
            return None

class PricePatternExtractor:
    """가격 패턴 추출 클래스"""
    
    def __init__(self):
        self.korean_converter = KoreanNumberConverter()
        
        # 가격 패턴들
        self.price_patterns = {
            # 범위 패턴
            'range_patterns': [
                r'([0-9,만천원]+)\s*[~-]\s*([0-9,만천원]+)',
                r'([0-9,만천원]+)\s*부터\s*([0-9,만천원]+)',
                r'([0-9,만천원]+)\s*에서\s*([0-9,만천원]+)',
            ],
            
            # 조건부 패턴
            'conditional_patterns': [
                r'([0-9,만천원]+)\s*\(([^)]+)\)',
                r'([0-9,만천원]+)\s*([0-9]+인\s*이상)',
                r'([^0-9]*)\s*([0-9,만천원]+)',
            ],
            
            # 시간대별 패턴
            'time_based_patterns': [
                r'런치\s*([0-9,만천원]+)',
                r'디너\s*([0-9,만천원]+)',
                r'점심\s*([0-9,만천원]+)',
                r'저녁\s*([0-9,만천원]+)',
                r'평일\s*([0-9,만천원]+)',
                r'주말\s*([0-9,만천원]+)',
            ],
            
            # 메뉴별 패턴
            'menu_based_patterns': [
                r'([가-힣]+)\s*([0-9,만천원]+)',
                r'([가-힣]+고기)\s*([0-9,만천원]+)',
                r'([가-힣]+무한리필)\s*([0-9,만천원]+)',
            ],
            
            # 단일 가격 패턴
            'single_patterns': [
                r'([0-9,만천원]+)원?',
                r'가격\s*([0-9,만천원]+)',
                r'([0-9]+)만?원?대?',
            ]
        }
        
        # 제외할 패턴들
        self.exclude_patterns = [
            r'가격\s*문의',
            r'시세',
            r'별도',
            r'추가\s*요금',
            r'서비스\s*요금',
        ]
    
    def extract_price_info(self, text: str) -> PriceInfo:
        """텍스트에서 가격 정보 추출"""
        if not text:
            return PriceInfo(price_type='unknown', original_text=text)
        
        # 제외 패턴 확인
        for pattern in self.exclude_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return PriceInfo(
                    price_type='inquiry',
                    original_text=text,
                    confidence=0.9
                )
        
        # 1. 범위 패턴 확인
        range_result = self._extract_range_price(text)
        if range_result:
            return range_result
        
        # 2. 시간대별 패턴 확인
        time_result = self._extract_time_based_price(text)
        if time_result:
            return time_result
        
        # 3. 조건부 패턴 확인
        conditional_result = self._extract_conditional_price(text)
        if conditional_result:
            return conditional_result
        
        # 4. 단일 가격 패턴 확인
        single_result = self._extract_single_price(text)
        if single_result:
            return single_result
        
        # 5. 실패 시 기본값 반환
        return PriceInfo(
            price_type='unknown',
            original_text=text,
            confidence=0.0
        )
    
    def _extract_range_price(self, text: str) -> Optional[PriceInfo]:
        """범위 가격 추출"""
        for pattern in self.price_patterns['range_patterns']:
            match = re.search(pattern, text)
            if match:
                min_price_text = match.group(1)
                max_price_text = match.group(2)
                
                min_price = self.korean_converter.convert_korean_to_number(min_price_text)
                max_price = self.korean_converter.convert_korean_to_number(max_price_text)
                
                if min_price and max_price:
                    return PriceInfo(
                        price_type='range',
                        min_price=min_price,
                        max_price=max_price,
                        original_text=text,
                        confidence=0.9
                    )
        
        # "2만원대" 같은 범위 표현
        match = re.search(r'([0-9]+)만?원?대', text)
        if match:
            base = int(match.group(1))
            if '만' in text:
                min_price = base * 10000
                max_price = (base + 1) * 10000 - 1
            else:
                min_price = base * 1000
                max_price = (base + 1) * 1000 - 1
            
            return PriceInfo(
                price_type='range',
                min_price=min_price,
                max_price=max_price,
                original_text=text,
                confidence=0.8
            )
        
        return None
    
    def _extract_time_based_price(self, text: str) -> Optional[PriceInfo]:
        """시간대별 가격 추출"""
        time_prices = {}
        
        for pattern in self.price_patterns['time_based_patterns']:
            matches = re.finditer(pattern, text)
            for match in matches:
                time_key = self._normalize_time_key(match.group(0))
                price_text = match.group(1)
                price = self.korean_converter.convert_korean_to_number(price_text)
                
                if price:
                    time_prices[time_key] = {'min': price, 'max': price}
        
        if time_prices:
            # 전체 범위 계산
            all_prices = []
            for time_info in time_prices.values():
                all_prices.extend([time_info['min'], time_info['max']])
            
            return PriceInfo(
                price_type='time_based',
                min_price=min(all_prices),
                max_price=max(all_prices),
                time_based=time_prices,
                original_text=text,
                confidence=0.85
            )
        
        return None
    
    def _extract_conditional_price(self, text: str) -> Optional[PriceInfo]:
        """조건부 가격 추출"""
        for pattern in self.price_patterns['conditional_patterns']:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 2:
                    price_text = match.group(1)
                    condition = match.group(2)
                    
                    price = self.korean_converter.convert_korean_to_number(price_text)
                    
                    if price:
                        return PriceInfo(
                            price_type='conditional',
                            min_price=price,
                            max_price=price,
                            conditions=condition.strip(),
                            original_text=text,
                            confidence=0.8
                        )
        
        return None
    
    def _extract_single_price(self, text: str) -> Optional[PriceInfo]:
        """단일 가격 추출"""
        # 모든 숫자 패턴 찾기
        prices = []
        
        for pattern in self.price_patterns['single_patterns']:
            matches = re.finditer(pattern, text)
            for match in matches:
                price_text = match.group(1) if match.groups() else match.group(0)
                price = self.korean_converter.convert_korean_to_number(price_text)
                if price and price > 1000:  # 1000원 이상만 유효한 가격으로 간주
                    prices.append(price)
        
        if prices:
            # 가장 대표적인 가격 선택 (중간값 또는 최빈값)
            if len(prices) == 1:
                price = prices[0]
                return PriceInfo(
                    price_type='single',
                    min_price=price,
                    max_price=price,
                    original_text=text,
                    confidence=0.9
                )
            else:
                # 여러 가격이 있는 경우 범위로 처리
                min_price = min(prices)
                max_price = max(prices)
                return PriceInfo(
                    price_type='range',
                    min_price=min_price,
                    max_price=max_price,
                    original_text=text,
                    confidence=0.7
                )
        
        return None
    
    def _normalize_time_key(self, time_text: str) -> str:
        """시간 키 정규화"""
        time_text = time_text.lower()
        
        if '런치' in time_text or '점심' in time_text:
            return 'lunch'
        elif '디너' in time_text or '저녁' in time_text:
            return 'dinner'
        elif '평일' in time_text:
            return 'weekday'
        elif '주말' in time_text:
            return 'weekend'
        else:
            return 'other'

class PriceNormalizer:
    """가격 정보 정규화 통합 클래스"""
    
    def __init__(self):
        self.pattern_extractor = PricePatternExtractor()
        self.stats = {
            'total_processed': 0,
            'single_price': 0,
            'range_price': 0,
            'time_based_price': 0,
            'conditional_price': 0,
            'inquiry_price': 0,
            'unknown_price': 0,
            'success_rate': 0.0
        }
    
    def normalize_price(self, price_text: str, additional_info: Dict = None) -> PriceInfo:
        """가격 정보 정규화"""
        self.stats['total_processed'] += 1
        
        if not price_text:
            self.stats['unknown_price'] += 1
            return PriceInfo(price_type='unknown', original_text='')
        
        # 기본 정제
        cleaned_text = self._clean_price_text(price_text)
        
        # 추가 정보가 있는 경우 결합
        if additional_info:
            menu_info = additional_info.get('menu_items', [])
            if menu_info:
                cleaned_text += ' ' + ' '.join(menu_info[:3])  # 상위 3개 메뉴만
        
        # 패턴 추출
        price_info = self.pattern_extractor.extract_price_info(cleaned_text)
        
        # 통계 업데이트
        self.stats[f"{price_info.price_type}_price"] += 1
        
        # 성공률 계산
        success_types = ['single', 'range', 'time_based', 'conditional', 'inquiry']
        successful = sum(self.stats[f"{t}_price"] for t in success_types)
        self.stats['success_rate'] = (successful / self.stats['total_processed']) * 100
        
        return price_info
    
    def _clean_price_text(self, text: str) -> str:
        """가격 텍스트 정제"""
        if not text:
            return ""
        
        # 기본 정제
        cleaned = text.strip()
        
        # 불필요한 문구 제거
        remove_patterns = [
            r'가격\s*:',
            r'요금\s*:',
            r'비용\s*:',
            r'\s+',  # 여러 공백을 하나로
        ]
        
        for pattern in remove_patterns:
            cleaned = re.sub(pattern, ' ', cleaned)
        
        return cleaned.strip()
    
    def normalize_batch(self, price_data: List[Dict]) -> List[Dict]:
        """배치 가격 정규화"""
        results = []
        
        for item in price_data:
            price_text = item.get('price', '') or item.get('price_range', '')
            additional_info = {
                'menu_items': item.get('menu_items', []),
                'refill_items': item.get('refill_items', [])
            }
            
            normalized = self.normalize_price(price_text, additional_info)
            
            # 원본 데이터에 정규화된 정보 추가
            result = item.copy()
            result.update({
                'normalized_price': {
                    'price_type': normalized.price_type,
                    'min_price': normalized.min_price,
                    'max_price': normalized.max_price,
                    'time_based': normalized.time_based,
                    'conditions': normalized.conditions,
                    'confidence': normalized.confidence
                }
            })
            
            results.append(result)
        
        return results
    
    def get_stats(self) -> Dict:
        """정규화 통계 반환"""
        return self.stats.copy()
    
    def get_price_distribution(self, normalized_data: List[Dict]) -> Dict:
        """가격 분포 분석"""
        prices = []
        price_types = {}
        
        for item in normalized_data:
            norm_price = item.get('normalized_price', {})
            price_type = norm_price.get('price_type')
            
            if price_type:
                price_types[price_type] = price_types.get(price_type, 0) + 1
            
            min_price = norm_price.get('min_price')
            max_price = norm_price.get('max_price')
            
            if min_price:
                prices.append(min_price)
            if max_price and max_price != min_price:
                prices.append(max_price)
        
        if prices:
            prices.sort()
            return {
                'total_items': len(normalized_data),
                'price_types': price_types,
                'price_range': {
                    'min': min(prices),
                    'max': max(prices),
                    'median': prices[len(prices)//2],
                    'avg': sum(prices) / len(prices)
                },
                'price_brackets': {
                    '1만원 이하': len([p for p in prices if p <= 10000]),
                    '1-2만원': len([p for p in prices if 10000 < p <= 20000]),
                    '2-3만원': len([p for p in prices if 20000 < p <= 30000]),
                    '3만원 이상': len([p for p in prices if p > 30000])
                }
            }
        
        return {'total_items': len(normalized_data), 'no_price_data': True}

def test_price_normalizer():
    """가격 정규화 테스트 함수"""
    normalizer = PriceNormalizer()
    
    test_cases = [
        "1만원",
        "10,000원~15,000원",
        "런치 8천원, 디너 1만2천원",
        "1인 12000원 (2인 이상)",
        "무한리필 19900원",
        "가격 문의",
        "2만원대",
        "평일 1만8천원, 주말 2만2천원",
        "소고기 2만원, 돼지고기 1만5천원"
    ]
    
    print("=== 가격 정규화 테스트 ===")
    for test_case in test_cases:
        result = normalizer.normalize_price(test_case)
        print(f"\n입력: {test_case}")
        print(f"타입: {result.price_type}")
        print(f"가격: {result.min_price} ~ {result.max_price}")
        print(f"조건: {result.conditions}")
        print(f"시간대별: {result.time_based}")
        print(f"신뢰도: {result.confidence:.2f}")
    
    print(f"\n통계: {normalizer.get_stats()}")

if __name__ == "__main__":
    test_price_normalizer() 