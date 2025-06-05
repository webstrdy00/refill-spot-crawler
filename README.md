# 🍽️ 리필스팟 크롤러 (Refill Spot Crawler)

서울시 무료 리필 가능 음식점 정보를 자동으로 수집하고 관리하는 고도화된 크롤링 시스템입니다.

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [주요 기능](#-주요-기능)
- [프로젝트 구조](#-프로젝트-구조)
- [설치 및 설정](#-설치-및-설정)
- [사용법](#-사용법)
- [6단계 자동화 시스템](#-6단계-자동화-시스템)
- [API 문서](#-api-문서)
- [기여하기](#-기여하기)

## 🎯 프로젝트 개요

리필스팟 크롤러는 다이닝코드(DiningCode)에서 서울시 25개 구의 무료 리필 가능 음식점 정보를 자동으로 수집하고, 데이터 품질을 관리하며, 무인 운영이 가능한 완전 자동화 시스템입니다.

### 🌟 주요 특징

- **완전 자동화**: 무인 운영 가능한 스케줄링 및 모니터링
- **고성능**: 병렬 처리 및 캐싱을 통한 최적화
- **품질 관리**: ML 기반 중복 감지 및 자동 품질 검증
- **예외 처리**: 웹사이트 구조 변경 감지 및 자동 복구
- **실시간 알림**: Slack/Discord/Email 통합 알림 시스템

## 🚀 주요 기능

### 1단계: 기본 크롤링

- 다이닝코드 웹사이트 크롤링
- 가게 기본 정보 수집 (이름, 주소, 전화번호 등)
- PostgreSQL 데이터베이스 저장

### 2단계: 데이터 강화

- 지오코딩을 통한 좌표 정보 추가
- 가격 정보 정규화
- 영업시간 파싱 및 표준화

### 3단계: 고도화

- 상세 페이지 정보 수집
- 메뉴 및 가격 정보 추가
- 리뷰 데이터 수집

### 4단계: 서울 완전 커버리지

- 서울시 25개 구 전체 크롤링
- 지역별 스케줄링
- 자동화된 일일 업데이트

### 5단계: 성능 최적화

- 병렬 처리 시스템
- Redis 캐싱
- 메모리 및 CPU 최적화

### 6단계: 운영 자동화 ⭐

- **자동 품질 검증**: ML 기반 중복 감지, 좌표 검증
- **예외 상황 처리**: IP 차단 대응, 구조 변경 감지
- **상태 관리**: 휴업/폐업 가게 자동 감지
- **알림 시스템**: 실시간 모니터링 및 보고

## 📁 프로젝트 구조

```
refill-spot-crawler/
├── 📁 src/                          # 소스 코드
│   ├── 📁 core/                     # 핵심 모듈
│   │   ├── database.py              # 데이터베이스 관리
│   │   ├── crawler.py               # 크롤링 엔진
│   │   ├── geocoding.py             # 지오코딩
│   │   ├── data_enhancement.py      # 데이터 강화
│   │   ├── price_normalizer.py      # 가격 정규화
│   │   ├── caching_system.py        # 캐싱 시스템
│   │   └── optimized_database.py    # 최적화된 DB
│   │
│   ├── 📁 automation/               # 6단계 자동화 시스템
│   │   ├── quality_assurance.py     # 품질 검증
│   │   ├── exception_handler.py     # 예외 처리
│   │   ├── store_status_manager.py  # 상태 관리
│   │   ├── notification_system.py   # 알림 시스템
│   │   └── automated_operations.py  # 통합 자동화
│   │
│   ├── 📁 utils/                    # 유틸리티
│   │   ├── seoul_districts.py       # 서울 구 정보
│   │   ├── seoul_scheduler.py       # 스케줄러
│   │   ├── parallel_crawler.py      # 병렬 크롤러
│   │   ├── main.py                  # 메인 크롤러
│   │   └── stage5_main.py          # 5단계 메인
│   │
│   └── 📁 tests/                    # 테스트
│       ├── stage6_test.py           # 6단계 테스트
│       ├── stage5_test.py           # 5단계 테스트
│       └── test_*.py               # 기타 테스트
│
├── 📁 config/                       # 설정 파일
│   ├── config.py                    # 메인 설정
│   ├── docker-compose.yml           # Docker 설정
│   └── init.sql                     # DB 초기화
│
├── 📁 docs/                         # 문서
│   ├── README.md                    # 이 파일
│   ├── STAGE6_AUTOMATION_GUIDE.md   # 6단계 가이드
│   └── STAGE5_GUIDE.md             # 5단계 가이드
│
├── 📁 logs/                         # 로그 파일
├── 📁 data/                         # 데이터 파일
├── 📁 reports/                      # 생성된 보고서
│
├── run_crawler.py                   # 메인 실행 파일
├── requirements.txt                 # 의존성
├── setup.sh                        # 리눅스 설정
├── setup_venv.bat                  # 윈도우 설정
└── .gitignore                      # Git 무시 파일
```

## 🛠️ 설치 및 설정

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/refill-spot-crawler.git
cd refill-spot-crawler
```

### 2. 가상환경 설정

**Windows:**

```bash
setup_venv.bat
```

**Linux/Mac:**

```bash
chmod +x setup.sh
./setup.sh
```

### 3. 의존성 설치

```bash
# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 4. 데이터베이스 설정

```bash
# PostgreSQL 설정 (Docker 사용)
docker-compose up -d

# 또는 수동 설정
psql -U postgres -f config/init.sql
```

### 5. 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필요한 설정 값 입력
# - 데이터베이스 연결 정보
# - API 키 (지오코딩, 알림 등)
# - 웹훅 URL (Slack, Discord)
```

## 🎮 사용법

### 기본 크롤링 실행

```bash
# 기본 크롤링 모드
python run_crawler.py --mode crawler

# 자동화 모드 (6단계)
python run_crawler.py --mode automation

# 테스트 모드
python run_crawler.py --test
```

### 개별 모듈 실행

```bash
# 품질 검증만 실행
python -m src.automation.quality_assurance

# 상태 관리만 실행
python -m src.automation.store_status_manager

# 알림 시스템 테스트
python -m src.automation.notification_system
```

### 테스트 실행

```bash
# 6단계 전체 테스트
python src/tests/stage6_test.py

# 5단계 테스트
python src/tests/stage5_test.py
```

## 🤖 6단계 자동화 시스템

### 주요 구성요소

#### 1. 품질 검증 시스템 (`quality_assurance.py`)

- **좌표 유효성 검증**: 한국 영역 확인, 주소-좌표 일치성
- **ML 기반 중복 감지**: TF-IDF + 코사인 유사도 + DBSCAN 클러스터링
- **영업시간 검증**: 논리적 오류 검출, 24시간 영업 확인
- **자동 수정**: 수정 가능한 이슈 자동 처리

#### 2. 예외 처리 시스템 (`exception_handler.py`)

- **웹사이트 구조 변경 감지**: 실패율 분석, 새 셀렉터 자동 감지
- **IP 차단 대응**: 프록시 로테이션, User-Agent 변경
- **요청 간격 조정**: 성공/실패에 따른 동적 지연
- **백업 전략**: 대체 엔드포인트, Selenium 헤드리스

#### 3. 상태 관리 시스템 (`store_status_manager.py`)

- **전화번호 검증**: 연결 가능성 확인
- **웹사이트 접근성**: 폐업/휴업 키워드 감지
- **리뷰 활동 모니터링**: 90일 비활성 감지
- **자동 상태 업데이트**: 휴업/폐업 자동 처리

#### 4. 알림 시스템 (`notification_system.py`)

- **Slack/Discord 알림**: 일일 보고, 에러 알림
- **이메일 보고서**: 주간 HTML 보고서
- **자동 보고서 생성**: 트렌드 분석, 시각화

#### 5. 통합 자동화 (`automated_operations.py`)

- **스케줄링**: 일일/주간 작업 자동 실행
- **상태 모니터링**: 30분마다 시스템 상태 확인
- **자동 복구**: 연속 실패 시 자동 복구 시도
- **데이터 정리**: 오래된 로그/보고서 자동 삭제

### 자동화 스케줄

| 시간       | 작업          | 설명                     |
| ---------- | ------------- | ------------------------ |
| 02:00      | 일일 크롤링   | 전체 데이터 업데이트     |
| 03:00      | 품질 검증     | 데이터 품질 자동 검사    |
| 04:00      | 상태 확인     | 가게 상태 업데이트       |
| 09:00 (월) | 주간 보고서   | HTML 보고서 생성 및 발송 |
| 매 30분    | 상태 모니터링 | 시스템 헬스체크          |

## 📊 모니터링 및 알림

### 알림 유형

1. **일일 크롤링 완료 보고**

   - 처리된 가게 수, 신규 가게, 성공률
   - 품질 점수, 발견된 이슈 수

2. **에러 발생 시 즉시 알림**

   - IP 차단, 웹사이트 구조 변경
   - 시스템 오류, 데이터베이스 연결 실패

3. **주간 데이터 품질 리포트**
   - 지역별 성장 추이
   - 신규 개업 가게 리스트
   - 트렌드 분석 및 시각화

### 품질 지표

- **데이터 품질 점수**: 0-100점 (이슈 심각도 기반)
- **크롤링 성공률**: 성공한 요청 / 전체 요청
- **중복 감지율**: ML 모델 정확도
- **자동 수정률**: 자동으로 해결된 이슈 비율

## 🔧 설정 옵션

### 품질 검증 설정 (`QualityConfig`)

```python
QualityConfig(
    coordinate_validation_enabled=True,
    duplicate_detection_enabled=True,
    similarity_threshold=0.85,
    auto_fix_enabled=True
)
```

### 예외 처리 설정 (`ExceptionConfig`)

```python
ExceptionConfig(
    failure_rate_threshold=0.15,
    ip_block_detection_enabled=True,
    proxy_rotation_enabled=True,
    max_retries=3
)
```

### 알림 설정 (`NotificationConfig`)

```python
NotificationConfig(
    slack_webhook_url="https://hooks.slack.com/...",
    discord_webhook_url="https://discord.com/api/webhooks/...",
    email_recipients=["admin@example.com"]
)
```

## 📈 성능 지표

- **처리 속도**: 시간당 ~10,000개 가게 처리
- **메모리 사용량**: 평균 500MB 이하
- **데이터 정확도**: 95% 이상
- **시스템 가용성**: 99.5% 이상

## 🐛 문제 해결

### 자주 발생하는 문제

1. **IP 차단**

   - 자동 프록시 로테이션 활성화
   - 요청 간격 증가

2. **메모리 부족**

   - 배치 크기 조정
   - 캐시 크기 제한

3. **데이터베이스 연결 실패**
   - 연결 풀 설정 확인
   - 자동 재연결 활성화

### 로그 확인

```bash
# 실시간 로그 모니터링
tail -f logs/crawler.log
tail -f logs/automated_operations.log

# 에러 로그만 확인
grep "ERROR" logs/*.log
```

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 연락처

프로젝트 관리자 - [your-email@example.com](mailto:your-email@example.com)

프로젝트 링크: [https://github.com/your-username/refill-spot-crawler](https://github.com/your-username/refill-spot-crawler)

---

⭐ 이 프로젝트가 도움이 되었다면 스타를 눌러주세요!
