-- Refill Spot Supabase 초기 데이터
-- 생성일: 2024년
-- 설명: 리필스팟 프로젝트의 초기 카테고리 데이터 및 기본 설정

-- 카테고리 데이터 삽입
INSERT INTO categories (name) VALUES 
('카페'),
('음식점'),
('베이커리'),
('디저트'),
('음료'),
('패스트푸드'),
('한식'),
('중식'),
('일식'),
('양식'),
('분식'),
('치킨'),
('피자'),
('버거'),
('아이스크림'),
('주스'),
('커피'),
('차'),
('샐러드'),
('건강식품')
ON CONFLICT (name) DO NOTHING;

-- 샘플 관리자 프로필 (실제 사용 시 수정 필요)
-- 주의: 실제 UUID는 Supabase Auth에서 생성된 사용자 ID를 사용해야 함
/*
INSERT INTO profiles (id, username, role, is_admin) VALUES 
('00000000-0000-0000-0000-000000000001', 'admin', 'admin', true)
ON CONFLICT (id) DO NOTHING;
*/

-- 매장 상태별 통계 뷰 생성
CREATE OR REPLACE VIEW store_statistics AS
SELECT 
    COUNT(*) as total_stores,
    COUNT(CASE WHEN naver_rating IS NOT NULL THEN 1 END) as stores_with_naver_rating,
    COUNT(CASE WHEN kakao_rating IS NOT NULL THEN 1 END) as stores_with_kakao_rating,
    COUNT(CASE WHEN array_length(refill_items, 1) > 0 THEN 1 END) as stores_with_refill_items,
    COUNT(CASE WHEN array_length(image_urls, 1) > 0 THEN 1 END) as stores_with_images,
    AVG(naver_rating) as avg_naver_rating,
    AVG(kakao_rating) as avg_kakao_rating
FROM stores;

-- 카테고리별 매장 수 뷰
CREATE OR REPLACE VIEW category_store_counts AS
SELECT 
    c.id,
    c.name,
    COUNT(sc.store_id) as store_count
FROM categories c
LEFT JOIN store_categories sc ON c.id = sc.category_id
GROUP BY c.id, c.name
ORDER BY store_count DESC, c.name;

-- 최근 추가된 매장 뷰
CREATE OR REPLACE VIEW recent_stores AS
SELECT 
    s.*,
    array_agg(c.name) as category_names
FROM stores s
LEFT JOIN store_categories sc ON s.id = sc.store_id
LEFT JOIN categories c ON sc.category_id = c.id
WHERE s.created_at >= NOW() - INTERVAL '30 days'
GROUP BY s.id
ORDER BY s.created_at DESC;

-- 평점이 높은 매장 뷰
CREATE OR REPLACE VIEW top_rated_stores AS
SELECT 
    s.*,
    COALESCE(s.naver_rating, 0) + COALESCE(s.kakao_rating, 0) as combined_rating,
    array_agg(c.name) as category_names
FROM stores s
LEFT JOIN store_categories sc ON s.id = sc.store_id
LEFT JOIN categories c ON sc.category_id = c.id
WHERE s.naver_rating IS NOT NULL OR s.kakao_rating IS NOT NULL
GROUP BY s.id
ORDER BY combined_rating DESC
LIMIT 50;

-- 리필 아이템이 많은 매장 뷰
CREATE OR REPLACE VIEW stores_with_most_refills AS
SELECT 
    s.*,
    array_length(s.refill_items, 1) as refill_count,
    array_agg(c.name) as category_names
FROM stores s
LEFT JOIN store_categories sc ON s.id = sc.store_id
LEFT JOIN categories c ON sc.category_id = c.id
WHERE s.refill_items IS NOT NULL AND array_length(s.refill_items, 1) > 0
GROUP BY s.id
ORDER BY refill_count DESC, s.name;

-- 데이터 품질 체크 함수
CREATE OR REPLACE FUNCTION check_data_quality()
RETURNS TABLE (
    check_name TEXT,
    issue_count BIGINT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    
    -- 좌표가 서울 범위를 벗어난 매장
    SELECT 
        'invalid_seoul_coordinates'::TEXT,
        COUNT(*)::BIGINT,
        '서울 좌표 범위(위도 37.4-37.7, 경도 126.8-127.2)를 벗어난 매장'::TEXT
    FROM stores 
    WHERE position_lat < 37.4 OR position_lat > 37.7 
       OR position_lng < 126.8 OR position_lng > 127.2
    
    UNION ALL
    
    -- 매장명이 비어있는 경우
    SELECT 
        'empty_store_names'::TEXT,
        COUNT(*)::BIGINT,
        '매장명이 비어있는 매장'::TEXT
    FROM stores 
    WHERE name IS NULL OR trim(name) = ''
    
    UNION ALL
    
    -- 주소가 비어있는 경우
    SELECT 
        'empty_addresses'::TEXT,
        COUNT(*)::BIGINT,
        '주소가 비어있는 매장'::TEXT
    FROM stores 
    WHERE address IS NULL OR trim(address) = ''
    
    UNION ALL
    
    -- 카테고리가 없는 매장
    SELECT 
        'stores_without_categories'::TEXT,
        COUNT(*)::BIGINT,
        '카테고리가 할당되지 않은 매장'::TEXT
    FROM stores s
    LEFT JOIN store_categories sc ON s.id = sc.store_id
    WHERE sc.store_id IS NULL
    
    UNION ALL
    
    -- 중복 매장명 + 주소
    SELECT 
        'duplicate_stores'::TEXT,
        COUNT(*) - COUNT(DISTINCT name, address)::BIGINT,
        '동일한 이름과 주소를 가진 중복 매장'::TEXT
    FROM stores;
    
END;
$$ LANGUAGE plpgsql;

-- 매장 데이터 정리 함수
CREATE OR REPLACE FUNCTION cleanup_store_data()
RETURNS TEXT AS $$
DECLARE
    cleanup_count INTEGER := 0;
BEGIN
    -- 빈 문자열을 NULL로 변경
    UPDATE stores 
    SET description = NULL 
    WHERE description IS NOT NULL AND trim(description) = '';
    
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    
    UPDATE stores 
    SET open_hours = NULL 
    WHERE open_hours IS NOT NULL AND trim(open_hours) = '';
    
    UPDATE stores 
    SET price = NULL 
    WHERE price IS NOT NULL AND trim(price) = '';
    
    -- 빈 배열 정리
    UPDATE stores 
    SET refill_items = NULL 
    WHERE refill_items IS NOT NULL AND array_length(refill_items, 1) IS NULL;
    
    UPDATE stores 
    SET image_urls = NULL 
    WHERE image_urls IS NOT NULL AND array_length(image_urls, 1) IS NULL;
    
    RETURN '데이터 정리 완료: ' || cleanup_count || '개 레코드 처리됨';
END;
$$ LANGUAGE plpgsql;

-- 매장 검색을 위한 추가 인덱스
CREATE INDEX IF NOT EXISTS idx_stores_name_gin ON stores USING GIN (to_tsvector('korean', name));
CREATE INDEX IF NOT EXISTS idx_stores_address_gin ON stores USING GIN (to_tsvector('korean', address));
CREATE INDEX IF NOT EXISTS idx_stores_description_gin ON stores USING GIN (to_tsvector('korean', coalesce(description, '')));

-- 전문 검색 함수 (한국어 지원)
CREATE OR REPLACE FUNCTION search_stores_fulltext(search_term TEXT)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    address TEXT,
    description TEXT,
    position_lat DOUBLE PRECISION,
    position_lng DOUBLE PRECISION,
    naver_rating DOUBLE PRECISION,
    kakao_rating DOUBLE PRECISION,
    price TEXT,
    refill_items TEXT[],
    image_urls TEXT[],
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id, s.name, s.address, s.description,
        s.position_lat, s.position_lng,
        s.naver_rating, s.kakao_rating,
        s.price, s.refill_items, s.image_urls,
        ts_rank(
            to_tsvector('korean', s.name || ' ' || s.address || ' ' || coalesce(s.description, '')),
            plainto_tsquery('korean', search_term)
        ) as rank
    FROM stores s
    WHERE to_tsvector('korean', s.name || ' ' || s.address || ' ' || coalesce(s.description, ''))
          @@ plainto_tsquery('korean', search_term)
    ORDER BY rank DESC, s.name;
END;
$$ LANGUAGE plpgsql; 