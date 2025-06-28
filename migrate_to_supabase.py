#!/usr/bin/env python3
"""
Supabase MCP를 활용한 크롤링 데이터 마이그레이션
"""
import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 직접 import하여 패키지 의존성 회피
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'utils'))
from supabase_migration import SupabaseMigration

async def main():
    """메인 마이그레이션 실행"""
    print("🍽️ 리필스팟 Supabase 마이그레이션")
    print("=" * 50)
    
    # 마이그레이션 객체 생성
    migration = SupabaseMigration()
    
    try:
        # 1. 미리보기 생성
        print("👀 마이그레이션 미리보기 생성 중...")
        stores = migration.get_crawler_stores(limit=5)
        
        if not stores:
            print("❌ 크롤러 데이터가 없습니다.")
            return
        
        print(f"📊 총 {len(stores)}개 가게 발견")
        print("\n📋 샘플 데이터:")
        print("-" * 40)
        
        for i, store in enumerate(stores[:3], 1):
            try:
                processed = migration.process_store_data(store)
                print(f"{i}. {processed['name']}")
                print(f"   주소: {processed['address']}")
                print(f"   카테고리: {', '.join(processed['categories'])}")
                print(f"   리필아이템: {', '.join(processed['refill_items'][:3])}")
                print()
            except Exception as e:
                print(f"   ❌ 데이터 처리 실패: {e}")
                continue
        
        # 2. SQL 생성
        print("📝 SQL 문 생성 중...")
        sql_statements = migration.generate_sql_statements(limit=10)
        
        # 3. SQL 파일 저장
        output_file = "supabase_migration.sql"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- Supabase 마이그레이션 SQL\n")
            f.write("-- 리필스팟 크롤러 데이터 → Supabase\n\n")
            f.write("\n".join(sql_statements))
        
        print(f"✅ SQL 파일 생성 완료: {output_file}")
        print(f"📄 총 {len(sql_statements)}개 SQL 문 생성")
        
        # 4. 다음 단계 안내
        print("\n🔧 다음 단계:")
        print("1. supabase_migration.sql 파일을 확인하세요")
        print("2. Supabase SQL Editor에서 실행하거나")
        print("3. 아래 명령어로 MCP를 통해 실행하세요:")
        print("   python execute_supabase_migration.py")
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        raise
    finally:
        migration.close()
        print("\n🔚 마이그레이션 스크립트 완료")

if __name__ == "__main__":
    asyncio.run(main()) 