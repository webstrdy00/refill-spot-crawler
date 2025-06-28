#!/usr/bin/env python3
"""
리필스팟 크롤러 메인 실행 파일
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_main_crawler():
    """메인 크롤러 실행"""
    try:
        # 직접 import하여 실행 (실시간 로그 확인 가능)
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'utils'))
        from main import run_enhanced_crawling
        
        print("📍 강남 지역 크롤링을 시작합니다...")
        print("💡 전체 서울 크롤링을 원하시면 'python src/utils/main.py stage4'를 직접 실행하세요")
        
        # enhanced 모드로 실행 (강남 지역만, 빠른 테스트용)
        result = run_enhanced_crawling()
        
        if result:
            print("✅ 크롤링 완료!")
            return True
        else:
            print("❌ 크롤링 실패!")
            return False
            
    except Exception as e:
        print(f"❌ 크롤러 실행 오류: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def run_automation():
    """자동화 시스템 실행"""
    try:
        from src.automation.automated_operations import main
        return main()
    except ImportError:
        print("❌ 자동화 모듈을 찾을 수 없습니다.")
        print("src/automation/automated_operations.py 파일이 존재하는지 확인해주세요.")
        return False

def run_tests():
    """테스트 실행"""
    try:
        from src.tests.stage6_test import main as test_main
        results = asyncio.run(test_main())
        # 테스트 결과가 딕셔너리인 경우, 모든 테스트가 통과했는지 확인
        if isinstance(results, dict):
            return all(results.values())
        return True  # 테스트가 완료되면 성공으로 간주
    except ImportError:
        print("❌ 테스트 모듈을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='리필스팟 크롤러 시스템')
    parser.add_argument('--mode', choices=['crawler', 'automation', 'test'], 
                       default='crawler', help='실행 모드 선택')
    
    args = parser.parse_args()
    
    print("🍽️ 리필스팟 크롤러 시스템")
    print("=" * 50)
    
    if args.mode == 'crawler':
        print("🚀 크롤러 모드로 실행합니다...")
        success = run_main_crawler()
    elif args.mode == 'automation':
        print("🤖 자동화 모드로 실행합니다...")
        success = asyncio.run(run_automation())
    elif args.mode == 'test':
        print("🧪 테스트 모드로 실행합니다...")
        success = run_tests()
    
    if success:
        print("✅ 실행 완료!")
    else:
        print("❌ 실행 실패!")
        sys.exit(1)

if __name__ == "__main__":
    main() 