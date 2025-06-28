"""
서울 25개 구 완전 데이터베이스 및 상권 분석 시스템
4단계: 서울 완전 커버리지 구현
"""

import logging
import requests
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import math

logger = logging.getLogger(__name__)

@dataclass
class DistrictInfo:
    """구 정보 데이터 클래스"""
    name: str
    priority: int
    density: str
    hotspots: List[str]
    center: Dict[str, float]
    rect: str
    keywords: List[str]
    status: str = "대기"
    expected_stores: int = 0
    subway_stations: List[str] = None

@dataclass
class HotspotInfo:
    """핫스팟 정보 데이터 클래스"""
    name: str
    rect: str
    density: str
    daily_passengers: int = 0
    commercial_score: float = 0.0
    grid_size: int = 800  # 기본 격자 크기 (미터)

# 서울 25개 구 완전 분류 (상권 밀도 및 무한리필 수요 기반)
SEOUL_DISTRICTS = {
    # Tier 1: 초고밀도 상권 (이미 완료)
    "강남구": {
        "priority": 1, 
        "density": "초고밀도", 
        "status": "완료",
        "hotspots": ["강남역", "선릉역", "압구정로데오", "청담", "대치"],
        "expected_stores": 80,
        "subway_stations": ["강남역", "선릉역", "역삼역", "압구정역", "청담역", "대치역", "학여울역", "대청역", "일원역", "수서역"]
    },
    "마포구": {
        "priority": 1, 
        "density": "초고밀도", 
        "status": "완료",
        "hotspots": ["홍대입구", "합정", "상암", "공덕", "아현"],
        "expected_stores": 75,
        "subway_stations": ["홍대입구역", "합정역", "상암역", "공덕역", "아현역", "신촌역", "마포역", "망원역"]
    },
    "서초구": {
        "priority": 1, 
        "density": "고밀도", 
        "status": "부분완료",
        "hotspots": ["강남역", "교대", "사당", "방배", "서초"],
        "expected_stores": 70,
        "subway_stations": ["교대역", "서초역", "방배역", "사당역", "남태령역", "양재역", "매봉역", "도곡역"]
    },
    
    # Tier 2: 고밀도 상권 (우선 확장 대상)
    "송파구": {
        "priority": 2, 
        "density": "고밀도",
        "hotspots": ["잠실", "석촌호수", "가락시장", "문정", "방이"],
        "expected_stores": 65,
        "subway_stations": ["잠실역", "석촌호수역", "가락시장역", "문정역", "방이역", "오금역", "개롱역", "거여역", "마천역"]
    },
    "영등포구": {
        "priority": 2, 
        "density": "고밀도",
        "hotspots": ["여의도", "영등포역", "당산", "신길", "대림"],
        "expected_stores": 60,
        "subway_stations": ["여의도역", "영등포역", "당산역", "신길역", "대림역", "도림천역", "양화역", "선유도역"]
    },
    "용산구": {
        "priority": 2, 
        "density": "고밀도",
        "hotspots": ["이태원", "용산역", "한강진", "효창공원앞", "삼각지"],
        "expected_stores": 55,
        "subway_stations": ["이태원역", "용산역", "한강진역", "효창공원앞역", "삼각지역", "녹사평역", "신용산역"]
    },
    "성동구": {
        "priority": 2, 
        "density": "고밀도",
        "hotspots": ["건대입구", "성수동", "왕십리", "금호", "옥수"],
        "expected_stores": 55,
        "subway_stations": ["건대입구역", "성수역", "왕십리역", "금고역", "옥수역", "압구정역", "한양대역", "뚝섬역"]
    },
    "광진구": {
        "priority": 2, 
        "density": "고밀도",
        "hotspots": ["건대", "구의역", "자양동", "광나루", "천호"],
        "expected_stores": 50,
        "subway_stations": ["건대입구역", "구의역", "강변역", "자양역", "광나루역", "천호역", "아차산역"]
    },
    
    # Tier 3: 중밀도 상권 (대학가/주거상업 복합)
    "관악구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["신림", "서울대입구", "봉천", "사당", "낙성대"],
        "expected_stores": 45,
        "subway_stations": ["신림역", "서울대입구역", "봉천역", "사당역", "낙성대역", "서원역"]
    },
    "서대문구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["신촌", "이대", "홍제", "독립문", "아현"],
        "expected_stores": 40,
        "subway_stations": ["신촌역", "이대역", "홍제역", "독립문역", "아현역", "충정로역"]
    },
    "종로구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["종각", "인사동", "대학로", "혜화", "동대문"],
        "expected_stores": 40,
        "subway_stations": ["종각역", "인사동역", "혜화역", "동대문역", "을지로입구역", "종로3가역", "안국역", "경복궁역"]
    },
    "중구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["명동", "동대문", "을지로", "충무로", "회현"],
        "expected_stores": 35,
        "subway_stations": ["명동역", "동대문역", "을지로역", "충무로역", "회현역", "시청역", "을지로3가역", "을지로4가역"]
    },
    "성북구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["성신여대입구", "한성대입구", "길음", "미아", "정릉"],
        "expected_stores": 35,
        "subway_stations": ["성신여대입구역", "한성대입구역", "길음역", "미아역", "정릉역", "보문역"]
    },
    "동대문구": {
        "priority": 3, 
        "density": "중밀도",
        "hotspots": ["회기", "외대앞", "청량리", "신설동", "제기동"],
        "expected_stores": 35,
        "subway_stations": ["회기역", "외대앞역", "청량리역", "신설동역", "제기동역", "동대문역사문화공원역"]
    },
    
    # Tier 4: 주거 중심 (꾸준한 수요)
    "노원구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["노원역", "상계역", "중계", "하계", "공릉"],
        "expected_stores": 30,
        "subway_stations": ["노원역", "상계역", "중계역", "하계역", "공릉역", "태릉입구역", "화랑대역"]
    },
    "강북구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["수유역", "미아역", "미아사거리", "번동", "우이"],
        "expected_stores": 30,
        "subway_stations": ["수유역", "미아역", "미아사거리역", "길음역", "4.19민주묘지역", "솔밭공원역", "북한산우이역"]
    },
    "은평구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["연신내", "불광", "응암", "역촌", "구파발"],
        "expected_stores": 30,
        "subway_stations": ["연신내역", "불광역", "응암역", "역촌역", "구파발역", "독바위역", "화정역"]
    },
    "강서구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["화곡", "발산", "공항대로", "마곡", "염창"],
        "expected_stores": 30,
        "subway_stations": ["화곡역", "발산역", "마곡역", "염창역", "등촌역", "김포공항역", "송정역", "마곡나루역"]
    },
    "양천구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["목동", "신정네거리", "양천구청", "신월", "오목교"],
        "expected_stores": 25,
        "subway_stations": ["목동역", "신정네거리역", "양천구청역", "신월역", "오목교역", "양평역"]
    },
    "구로구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["신도림", "구로디지털단지", "대림", "구일", "개봉"],
        "expected_stores": 25,
        "subway_stations": ["신도림역", "구로디지털단지역", "대림역", "구일역", "개봉역", "오류동역", "천왕역"]
    },
    "금천구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["가산디지털단지", "독산", "시흥", "금천구청", "석수"],
        "expected_stores": 25,
        "subway_stations": ["가산디지털단지역", "독산역", "시흥역", "금천구청역", "석수역", "관악역"]
    },
    "동작구": {
        "priority": 4, 
        "density": "중저밀도",
        "hotspots": ["사당", "노량진", "상도", "흑석", "동작"],
        "expected_stores": 25,
        "subway_stations": ["사당역", "노량진역", "상도역", "흑석역", "동작역", "총신대입구역", "이수역"]
    },
    
    # Tier 5: 저밀도 (선택적 커버리지)
    "강동구": {
        "priority": 5, 
        "density": "저밀도",
        "hotspots": ["천호", "강동역", "길동", "둔촌동", "암사"],
        "expected_stores": 20,
        "subway_stations": ["천호역", "강동역", "길동역", "둔촌동역", "암사역", "상일동역", "고덕역", "명일역"]
    },
    "중랑구": {
        "priority": 5, 
        "density": "저밀도",
        "hotspots": ["상봉", "면목", "중화", "먹골", "신내"],
        "expected_stores": 20,
        "subway_stations": ["상봉역", "면목역", "중화역", "먹골역", "신내역", "망우역", "용마산역", "사가정역"]
    },
    "도봉구": {
        "priority": 5, 
        "density": "저밀도",
        "hotspots": ["도봉산", "창동", "방학", "쌍문", "도봉"],
        "expected_stores": 20,
        "subway_stations": ["도봉산역", "창동역", "방학역", "쌍문역", "도봉역", "망월사역"]
    }
}

# 주요 구의 세부 상권 분석 (역세권 중심)
DETAILED_HOTSPOTS = {
    "강남구": {
        "강남역": {
            "rect": "37.4979,127.0276,37.5079,127.0376", 
            "density": "최고",
            "daily_passengers": 200000,
            "commercial_score": 10.0,
            "grid_size": 300
        },
        "선릉역": {
            "rect": "37.5044,127.0481,37.5144,127.0581", 
            "density": "고",
            "daily_passengers": 80000,
            "commercial_score": 8.5,
            "grid_size": 500
        },
        "압구정로데오": {
            "rect": "37.5270,127.0287,37.5370,127.0387", 
            "density": "고",
            "daily_passengers": 60000,
            "commercial_score": 8.0,
            "grid_size": 500
        },
        "청담": {
            "rect": "37.5197,127.0478,37.5297,127.0578", 
            "density": "중",
            "daily_passengers": 40000,
            "commercial_score": 7.0,
            "grid_size": 800
        },
        "대치": {
            "rect": "37.4942,127.0625,37.5042,127.0725", 
            "density": "중저",
            "daily_passengers": 30000,
            "commercial_score": 6.0,
            "grid_size": 1200
        }
    },
    
    "송파구": {
        "잠실": {
            "rect": "37.5080,127.0820,37.5180,127.0920", 
            "density": "최고",
            "daily_passengers": 150000,
            "commercial_score": 9.5,
            "grid_size": 300
        },
        "석촌호수": {
            "rect": "37.5069,127.1003,37.5169,127.1103", 
            "density": "고",
            "daily_passengers": 70000,
            "commercial_score": 8.0,
            "grid_size": 500
        },
        "가락시장": {
            "rect": "37.4928,127.1185,37.5028,127.1285", 
            "density": "고",
            "daily_passengers": 60000,
            "commercial_score": 7.5,
            "grid_size": 500
        },
        "문정": {
            "rect": "37.4848,127.1249,37.4948,127.1349", 
            "density": "중",
            "daily_passengers": 40000,
            "commercial_score": 6.5,
            "grid_size": 800
        },
        "방이": {
            "rect": "37.5107,127.1265,37.5207,127.1365", 
            "density": "중저",
            "daily_passengers": 25000,
            "commercial_score": 5.5,
            "grid_size": 1200
        }
    },
    
    "영등포구": {
        "여의도": {
            "rect": "37.5194,126.9194,37.5294,126.9294", 
            "density": "고",
            "daily_passengers": 100000,
            "commercial_score": 8.5,
            "grid_size": 500
        },
        "영등포역": {
            "rect": "37.5153,126.9073,37.5253,126.9173", 
            "density": "최고",
            "daily_passengers": 120000,
            "commercial_score": 9.0,
            "grid_size": 400
        },
        "당산": {
            "rect": "37.5344,126.8952,37.5444,126.9052", 
            "density": "고",
            "daily_passengers": 60000,
            "commercial_score": 7.5,
            "grid_size": 600
        },
        "신길": {
            "rect": "37.5071,126.9137,37.5171,126.9237", 
            "density": "중",
            "daily_passengers": 35000,
            "commercial_score": 6.0,
            "grid_size": 800
        },
        "대림": {
            "rect": "37.4931,126.8955,37.5031,126.9055", 
            "density": "중저",
            "daily_passengers": 25000,
            "commercial_score": 5.0,
            "grid_size": 1000
        }
    }
}

class SeoulDistrictManager:
    """서울 25개 구 관리 클래스"""
    
    def __init__(self):
        self.districts = self._initialize_districts()
        self.hotspots = DETAILED_HOTSPOTS
        
    def _initialize_districts(self) -> Dict[str, DistrictInfo]:
        """구 정보 초기화"""
        districts = {}
        
        for district_name, info in SEOUL_DISTRICTS.items():
            # 구 중심점 계산 (핫스팟들의 평균)
            center = self._calculate_district_center(district_name)
            
            # 구 전체 검색 영역 계산
            rect = self._calculate_district_rect(center)
            
            # 구별 맞춤 키워드 생성
            keywords = self._generate_district_keywords(district_name, info["hotspots"])
            
            districts[district_name] = DistrictInfo(
                name=district_name,
                priority=info["priority"],
                density=info["density"],
                hotspots=info["hotspots"],
                center=center,
                rect=rect,
                keywords=keywords,
                status=info.get("status", "대기"),
                expected_stores=info["expected_stores"],
                subway_stations=info.get("subway_stations", [])
            )
        
        return districts
    
    def _calculate_district_center(self, district_name: str) -> Dict[str, float]:
        """구의 중심점 계산"""
        # 서울시 공식 구청 위치 기반 중심점
        district_centers = {
            "강남구": {"lat": 37.5173, "lng": 127.0473},
            "마포구": {"lat": 37.5663, "lng": 126.9019},
            "서초구": {"lat": 37.4837, "lng": 127.0324},
            "송파구": {"lat": 37.5145, "lng": 127.1059},
            "영등포구": {"lat": 37.5264, "lng": 126.8962},
            "용산구": {"lat": 37.5384, "lng": 126.9654},
            "성동구": {"lat": 37.5636, "lng": 127.0365},
            "광진구": {"lat": 37.5384, "lng": 127.0822},
            "관악구": {"lat": 37.4781, "lng": 126.9515},
            "서대문구": {"lat": 37.5791, "lng": 126.9368},
            "종로구": {"lat": 37.5735, "lng": 126.9788},
            "중구": {"lat": 37.5641, "lng": 126.9979},
            "성북구": {"lat": 37.5894, "lng": 127.0167},
            "동대문구": {"lat": 37.5744, "lng": 127.0098},
            "노원구": {"lat": 37.6542, "lng": 127.0568},
            "강북구": {"lat": 37.6398, "lng": 127.0256},
            "은평구": {"lat": 37.6176, "lng": 126.9227},
            "강서구": {"lat": 37.5509, "lng": 126.8495},
            "양천구": {"lat": 37.5170, "lng": 126.8664},
            "구로구": {"lat": 37.4954, "lng": 126.8874},
            "금천구": {"lat": 37.4519, "lng": 126.9018},
            "동작구": {"lat": 37.5124, "lng": 126.9393},
            "강동구": {"lat": 37.5301, "lng": 127.1238},
            "중랑구": {"lat": 37.6063, "lng": 127.0925},
            "도봉구": {"lat": 37.6688, "lng": 127.0471}
        }
        
        return district_centers.get(district_name, {"lat": 37.5665, "lng": 126.9780})
    
    def _calculate_district_rect(self, center: Dict[str, float], radius_km: float = 3.0) -> str:
        """구의 검색 영역 계산"""
        lat = center["lat"]
        lng = center["lng"]
        
        # 위도/경도 변환 (1km ≈ 0.009도)
        lat_offset = radius_km * 0.009
        lng_offset = radius_km * 0.009 / 1.1  # 경도는 위도보다 약간 작음
        
        min_lat = lat - lat_offset
        min_lng = lng - lng_offset
        max_lat = lat + lat_offset
        max_lng = lng + lng_offset
        
        return f"{min_lat:.4f},{min_lng:.4f},{max_lat:.4f},{max_lng:.4f}"
    
    def _generate_district_keywords(self, district_name: str, hotspots: List[str]) -> List[str]:
        """구별 최적화된 키워드 생성"""
        base_keywords = [
            f"서울 {district_name} 무한리필",
            f"{district_name} 고기무한리필",
            f"{district_name} 무한리필 맛집"
        ]
        
        # 핫스팟별 키워드 추가 (무한리필만)
        hotspot_keywords = []
        for hotspot in hotspots:
            hotspot_keywords.extend([
                f"{hotspot} 무한리필",
                f"{hotspot} 고기무한리필",
                f"{hotspot}역 무한리필"
            ])
        
        # 서울 특화 키워드
        seoul_special = [
            f"{district_name} 회식 무한리필",
            f"{district_name} 가족 무한리필",
            f"{district_name} 저렴한 무한리필"
        ]
        
        return base_keywords + hotspot_keywords + seoul_special
    
    def get_district_by_priority(self, priority: int) -> List[DistrictInfo]:
        """우선순위별 구 목록 반환"""
        return [district for district in self.districts.values() 
                if district.priority == priority]
    
    def get_incomplete_districts(self) -> List[DistrictInfo]:
        """미완료 구 목록 반환"""
        return [district for district in self.districts.values() 
                if district.status in ["대기", "진행중", "오류"]]
    
    def get_district_info(self, district_name: str) -> Optional[DistrictInfo]:
        """특정 구 정보 반환"""
        return self.districts.get(district_name)
    
    def update_district_status(self, district_name: str, status: str, stores_found: int = 0):
        """구 상태 업데이트"""
        if district_name in self.districts:
            self.districts[district_name].status = status
            if stores_found > 0:
                self.districts[district_name].expected_stores = stores_found
    
    def get_seoul_coverage_stats(self) -> Dict:
        """서울 커버리지 통계"""
        total_districts = len(self.districts)
        completed = len([d for d in self.districts.values() if d.status == "완료"])
        in_progress = len([d for d in self.districts.values() if d.status == "진행중"])
        pending = len([d for d in self.districts.values() if d.status == "대기"])
        error = len([d for d in self.districts.values() if d.status == "오류"])
        
        total_expected_stores = sum(d.expected_stores for d in self.districts.values())
        
        return {
            "total_districts": total_districts,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "error": error,
            "completion_rate": completed / total_districts * 100,
            "total_expected_stores": total_expected_stores,
            "tier_breakdown": self._get_tier_breakdown()
        }
    
    def _get_tier_breakdown(self) -> Dict:
        """티어별 분석"""
        tier_stats = {}
        for tier in range(1, 6):
            tier_districts = self.get_district_by_priority(tier)
            tier_stats[f"tier_{tier}"] = {
                "count": len(tier_districts),
                "districts": [d.name for d in tier_districts],
                "completed": len([d for d in tier_districts if d.status == "완료"]),
                "expected_stores": sum(d.expected_stores for d in tier_districts)
            }
        return tier_stats

class SeoulGridSystem:
    """서울 전용 자동 격자 시스템"""
    
    def __init__(self, district_manager: SeoulDistrictManager):
        self.district_manager = district_manager
        self.seoul_open_data = SeoulOpenDataConnector()
    
    def create_station_based_grid(self, district_name: str) -> List[Dict]:
        """지하철역 기반 상권 중심 격자 생성"""
        district_info = self.district_manager.get_district_info(district_name)
        if not district_info:
            return []
        
        grids = []
        
        # 해당 구의 지하철역 목록
        stations = district_info.subway_stations or []
        
        for station in stations:
            # 역별 상권 규모 측정
            station_score = self._calculate_station_importance(station)
            
            # 상권 규모별 격자 크기 조정
            grid_size = self._determine_grid_size(station_score)
            
            # 역 중심 격자 생성
            station_coords = self._get_station_coordinates(station)
            if station_coords:
                station_grid = self._create_grid_around_point(
                    station_coords, grid_size, station
                )
                grids.append(station_grid)
        
        # 핫스팟 기반 추가 격자
        for hotspot in district_info.hotspots:
            if hotspot in DETAILED_HOTSPOTS.get(district_name, {}):
                hotspot_info = DETAILED_HOTSPOTS[district_name][hotspot]
                hotspot_grid = {
                    "name": f"{district_name}_{hotspot}",
                    "rect": hotspot_info["rect"],
                    "grid_size": hotspot_info["grid_size"],
                    "density": hotspot_info["density"],
                    "type": "hotspot"
                }
                grids.append(hotspot_grid)
        
        return grids
    
    def _calculate_station_importance(self, station: str) -> float:
        """역의 상권 중요도 계산"""
        # 실제로는 서울시 공공데이터에서 승하차 인원 등을 가져와야 함
        # 여기서는 간단한 휴리스틱 사용
        major_stations = {
            "강남역": 10.0, "잠실역": 9.5, "홍대입구역": 9.0, "신촌역": 8.5,
            "건대입구역": 8.0, "이태원역": 7.5, "명동역": 7.0, "종각역": 6.5,
            "영등포역": 9.0, "여의도역": 8.5, "사당역": 7.5, "노원역": 6.0
        }
        
        return major_stations.get(station, 5.0)  # 기본값 5.0
    
    def _determine_grid_size(self, station_score: float) -> int:
        """상권 규모별 격자 크기 결정"""
        if station_score >= 9:      # 초대형 상권
            return 300
        elif station_score >= 7:    # 대형 상권
            return 500
        elif station_score >= 5:    # 중형 상권
            return 800
        else:                       # 소형 상권
            return 1200
    
    def _get_station_coordinates(self, station: str) -> Optional[Dict[str, float]]:
        """지하철역 좌표 조회"""
        # 실제로는 서울시 지하철역 좌표 DB에서 조회
        # 여기서는 주요 역만 하드코딩
        station_coords = {
            "강남역": {"lat": 37.4979, "lng": 127.0276},
            "잠실역": {"lat": 37.5133, "lng": 127.1000},
            "홍대입구역": {"lat": 37.5571, "lng": 126.9245},
            "건대입구역": {"lat": 37.5401, "lng": 127.0695},
            "영등포역": {"lat": 37.5153, "lng": 126.9073},
            "사당역": {"lat": 37.4767, "lng": 126.9815}
        }
        
        return station_coords.get(station)
    
    def _create_grid_around_point(self, center: Dict[str, float], 
                                  grid_size: int, name: str) -> Dict:
        """특정 지점 중심의 격자 생성"""
        lat = center["lat"]
        lng = center["lng"]
        
        # 격자 크기를 위도/경도로 변환
        size_in_degrees = grid_size * 0.009 / 1000  # 미터를 도로 변환
        
        min_lat = lat - size_in_degrees / 2
        min_lng = lng - size_in_degrees / 2
        max_lat = lat + size_in_degrees / 2
        max_lng = lng + size_in_degrees / 2
        
        return {
            "name": f"{name}_grid",
            "rect": f"{min_lat:.4f},{min_lng:.4f},{max_lat:.4f},{max_lng:.4f}",
            "center": center,
            "grid_size": grid_size,
            "type": "station_based"
        }
    
    def optimize_grid_based_on_results(self, district_name: str, 
                                       grids: List[Dict], 
                                       crawling_results: List[Dict]) -> List[Dict]:
        """실제 크롤링 결과를 반영한 격자 최적화"""
        optimized_grids = []
        
        for grid in grids:
            # 해당 격자 내 가게 수 계산
            stores_in_grid = self._count_stores_in_grid(grid, crawling_results)
            
            if stores_in_grid > 50:
                # 너무 많은 가게 → 격자 세분화
                sub_grids = self._split_grid_into_4(grid)
                optimized_grids.extend(sub_grids)
                logger.info(f"격자 세분화: {grid['name']} - {stores_in_grid}개 → 4개 격자로 분할")
                
            elif stores_in_grid < 5:
                # 너무 적은 가게 → 주변 격자와 통합 고려
                merged_grid = self._merge_with_adjacent_grid(grid, grids)
                if merged_grid:
                    optimized_grids.append(merged_grid)
                    logger.info(f"격자 통합: {grid['name']} - {stores_in_grid}개 → 주변 격자와 병합")
                else:
                    optimized_grids.append(grid)  # 통합 실패 시 유지
                    
            else:
                # 적정 수준 → 유지
                optimized_grids.append(grid)
        
        return optimized_grids
    
    def _count_stores_in_grid(self, grid: Dict, stores: List[Dict]) -> int:
        """격자 내 가게 수 계산"""
        rect_parts = grid["rect"].split(",")
        min_lat, min_lng, max_lat, max_lng = map(float, rect_parts)
        
        count = 0
        for store in stores:
            lat = store.get("position_lat")
            lng = store.get("position_lng")
            
            if lat and lng:
                if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                    count += 1
        
        return count
    
    def _split_grid_into_4(self, grid: Dict) -> List[Dict]:
        """격자를 4개로 분할"""
        rect_parts = grid["rect"].split(",")
        min_lat, min_lng, max_lat, max_lng = map(float, rect_parts)
        
        mid_lat = (min_lat + max_lat) / 2
        mid_lng = (min_lng + max_lng) / 2
        
        sub_grids = []
        quadrants = [
            ("NW", min_lat, min_lng, mid_lat, mid_lng),
            ("NE", min_lat, mid_lng, mid_lat, max_lng),
            ("SW", mid_lat, min_lng, max_lat, mid_lng),
            ("SE", mid_lat, mid_lng, max_lat, max_lng)
        ]
        
        for i, (direction, s_lat, s_lng, e_lat, e_lng) in enumerate(quadrants):
            sub_grid = grid.copy()
            sub_grid["name"] = f"{grid['name']}_{direction}"
            sub_grid["rect"] = f"{s_lat:.4f},{s_lng:.4f},{e_lat:.4f},{e_lng:.4f}"
            sub_grid["grid_size"] = grid["grid_size"] // 2
            sub_grids.append(sub_grid)
        
        return sub_grids
    
    def _merge_with_adjacent_grid(self, grid: Dict, all_grids: List[Dict]) -> Optional[Dict]:
        """인접 격자와 통합"""
        # 간단한 구현: 첫 번째 인접 격자와 통합
        # 실제로는 더 정교한 인접성 검사 필요
        for other_grid in all_grids:
            if other_grid["name"] != grid["name"]:
                # 통합된 격자 생성 (간단한 예시)
                merged_grid = grid.copy()
                merged_grid["name"] = f"{grid['name']}_merged"
                return merged_grid
        
        return None

class SeoulOpenDataConnector:
    """서울시 공공데이터 연동 클래스"""
    
    def __init__(self):
        self.base_urls = {
            "district_boundaries": "http://data.seoul.go.kr/dataList/OA-11677/S/1/",
            "dong_boundaries": "http://data.seoul.go.kr/dataList/OA-11676/S/1/",
            "commercial_areas": "http://data.seoul.go.kr/dataList/OA-15560/S/1/",
            "subway_stations": "http://data.seoul.go.kr/dataList/OA-12035/S/1/"
        }
    
    def get_district_boundaries(self, district_name: str) -> Optional[Dict]:
        """구 경계 정보 조회"""
        # 실제 구현에서는 서울시 공공데이터 API 호출
        # 여기서는 더미 데이터 반환
        return {
            "district": district_name,
            "boundaries": "GeoJSON 형태의 경계 데이터",
            "area_km2": 24.5,
            "population": 570000
        }
    
    def get_commercial_density(self, district_name: str) -> Dict:
        """상권 밀도 정보 조회"""
        # 실제 구현에서는 상권 정보 API 호출
        return {
            "district": district_name,
            "total_businesses": 15000,
            "restaurant_count": 3500,
            "density_score": 8.5
        }
    
    def get_subway_passenger_data(self, station: str) -> Dict:
        """지하철역 승하차 인원 데이터"""
        # 실제 구현에서는 지하철 이용객 데이터 API 호출
        return {
            "station": station,
            "daily_passengers": 50000,
            "peak_hours": ["08:00-09:00", "18:00-19:00"],
            "commercial_score": 7.5
        }

def test_seoul_district_system():
    """서울 구 시스템 테스트"""
    logger.info("=== 서울 25개 구 시스템 테스트 ===")
    
    # 구 관리자 초기화
    district_manager = SeoulDistrictManager()
    
    # 전체 통계
    stats = district_manager.get_seoul_coverage_stats()
    logger.info(f"총 구 수: {stats['total_districts']}")
    logger.info(f"완료율: {stats['completion_rate']:.1f}%")
    logger.info(f"예상 총 가게 수: {stats['total_expected_stores']:,}개")
    
    # 티어별 분석
    for tier, info in stats['tier_breakdown'].items():
        logger.info(f"{tier}: {info['count']}개 구, 예상 {info['expected_stores']}개 가게")
        logger.info(f"  구 목록: {', '.join(info['districts'])}")
    
    # 미완료 구 목록
    incomplete = district_manager.get_incomplete_districts()
    logger.info(f"\n미완료 구: {len(incomplete)}개")
    for district in incomplete[:5]:  # 처음 5개만
        logger.info(f"  {district.name}: {district.status}, 예상 {district.expected_stores}개")
    
    # 격자 시스템 테스트
    grid_system = SeoulGridSystem(district_manager)
    
    # 강남구 격자 생성 테스트
    gangnam_grids = grid_system.create_station_based_grid("강남구")
    logger.info(f"\n강남구 격자 수: {len(gangnam_grids)}개")
    for grid in gangnam_grids[:3]:  # 처음 3개만
        logger.info(f"  {grid['name']}: {grid['rect']}, 크기: {grid.get('grid_size', 'N/A')}m")

if __name__ == "__main__":
    test_seoul_district_system() 