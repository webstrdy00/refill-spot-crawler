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
        from src.utils.main import main
        return main()
    except ImportError:
        print("❌ 크롤러 모듈을 찾을 수 없습니다.")
        print("src/utils/main.py 파일이 존재하는지 확인해주세요.")
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
        return asyncio.run(test_main())
    except ImportError:
        print("❌ 테스트 모듈을 찾을 수 없습니다.")
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