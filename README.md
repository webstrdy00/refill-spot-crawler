# 🍽️ Refill Spot Crawler (2단계 강화 버전)

다이닝코드에서 무한리필 가게 정보를 수집하는 고도화된 크롤링 시스템입니다.

## 📋 2단계 주요 개선사항

### 🔧 상세페이지 파싱 강화

- **메뉴 정보**: 메뉴 아이템, 카테고리, 대표메뉴 추출
- **가격 정보**: 가격 범위, 평균 가격, 상세 가격 정보
- **영업시간**: 브레이크타임, 라스트오더, 휴무일 정보
- **이미지 수집**: 메인, 메뉴, 인테리어 이미지 분류 수집
- **리뷰 분석**: 키워드 추출, 분위기 정보
- **연락처**: 전화번호, 웹사이트, 소셜미디어

### ⚡ 성능 및 안정성 향상

- **재시도 로직**: 실패 시 자동 재시도 (최대 3회)
- **배치 처리**: 5개씩 묶어서 처리로 메모리 효율성 향상
- **진행상황 모니터링**: 실시간 진행률 및 예상 완료 시간
- **에러 로깅**: 상세한 에러 추적 및 복구
- **중간 저장**: 키워드별 중간 저장으로 데이터 손실 방지

### 🗺️ 지역 확장

- **서울 12개 주요 지역**: 강남, 홍대, 강서, 송파, 강동, 서초, 영등포, 마포, 용산, 성동, 광진, 강북
- **자동 좌표 생성**: 중심점 기반 검색 영역 자동 생성
- **지역별 성능 비교**: 지역별 수집 통계 제공

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화 (Windows)
python -m venv venv
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 설정 (Docker 사용)
docker-compose up -d
```

### 2. 실행 방법

#### 기본 실행 (강화된 크롤링)

```bash
python main.py
# 또는
python main.py enhanced
```

#### 모든 지역 크롤링

```bash
python main.py regions
```

#### 단일 가게 테스트

```bash
python main.py test
```

#### 데이터베이스 통계 조회

```bash
python main.py stats
```

#### 설정 정보 확인

```bash
python main.py config
```

## 📊 강화된 데이터 스키마

### 기본 정보

- `name`: 가게명
- `address`: 주소
- `description`: 설명
- `phone_number`: 전화번호
- `website`: 웹사이트

### 위치 정보

- `position_lat`, `position_lng`: GPS 좌표
- `geom`: PostGIS 지리 정보 (거리 기반 검색 지원)

### 무한리필 정보 (강화)

- `is_confirmed_refill`: 무한리필 확정 여부
- `refill_type`: 리필 타입 (고기무한리필, 뷔페 등)
- `refill_items`: 리필 가능 아이템 목록
- `refill_conditions`: 리필 조건

### 메뉴 정보 (신규)

- `menu_items`: 메뉴 아이템 (JSON 형태)
- `menu_categories`: 메뉴 카테고리
- `signature_menu`: 대표 메뉴

### 가격 정보 (강화)

- `price`: 기본 가격
- `price_range`: 가격 범위
- `average_price`: 평균 가격
- `price_details`: 상세 가격 정보

### 영업시간 정보 (강화)

- `open_hours`: 정규화된 영업시간
- `open_hours_raw`: 원본 영업시간
- `break_time`: 브레이크타임
- `last_order`: 라스트오더
- `holiday`: 휴무일

### 이미지 정보 (강화)

- `image_urls`: 모든 이미지 URL
- `main_image`: 메인 이미지
- `menu_images`: 메뉴 이미지들
- `interior_images`: 인테리어 이미지들

### 리뷰 및 키워드 (신규)

- `review_summary`: 리뷰 요약
- `keywords`: 추출된 키워드
- `atmosphere`: 분위기 정보

## 🔧 설정 파일 (config.py)

### 크롤링 성능 설정

```python
CRAWLING_CONFIG = {
    "batch_size": 5,  # 배치 처리 크기
    "max_stores_per_keyword": 20,  # 키워드당 최대 가게 수
    "retry_attempts": 3,  # 재시도 횟수
    "delay_between_batches": 3,  # 배치 간 지연 시간
    "delay_between_stores": 1,  # 가게 간 지연 시간
    "delay_between_keywords": 2,  # 키워드 간 지연 시간
    "delay_between_regions": 10,  # 지역 간 지연 시간
}
```

### 데이터 품질 검증 설정

```python
VALIDATION_CONFIG = {
    "required_fields": ["name", "diningcode_place_id"],
    "coordinate_bounds": {
        "lat_min": 33.0, "lat_max": 39.0,
        "lng_min": 124.0, "lng_max": 132.0
    },
    "refill_keywords": [
        "무한리필", "뷔페", "무제한", "리필", "셀프바"
    ]
}
```

## 📈 모니터링 및 통계

### 실시간 진행상황

- 키워드별 진행률
- 예상 완료 시간
- 성공/실패 통계
- 처리 속도

### 데이터베이스 통계

- 총 가게 수
- 무한리필 확정 가게 수
- 메뉴/이미지/가격 정보 보유 가게 수
- 지역별 분포
- 리필 타입별 분포

### 크롤링 로그

- 세션별 수집 통계
- 에러 발생 현황
- 성능 지표

## 🗺️ 지원 지역

### 서울 주요 지역 (12개)

1. **강남**: 강남구 전체
2. **홍대**: 홍익대학교 주변
3. **강서**: 김포공항 주변
4. **송파**: 잠실, 롯데월드 주변
5. **강동**: 천호동 주변
6. **서초**: 교대, 사당 주변
7. **영등포**: 여의도, 타임스퀘어 주변
8. **마포**: 합정, 상암 주변
9. **용산**: 이태원, 한남 주변
10. **성동**: 왕십리, 성수 주변
11. **광진**: 건대 주변
12. **강북**: 강북구 전체

### 자동 확장 지역 (16개)

종로, 중구, 동대문, 중랑, 성북, 도봉, 노원, 은평, 서대문, 양천, 구로, 금천, 관악, 동작 등

## 🔍 고급 검색 기능

### 거리 기반 검색

```sql
-- 특정 위치에서 5km 내 무한리필 가게 검색
SELECT * FROM find_nearby_stores(37.5665, 126.9780, 5);
```

### 무한리필 확정 가게 조회

```sql
-- 무한리필이 확정된 가게만 조회
SELECT * FROM confirmed_refill_stores;
```

### 지역별 통계 조회

```sql
-- 지역별 가게 분포 통계
SELECT * FROM regional_stats;
```

## 📝 로그 파일

### 주요 로그 파일

- `refill_spot_crawler.log`: 메인 크롤링 로그
- `crawler.log`: 상세 크롤링 로그

### 로그 레벨

- **INFO**: 일반 진행 상황
- **WARNING**: 주의사항 (데이터 품질 이슈 등)
- **ERROR**: 오류 발생 (재시도 가능)
- **CRITICAL**: 심각한 오류 (중단 필요)

## 🛠️ 문제 해결

### 일반적인 문제

#### 1. 데이터베이스 연결 실패

```bash
# Docker 컨테이너 상태 확인
docker-compose ps

# 컨테이너 재시작
docker-compose restart
```

#### 2. 크롤링 속도 느림

- `config.py`에서 지연 시간 조정
- 배치 크기 증가 (단, 메모리 사용량 증가)

#### 3. 메모리 부족

- 배치 크기 감소
- 키워드당 최대 가게 수 제한

#### 4. 무한리필 관련성 낮음

- `VALIDATION_CONFIG`에서 키워드 추가
- 검증 로직 강화

### 성능 최적화

#### 크롤링 속도 향상

```python
# config.py 수정
CRAWLING_CONFIG = {
    "batch_size": 10,  # 증가
    "delay_between_stores": 0.5,  # 감소
    "delay_between_batches": 2,  # 감소
}
```

#### 메모리 사용량 최적화

```python
CRAWLING_CONFIG = {
    "batch_size": 3,  # 감소
    "max_stores_per_keyword": 10,  # 제한
}
```

## 📊 데이터 품질 지표

### 수집 품질

- **완성도**: 필수 필드 보유율
- **정확도**: 좌표 유효성, 전화번호 형식
- **관련성**: 무한리필 키워드 매칭률
- **신선도**: 최근 업데이트 비율

### 검증 기준

- 가게명 2자 이상
- 한국 내 좌표 범위
- 무한리필 관련 키워드 포함
- 중복 제거 (diningcode_place_id 기준)

## 🔄 업데이트 계획

### 3단계 계획 (예정)

- **다중 플랫폼 지원**: 네이버, 카카오맵 연동
- **실시간 업데이트**: 변경사항 자동 감지
- **AI 기반 분류**: 자동 카테고리 분류
- **API 서버**: RESTful API 제공

## 📞 지원

문제가 발생하거나 개선 제안이 있으시면 이슈를 등록해 주세요.

### 로그 확인 방법

```bash
# 최근 로그 확인
tail -f refill_spot_crawler.log

# 에러 로그만 확인
grep ERROR refill_spot_crawler.log
```

### 통계 확인

```bash
python main.py stats
```

---

**⚠️ 주의사항**: 이 도구는 교육 및 연구 목적으로만 사용하세요. 웹사이트의 이용약관을 준수하고, 과도한 요청으로 서버에 부하를 주지 않도록 주의하세요.
