-- Refill Spot 데이터베이스 스키마 (기존 프로젝트 구조 기반)

-- 1. PostGIS 확장 활성화 (공간 인덱싱용)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. 카테고리 테이블
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 가게 테이블 (기존 구조 + 크롤링 필드 추가)
CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  diningcode_place_id VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  address TEXT,
  description TEXT,
  
  -- 위치 정보
  position_lat DECIMAL(10, 8),
  position_lng DECIMAL(11, 8),
  position_x DECIMAL(15, 6),  -- 카카오맵 좌표
  position_y DECIMAL(15, 6),  -- 카카오맵 좌표
  geom GEOMETRY(POINT, 4326), -- PostGIS 지리 정보
  
  -- 평점 정보
  naver_rating DECIMAL(3, 2),
  kakao_rating DECIMAL(3, 2),
  diningcode_rating DECIMAL(3, 2),
  
  -- 영업시간 정보 (강화)
  open_hours TEXT,
  open_hours_raw TEXT,
  break_time TEXT,
  last_order TEXT,
  holiday TEXT,
  
  -- 가격 정보 (강화)
  price INTEGER,
  price_range TEXT,
  average_price TEXT,
  price_details TEXT[],
  
  -- 무한리필 정보 (강화)
  refill_items TEXT[],
  refill_type TEXT,
  refill_conditions TEXT,
  is_confirmed_refill BOOLEAN DEFAULT FALSE,
  
  -- 이미지 정보 (강화)
  image_urls TEXT[],
  main_image TEXT,
  menu_images TEXT[],
  interior_images TEXT[],
  
  -- 메뉴 정보 (강화)
  menu_items JSONB,
  menu_categories TEXT[],
  signature_menu TEXT[],
  
  -- 리뷰 및 설명 정보 (강화)
  review_summary TEXT,
  keywords TEXT[],
  atmosphere TEXT,
  
  -- 연락처 정보 (강화)
  phone_number VARCHAR(20),
  website TEXT,
  social_media TEXT[],
  
  -- 기존 필드
  raw_categories_diningcode TEXT[],
  status VARCHAR(20) DEFAULT '운영중',
  
  -- 타임스탬프
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
  keyword VARCHAR(100),
  rect_area VARCHAR(200),
  stores_found INTEGER DEFAULT 0,
  stores_processed INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'running',
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
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

-- 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_stores_diningcode_id ON stores(diningcode_place_id);
CREATE INDEX IF NOT EXISTS idx_stores_position ON stores(position_lat, position_lng);
CREATE INDEX IF NOT EXISTS idx_stores_geom ON stores USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stores_refill_type ON stores(refill_type);
CREATE INDEX IF NOT EXISTS idx_stores_confirmed_refill ON stores(is_confirmed_refill);
CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(status);
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores USING GIN(to_tsvector('korean', name));
CREATE INDEX IF NOT EXISTS idx_stores_address ON stores USING GIN(to_tsvector('korean', address));
CREATE INDEX IF NOT EXISTS idx_stores_keywords ON stores USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);
CREATE INDEX IF NOT EXISTS idx_crawling_logs_created_at ON crawling_logs(created_at);

-- 트리거 함수: 좌표가 업데이트될 때 geom 필드 자동 업데이트
CREATE OR REPLACE FUNCTION update_geom_from_coordinates()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.position_lat IS NOT NULL AND NEW.position_lng IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.position_lng, NEW.position_lat), 4326);
    END IF;
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성
DROP TRIGGER IF EXISTS trigger_update_geom ON stores;
CREATE TRIGGER trigger_update_geom
    BEFORE INSERT OR UPDATE ON stores
    FOR EACH ROW
    EXECUTE FUNCTION update_geom_from_coordinates();

-- 기본 카테고리 데이터 삽입
INSERT INTO categories (name, description) VALUES 
    ('무한리필', '무한리필 서비스를 제공하는 음식점'),
    ('고기무한리필', '고기류 무한리필 전문점'),
    ('소고기무한리필', '소고기 무한리필 전문점'),
    ('삼겹살무한리필', '삼겹살 무한리필 전문점'),
    ('뷔페', '뷔페 형태의 음식점'),
    ('초밥뷔페', '초밥 뷔페 전문점'),
    ('해산물무한리필', '해산물 무한리필 전문점'),
    ('야채무한리필', '야채 무한리필 서비스'),
    ('셀프바', '셀프바 운영 음식점'),
    ('한식', '한국 음식 전문점'),
    ('일식', '일본 음식 전문점'),
    ('중식', '중국 음식 전문점'),
    ('양식', '서양 음식 전문점'),
    ('아시안', '아시아 음식 전문점'),
    ('강남', '강남 지역'),
    ('홍대', '홍대 지역'),
    ('마포', '마포 지역'),
    ('강북', '강북 지역'),
    ('서울', '서울 지역')
ON CONFLICT (name) DO NOTHING;

-- 뷰 생성: 무한리필 확정 가게 목록
CREATE OR REPLACE VIEW confirmed_refill_stores AS
SELECT 
    s.*,
    array_agg(DISTINCT c.name) as category_names
FROM stores s
LEFT JOIN store_categories sc ON s.id = sc.store_id
LEFT JOIN categories c ON sc.category_id = c.id
WHERE s.is_confirmed_refill = true
GROUP BY s.id;

-- 뷰 생성: 지역별 통계
CREATE OR REPLACE VIEW regional_stats AS
SELECT 
    CASE 
        WHEN address LIKE '%강남%' THEN '강남'
        WHEN address LIKE '%홍대%' OR address LIKE '%마포%' THEN '홍대/마포'
        WHEN address LIKE '%강북%' THEN '강북'
        WHEN address LIKE '%서울%' THEN '기타 서울'
        ELSE '기타'
    END as region,
    COUNT(*) as total_stores,
    COUNT(CASE WHEN is_confirmed_refill = true THEN 1 END) as confirmed_refill_stores,
    AVG(CASE WHEN diningcode_rating IS NOT NULL THEN diningcode_rating END) as avg_rating,
    COUNT(CASE WHEN menu_items IS NOT NULL THEN 1 END) as stores_with_menu
FROM stores
GROUP BY region
ORDER BY total_stores DESC;

-- 함수 생성: 거리 기반 검색
CREATE OR REPLACE FUNCTION find_nearby_stores(
    lat DECIMAL(10, 8),
    lng DECIMAL(11, 8),
    radius_km INTEGER DEFAULT 5
)
RETURNS TABLE (
    store_id INTEGER,
    store_name VARCHAR(200),
    distance_km DECIMAL(10, 3),
    refill_type TEXT,
    is_confirmed BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.name,
        ROUND(ST_Distance(
            ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
            s.geom::geography
        ) / 1000, 3) as distance_km,
        s.refill_type,
        s.is_confirmed_refill
    FROM stores s
    WHERE s.geom IS NOT NULL
    AND ST_DWithin(
        ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
        s.geom::geography,
        radius_km * 1000
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

-- 권한 설정 (필요한 경우)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- 완료 메시지
DO $$
BEGIN
    RAISE NOTICE '데이터베이스 초기화 완료 (강화된 스키마)';
    RAISE NOTICE '- PostGIS 확장 설치됨';
    RAISE NOTICE '- 강화된 stores 테이블 생성됨';
    RAISE NOTICE '- 성능 최적화 인덱스 생성됨';
    RAISE NOTICE '- 지리 정보 처리 기능 추가됨';
    RAISE NOTICE '- 기본 카테고리 데이터 삽입됨';
    RAISE NOTICE '- 유용한 뷰와 함수 생성됨';
END $$;