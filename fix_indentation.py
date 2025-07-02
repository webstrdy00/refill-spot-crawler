#!/usr/bin/env python3
"""
들여쓰기 오류 수정 스크립트
"""

def fix_supabase_migration():
    """supabase_migration.py 들여쓰기 수정"""
    with open('src/utils/supabase_migration.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 208번째 줄 수정 (0-based index이므로 207)
    if len(lines) > 207:
        lines[207] = '                if (url.startswith((\'data/\', \'data\\\\\', \'/\')) or \n'
    
    with open('src/utils/supabase_migration.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ supabase_migration.py 수정 완료")

def fix_crawler():
    """crawler.py 들여쓰기 수정"""
    with open('src/core/crawler.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 1342번째 줄 수정 (0-based index이므로 1341)
    if len(lines) > 1341:
        lines[1341] = '                    src = img.get(\'src\') or img.get(\'data-src\') or img.get(\'data-lazy\')\n'
    
    # 1350번째 줄 수정 (0-based index이므로 1349)
    if len(lines) > 1349:
        lines[1349] = '                            alt_text = img.get(\'alt\', \'\').lower()\n'
    
    # 1942번째 줄 수정 (0-based index이므로 1941)
    if len(lines) > 1941:
        lines[1941] = '                self.driver.quit()\n'
    
    with open('src/core/crawler.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ crawler.py 수정 완료")

if __name__ == "__main__":
    print("🔧 들여쓰기 오류 수정 시작...")
    
    try:
        fix_supabase_migration()
        fix_crawler()
        print("\n🎉 모든 들여쓰기 오류 수정 완료!")
        
        # 수정 확인
        print("\n📋 수정 확인 중...")
        
        # supabase_migration.py 테스트
        try:
            import sys
            sys.path.append('.')
            from src.utils.supabase_migration import SupabaseMigration
            print("✅ supabase_migration.py import 성공")
        except Exception as e:
            print(f"❌ supabase_migration.py import 실패: {e}")
        
        # crawler.py 테스트
        try:
            from src.core.crawler import DiningCodeCrawler
            print("✅ crawler.py import 성공")
        except Exception as e:
            print(f"❌ crawler.py import 실패: {e}")
            
    except Exception as e:
        print(f"❌ 수정 실패: {e}") 