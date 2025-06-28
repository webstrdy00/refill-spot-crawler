# Refill Spot Supabase 데이터베이스 스키마

## 개요

리필스팟 프로젝트의 Supabase 데이터베이스 스키마 정의서입니다. 이 문서는 실제 운영 중인 Supabase 데이터베이스의 구조를 기반으로 작성되었습니다.

## 테이블 구조

### 1. categories (카테고리)

매장의 카테고리를 관리하는 테이블입니다.

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
```

**필드 설명:**

- `id`: 카테고리 고유 ID (자동 증가)
- `name`: 카테고리 이름 (중복 불가)

**현재 데이터:** 20개 카테고리

### 2. profiles (사용자 프로필)

Supabase Auth와 연동된 사용자 프로필 테이블입니다.

```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_admin BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**필드 설명:**

- `id`: 사용자 UUID (Supabase Auth와 연동)
- `username`: 사용자명
- `role`: 사용자 역할 (기본값: 'user')
- `is_admin`: 관리자 여부 (기본값: false)
- `updated_at`: 최종 수정일시

**현재 데이터:** 3개 프로필

### 3. stores (매장) - 메인 테이블

리필스팟의 핵심 비즈니스 테이블로 매장 정보를 저장합니다.

```sql
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    description TEXT,
    position_lat DOUBLE PRECISION NOT NULL,
    position_lng DOUBLE PRECISION NOT NULL,
    position_x DOUBLE PRECISION NOT NULL,
    position_y DOUBLE PRECISION NOT NULL,
    naver_rating DOUBLE PRECISION,
    kakao_rating DOUBLE PRECISION,
    open_hours TEXT,
    price TEXT,
    refill_items TEXT[],
    image_urls TEXT[],
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**필드 설명:**

- `id`: 매장 고유 ID (자동 증가)
- `name`: 매장명
- `address`: 매장 주소
- `description`: 매장 설명
- `position_lat/lng`: 위도/경도 (WGS84)
- `position_x/y`: TM 좌표계 좌표
- `naver_rating`: 네이버 평점
- `kakao_rating`: 카카오 평점
- `open_hours`: 영업시간
- `price`: 가격 정보
- `refill_items`: 리필 가능 품목 배열
- `image_urls`: 이미지 URL 배열
- `geom`: PostGIS 지리 정보
- `created_at/updated_at`: 생성/수정일시

**현재 데이터:** 18개 매장

### 4. store_categories (매장-카테고리 연결)

매장과 카테고리 간의 다대다 관계를 관리하는 테이블입니다.

```sql
CREATE TABLE store_categories (
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (store_id, category_id)
);
```

**필드 설명:**

- `store_id`: 매장 ID (외래키)
- `category_id`: 카테고리 ID (외래키)

**현재 데이터:** 33개 연결

### 5. favorites (즐겨찾기)

사용자의 매장 즐겨찾기를 관리하는 테이블입니다.

```sql
CREATE TABLE favorites (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, store_id)
);
```

**필드 설명:**

- `id`: 즐겨찾기 고유 ID
- `user_id`: 사용자 ID (외래키)
- `store_id`: 매장 ID (외래키)
- `created_at`: 생성일시

**현재 데이터:** 0개 (빈 테이블)

### 6. reviews (리뷰)

매장에 대한 사용자 리뷰를 관리하는 테이블입니다.

```sql
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    rating DOUBLE PRECISION NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**필드 설명:**

- `id`: 리뷰 고유 ID
- `user_id`: 작성자 ID (외래키)
- `store_id`: 매장 ID (외래키)
- `rating`: 평점
- `content`: 리뷰 내용
- `created_at/updated_at`: 생성/수정일시

**현재 데이터:** 0개 (빈 테이블)

### 7. contacts (고객 문의)

고객 문의사항을 관리하는 테이블입니다.

```sql
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    store_name TEXT,
    store_address TEXT,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**필드 설명:**

- `id`: 문의 고유 ID
- `type`: 문의 유형
- `name`: 문의자 이름
- `email`: 문의자 이메일
- `phone`: 전화번호 (선택)
- `store_name/store_address`: 관련 매장 정보 (선택)
- `message`: 문의 내용
- `status`: 처리 상태 (기본값: 'pending')
- `created_at/updated_at`: 생성/수정일시

**현재 데이터:** 0개 (빈 테이블)

## 인덱스 및 제약조건

### 기본 인덱스

- 모든 테이블의 PRIMARY KEY 인덱스
- UNIQUE 제약조건 인덱스

### 추가 인덱스

```sql
-- 공간 검색용 인덱스
CREATE INDEX idx_stores_geom ON stores USING GIST (geom);

-- 검색 성능 향상용 인덱스
CREATE INDEX idx_stores_position ON stores (position_lat, position_lng);
CREATE INDEX idx_stores_name ON stores (name);
CREATE INDEX idx_reviews_store_id ON reviews (store_id);
CREATE INDEX idx_favorites_user_id ON favorites (user_id);
CREATE INDEX idx_contacts_status ON contacts (status);
CREATE INDEX idx_stores_created_at ON stores (created_at);

-- 전문 검색용 GIN 인덱스
CREATE INDEX idx_stores_name_gin ON stores USING GIN (to_tsvector('korean', name));
CREATE INDEX idx_stores_address_gin ON stores USING GIN (to_tsvector('korean', address));
CREATE INDEX idx_stores_description_gin ON stores USING GIN (to_tsvector('korean', coalesce(description, '')));
```

### 외래키 제약조건

- `store_categories.store_id` → `stores.id`
- `store_categories.category_id` → `categories.id`
- `favorites.user_id` → `profiles.id`
- `favorites.store_id` → `stores.id`
- `reviews.user_id` → `profiles.id`
- `reviews.store_id` → `stores.id`
- `profiles.id` → `auth.users.id`

## Row Level Security (RLS) 정책

### profiles 테이블

- 사용자는 자신의 프로필만 조회/수정 가능

### favorites 테이블

- 사용자는 자신의 즐겨찾기만 관리 가능

### reviews 테이블

- 모든 사용자가 리뷰 조회 가능
- 사용자는 자신의 리뷰만 생성/수정/삭제 가능

### contacts 테이블

- 모든 사용자가 문의 생성 가능
- 사용자는 자신의 문의만 조회 가능

### 공개 테이블

- `stores`, `categories`, `store_categories`: 모든 사용자가 조회 가능

## 뷰 (Views)

### store_statistics

매장 관련 통계 정보를 제공하는 뷰

### category_store_counts

카테고리별 매장 수를 제공하는 뷰

### recent_stores

최근 30일 내 추가된 매장을 보여주는 뷰

### top_rated_stores

평점이 높은 상위 50개 매장을 보여주는 뷰

### stores_with_most_refills

리필 아이템이 많은 매장을 보여주는 뷰

## 함수 (Functions)

### search_stores(search_term TEXT)

기본 매장 검색 함수 (ILIKE 사용)

### search_stores_by_distance(user_lat, user_lng, radius_km)

거리 기반 매장 검색 함수 (PostGIS 사용)

### search_stores_fulltext(search_term TEXT)

전문 검색 함수 (한국어 지원, GIN 인덱스 활용)

### check_data_quality()

데이터 품질 체크 함수

### cleanup_store_data()

매장 데이터 정리 함수

## 트리거 (Triggers)

### updated_at 자동 업데이트

다음 테이블에 대해 `updated_at` 필드를 자동으로 현재 시간으로 업데이트:

- `stores`
- `profiles`
- `reviews`
- `contacts`

## 사용 예시

### 1. 거리 기반 매장 검색

```sql
SELECT * FROM search_stores_by_distance(37.5665, 126.9780, 2.0);
```

### 2. 전문 검색

```sql
SELECT * FROM search_stores_fulltext('카페');
```

### 3. 데이터 품질 체크

```sql
SELECT * FROM check_data_quality();
```

### 4. 통계 조회

```sql
SELECT * FROM store_statistics;
SELECT * FROM category_store_counts;
```

## 데이터 마이그레이션

크롤러 데이터베이스에서 Supabase로 데이터를 마이그레이션할 때는 다음 스크립트를 사용:

- `migrate_to_supabase.py`: 마이그레이션 미리보기
- `execute_supabase_migration.py`: 실제 마이그레이션 실행

## 주의사항

1. **좌표 범위**: 서울시 좌표 범위(위도 37.4-37.7, 경도 126.8-127.2) 내의 데이터만 처리
2. **RLS 정책**: 사용자 관련 테이블은 RLS가 활성화되어 있음
3. **배열 필드**: `refill_items`, `image_urls`는 PostgreSQL 배열 타입 사용
4. **공간 데이터**: PostGIS 확장을 사용하여 지리 정보 처리
5. **한국어 검색**: 전문 검색 시 한국어 사전 사용
