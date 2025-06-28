"""
영업시간 파싱 로직 테스트
실제 다이닝코드에서 가져온 텍스트로 파싱 테스트
"""
import re
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_hours_text(hours_text):
    """영업시간 텍스트 파싱"""
    hours_info = {
        'open_hours': '',
        'holiday': '',
        'break_time': '',
        'last_order': ''
    }
    
    # 날짜별 영업시간을 요일별로 변환
    day_hours = {}
    holiday_days = []
    
    logger.info(f"파싱할 텍스트: {hours_text[:300]}...")
    
    # 라스트오더 정보 추출
    last_order_patterns = [
        r'라스트\s*오더\s*[:：]?\s*(\d{1,2}:\d{2})',
        r'라스트오더\s*[:：]?\s*(\d{1,2}:\d{2})',
        r'L\.?O\.?\s*[:：]?\s*(\d{1,2}:\d{2})',
        r'주문\s*마감\s*[:：]?\s*(\d{1,2}:\d{2})'
    ]
    
    for pattern in last_order_patterns:
        matches = re.findall(pattern, hours_text)
        if matches:
            hours_info['last_order'] = matches[0]
            logger.info(f"라스트오더 추출: {hours_info['last_order']}")
            break
    
    # 브레이크타임 정보 추출
    break_patterns = [
        r'브레이크\s*타임?\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
        r'브레이크\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
        r'휴게시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
        r'브레이크타임\s*없음'
    ]
    
    for pattern in break_patterns:
        matches = re.findall(pattern, hours_text)
        if matches:
            if pattern.endswith('없음'):
                hours_info['break_time'] = '없음'
            else:
                start_time, end_time = matches[0]
                hours_info['break_time'] = f"{start_time}-{end_time}"
            logger.info(f"브레이크타임 추출: {hours_info['break_time']}")
            break
    
    # 날짜별 영업시간 패턴 매칭 (개선된 버전)
    date_patterns = [
        # 휴무일 패턴
        r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*휴무일?',
        # 영업시간 패턴 (라스트오더 포함)
        r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*영업시간:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})(?:\s*라스트오더:\s*(\d{1,2}:\d{2}))?',
        # 간단한 영업시간 패턴
        r'(\d{1,2}월\s*\d{1,2}일)\s*\(([월화수목금토일])\)\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, hours_text)
        logger.info(f"패턴 '{pattern}' 매칭 결과: {matches}")
        
        for match in matches:
            if len(match) == 2:  # 휴무일
                date, day = match
                holiday_days.append(day)
                logger.info(f"휴무일 발견: {day}요일 ({date})")
            elif len(match) >= 4:  # 영업시간
                if len(match) == 5:  # 라스트오더 포함
                    date, day, start_time, end_time, last_order = match
                    if last_order:
                        day_hours[day] = f"{start_time}-{end_time} (L.O: {last_order})"
                    else:
                        day_hours[day] = f"{start_time}-{end_time}"
                else:  # 기본 영업시간
                    date, day, start_time, end_time = match[:4]
                    day_hours[day] = f"{start_time}-{end_time}"
                logger.info(f"영업시간 발견: {day}요일 {day_hours[day]} ({date})")
    
    # 특별 패턴: "화~일 11:30~21:00" 형태
    range_pattern = r'([월화수목금토일])~([월화수목금토일])\s*(\d{1,2}:\d{2})~(\d{1,2}:\d{2})'
    range_matches = re.findall(range_pattern, hours_text)
    
    if range_matches:
        start_day, end_day, start_time, end_time = range_matches[0]
        logger.info(f"범위 패턴 발견: {start_day}~{end_day} {start_time}~{end_time}")
        
        # 요일 순서
        days_order = ['월', '화', '수', '목', '금', '토', '일']
        start_idx = days_order.index(start_day)
        end_idx = days_order.index(end_day)
        
        # 범위에 포함되는 모든 요일에 영업시간 적용
        if end_idx >= start_idx:
            for i in range(start_idx, end_idx + 1):
                day = days_order[i]
                day_hours[day] = f"{start_time}-{end_time}"
                if hours_info['last_order']:
                    day_hours[day] += f" (L.O: {hours_info['last_order']})"
                logger.info(f"범위 패턴으로 {day}요일 영업시간 설정: {day_hours[day]}")
    
    # 월요일 정기휴무 패턴
    if '매주 월요일 정기휴무' in hours_text or '월요일 휴무' in hours_text:
        holiday_days.append('월')
        logger.info("월요일 정기휴무 발견")
    
    # 최종 영업시간 문자열 생성
    if day_hours:
        hours_parts = []
        days_order = ['월', '화', '수', '목', '금', '토', '일']
        
        for day in days_order:
            if day in day_hours:
                hours_parts.append(f"{day}: {day_hours[day]}")
            elif day in holiday_days:
                hours_parts.append(f"{day}: 휴무")
        
        hours_info['open_hours'] = ', '.join(hours_parts)
    
    # 휴무일 설정
    if holiday_days:
        unique_holidays = list(set(holiday_days))
        if len(unique_holidays) == 1:
            hours_info['holiday'] = f"매주 {unique_holidays[0]}요일 휴무"
        else:
            hours_info['holiday'] = ', '.join(unique_holidays) + '요일 휴무'
    elif len(day_hours) == 7:
        hours_info['holiday'] = '연중무휴'
    
    return hours_info

def test_hours_parsing():
    """영업시간 파싱 테스트"""
    
    # 실제 다이닝코드에서 가져온 텍스트들
    test_cases = [
        {
            'name': '우래옥 - 토글 전 기본 정보',
            'text': '라스트 오더 8분 전 오늘(토) · 영업시간: 11:30 - 21:00'
        },
        {
            'name': '우래옥 - 토글 후 확장 정보 (실제)',
            'text': '6월 29일(일) 휴무일 6월 30일(월) 영업시간: 11:30 - 21:00 라스트오더: 20:20 7월 1일(화) 영업시간: 11:30 - 21:00 라스트오더: 20:20 7월 2일(수) 영업시간: 11:30 - 21:00 라스트오더: 20:20 7월 3일(목) 영업시간: 11:30 - 21:00 라스트오더: 20:20 7월 4일(금) 영업시간: 11:30 - 21:00 라스트오더: 20:20'
        },
        {
            'name': '우래옥 - 블로그 리뷰에서 추출한 정보',
            'text': '우래옥 ✔️ 화~일 11:30~21:00 ✔ 브레이크타임 없음 ✔️ 라스트오더 20:20 ✔️ 매주 월요일 정기휴무'
        },
        {
            'name': '일반적인 가게 패턴',
            'text': '6월 28일(금) 영업시간: 10:00 - 22:00 브레이크타임: 15:00 - 17:00 라스트오더: 21:30'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"테스트 {i}: {test_case['name']}")
        print(f"{'='*80}")
        
        result = parse_hours_text(test_case['text'])
        
        print(f"원본 텍스트: {test_case['text']}")
        print(f"\n[파싱 결과]")
        print(f"영업시간: {result['open_hours'] or 'N/A'}")
        print(f"휴무일: {result['holiday'] or 'N/A'}")
        print(f"브레이크타임: {result['break_time'] or 'N/A'}")
        print(f"라스트오더: {result['last_order'] or 'N/A'}")
        
        # 완성도 분석
        days_count = result['open_hours'].count(':') if result['open_hours'] else 0
        completeness = f"{days_count}/7 요일"
        
        extra_info = []
        if result['break_time']:
            extra_info.append("브레이크타임")
        if result['last_order']:
            extra_info.append("라스트오더")
        
        extra_str = f" + {', '.join(extra_info)}" if extra_info else ""
        print(f"완성도: {completeness}{extra_str}")

if __name__ == "__main__":
    test_hours_parsing() 