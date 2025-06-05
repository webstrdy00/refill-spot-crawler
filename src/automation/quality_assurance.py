"""
6단계: 자동 품질 검증 시스템
무인 운영을 위한 데이터 품질 자동 검증 및 관리
"""

import logging
import re
import json
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import requests
from geopy.distance import geodesic
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
from ..core.database import DatabaseManager
from ..core.geocoding import GeocodingManager

logger = logging.getLogger(__name__)

@dataclass
class QualityConfig:
    """품질 검증 설정"""
    coordinate_validation_enabled: bool = True
    duplicate_detection_enabled: bool = True
    business_hours_validation_enabled: bool = True
    auto_fix_enabled: bool = True
    similarity_threshold: float = 0.85
    cluster_eps: float = 0.3
    batch_size: int = 1000
    max_workers: int = 4

@dataclass
class QualityIssue:
    """품질 문제 정보"""
    store_id: str
    issue_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    suggested_action: str
    detected_at: datetime
    auto_fixable: bool = False

@dataclass
class QualityReport:
    """품질 검증 리포트"""
    total_stores: int
    issues_found: int
    critical_issues: int
    auto_fixed: int
    quality_score: float
    issues: List[QualityIssue]
    processing_time: float

class CoordinateValidator:
    """좌표 유효성 검증 (강화)"""
    
    def __init__(self):
        self.geocoding_manager = GeocodingManager()
        self.korea_bounds = {
            'min_lat': 33.0, 'max_lat': 38.6,
            'min_lng': 124.5, 'max_lng': 132.0
        }
        
        # 서울 구별 경계 (대략적)
        self.seoul_district_bounds = {
            '강남구': {'lat': (37.4979, 37.5279), 'lng': (127.0276, 127.0576)},
            '마포구': {'lat': (37.5400, 37.5700), 'lng': (126.9000, 126.9400)},
            '서초구': {'lat': (37.4700, 37.5100), 'lng': (127.0000, 127.0500)},
            # ... 다른 구들도 추가 가능
        }
    
    def validate_coordinates(self, store: Dict) -> List[QualityIssue]:
        """좌표가 실제 주소와 일치하는지 검증"""
        issues = []
        
        lat = store.get('position_lat')
        lng = store.get('position_lng')
        address = store.get('address', '')
        store_id = store.get('diningcode_place_id', 'unknown')
        
        # 1. 기본 좌표 유효성 검증
        if not lat or not lng:
            issues.append(QualityIssue(
                store_id=store_id,
                issue_type='missing_coordinates',
                severity='high',
                description='좌표 정보가 누락됨',
                suggested_action='지오코딩 API를 통한 좌표 재생성',
                detected_at=datetime.now(),
                auto_fixable=True
            ))
            return issues
        
        try:
            lat, lng = float(lat), float(lng)
        except (ValueError, TypeError):
            issues.append(QualityIssue(
                store_id=store_id,
                issue_type='invalid_coordinate_format',
                severity='critical',
                description='좌표 형식이 잘못됨',
                suggested_action='좌표 데이터 재수집',
                detected_at=datetime.now(),
                auto_fixable=True
            ))
            return issues
        
        # 2. 한국 영역 내 확인
        if not self._is_within_korea(lat, lng):
            issues.append(QualityIssue(
                store_id=store_id,
                issue_type='coordinates_outside_korea',
                severity='critical',
                description=f'좌표가 한국 영역 밖에 위치: ({lat}, {lng})',
                suggested_action='주소 기반 좌표 재생성',
                detected_at=datetime.now(),
                auto_fixable=True
            ))
        
        # 3. 주소-좌표 일치성 검증
        if address:
            address_validation = self._validate_address_coordinate_match(address, lat, lng)
            if not address_validation['is_valid']:
                issues.append(QualityIssue(
                    store_id=store_id,
                    issue_type='address_coordinate_mismatch',
                    severity='medium',
                    description=f'주소와 좌표 불일치: {address_validation["reason"]}',
                    suggested_action='주소 기반 좌표 재검증',
                    detected_at=datetime.now(),
                    auto_fixable=True
                ))
        
        # 4. 바다/산속 등 의심스러운 위치 확인
        if self._is_suspicious_location(lat, lng):
            issues.append(QualityIssue(
                store_id=store_id,
                issue_type='suspicious_location',
                severity='medium',
                description='음식점이 있기 어려운 위치 (바다, 산속 등)',
                suggested_action='좌표 재검증 필요',
                detected_at=datetime.now(),
                auto_fixable=False
            ))
        
        return issues
    
    def _is_within_korea(self, lat: float, lng: float) -> bool:
        """한국 영역 내부 여부 확인"""
        return (self.korea_bounds['min_lat'] <= lat <= self.korea_bounds['max_lat'] and
                self.korea_bounds['min_lng'] <= lng <= self.korea_bounds['max_lng'])
    
    def _validate_address_coordinate_match(self, address: str, lat: float, lng: float) -> Dict:
        """주소와 좌표 일치성 검증"""
        # 주소에서 구 정보 추출
        district = self._extract_district_from_address(address)
        
        if district and district in self.seoul_district_bounds:
            bounds = self.seoul_district_bounds[district]
            
            # 구 경계 내에 있는지 확인
            if not (bounds['lat'][0] <= lat <= bounds['lat'][1] and
                    bounds['lng'][0] <= lng <= bounds['lng'][1]):
                return {
                    'is_valid': False,
                    'reason': f'{district} 경계를 벗어남'
                }
        
        # 지오코딩 API로 주소 검증 (선택적)
        try:
            geocoded = self.geocoding_manager.geocode_address(address)
            if geocoded:
                distance = geodesic((lat, lng), (geocoded.latitude, geocoded.longitude)).meters
                if distance > 1000:  # 1km 이상 차이
                    return {
                        'is_valid': False,
                        'reason': f'지오코딩 결과와 {distance:.0f}m 차이'
                    }
        except Exception as e:
            logger.warning(f"지오코딩 검증 실패: {e}")
        
        return {'is_valid': True, 'reason': ''}
    
    def _extract_district_from_address(self, address: str) -> Optional[str]:
        """주소에서 구 정보 추출"""
        for district in self.seoul_district_bounds.keys():
            if district in address:
                return district
        return None
    
    def _is_suspicious_location(self, lat: float, lng: float) -> bool:
        """의심스러운 위치 확인"""
        # 인천공항 활주로 등 명백히 음식점이 있을 수 없는 곳
        suspicious_areas = [
            {'lat_range': (37.44, 37.47), 'lng_range': (126.43, 126.46), 'name': '인천공항'},
            {'lat_range': (37.55, 37.57), 'lng_range': (126.79, 126.81), 'name': '김포공항'},
        ]
        
        for area in suspicious_areas:
            if (area['lat_range'][0] <= lat <= area['lat_range'][1] and
                area['lng_range'][0] <= lng <= area['lng_range'][1]):
                return True
        
        return False

class MLDuplicateDetector:
    """ML 기반 중복 가게 자동 감지"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,
            ngram_range=(1, 2)
        )
        self.similarity_threshold = 0.85
        self.distance_threshold = 200  # 200m
    
    def detect_duplicates(self, stores: List[Dict]) -> List[QualityIssue]:
        """ML 기반 중복 가게 감지"""
        issues = []
        
        if len(stores) < 2:
            return issues
        
        logger.info(f"ML 기반 중복 감지 시작: {len(stores)}개 가게")
        
        # 1. 특성 벡터 생성
        features = self._extract_features(stores)
        
        # 2. 텍스트 유사도 계산
        text_similarities = self._calculate_text_similarities(stores)
        
        # 3. 위치 기반 클러스터링
        location_clusters = self._cluster_by_location(stores)
        
        # 4. 종합 중복 판단
        duplicate_groups = self._identify_duplicate_groups(
            stores, text_similarities, location_clusters, features
        )
        
        # 5. 중복 이슈 생성
        for group in duplicate_groups:
            if len(group) > 1:
                primary_store = stores[group[0]]
                duplicate_stores = [stores[i] for i in group[1:]]
                
                for dup_store in duplicate_stores:
                    issues.append(QualityIssue(
                        store_id=dup_store.get('diningcode_place_id', 'unknown'),
                        issue_type='duplicate_store',
                        severity='medium',
                        description=f'중복 가게 감지: {primary_store.get("name")}와 유사',
                        suggested_action='수동 검토 후 중복 제거',
                        detected_at=datetime.now(),
                        auto_fixable=False
                    ))
        
        logger.info(f"중복 감지 완료: {len(duplicate_groups)}개 그룹, {len(issues)}개 이슈")
        return issues
    
    def _extract_features(self, stores: List[Dict]) -> np.ndarray:
        """가게 특성 벡터 추출"""
        features = []
        
        for store in stores:
            # 텍스트 특성
            name = store.get('name', '')
            address = store.get('address', '')
            description = store.get('description', '')
            
            # 위치 특성
            lat = store.get('position_lat', 0)
            lng = store.get('position_lng', 0)
            
            # 기타 특성
            phone = store.get('phone_number', '')
            
            feature_text = f"{name} {address} {description} {phone}"
            features.append(feature_text)
        
        return features
    
    def _calculate_text_similarities(self, stores: List[Dict]) -> np.ndarray:
        """텍스트 유사도 계산"""
        features = self._extract_features(stores)
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(features)
            similarities = cosine_similarity(tfidf_matrix)
            return similarities
        except Exception as e:
            logger.warning(f"텍스트 유사도 계산 실패: {e}")
            return np.zeros((len(stores), len(stores)))
    
    def _cluster_by_location(self, stores: List[Dict]) -> List[int]:
        """위치 기반 클러스터링"""
        coordinates = []
        
        for store in stores:
            lat = store.get('position_lat')
            lng = store.get('position_lng')
            
            if lat and lng:
                try:
                    coordinates.append([float(lat), float(lng)])
                except (ValueError, TypeError):
                    coordinates.append([0, 0])
            else:
                coordinates.append([0, 0])
        
        if not coordinates:
            return [-1] * len(stores)
        
        try:
            # DBSCAN 클러스터링 (eps는 대략 200m를 위도/경도로 변환)
            eps = 0.002  # 약 200m
            clustering = DBSCAN(eps=eps, min_samples=2).fit(coordinates)
            return clustering.labels_
        except Exception as e:
            logger.warning(f"위치 클러스터링 실패: {e}")
            return [-1] * len(stores)
    
    def _identify_duplicate_groups(self, stores: List[Dict], text_similarities: np.ndarray, 
                                 location_clusters: List[int], features: List[str]) -> List[List[int]]:
        """종합 중복 그룹 식별"""
        duplicate_groups = []
        processed = set()
        
        for i in range(len(stores)):
            if i in processed:
                continue
            
            current_group = [i]
            
            for j in range(i + 1, len(stores)):
                if j in processed:
                    continue
                
                # 중복 판단 기준
                is_duplicate = False
                
                # 1. 전화번호 일치
                if self._phone_numbers_match(stores[i], stores[j]):
                    is_duplicate = True
                
                # 2. 텍스트 유사도 + 위치 클러스터
                elif (text_similarities[i][j] > self.similarity_threshold and
                      location_clusters[i] == location_clusters[j] and
                      location_clusters[i] != -1):
                    is_duplicate = True
                
                # 3. 이름 매우 유사 + 가까운 거리
                elif (text_similarities[i][j] > 0.9 and
                      self._calculate_distance(stores[i], stores[j]) < 100):
                    is_duplicate = True
                
                if is_duplicate:
                    current_group.append(j)
                    processed.add(j)
            
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                processed.update(current_group)
        
        return duplicate_groups
    
    def _phone_numbers_match(self, store1: Dict, store2: Dict) -> bool:
        """전화번호 일치 확인"""
        phone1 = re.sub(r'[^0-9]', '', store1.get('phone_number', ''))
        phone2 = re.sub(r'[^0-9]', '', store2.get('phone_number', ''))
        
        if len(phone1) < 8 or len(phone2) < 8:
            return False
        
        return phone1 == phone2
    
    def _calculate_distance(self, store1: Dict, store2: Dict) -> float:
        """두 가게 간 거리 계산 (미터)"""
        lat1, lng1 = store1.get('position_lat'), store1.get('position_lng')
        lat2, lng2 = store2.get('position_lat'), store2.get('position_lng')
        
        if not all([lat1, lng1, lat2, lng2]):
            return float('inf')
        
        try:
            return geodesic((float(lat1), float(lng1)), (float(lat2), float(lng2))).meters
        except:
            return float('inf')

class BusinessHoursValidator:
    """영업시간 논리적 오류 검출"""
    
    def __init__(self):
        self.time_pattern = re.compile(r'(\d{1,2}):(\d{2})')
        self.common_errors = [
            'invalid_time_format',
            'impossible_hours',
            'break_time_conflict',
            'last_order_conflict',
            'holiday_conflict'
        ]
    
    def verify_business_hours(self, store: Dict) -> List[QualityIssue]:
        """영업시간 논리적 오류 검출"""
        issues = []
        store_id = store.get('diningcode_place_id', 'unknown')
        
        open_hours = store.get('open_hours', '')
        break_time = store.get('break_time', '')
        last_order = store.get('last_order', '')
        holiday = store.get('holiday', '')
        
        # 1. 영업시간 형식 검증
        if open_hours:
            format_issues = self._validate_time_format(open_hours)
            for issue in format_issues:
                issues.append(QualityIssue(
                    store_id=store_id,
                    issue_type='invalid_time_format',
                    severity='low',
                    description=f'영업시간 형식 오류: {issue}',
                    suggested_action='영업시간 형식 표준화',
                    detected_at=datetime.now(),
                    auto_fixable=True
                ))
        
        # 2. 논리적 오류 검증
        logical_issues = self._validate_time_logic(open_hours, break_time, last_order)
        for issue in logical_issues:
            issues.append(QualityIssue(
                store_id=store_id,
                issue_type='business_hours_logic_error',
                severity='medium',
                description=issue,
                suggested_action='영업시간 정보 재검토',
                detected_at=datetime.now(),
                auto_fixable=False
            ))
        
        # 3. 24시간 영업 검증
        if self._is_24_hour_claim(open_hours):
            if break_time or last_order:
                issues.append(QualityIssue(
                    store_id=store_id,
                    issue_type='24hour_conflict',
                    severity='medium',
                    description='24시간 영업인데 브레이크타임/라스트오더 존재',
                    suggested_action='영업시간 정보 일관성 확인',
                    detected_at=datetime.now(),
                    auto_fixable=False
                ))
        
        return issues
    
    def _validate_time_format(self, time_text: str) -> List[str]:
        """시간 형식 검증"""
        issues = []
        
        # 시간 패턴 찾기
        times = self.time_pattern.findall(time_text)
        
        for hour_str, minute_str in times:
            hour, minute = int(hour_str), int(minute_str)
            
            # 시간 범위 검증
            if not (0 <= hour <= 24):
                issues.append(f'잘못된 시간: {hour}시')
            
            if not (0 <= minute <= 59):
                issues.append(f'잘못된 분: {minute}분')
        
        return issues
    
    def _validate_time_logic(self, open_hours: str, break_time: str, last_order: str) -> List[str]:
        """영업시간 논리 검증"""
        issues = []
        
        # 영업시간에서 시작/종료 시간 추출
        open_times = self._extract_time_ranges(open_hours)
        
        for start_time, end_time in open_times:
            # 시작 시간이 종료 시간보다 늦은 경우 (다음날 영업 제외)
            if start_time and end_time:
                if start_time >= end_time and end_time > 12:  # 12시 이후 종료는 다음날로 간주
                    issues.append(f'영업 시작시간({start_time})이 종료시간({end_time})보다 늦음')
        
        # 브레이크타임 검증
        if break_time and open_times:
            break_times = self._extract_time_ranges(break_time)
            for break_start, break_end in break_times:
                if break_start and break_end:
                    # 브레이크타임이 영업시간 밖에 있는지 확인
                    is_within_hours = False
                    for open_start, open_end in open_times:
                        if open_start and open_end:
                            if open_start <= break_start <= open_end:
                                is_within_hours = True
                                break
                    
                    if not is_within_hours:
                        issues.append(f'브레이크타임({break_start}-{break_end})이 영업시간 밖에 설정됨')
        
        return issues
    
    def _extract_time_ranges(self, time_text: str) -> List[Tuple[Optional[int], Optional[int]]]:
        """시간 범위 추출 (HH:MM 형태를 분 단위로 변환)"""
        ranges = []
        
        # "HH:MM - HH:MM" 또는 "HH:MM~HH:MM" 패턴 찾기
        range_pattern = re.compile(r'(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})')
        matches = range_pattern.findall(time_text)
        
        for match in matches:
            start_hour, start_min, end_hour, end_min = map(int, match)
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            ranges.append((start_minutes, end_minutes))
        
        return ranges
    
    def _is_24_hour_claim(self, open_hours: str) -> bool:
        """24시간 영업 표시 확인"""
        indicators = ['24시간', '24hour', '24hr', '24H', '무휴', '24/7']
        return any(indicator in open_hours for indicator in indicators)

class QualityAssurance:
    """데이터 품질 자동 검증 통합 시스템"""
    
    def __init__(self, config: QualityConfig, db_path: str):
        self.config = config
        self.db_path = db_path
        self.coordinate_validator = CoordinateValidator()
        self.duplicate_detector = MLDuplicateDetector()
        self.hours_validator = BusinessHoursValidator()
        self.db_manager = DatabaseManager()
    
    async def run_comprehensive_quality_check(self) -> QualityReport:
        """포괄적 품질 검증 실행 (비동기)"""
        return self.run_quality_check()
    
    def run_quality_check(self, stores: List[Dict] = None) -> QualityReport:
        """전체 품질 검증 실행"""
        start_time = time.time()
        
        logger.info("=== 자동 품질 검증 시작 ===")
        
        # 데이터 로드 (전달되지 않은 경우 DB에서 조회)
        if stores is None:
            stores = self._load_stores_from_db()
        
        total_stores = len(stores)
        all_issues = []
        auto_fixed = 0
        
        logger.info(f"검증 대상: {total_stores}개 가게")
        
        # 1. 좌표 유효성 검증
        logger.info("1️⃣ 좌표 유효성 검증 중...")
        for store in stores:
            coordinate_issues = self.coordinate_validator.validate_coordinates(store)
            all_issues.extend(coordinate_issues)
            
            # 자동 수정 가능한 이슈 처리
            for issue in coordinate_issues:
                if issue.auto_fixable:
                    if self._auto_fix_coordinate_issue(store, issue):
                        auto_fixed += 1
        
        # 2. 중복 가게 감지
        logger.info("2️⃣ ML 기반 중복 가게 감지 중...")
        duplicate_issues = self.duplicate_detector.detect_duplicates(stores)
        all_issues.extend(duplicate_issues)
        
        # 3. 영업시간 검증
        logger.info("3️⃣ 영업시간 논리 검증 중...")
        for store in stores:
            hours_issues = self.hours_validator.verify_business_hours(store)
            all_issues.extend(hours_issues)
            
            # 자동 수정 가능한 이슈 처리
            for issue in hours_issues:
                if issue.auto_fixable:
                    if self._auto_fix_hours_issue(store, issue):
                        auto_fixed += 1
        
        # 품질 점수 계산
        quality_score = self._calculate_quality_score(total_stores, all_issues)
        
        # 심각한 이슈 수 계산
        critical_issues = sum(1 for issue in all_issues if issue.severity == 'critical')
        
        processing_time = time.time() - start_time
        
        report = QualityReport(
            total_stores=total_stores,
            issues_found=len(all_issues),
            critical_issues=critical_issues,
            auto_fixed=auto_fixed,
            quality_score=quality_score,
            issues=all_issues,
            processing_time=processing_time
        )
        
        logger.info("=== 품질 검증 완료 ===")
        logger.info(f"총 이슈: {len(all_issues)}개")
        logger.info(f"심각한 이슈: {critical_issues}개")
        logger.info(f"자동 수정: {auto_fixed}개")
        logger.info(f"품질 점수: {quality_score:.1f}/100")
        logger.info(f"처리 시간: {processing_time:.2f}초")
        
        return report
    
    def _load_stores_from_db(self) -> List[Dict]:
        """데이터베이스에서 가게 정보 로드"""
        try:
            query = """
            SELECT diningcode_place_id, name, address, position_lat, position_lng,
                   phone_number, open_hours, open_hours_raw, break_time, 
                   last_order, holiday, description
            FROM refill_spots 
            WHERE status = '운영중'
            ORDER BY created_at DESC
            """
            
            results = self.db_manager.execute_query(query)
            
            stores = []
            for row in results:
                store = {
                    'diningcode_place_id': row[0],
                    'name': row[1],
                    'address': row[2],
                    'position_lat': row[3],
                    'position_lng': row[4],
                    'phone_number': row[5],
                    'open_hours': row[6],
                    'open_hours_raw': row[7],
                    'break_time': row[8],
                    'last_order': row[9],
                    'holiday': row[10],
                    'description': row[11]
                }
                stores.append(store)
            
            return stores
            
        except Exception as e:
            logger.error(f"데이터베이스에서 가게 정보 로드 실패: {e}")
            return []
    
    def _auto_fix_coordinate_issue(self, store: Dict, issue: QualityIssue) -> bool:
        """좌표 이슈 자동 수정"""
        try:
            if issue.issue_type == 'missing_coordinates':
                # 주소 기반 지오코딩
                address = store.get('address')
                if address:
                    geocoded = self.coordinate_validator.geocoding_manager.geocode_address(address)
                    if geocoded:
                        # 데이터베이스 업데이트
                        self._update_store_coordinates(
                            store.get('diningcode_place_id'),
                            geocoded.latitude,
                            geocoded.longitude
                        )
                        logger.info(f"좌표 자동 수정: {store.get('name')} -> ({geocoded.latitude}, {geocoded.longitude})")
                        return True
            
            elif issue.issue_type == 'address_coordinate_mismatch':
                # 주소 기반 좌표 재생성
                address = store.get('address')
                if address:
                    geocoded = self.coordinate_validator.geocoding_manager.geocode_address(address)
                    if geocoded:
                        self._update_store_coordinates(
                            store.get('diningcode_place_id'),
                            geocoded.latitude,
                            geocoded.longitude
                        )
                        logger.info(f"좌표 불일치 자동 수정: {store.get('name')}")
                        return True
            
        except Exception as e:
            logger.warning(f"좌표 이슈 자동 수정 실패: {e}")
        
        return False
    
    def _auto_fix_hours_issue(self, store: Dict, issue: QualityIssue) -> bool:
        """영업시간 이슈 자동 수정"""
        try:
            if issue.issue_type == 'invalid_time_format':
                # 시간 형식 표준화
                open_hours = store.get('open_hours', '')
                normalized_hours = self._normalize_time_format(open_hours)
                
                if normalized_hours != open_hours:
                    self._update_store_hours(
                        store.get('diningcode_place_id'),
                        normalized_hours
                    )
                    logger.info(f"영업시간 형식 자동 수정: {store.get('name')}")
                    return True
            
        except Exception as e:
            logger.warning(f"영업시간 이슈 자동 수정 실패: {e}")
        
        return False
    
    def _normalize_time_format(self, time_text: str) -> str:
        """시간 형식 표준화"""
        # 다양한 시간 표기를 표준 형식으로 변환
        normalized = time_text
        
        # "오전/오후" 표기 변환
        normalized = re.sub(r'오전\s*(\d{1,2})', r'\1', normalized)
        normalized = re.sub(r'오후\s*(\d{1,2})', lambda m: str(int(m.group(1)) + 12), normalized)
        
        # 시간 구분자 표준화
        normalized = re.sub(r'(\d{1,2})\s*시\s*(\d{1,2})\s*분', r'\1:\2', normalized)
        normalized = re.sub(r'(\d{1,2})\s*시', r'\1:00', normalized)
        
        # 범위 구분자 표준화
        normalized = re.sub(r'\s*~\s*', ' - ', normalized)
        normalized = re.sub(r'\s*-\s*', ' - ', normalized)
        
        return normalized.strip()
    
    def _update_store_coordinates(self, store_id: str, lat: float, lng: float):
        """가게 좌표 업데이트"""
        query = """
        UPDATE refill_spots 
        SET position_lat = %s, position_lng = %s, updated_at = NOW()
        WHERE diningcode_place_id = %s
        """
        self.db_manager.execute_query(query, (lat, lng, store_id))
    
    def _update_store_hours(self, store_id: str, hours: str):
        """가게 영업시간 업데이트"""
        query = """
        UPDATE refill_spots 
        SET open_hours = %s, updated_at = NOW()
        WHERE diningcode_place_id = %s
        """
        self.db_manager.execute_query(query, (hours, store_id))
    
    def _calculate_quality_score(self, total_stores: int, issues: List[QualityIssue]) -> float:
        """품질 점수 계산 (0-100)"""
        if total_stores == 0:
            return 100.0
        
        # 심각도별 가중치
        severity_weights = {
            'low': 1,
            'medium': 3,
            'high': 7,
            'critical': 15
        }
        
        # 총 감점 계산
        total_deduction = 0
        for issue in issues:
            weight = severity_weights.get(issue.severity, 1)
            total_deduction += weight
        
        # 점수 계산 (최대 감점은 총 가게 수 * 15)
        max_possible_deduction = total_stores * 15
        score = max(0, 100 - (total_deduction / max_possible_deduction * 100))
        
        return round(score, 1)
    
    def generate_quality_report_json(self, report: QualityReport) -> str:
        """품질 리포트 JSON 생성"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_stores': report.total_stores,
                'issues_found': report.issues_found,
                'critical_issues': report.critical_issues,
                'auto_fixed': report.auto_fixed,
                'quality_score': report.quality_score,
                'processing_time': report.processing_time
            },
            'issues_by_type': {},
            'issues_by_severity': {},
            'detailed_issues': []
        }
        
        # 이슈 유형별 집계
        for issue in report.issues:
            issue_type = issue.issue_type
            severity = issue.severity
            
            if issue_type not in report_data['issues_by_type']:
                report_data['issues_by_type'][issue_type] = 0
            report_data['issues_by_type'][issue_type] += 1
            
            if severity not in report_data['issues_by_severity']:
                report_data['issues_by_severity'][severity] = 0
            report_data['issues_by_severity'][severity] += 1
            
            # 상세 이슈 정보
            report_data['detailed_issues'].append({
                'store_id': issue.store_id,
                'issue_type': issue.issue_type,
                'severity': issue.severity,
                'description': issue.description,
                'suggested_action': issue.suggested_action,
                'detected_at': issue.detected_at.isoformat(),
                'auto_fixable': issue.auto_fixable
            })
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)

def run_quality_assurance():
    """품질 검증 실행 함수"""
    qa_system = QualityAssurance()
    report = qa_system.run_quality_check()
    
    # 리포트 저장
    report_json = qa_system.generate_quality_report_json(report)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(f'data/quality_report_{timestamp}.json', 'w', encoding='utf-8') as f:
        f.write(report_json)
    
    logger.info(f"품질 리포트 저장: data/quality_report_{timestamp}.json")
    
    return report

if __name__ == "__main__":
    run_quality_assurance() 