import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# 환경 변수 로드
load_dotenv()

# PostgreSQL 연결 설정 (DATABASE_URL 우선, 개별 설정 fallback)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password123@localhost:5432/refill_spot')

# DATABASE_URL 파싱
parsed_url = urlparse(DATABASE_URL)

DB_HOST = parsed_url.hostname or os.getenv('DB_HOST', 'localhost')
DB_PORT = parsed_url.port or int(os.getenv('DB_PORT', '5432'))
DB_NAME = parsed_url.path.lstrip('/') or os.getenv('DB_NAME', 'refill_spot')
DB_USER = parsed_url.username or os.getenv('DB_USER', 'postgres')
DB_PASSWORD = parsed_url.password or os.getenv('DB_PASSWORD', 'password123')

# 지오코딩 API 설정 (3단계 고도화 - 카카오 API 전용)
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY', '')  # 카카오 REST API 키

# 크롤링 설정
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# 크롤링 지연 시간 (초)
MIN_DELAY = 2
MAX_DELAY = 4

# 서울 주요 지역별 검색 설정 (확장)
REGIONS = {
    "강남": {
        "name": "서울 강남",
        "rect": "37.4979,127.0276,37.5279,127.0576",
        "center": {"lat": 37.5129, "lng": 127.0426},
        "keywords": [
            "서울 강남 무한리필",
            "강남 고기무한리필", 
            "강남 소고기무한리필",
            "강남 삼겹살무한리필",
            "강남 뷔페",
            "강남역 무한리필",
            "강남구 무한리필"
        ]
    },
    "홍대": {
        "name": "서울 홍대",  
        "rect": "37.5520,126.9200,37.5620,126.9300",
        "center": {"lat": 37.5570, "lng": 126.9250},
        "keywords": [
            "서울 홍대 무한리필",
            "홍대 고기무한리필",
            "홍대 삼겹살무한리필", 
            "홍대 뷔페",
            "홍익대 무한리필",
            "마포 무한리필"
        ]
    },
    "강북": {
        "name": "서울 강북",
        "rect": "37.6350,127.0250,37.6450,127.0350",
        "center": {"lat": 37.6400, "lng": 127.0300},
        "keywords": [
            "서울 강북 무한리필",
            "강북 고기무한리필",
            "강북 뷔페",
            "강북구 무한리필"
        ]
    },
    "강서": {
        "name": "서울 강서",
        "rect": "37.5400,126.8200,37.5700,126.8800",
        "center": {"lat": 37.5550, "lng": 126.8500},
        "keywords": [
            "서울 강서 무한리필",
            "강서 고기무한리필",
            "강서 뷔페",
            "김포공항 무한리필",
            "강서구 무한리필"
        ]
    },
    "송파": {
        "name": "서울 송파",
        "rect": "37.4700,127.0800,37.5200,127.1400",
        "center": {"lat": 37.4950, "lng": 127.1100},
        "keywords": [
            "서울 송파 무한리필",
            "송파 고기무한리필",
            "잠실 무한리필",
            "송파구 무한리필",
            "롯데월드 무한리필"
        ]
    },
    "강동": {
        "name": "서울 강동",
        "rect": "37.5200,127.1200,37.5600,127.1600",
        "center": {"lat": 37.5400, "lng": 127.1400},
        "keywords": [
            "서울 강동 무한리필",
            "강동 고기무한리필",
            "천호 무한리필",
            "강동구 무한리필"
        ]
    },
    "서초": {
        "name": "서울 서초",
        "rect": "37.4700,127.0000,37.5100,127.0500",
        "center": {"lat": 37.4900, "lng": 127.0250},
        "keywords": [
            "서울 서초 무한리필",
            "서초 고기무한리필",
            "교대 무한리필",
            "서초구 무한리필",
            "사당 무한리필"
        ]
    },
    "영등포": {
        "name": "서울 영등포",
        "rect": "37.5100,126.8900,37.5400,126.9300",
        "center": {"lat": 37.5250, "lng": 126.9100},
        "keywords": [
            "서울 영등포 무한리필",
            "영등포 고기무한리필",
            "여의도 무한리필",
            "영등포구 무한리필",
            "타임스퀘어 무한리필"
        ]
    },
    "마포": {
        "name": "서울 마포",
        "rect": "37.5400,126.9000,37.5700,126.9400",
        "center": {"lat": 37.5550, "lng": 126.9200},
        "keywords": [
            "서울 마포 무한리필",
            "마포 고기무한리필",
            "합정 무한리필",
            "마포구 무한리필",
            "상암 무한리필"
        ]
    },
    "용산": {
        "name": "서울 용산",
        "rect": "37.5200,126.9600,37.5500,127.0000",
        "center": {"lat": 37.5350, "lng": 126.9800},
        "keywords": [
            "서울 용산 무한리필",
            "용산 고기무한리필",
            "이태원 무한리필",
            "용산구 무한리필",
            "한남 무한리필"
        ]
    },
    "성동": {
        "name": "서울 성동",
        "rect": "37.5500,127.0200,37.5800,127.0600",
        "center": {"lat": 37.5650, "lng": 127.0400},
        "keywords": [
            "서울 성동 무한리필",
            "성동 고기무한리필",
            "왕십리 무한리필",
            "성동구 무한리필",
            "성수 무한리필"
        ]
    },
    "광진": {
        "name": "서울 광진",
        "rect": "37.5300,127.0600,37.5600,127.1000",
        "center": {"lat": 37.5450, "lng": 127.0800},
        "keywords": [
            "서울 광진 무한리필",
            "광진 고기무한리필",
            "건대 무한리필",
            "광진구 무한리필",
            "자양 무한리필"
        ]
    }
}

# MVP 테스트용 기본 설정 (강남)
TEST_REGION = "강남"
TEST_RECT = REGIONS[TEST_REGION]["rect"] 
TEST_KEYWORDS = REGIONS[TEST_REGION]["keywords"]

# 기본 무한리필 키워드 (지역명 없이)
BASIC_KEYWORDS = [
    "무한리필",
    "고기무한리필", 
    "소고기무한리필",
    "삼겹살무한리필",
    "초밥뷔페",
    "해산물무한리필",
    "뷔페",
    "셀프바"
]

# 크롤링 성능 설정
CRAWLING_CONFIG = {
    "batch_size": 5,  # 배치 처리 크기
    "max_stores_per_keyword": 20,  # 키워드당 최대 가게 수
    "retry_attempts": 3,  # 재시도 횟수
    "delay_between_batches": 3,  # 배치 간 지연 시간 (초)
    "delay_between_stores": 1,  # 가게 간 지연 시간 (초)
    "delay_between_keywords": 2,  # 키워드 간 지연 시간 (초)
    "delay_between_regions": 10,  # 지역 간 지연 시간 (초)
}

# 데이터 품질 검증 설정
VALIDATION_CONFIG = {
    "required_fields": ["name", "diningcode_place_id"],
    "coordinate_bounds": {
        "lat_min": 33.0,
        "lat_max": 39.0,
        "lng_min": 124.0,
        "lng_max": 132.0
    },
    "refill_keywords": [
        "무한리필", "뷔페", "무제한", "리필", "셀프바", 
        "무료리필", "리필가능", "무한", "unlimited"
    ],
    "min_name_length": 2,
    "max_description_length": 1000
}

# 자동 좌표 생성을 위한 지역 중심점 (추가 지역)
ADDITIONAL_REGIONS = {
    "종로": {"lat": 37.5735, "lng": 126.9788},
    "중구": {"lat": 37.5641, "lng": 126.9979},
    "동대문": {"lat": 37.5744, "lng": 127.0098},
    "중랑": {"lat": 37.6063, "lng": 127.0925},
    "성북": {"lat": 37.5894, "lng": 127.0167},
    "강북": {"lat": 37.6398, "lng": 127.0256},
    "도봉": {"lat": 37.6688, "lng": 127.0471},
    "노원": {"lat": 37.6542, "lng": 127.0568},
    "은평": {"lat": 37.6176, "lng": 126.9227},
    "서대문": {"lat": 37.5791, "lng": 126.9368},
    "양천": {"lat": 37.5170, "lng": 126.8664},
    "구로": {"lat": 37.4954, "lng": 126.8874},
    "금천": {"lat": 37.4519, "lng": 126.9018},
    "관악": {"lat": 37.4781, "lng": 126.9515},
    "동작": {"lat": 37.5124, "lng": 126.9393},
    "동대문": {"lat": 37.5744, "lng": 127.0098}
}

def generate_region_rect(center_lat: float, center_lng: float, radius_km: float = 2.0) -> str:
    """중심점과 반경을 기반으로 검색 영역 좌표 생성"""
    # 대략적인 위도/경도 변환 (1km ≈ 0.009도)
    lat_offset = radius_km * 0.009
    lng_offset = radius_km * 0.009 / 1.1  # 경도는 위도보다 약간 작음
    
    min_lat = center_lat - lat_offset
    min_lng = center_lng - lng_offset
    max_lat = center_lat + lat_offset
    max_lng = center_lng + lng_offset
    
    return f"{min_lat:.4f},{min_lng:.4f},{max_lat:.4f},{max_lng:.4f}"

def get_all_regions() -> dict:
    """모든 지역 정보 반환 (기본 + 추가)"""
    all_regions = REGIONS.copy()
    
    # 추가 지역들을 자동으로 생성
    for region_name, center in ADDITIONAL_REGIONS.items():
        if region_name not in all_regions:
            all_regions[region_name] = {
                "name": f"서울 {region_name}",
                "rect": generate_region_rect(center["lat"], center["lng"]),
                "center": center,
                "keywords": [
                    f"서울 {region_name} 무한리필",
                    f"{region_name} 고기무한리필",
                    f"{region_name} 뷔페",
                    f"{region_name}구 무한리필"
                ]
            }
    
    return all_regions

# 로깅 설정
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "file": "refill_spot_crawler.log",
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}