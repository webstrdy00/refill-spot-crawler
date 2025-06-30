import psycopg2
import json

# 데이터베이스 연결
conn = psycopg2.connect('postgresql://postgres:12345@localhost:5432/refill_spot_crawler')
cur = conn.cursor()

# 전체 통계
print("=== 전체 통계 ===")
cur.execute("SELECT COUNT(*) FROM stores")
print(f"총 가게 수: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM categories")
print(f"총 카테고리 수: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM store_categories")
print(f"총 가게-카테고리 연결 수: {cur.fetchone()[0]}")

# 최근 추가된 가게 확인
print("\n=== 최근 추가된 가게 (diningcode_place_id가 있는 것만) ===")
cur.execute("""
    SELECT id, name, diningcode_place_id, raw_categories_diningcode, created_at 
    FROM stores 
    WHERE diningcode_place_id IS NOT NULL
    ORDER BY created_at DESC 
    LIMIT 10
""")
stores = cur.fetchall()
print(f"DiningCode ID가 있는 가게 수: {len(stores)}")
for store in stores:
    print(f"\nID: {store[0]}, Name: {store[1]}")
    print(f"  DiningCode ID: {store[2]}")
    print(f"  Raw Categories: {store[3]}")
    print(f"  Created: {store[4]}")

# 가게별 카테고리 연결 확인
print("\n=== 가게별 카테고리 연결 상태 ===")
cur.execute("""
    SELECT s.id, s.name, s.diningcode_place_id, 
           array_agg(c.name ORDER BY c.name) as categories
    FROM stores s
    LEFT JOIN store_categories sc ON s.id = sc.store_id
    LEFT JOIN categories c ON sc.category_id = c.id
    WHERE s.diningcode_place_id IS NOT NULL
    GROUP BY s.id, s.name, s.diningcode_place_id
    ORDER BY s.created_at DESC
    LIMIT 10
""")
results = cur.fetchall()
for store_id, name, dining_id, categories in results:
    print(f"\n{name} (ID: {store_id}, DiningCode: {dining_id})")
    print(f"  연결된 카테고리: {categories if categories[0] else '없음'}")

# 카테고리별 가게 수
print("\n=== 카테고리별 가게 수 ===")
cur.execute("""
    SELECT c.name, COUNT(DISTINCT sc.store_id) as store_count
    FROM categories c
    LEFT JOIN store_categories sc ON c.id = sc.category_id
    GROUP BY c.name
    ORDER BY store_count DESC
""")
cat_stats = cur.fetchall()
for cat_name, count in cat_stats:
    print(f"  {cat_name}: {count}개 가게")

cur.close()
conn.close() 