@echo off
echo ===== 다이닝코드 크롤러 가상환경 설정 =====
echo.

REM 현재 디렉토리 확인
echo 현재 작업 디렉토리: %CD%
echo.

REM Python 버전 확인
echo Python 버전 확인 중...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
    echo Python 3.8 이상을 설치해주세요.
    pause
    exit /b 1
)
echo.

REM 기존 가상환경이 있으면 삭제 여부 확인
if exist "venv" (
    echo 기존 가상환경이 발견되었습니다.
    set /p choice="기존 가상환경을 삭제하고 새로 만드시겠습니까? (y/n): "
    if /i "%choice%"=="y" (
        echo 기존 가상환경 삭제 중...
        rmdir /s /q venv
        echo 삭제 완료.
    ) else (
        echo 기존 가상환경을 사용합니다.
        goto activate_env
    )
)

REM 가상환경 생성
echo 가상환경 생성 중...
python -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: 가상환경 생성에 실패했습니다.
    pause
    exit /b 1
)
echo 가상환경 생성 완료.
echo.

:activate_env
REM 가상환경 활성화
echo 가상환경 활성화 중...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: 가상환경 활성화에 실패했습니다.
    pause
    exit /b 1
)
echo 가상환경 활성화 완료.
echo.

REM pip 업그레이드
echo pip 업그레이드 중...
python -m pip install --upgrade pip
echo.

REM 의존성 설치
echo 의존성 패키지 설치 중...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: 의존성 설치에 실패했습니다.
        pause
        exit /b 1
    )
    echo 의존성 설치 완료.
) else (
    echo WARNING: requirements.txt 파일이 없습니다.
    echo 수동으로 필요한 패키지를 설치해주세요.
)
echo.

REM Chrome 드라이버 확인
echo Chrome 브라우저 및 드라이버 확인...
python -c "from selenium import webdriver; from selenium.webdriver.chrome.options import Options; options = Options(); options.add_argument('--headless'); driver = webdriver.Chrome(options=options); print('Chrome 드라이버 정상 작동'); driver.quit()" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: Chrome 드라이버가 제대로 설정되지 않았습니다.
    echo Chrome 브라우저가 최신 버전인지 확인하고, ChromeDriver를 설치해주세요.
    echo ChromeDriver 다운로드: https://chromedriver.chromium.org/
) else (
    echo Chrome 드라이버 정상 확인.
)
echo.

echo ===== 설정 완료 =====
echo.
echo 가상환경이 활성화되었습니다.
echo 크롤러를 실행하려면 다음 명령어를 사용하세요:
echo   python test_simple_crawler.py
echo   또는
echo   python main.py
echo.
echo 가상환경을 비활성화하려면: deactivate
echo 다음에 가상환경을 활성화하려면: venv\Scripts\activate
echo.
pause 