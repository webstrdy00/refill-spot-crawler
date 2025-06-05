import psycopg2
import config

try:
    conn = psycopg2.connect(
        host=config.DB_HOST, 
        port=config.DB_PORT, 
        database=config.DB_NAME, 
        user=config.DB_USER, 
        password=config.DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 총 가게 수
    cursor.execute('SELECT COUNT(*) FROM stores')
    total_count = cursor.fetchone()[0]
    print(f'총 가게 수: {total_count}')
    
    # 최근 저장된 가게들
    cursor.execute('SELECT name, address FROM stores ORDER BY id DESC LIMIT 5')
    results = cursor.fetchall()
    print('\n최근 저장된 가게:')
    for i, (name, address) in enumerate(results, 1):
        print(f'{i}. {name}: {address}')
    
    conn.close()
    print('\n✅ 데이터베이스 확인 완료')
    
except Exception as e:
    print(f'❌ 데이터베이스 연결 실패: {e}') 