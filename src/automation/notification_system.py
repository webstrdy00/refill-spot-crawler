"""
알림 및 리포팅 시스템
- Slack/Discord 알림 (일일 크롤링 완료 보고, 에러 발생 시 즉시 알림, 주간 데이터 품질 리포트)
- 자동 보고서 생성 (지역별 성장 추이, 신규 개업 가게 리스트, 트렌드 분석)
"""

import asyncio
import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import aiohttp
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from jinja2 import Template
import sqlite3
import os
from ..core.database import DatabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NotificationConfig:
    """알림 설정"""
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: List[str] = None
    
    def __post_init__(self):
        if self.email_recipients is None:
            self.email_recipients = []

@dataclass
class CrawlingStats:
    """크롤링 통계"""
    total_stores: int
    new_stores: int
    updated_stores: int
    failed_requests: int
    success_rate: float
    processing_time: float
    errors: List[str]
    districts_processed: List[str]
    timestamp: datetime

@dataclass
class QualityStats:
    """품질 통계"""
    total_issues: int
    coordinate_issues: int
    duplicate_issues: int
    business_hours_issues: int
    auto_fixed_issues: int
    manual_review_needed: int
    quality_score: float

@dataclass
class TrendAnalysis:
    """트렌드 분석"""
    district: str
    new_stores_trend: List[Tuple[str, int]]  # (날짜, 신규 가게 수)
    closure_trend: List[Tuple[str, int]]     # (날짜, 폐업 가게 수)
    category_growth: Dict[str, float]        # 카테고리별 성장률
    popular_areas: List[Tuple[str, int]]     # (지역명, 가게 수)

class SlackNotifier:
    """Slack 알림 발송"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_message(self, message: str, title: str = "크롤링 시스템 알림", 
                          color: str = "good") -> bool:
        """Slack 메시지 발송"""
        try:
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": title,
                        "text": message,
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Slack 메시지 발송 성공")
                        return True
                    else:
                        logger.error(f"Slack 메시지 발송 실패: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Slack 알림 발송 중 오류: {e}")
            return False
    
    async def send_daily_report(self, stats: CrawlingStats, quality_stats: QualityStats):
        """일일 크롤링 보고서 발송"""
        message = f"""
📊 **일일 크롤링 완료 보고**

🏪 **처리 현황**
• 총 가게 수: {stats.total_stores:,}개
• 신규 가게: {stats.new_stores:,}개
• 업데이트: {stats.updated_stores:,}개
• 성공률: {stats.success_rate:.1f}%
• 처리 시간: {stats.processing_time:.1f}분

🎯 **품질 현황**
• 품질 점수: {quality_stats.quality_score:.1f}/100
• 발견된 이슈: {quality_stats.total_issues}개
• 자동 수정: {quality_stats.auto_fixed_issues}개
• 수동 검토 필요: {quality_stats.manual_review_needed}개

📍 **처리 지역**
{', '.join(stats.districts_processed)}

⏰ 처리 완료: {stats.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        color = "good" if stats.success_rate >= 95 else "warning" if stats.success_rate >= 85 else "danger"
        await self.send_message(message, "일일 크롤링 완료 보고", color)
    
    async def send_error_alert(self, error_type: str, error_message: str, 
                              severity: str = "high"):
        """에러 알림 발송"""
        color_map = {"low": "good", "medium": "warning", "high": "danger"}
        color = color_map.get(severity, "warning")
        
        message = f"""
🚨 **크롤링 시스템 에러 발생**

**에러 유형:** {error_type}
**심각도:** {severity.upper()}
**발생 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**에러 내용:**
```
{error_message}
```

즉시 확인이 필요합니다.
        """
        
        await self.send_message(message, "🚨 시스템 에러 알림", color)

class DiscordNotifier:
    """Discord 알림 발송"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_message(self, message: str, title: str = "크롤링 시스템 알림") -> bool:
        """Discord 메시지 발송"""
        try:
            payload = {
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": 0x00ff00,  # 초록색
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.info("Discord 메시지 발송 성공")
                        return True
                    else:
                        logger.error(f"Discord 메시지 발송 실패: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Discord 알림 발송 중 오류: {e}")
            return False

class EmailNotifier:
    """이메일 알림 발송"""
    
    def __init__(self, config: NotificationConfig):
        self.smtp_server = config.email_smtp_server
        self.smtp_port = config.email_smtp_port
        self.username = config.email_username
        self.password = config.email_password
    
    def send_email(self, recipients: List[str], subject: str, body: str, 
                   attachments: List[str] = None) -> bool:
        """이메일 발송"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 첨부파일 처리
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            msg.attach(part)
            
            # SMTP 서버 연결 및 발송
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"이메일 발송 성공: {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"이메일 발송 실패: {e}")
            return False

class ReportGenerator:
    """자동 보고서 생성"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    def get_db_connection(self):
        """데이터베이스 연결"""
        return sqlite3.connect(self.db_path)
    
    def generate_daily_stats(self) -> CrawlingStats:
        """일일 통계 생성"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 오늘 처리된 데이터 조회
                today = datetime.now().date()
                
                # 총 가게 수
                cursor.execute("SELECT COUNT(*) FROM stores WHERE status = 'active'")
                total_stores = cursor.fetchone()[0]
                
                # 오늘 신규 가게
                cursor.execute("""
                    SELECT COUNT(*) FROM stores 
                    WHERE DATE(created_at) = ? AND status = 'active'
                """, (today,))
                new_stores = cursor.fetchone()[0]
                
                # 오늘 업데이트된 가게
                cursor.execute("""
                    SELECT COUNT(*) FROM stores 
                    WHERE DATE(updated_at) = ? AND DATE(created_at) != ?
                """, (today, today))
                updated_stores = cursor.fetchone()[0]
                
                # 크롤링 로그에서 실패 건수 조회
                cursor.execute("""
                    SELECT COUNT(*) FROM crawling_logs 
                    WHERE DATE(created_at) = ? AND status = 'failed'
                """, (today,))
                failed_requests = cursor.fetchone()[0] or 0
                
                # 성공률 계산
                total_requests = new_stores + updated_stores + failed_requests
                success_rate = ((new_stores + updated_stores) / max(total_requests, 1)) * 100
                
                # 처리된 지역 조회
                cursor.execute("""
                    SELECT DISTINCT district FROM stores 
                    WHERE DATE(updated_at) = ?
                """, (today,))
                districts = [row[0] for row in cursor.fetchall()]
                
                return CrawlingStats(
                    total_stores=total_stores,
                    new_stores=new_stores,
                    updated_stores=updated_stores,
                    failed_requests=failed_requests,
                    success_rate=success_rate,
                    processing_time=0,  # 실제 처리 시간은 별도 로깅 필요
                    errors=[],
                    districts_processed=districts,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"일일 통계 생성 실패: {e}")
            return CrawlingStats(0, 0, 0, 0, 0, 0, [str(e)], [], datetime.now())
    
    def generate_quality_stats(self) -> QualityStats:
        """품질 통계 생성"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                today = datetime.now().date()
                
                # 품질 이슈 조회
                cursor.execute("""
                    SELECT issue_type, COUNT(*) FROM quality_issues 
                    WHERE DATE(created_at) = ?
                    GROUP BY issue_type
                """, (today,))
                
                issue_counts = dict(cursor.fetchall())
                total_issues = sum(issue_counts.values())
                
                # 자동 수정된 이슈
                cursor.execute("""
                    SELECT COUNT(*) FROM quality_issues 
                    WHERE DATE(created_at) = ? AND auto_fixed = 1
                """, (today,))
                auto_fixed = cursor.fetchone()[0] or 0
                
                # 품질 점수 계산 (임시 로직)
                quality_score = max(0, 100 - (total_issues * 2))
                
                return QualityStats(
                    total_issues=total_issues,
                    coordinate_issues=issue_counts.get('coordinate', 0),
                    duplicate_issues=issue_counts.get('duplicate', 0),
                    business_hours_issues=issue_counts.get('business_hours', 0),
                    auto_fixed_issues=auto_fixed,
                    manual_review_needed=total_issues - auto_fixed,
                    quality_score=quality_score
                )
                
        except Exception as e:
            logger.error(f"품질 통계 생성 실패: {e}")
            return QualityStats(0, 0, 0, 0, 0, 0, 0)
    
    def generate_trend_analysis(self, days: int = 30) -> List[TrendAnalysis]:
        """트렌드 분석 생성"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 지난 N일간의 데이터 분석
                start_date = datetime.now() - timedelta(days=days)
                
                # 지역별 분석
                cursor.execute("SELECT DISTINCT district FROM stores WHERE district IS NOT NULL")
                districts = [row[0] for row in cursor.fetchall()]
                
                trend_analyses = []
                
                for district in districts:
                    # 신규 가게 트렌드
                    cursor.execute("""
                        SELECT DATE(created_at) as date, COUNT(*) as count
                        FROM stores 
                        WHERE district = ? AND created_at >= ?
                        GROUP BY DATE(created_at)
                        ORDER BY date
                    """, (district, start_date))
                    new_stores_trend = cursor.fetchall()
                    
                    # 폐업 가게 트렌드
                    cursor.execute("""
                        SELECT DATE(updated_at) as date, COUNT(*) as count
                        FROM stores 
                        WHERE district = ? AND status = 'closed' AND updated_at >= ?
                        GROUP BY DATE(updated_at)
                        ORDER BY date
                    """, (district, start_date))
                    closure_trend = cursor.fetchall()
                    
                    # 카테고리별 성장률 (임시 로직)
                    category_growth = {"음식점": 5.2, "카페": 3.1, "편의점": 1.8}
                    
                    # 인기 지역
                    cursor.execute("""
                        SELECT address, COUNT(*) as count
                        FROM stores 
                        WHERE district = ? AND status = 'active'
                        GROUP BY address
                        ORDER BY count DESC
                        LIMIT 5
                    """, (district,))
                    popular_areas = cursor.fetchall()
                    
                    trend_analyses.append(TrendAnalysis(
                        district=district,
                        new_stores_trend=new_stores_trend,
                        closure_trend=closure_trend,
                        category_growth=category_growth,
                        popular_areas=popular_areas
                    ))
                
                return trend_analyses
                
        except Exception as e:
            logger.error(f"트렌드 분석 생성 실패: {e}")
            return []
    
    def create_visualization(self, trend_analyses: List[TrendAnalysis]) -> str:
        """시각화 차트 생성"""
        try:
            # 한글 폰트 설정
            plt.rcParams['font.family'] = 'DejaVu Sans'
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('서울시 가게 현황 분석', fontsize=16, fontweight='bold')
            
            # 1. 지역별 신규 가게 수
            districts = [ta.district for ta in trend_analyses[:10]]  # 상위 10개 지역
            new_counts = [sum([count for _, count in ta.new_stores_trend]) for ta in trend_analyses[:10]]
            
            axes[0, 0].bar(districts, new_counts, color='skyblue')
            axes[0, 0].set_title('지역별 신규 가게 수 (최근 30일)')
            axes[0, 0].set_xlabel('지역')
            axes[0, 0].set_ylabel('신규 가게 수')
            axes[0, 0].tick_params(axis='x', rotation=45)
            
            # 2. 시간별 트렌드
            if trend_analyses:
                dates = [date for date, _ in trend_analyses[0].new_stores_trend]
                counts = [count for _, count in trend_analyses[0].new_stores_trend]
                
                axes[0, 1].plot(dates, counts, marker='o', color='green')
                axes[0, 1].set_title('신규 가게 등록 트렌드')
                axes[0, 1].set_xlabel('날짜')
                axes[0, 1].set_ylabel('신규 가게 수')
                axes[0, 1].tick_params(axis='x', rotation=45)
            
            # 3. 카테고리별 성장률
            if trend_analyses:
                categories = list(trend_analyses[0].category_growth.keys())
                growth_rates = list(trend_analyses[0].category_growth.values())
                
                axes[1, 0].pie(growth_rates, labels=categories, autopct='%1.1f%%', startangle=90)
                axes[1, 0].set_title('카테고리별 성장률')
            
            # 4. 상위 인기 지역
            if trend_analyses and trend_analyses[0].popular_areas:
                areas = [area for area, _ in trend_analyses[0].popular_areas]
                counts = [count for _, count in trend_analyses[0].popular_areas]
                
                axes[1, 1].barh(areas, counts, color='orange')
                axes[1, 1].set_title('인기 지역 TOP 5')
                axes[1, 1].set_xlabel('가게 수')
            
            plt.tight_layout()
            
            # 파일 저장
            chart_path = self.reports_dir / f"trend_analysis_{datetime.now().strftime('%Y%m%d')}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"시각화 생성 실패: {e}")
            return ""
    
    def generate_html_report(self, stats: CrawlingStats, quality_stats: QualityStats, 
                           trend_analyses: List[TrendAnalysis], chart_path: str = "") -> str:
        """HTML 보고서 생성"""
        template_str = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>크롤링 시스템 주간 보고서</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 3px solid #007bff; }
        .header h1 { color: #007bff; margin: 0; font-size: 2.5em; }
        .header p { color: #666; margin: 10px 0 0 0; font-size: 1.1em; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-card h3 { margin: 0 0 10px 0; font-size: 1.2em; opacity: 0.9; }
        .stat-card .number { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
        .quality-section { margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; }
        .quality-section h2 { color: #28a745; margin-bottom: 20px; }
        .progress-bar { background: #e9ecef; border-radius: 10px; overflow: hidden; height: 20px; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s ease; }
        .trend-section { margin: 30px 0; }
        .trend-section h2 { color: #dc3545; margin-bottom: 20px; }
        .district-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .district-card { background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; }
        .chart-section { text-align: center; margin: 30px 0; }
        .chart-section img { max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏪 크롤링 시스템 주간 보고서</h1>
            <p>{{ stats.timestamp.strftime('%Y년 %m월 %d일') }} 기준</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>총 가게 수</h3>
                <div class="number">{{ "{:,}".format(stats.total_stores) }}</div>
            </div>
            <div class="stat-card">
                <h3>신규 가게</h3>
                <div class="number">{{ "{:,}".format(stats.new_stores) }}</div>
            </div>
            <div class="stat-card">
                <h3>업데이트</h3>
                <div class="number">{{ "{:,}".format(stats.updated_stores) }}</div>
            </div>
            <div class="stat-card">
                <h3>성공률</h3>
                <div class="number">{{ "%.1f"|format(stats.success_rate) }}%</div>
            </div>
        </div>
        
        <div class="quality-section">
            <h2>📊 품질 현황</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <p><strong>품질 점수:</strong> {{ "%.1f"|format(quality_stats.quality_score) }}/100</p>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ quality_stats.quality_score }}%"></div>
                    </div>
                </div>
                <div>
                    <p><strong>총 이슈:</strong> {{ quality_stats.total_issues }}개</p>
                    <p><strong>자동 수정:</strong> {{ quality_stats.auto_fixed_issues }}개</p>
                    <p><strong>수동 검토 필요:</strong> {{ quality_stats.manual_review_needed }}개</p>
                </div>
            </div>
        </div>
        
        {% if chart_path %}
        <div class="chart-section">
            <h2>📈 트렌드 분석</h2>
            <img src="{{ chart_path }}" alt="트렌드 분석 차트">
        </div>
        {% endif %}
        
        <div class="trend-section">
            <h2>🏙️ 지역별 현황</h2>
            <div class="district-list">
                {% for trend in trend_analyses[:6] %}
                <div class="district-card">
                    <h4>{{ trend.district }}</h4>
                    <p><strong>신규 가게:</strong> {{ trend.new_stores_trend|length }}건</p>
                    <p><strong>인기 지역:</strong> 
                        {% for area, count in trend.popular_areas[:2] %}
                            {{ area }} ({{ count }}개){% if not loop.last %}, {% endif %}
                        {% endfor %}
                    </p>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="footer">
            <p>🤖 자동 생성된 보고서 | 크롤링 시스템 v6.0</p>
            <p>문의사항이 있으시면 시스템 관리자에게 연락해주세요.</p>
        </div>
    </div>
</body>
</html>
        """
        
        try:
            template = Template(template_str)
            html_content = template.render(
                stats=stats,
                quality_stats=quality_stats,
                trend_analyses=trend_analyses,
                chart_path=chart_path
            )
            
            # HTML 파일 저장
            report_path = self.reports_dir / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.html"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML 보고서 생성 완료: {report_path}")
            return str(report_path)
            
        except Exception as e:
            logger.error(f"HTML 보고서 생성 실패: {e}")
            return ""

class NotificationSystem:
    """통합 알림 시스템"""
    
    def __init__(self, config: NotificationConfig, db_path: str):
        self.config = config
        self.db_path = db_path
        self.db_manager = DatabaseManager()
        self.slack_notifier = SlackNotifier(config.slack_webhook_url)
        self.discord_notifier = DiscordNotifier(config.discord_webhook_url)
        self.email_notifier = EmailNotifier(config)
        self.report_generator = ReportGenerator(db_path)
        
        logger.info("알림 시스템 초기화 완료")
    
    async def send_daily_report(self):
        """일일 보고서 발송"""
        try:
            # 통계 생성
            stats = self.report_generator.generate_daily_stats()
            quality_stats = self.report_generator.generate_quality_stats()
            
            # Slack 알림
            if self.slack_notifier:
                await self.slack_notifier.send_daily_report(stats, quality_stats)
            
            # Discord 알림
            if self.discord_notifier:
                message = f"""
📊 **일일 크롤링 완료**
• 총 가게: {stats.total_stores:,}개
• 신규: {stats.new_stores:,}개  
• 성공률: {stats.success_rate:.1f}%
• 품질점수: {quality_stats.quality_score:.1f}/100
                """
                await self.discord_notifier.send_message(message, "일일 크롤링 보고")
            
            logger.info("일일 보고서 발송 완료")
            
        except Exception as e:
            logger.error(f"일일 보고서 발송 실패: {e}")
    
    async def send_error_alert(self, error_type: str, error_message: str, severity: str = "high"):
        """에러 알림 발송"""
        try:
            # Slack 알림
            if self.slack_notifier:
                await self.slack_notifier.send_error_alert(error_type, error_message, severity)
            
            # Discord 알림
            if self.discord_notifier:
                message = f"🚨 **{error_type}** 에러 발생\n심각도: {severity}\n```{error_message}```"
                await self.discord_notifier.send_message(message, "시스템 에러 알림")
            
            logger.info(f"에러 알림 발송 완료: {error_type}")
            
        except Exception as e:
            logger.error(f"에러 알림 발송 실패: {e}")
    
    def generate_weekly_report(self) -> str:
        """주간 보고서 생성"""
        try:
            # 통계 및 트렌드 분석 생성
            stats = self.report_generator.generate_daily_stats()
            quality_stats = self.report_generator.generate_quality_stats()
            trend_analyses = self.report_generator.generate_trend_analysis(days=7)
            
            # 시각화 차트 생성
            chart_path = self.report_generator.create_visualization(trend_analyses)
            
            # HTML 보고서 생성
            report_path = self.report_generator.generate_html_report(
                stats, quality_stats, trend_analyses, chart_path
            )
            
            # 이메일 발송
            if self.email_notifier and self.config.email_recipients:
                subject = f"크롤링 시스템 주간 보고서 - {datetime.now().strftime('%Y.%m.%d')}"
                body = f"""
                <h2>크롤링 시스템 주간 보고서</h2>
                <p>상세한 보고서는 첨부파일을 확인해주세요.</p>
                <ul>
                    <li>총 가게 수: {stats.total_stores:,}개</li>
                    <li>신규 가게: {stats.new_stores:,}개</li>
                    <li>성공률: {stats.success_rate:.1f}%</li>
                    <li>품질 점수: {quality_stats.quality_score:.1f}/100</li>
                </ul>
                """
                
                attachments = [report_path]
                if chart_path:
                    attachments.append(chart_path)
                
                self.email_notifier.send_email(
                    self.config.email_recipients, subject, body, attachments
                )
            
            logger.info(f"주간 보고서 생성 완료: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"주간 보고서 생성 실패: {e}")
            return ""
    
    async def health_check_alert(self):
        """시스템 상태 확인 알림"""
        try:
            # 시스템 상태 확인
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 최근 24시간 내 크롤링 활동 확인
                yesterday = datetime.now() - timedelta(days=1)
                cursor.execute("""
                    SELECT COUNT(*) FROM stores 
                    WHERE updated_at >= ?
                """, (yesterday,))
                
                recent_activity = cursor.fetchone()[0]
                
                if recent_activity == 0:
                    await self.send_error_alert(
                        "시스템 비활성화",
                        "최근 24시간 동안 크롤링 활동이 감지되지 않았습니다.",
                        "high"
                    )
                else:
                    logger.info(f"시스템 정상 동작 중 (최근 활동: {recent_activity}건)")
                    
        except Exception as e:
            logger.error(f"상태 확인 실패: {e}")
            await self.send_error_alert("상태 확인 실패", str(e), "medium")

def run_notification_system():
    """알림 시스템 실행 함수"""
    config = NotificationConfig()
    notification_system = NotificationSystem(config, "refill_spot_crawler.db")
    
    # 일일 보고서 발송
    notification_system.send_daily_report()

if __name__ == "__main__":
    run_notification_system() 