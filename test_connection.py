"""
환경 설정 및 연결 테스트 스크립트
Python 3.12 + Docker PostgreSQL 환경용
"""

import sys
import subprocess
import platform

def check_python_version():
    """Python 버전 확인"""
    print("🐍 Python 버전 확인...")
    version = sys.version_info
    print(f"   현재 버전: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 8:
        print("❌ Python 3.8 이상이 필요합니다.")
        return False
    
    if version.minor == 12:
        print("✅ Python 3.12 감지 - 최적화된 설정 사용")
    else:
        print("⚠️  Python 3.12가 아니지만 호환 가능")
    
    return True

def check_docker():
    """Docker 설치 및 실행 상태 확인"""
    print("\n🐳 Docker 확인...")
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Docker 설치됨: {result.stdout.strip()}")
            
            # Docker Compose 확인
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ Docker Compose 설치됨: {result.stdout.strip()}")
                return True
            else:
                print("❌ Docker Compose가 설치되지 않았습니다.")
                return False
        else:
            print("❌ Docker가 설치되지 않았거나 실행되지 않습니다.")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Docker를 찾을 수 없습니다.")
        return False

def check_chrome():
    """Chrome/Chromium 및 ChromeDriver 확인"""
    print("\n🌐 Chrome 및 ChromeDriver 확인...")
    
    # Chrome 버전 확인
    chrome_commands = ['google-chrome', 'chromium', 'chromium-browser', 'chrome']
    chrome_found = False
    
    for cmd in chrome_commands:
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ Chrome 발견: {result.stdout.strip()}")
                chrome_found = True
                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    if not chrome_found:
        print("⚠️  Chrome/Chromium을 찾을 수 없습니다.")
    
    # ChromeDriver 확인
    try:
        result = subprocess.run(['chromedriver', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ ChromeDriver 발견: {result.stdout.strip()}")
            return True
        else:
            print("❌ ChromeDriver가 설치되지 않았습니다.")
            print("   설치 방법:")
            if platform.system() == "Darwin":  # macOS
                print("   brew install chromedriver")
            elif platform.system() == "Linux":
                print("   sudo apt-get install chromium-chromedriver")
            else:  # Windows
                print("   https://chromedriver.chromium.org/ 에서 다운로드")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ ChromeDriver를 찾을 수 없습니다.")
        return False

def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("\n🗄️  데이터베이스 연결 테스트...")
    
    try:
        import config
        
        # DATABASE_URL 설정 확인
        if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL:
            # 비밀번호 마스킹해서 표시
            masked_url = config.DATABASE_URL
            if config.DB_PASSWORD and config.DB_PASSWORD in masked_url:
                masked_url = masked_url.replace(config.DB_PASSWORD, '***')
            print(f"✅ DATABASE_URL 설정: {masked_url}")
        else:
            print(f"✅ 개별 파라미터 설정:")
            print(f"  Host: {config.DB_HOST}")
            print(f"  Port: {config.DB_PORT}")
            print(f"  Database: {config.DB_NAME}")
            print(f"  User: {config.DB_USER}")
        
        from database import DatabaseManager
        
        db = DatabaseManager()
        if db.test_connection():
            print("✅ PostgreSQL 연결 성공!")
            
            # 테이블 존재 확인
            cursor = db.pg_conn.cursor()
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            expected_tables = ['stores', 'categories', 'store_categories']
            for table in expected_tables:
                if table in tables:
                    print(f"✅ 테이블 '{table}' 존재")
                else:
                    print(f"⚠️  테이블 '{table}' 없음 - 자동 생성될 예정")
            
            # 추가 테이블 확인
            if 'crawling_logs' in tables:
                print("✅ 크롤링 로그 테이블 존재")
            
            db.close()
            return True
        else:
            print("❌ 데이터베이스 연결 실패")
            return False
            
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("   pip install -r requirements.txt 를 실행하세요.")
        return False
    except Exception as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")
        print("   docker-compose up -d postgres 를 실행하세요.")
        print("   또는 DATABASE_URL 설정을 확인하세요.")
        return False

def test_crawler_basic():
    """크롤러 기본 동작 테스트"""
    print("\n🕷️  크롤러 기본 테스트...")
    
    try:
        from crawler import DiningCodeCrawler
        import config
        
        print("✅ 크롤러 모듈 import 성공")
        print(f"✅ 테스트 영역: {config.TEST_RECT}")
        print(f"✅ 검색 키워드: {config.KEYWORDS}")
        
        # WebDriver 초기화 테스트 (실제 실행하지 않음)
        print("⏳ WebDriver 초기화 테스트...")
        crawler = DiningCodeCrawler()
        print("✅ WebDriver 초기화 성공")
        crawler.close()
        
        return True
        
    except ImportError as e:
        print(f"❌ 크롤러 모듈 import 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 크롤러 초기화 실패: {e}")
        return False

def check_environment_file():
    """환경변수 파일 확인"""
    print("\n📝 환경 설정 파일 확인...")
    
    import os
    
    if os.path.exists('.env'):
        print("✅ .env 파일 존재")
        
        # .env 파일 내용 확인
        with open('.env', 'r') as f:
            content = f.read()
            
        required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        for var in required_vars:
            if var in content:
                print(f"✅ {var} 설정됨")
            else:
                print(f"⚠️  {var} 누락")
        
        return True
    else:
        print("❌ .env 파일 없음")
        print("   cp .env.example .env 를 실행하세요.")
        return False

def main():
    """전체 환경 테스트 실행"""
    print("🚀 Refill Spot 크롤러 환경 테스트 시작")
    print("=" * 50)
    
    tests = [
        ("Python 버전", check_python_version),
        ("Docker", check_docker),
        ("Chrome/ChromeDriver", check_chrome),
        ("환경 설정 파일", check_environment_file),
        ("데이터베이스 연결", test_database_connection),
        ("크롤러 기본 동작", test_crawler_basic),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 오류: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📋 테스트 결과 요약")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name:<20}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 {passed}/{len(results)}개 테스트 통과")
    
    if passed == len(results):
        print("\n🎉 모든 테스트 통과! 크롤링을 시작할 수 있습니다.")
        print("\n다음 명령어로 실행하세요:")
        print("  python main.py test     # 단일 가게 테스트")
        print("  python main.py          # 전체 MVP 실행")
    else:
        print(f"\n⚠️  {len(results) - passed}개 테스트 실패. 위의 오류를 해결하세요.")
        print("\n도움말:")
        print("  ./setup.sh              # 자동 설정 스크립트")
        print("  docker-compose up -d    # PostgreSQL 시작")
        print("  pip install -r requirements.txt  # 의존성 설치")

if __name__ == "__main__":
    main()