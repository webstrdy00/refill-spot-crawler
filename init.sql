
-- Refill Spot 데이터베이스 스키마 (기존 프로젝트 구조 기반)

-- 1. PostGIS 확장 활성화 (공간 인덱싱용)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. 카테고리 테이블
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 가게 테이블 (기존 구조 + 크롤링 필드 추가)
CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT NOT NULL,
  description TEXT,
  position_lat FLOAT NOT NULL,
  position_lng FLOAT NOT NULL,
  position_x FLOAT,  -- 카카오맵 좌표계 (선택사항)
  position_y FLOAT,  -- 카카오맵 좌표계 (선택사항)
  naver_rating FLOAT,
  kakao_rating FLOAT,
  diningcode_rating FLOAT,  -- 다이닝코드 평점 추가
  open_hours TEXT,
  open_hours_raw TEXT,  -- 크롤링된 원본 영업시간
  price TEXT,
  refill_items TEXT[],
  image_urls TEXT[],
  phone_number TEXT,  -- 전화번호 추가
  diningcode_place_id TEXT UNIQUE,  -- 다이닝코드 고유 ID
  raw_categories_diningcode TEXT[],  -- 다이닝코드 원본 카테고리
  status TEXT DEFAULT '운영중',  -- 운영 상태
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PostGIS 공간 인덱싱을 위한 geom 컬럼 추가
ALTER TABLE stores ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);

-- 자동으로 geom 컬럼을 채우는 트리거 함수
CREATE OR REPLACE FUNCTION update_store_geom()
RETURNS TRIGGER AS $
BEGIN
  NEW.geom = ST_SetSRID(ST_MakePoint(NEW.position_lng, NEW.position_lat), 4326);
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$ LANGUAGE plpgsql;

-- 트리거 생성 (INSERT/UPDATE 시 geom 자동 업데이트)
DROP TRIGGER IF EXISTS update_store_geom_trigger ON stores;
CREATE TRIGGER update_store_geom_trigger
BEFORE INSERT OR UPDATE ON stores
FOR EACH ROW EXECUTE FUNCTION update_store_geom();

-- 기존 데이터에 대해 geom 컬럼 업데이트
UPDATE stores SET geom = ST_SetSRID(ST_MakePoint(position_lng, position_lat), 4326)
WHERE position_lng IS NOT NULL AND position_lat IS NOT NULL;

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_stores_geom ON stores USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stores_diningcode_id ON stores(diningcode_place_id);
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name);
CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(status);

-- 4. 가게-카테고리 연결 테이블
CREATE TABLE IF NOT EXISTS store_categories (
  store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (store_id, category_id)
);

-- 5. 크롤링 로그 테이블 (추가)
CREATE TABLE IF NOT EXISTS crawling_logs (
  id SERIAL PRIMARY KEY,
  keyword TEXT,
  rect_area TEXT,
  stores_found INTEGER DEFAULT 0,
  stores_processed INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'running',  -- running, completed, failed
  error_message TEXT
);

-- 6. RPC 함수들 (기존 프로젝트 구조 유지)

-- 반경 내 무한리필 가게 검색
CREATE OR REPLACE FUNCTION stores_within_radius(lat float, lng float, radius_meters float)
RETURNS TABLE (
  id integer,
  name text,
  address text,
  description text,
  position_lat float,
  position_lng float,
  position_x float,
  position_y float,
  naver_rating float,
  kakao_rating float,
  diningcode_rating float,
  open_hours text,
  price text,
  refill_items text[],
  image_urls text[],
  phone_number text,
  status text,
  created_at timestamptz,
  updated_at timestamptz,
  distance float
) AS $
  SELECT 
    s.id, s.name, s.address, s.description,
    s.position_lat, s.position_lng, s.position_x, s.position_y,
    s.naver_rating, s.kakao_rating, s.diningcode_rating,
    s.open_hours, s.price, s.refill_items, s.image_urls,
    s.phone_number, s.status, s.created_at, s.updated_at,
    ST_Distance(
      s.geom::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
    ) as distance
  FROM 
    stores s
  WHERE 
    s.status = '운영중'
    AND ST_DWithin(
      s.geom::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
      radius_meters
    )
  ORDER BY 
    distance;
$ LANGUAGE sql STABLE;

-- 필터링 함수 (거리 + 카테고리 + 평점)
CREATE OR REPLACE FUNCTION stores_filter(
  lat float, 
  lng float, 
  max_distance float,
  min_rating float DEFAULT NULL,
  categories_filter text[] DEFAULT NULL
)
RETURNS TABLE (
  id integer,
  name text,
  address text,
  description text,
  position_lat float,
  position_lng float,
  naver_rating float,
  kakao_rating float,
  diningcode_rating float,
  open_hours text,
  price text,
  refill_items text[],
  image_urls text[],
  phone_number text,
  distance float
) AS $
  SELECT 
    s.id, s.name, s.address, s.description,
    s.position_lat, s.position_lng,
    s.naver_rating, s.kakao_rating, s.diningcode_rating,
    s.open_hours, s.price, s.refill_items, s.image_urls, s.phone_number,
    ST_Distance(
      s.geom::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
    ) as distance
  FROM 
    stores s
  WHERE 
    s.status = '운영중'
    AND ST_DWithin(
      s.geom::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
      max_distance
    )
    AND (min_rating IS NULL OR 
         GREATEST(s.naver_rating, s.kakao_rating, s.diningcode_rating) >= min_rating)
    AND (
      categories_filter IS NULL 
      OR EXISTS (
        SELECT 1
        FROM store_categories sc
        JOIN categories c ON sc.category_id = c.id
        WHERE sc.store_id = s.id
        AND c.name = ANY(categories_filter)
      )
    )
  ORDER BY 
    distance;
$ LANGUAGE sql STABLE;

-- 7. 기본 카테고리 데이터 (무한리필 특화)
INSERT INTO categories (name, description) VALUES 
('무한리필', '무한리필이 가능한 음식점'),
('고기', '고기 요리 전문점'),
('해산물', '해산물 요리 전문점'),
('양식', '서양 음식'),
('한식', '한국 전통 음식'),
('중식', '중국 음식'),
('일식', '일본 음식'),
('디저트', '디저트 전문점'),
('뷔페', '뷔페 형태의 음식점'),
('피자', '피자 전문점'),
('치킨', '치킨 전문점'),
('족발', '족발/보쌈 전문점'),
('곱창', '곱창 전문점'),
('스테이크', '스테이크 전문점'),
('초밥', '초밥/회 전문점'),
('삼겹살', '삼겹살 전문점'),
('갈비', '갈비 전문점'),
('샤브샤브', '샤브샤브 전문점'),
('냉면', '냉면 전문점'),
('파스타', '파스타 전문점')
ON CONFLICT (name) DO NOTHING;

-- 8. 크롤링 통계 함수
CREATE OR REPLACE FUNCTION get_crawling_stats()
RETURNS TABLE (
  total_stores integer,
  stores_with_coordinates integer,
  stores_with_phone integer,
  stores_with_rating integer,
  avg_rating float,
  categories_count integer,
  last_crawled timestamptz
) AS $
  SELECT 
    COUNT(*)::integer as total_stores,
    COUNT(CASE WHEN position_lat IS NOT NULL AND position_lng IS NOT NULL THEN 1 END)::integer as stores_with_coordinates,
    COUNT(CASE WHEN phone_number IS NOT NULL AND phone_number != '' THEN 1 END)::integer as stores_with_phone,
    COUNT(CASE WHEN diningcode_rating IS NOT NULL THEN 1 END)::integer as stores_with_rating,
    AVG(diningcode_rating) as avg_rating,
    (SELECT COUNT(*) FROM categories)::integer as categories_count,
    MAX(created_at) as last_crawled
  FROM stores;
$ LANGUAGE sql STABLE;