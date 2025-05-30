#!/bin/bash

echo "🚀 Refill Spot 크롤러 설정 시작 (Python 3.12)"

# Python 버전 확인
echo "📋 Python 버전 확인..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3가 설치되지 않았습니다."
    exit 1
fi

# 가상환경 생성
echo "🔧 가상환경 생성..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ 가상환경 생성 실패"
    exit 1
fi

# 가상환경 활성화
echo "✅ 가상환경 활성화..."
source venv/bin/activate

# 의존성 설치
echo "📦 의존성 설치..."
pip install --upgrade pip
pip install -r requirements.txt

# .env 파일 설정
if [ ! -f .env ]; then
    echo "📝 .env 파일 생성..."
    cp .env.example .env
    echo "⚠️  .env 파일을 수정하여 DATABASE_URL을 확인하세요."
    echo "   기본값: postgresql://postgres:password123@localhost:5432/refill_spot"
fi

# Docker Compose 시작
echo "🐳 Docker PostgreSQL 시작..."
docker-compose up -d postgres

# 데이터베이스 연결 대기
echo "⏳ 데이터베이스 준비 대기..."
sleep 10

# 데이터베이스 연결 테스트
echo "🔍 데이터베이스 연결 테스트..."
python -c "
from database import DatabaseManager
try:
    db = DatabaseManager()
    if db.test_connection():
        print('✅ 데이터베이스 연결 성공!')
    db.close()
except Exception as e:
    print(f'❌ 데이터베이스 연결 실패: {e}')
    print('DATABASE_URL 설정을 확인하세요.')
"

echo ""
echo "🎉 설정 완료!"
echo ""
echo "DATABASE_URL 형식:"
echo "  postgresql://username:password@hostname:port/database"
echo "  예: postgresql://postgres:password123@localhost:5432/refill_spot"
echo ""
echo "다음 명령어로 크롤링을 시작하세요:"
echo "  python test_connection.py  # 전체 환경 검증"
echo "  python main.py test        # 단일 가게 테스트"
echo "  python main.py db          # DB 기능 테스트"
echo "  python main.py full        # 전체 MVP 실행"
echo ""
echo "PostgreSQL 관리:"
echo "  docker-compose up -d pgadmin   # pgAdmin 시작 (http://localhost:5050)"
echo "  docker-compose down            # 모든 서비스 종료"