#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
개선된 영업시간 파싱 로직
- 모든 요일의 영업시간 추출
- 라스트오더 정보 추출
- 브레이크타임 정보 추출
- 휴무일 정보 추출
"""

import re
import logging
from typing import Dict, List, Any

def parse_hours_info_improved(hours_text: str) -> Dict[str, Any]:
    """
    개선된 영업시간 정보 파싱
    
    Args:
        hours_text: 영업시간 관련 텍스트
        
    Returns:
        Dict: 파싱된 영업시간 정보
    """
    hours_info = {
        'open_hours': '',
        'holiday': '',
        'break_time': '',
        'last_order': ''
    }
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"파싱할 텍스트 길이: {len(hours_text)} 문자")
        
        # 1단계: 라스트오더 정보 추출
        last_order_patterns = [
            r'라스트\s*오더\s*[:：]?\s*(\d{1,2}:\d{2})',
            r'라스트오더\s*[:：]?\s*(\d{1,2}:\d{2})',
            r'L\.?O\.?\s*[:：]?\s*(\d{1,2}:\d{2})',
            r'주문\s*마감\s*[:：]?\s*(\d{1,2}:\d{2})',
            r'마지막\s*주문\s*[:：]?\s*(\d{1,2}:\d{2})'
        ]
        
        for pattern in last_order_patterns:
            matches = re.findall(pattern, hours_text, re.IGNORECASE)
            if matches:
                hours_info['last_order'] = matches[0]
                logger.info(f"라스트오더 추출: {hours_info['last_order']}")
                break
        
        # 2단계: 브레이크타임 정보 추출
        break_patterns = [
            r'브레이크\s*타임?\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            r'브레이크\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            r'휴게시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            r'쉬는시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            r'중간휴식\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})'
        ]
        
        for pattern in break_patterns:
            matches = re.findall(pattern, hours_text, re.IGNORECASE)
            if matches:
                start_time, end_time = matches[0]
                hours_info['break_time'] = f"{start_time}-{end_time}"
                logger.info(f"브레이크타임 추출: {hours_info['break_time']}")
                break
        
        # 3단계: 요일별 영업시간 추출 (개선된 방법)
        day_hours = {}
        holiday_days = []
        
        # 한국어 요일 매핑
        day_mapping = {
            '월': '월', '화': '화', '수': '수', '목': '목', '금': '금', '토': '토', '일': '일',
            '월요일': '월', '화요일': '화', '수요일': '수', '목요일': '목', 
            '금요일': '금', '토요일': '토', '일요일': '일'
        }
        
        # 영업시간 패턴들 (우선순위 순)
        hour_patterns = [
            # 패턴 1: "영업시간: 11:00 - 23:00" 형태
            r'영업시간\s*[:：]?\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            
            # 패턴 2: "11:00 - 23:00" 단순 형태
            r'(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})',
            
            # 패턴 3: "오전 11시 - 오후 11시" 형태
            r'오전\s*(\d{1,2})시?\s*[-~]\s*오후\s*(\d{1,2})시?',
            
            # 패턴 4: "11시 - 23시" 형태
            r'(\d{1,2})시\s*[-~]\s*(\d{1,2})시'
        ]
        
        # 휴무 패턴들
        holiday_patterns = [
            r'([월화수목금토일])요일\s*휴무',
            r'([월화수목금토일])\s*[:：]?\s*휴무',
            r'매주\s*([월화수목금토일])요일\s*휴무',
            r'휴무일?\s*[:：]?\s*([월화수목금토일])요일?'
        ]
        
        # 텍스트를 줄 단위로 분할하여 처리
        lines = hours_text.split('\n')
        
        current_day = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            logger.debug(f"처리 중인 라인: {line[:100]}")
            
            # 요일 감지
            for day_text, day_short in day_mapping.items():
                if day_text in line:
                    current_day = day_short
                    break
            
            # 휴무일 확인
            for pattern in holiday_patterns:
                matches = re.findall(pattern, line)
                if matches:
                    for match in matches:
                        day = day_mapping.get(match, match)
                        if day and day not in holiday_days:
                            holiday_days.append(day)
                            logger.info(f"휴무일 발견: {day}요일")
            
            # 영업시간 추출
            for pattern in hour_patterns:
                matches = re.findall(pattern, line)
                if matches and current_day:
                    start_time, end_time = matches[0]
                    
                    # 시간 형식 정규화
                    if ':' not in start_time:  # "11시" 형태
                        start_time = f"{start_time.zfill(2)}:00"
                    if ':' not in end_time:    # "23시" 형태
                        end_time = f"{end_time.zfill(2)}:00"
                    
                    # 오전/오후 처리
                    if '오전' in line and '오후' in line:
                        # start_time은 오전이므로 그대로
                        # end_time은 오후이므로 12시간 추가 (단, 12시는 제외)
                        end_hour = int(end_time.split(':')[0])
                        if end_hour != 12:
                            end_hour += 12
                        end_time = f"{end_hour:02d}:{end_time.split(':')[1]}"
                    
                    hours_str = f"{start_time}-{end_time}"
                    day_hours[current_day] = hours_str
                    logger.info(f"영업시간 발견: {current_day}요일 {hours_str}")
                    break
        
        # 4단계: 패턴 분석으로 누락된 요일 보완
        all_days = ['월', '화', '수', '목', '금', '토', '일']
        collected_days = set(day_hours.keys())
        missing_days = [d for d in all_days if d not in collected_days and d not in holiday_days]
        
        logger.info(f"수집된 요일: {list(collected_days)}")
        logger.info(f"휴무일: {holiday_days}")
        logger.info(f"누락된 요일: {missing_days}")
        
        # 패턴 분석하여 누락된 요일 보완
        if len(day_hours) >= 1 and missing_days:
            # 주중/주말 패턴 분석
            weekday_hours = []
            weekend_hours = []
            
            for day in ['월', '화', '수', '목', '금']:
                if day in day_hours:
                    weekday_hours.append(day_hours[day])
            
            for day in ['토', '일']:
                if day in day_hours:
                    weekend_hours.append(day_hours[day])
            
            # 주중 패턴 적용 (2개 이상 동일한 시간이면 패턴으로 인정)
            if weekday_hours and len(weekday_hours) >= 2:
                most_common_weekday = max(set(weekday_hours), key=weekday_hours.count)
                if weekday_hours.count(most_common_weekday) >= 2:
                    for day in ['월', '화', '수', '목', '금']:
                        if day in missing_days:
                            day_hours[day] = most_common_weekday
                            logger.info(f"{day}요일에 주중 패턴 적용: {most_common_weekday}")
            
            # 주말 패턴 적용
            if weekend_hours and len(weekend_hours) >= 1:
                most_common_weekend = max(set(weekend_hours), key=weekend_hours.count)
                for day in ['토', '일']:
                    if day in missing_days and day not in holiday_days:
                        day_hours[day] = most_common_weekend
                        logger.info(f"{day}요일에 주말 패턴 적용: {most_common_weekend}")
            
            # 전체 동일 패턴 적용 (모든 요일이 같은 시간인 경우)
            if len(day_hours) == 1:
                common_hours = list(day_hours.values())[0]
                for day in missing_days:
                    if day not in holiday_days:
                        day_hours[day] = common_hours
                        logger.info(f"{day}요일에 전체 패턴 적용: {common_hours}")
        
        # 5단계: 최종 영업시간 문자열 생성
        if day_hours:
            hours_parts = []
            days_order = ['월', '화', '수', '목', '금', '토', '일']
            
            for day in days_order:
                if day in day_hours:
                    hours_parts.append(f"{day}: {day_hours[day]}")
                elif day in holiday_days:
                    hours_parts.append(f"{day}: 휴무")
            
            # 기본 영업시간 설정
            hours_info['open_hours'] = ', '.join(hours_parts)
            
            # 라스트오더가 있으면 맨 마지막에 추가
            if hours_info['last_order']:
                hours_info['open_hours'] += f" / 라스트오더: {hours_info['last_order']}"
        
        # 6단계: 휴무일 설정
        if holiday_days:
            unique_holidays = list(set(holiday_days))
            if len(unique_holidays) == 1:
                hours_info['holiday'] = f"매주 {unique_holidays[0]}요일 휴무"
            else:
                hours_info['holiday'] = f"매주 {', '.join(unique_holidays)}요일 휴무"
        
        logger.info(f"최종 영업시간: {hours_info['open_hours']}")
        logger.info(f"휴무일: {hours_info['holiday']}")
        logger.info(f"브레이크타임: {hours_info['break_time']}")
        logger.info(f"라스트오더: {hours_info['last_order']}")
        
    except Exception as e:
        logger.error(f"영업시간 정보 파싱 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return hours_info

def test_hours_parsing():
    """영업시간 파싱 테스트"""
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "기본 영업시간",
            "text": """
            영업 중
            오늘(목)
            영업시간: 11:30 - 23:30
            
            7월 4일(금) 영업시간: 11:30 - 23:30
            7월 5일(토) 영업시간: 11:30 - 23:30
            7월 6일(일) 영업시간: 11:30 - 23:30
            7월 7일(월) 영업시간: 11:30 - 23:30
            7월 8일(화) 영업시간: 11:30 - 23:30
            7월 9일(수) 영업시간: 11:30 - 23:30
            """
        },
        {
            "name": "라스트오더 포함",
            "text": """
            브레이크 타임
            오늘(목)
            영업시간: 11:00 - 23:00
            라스트오더: 22:00
            
            7월 4일(금) 영업시간: 11:00 - 23:00 라스트오더: 22:00
            7월 5일(토) 영업시간: 16:00 - 22:00 라스트오더: 21:00
            7월 6일(일) 휴무일
            7월 7일(월) 영업시간: 11:00 - 23:00 라스트오더: 22:00
            """
        },
        {
            "name": "24시간 영업",
            "text": """
            영업 중
            오늘(목)
            영업시간: 00:00 - 24:00
            
            7월 4일(금) 영업시간: 00:00 - 24:00
            7월 5일(토) 영업시간: 00:00 - 24:00
            7월 6일(일) 영업시간: 00:00 - 24:00
            """
        }
    ]
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n=== 테스트 케이스 {i}: {test_case['name']} ===")
        result = parse_hours_info_improved(test_case['text'])
        
        print(f"영업시간: {result['open_hours']}")
        print(f"휴무일: {result['holiday']}")
        print(f"라스트오더: {result['last_order']}")
        print(f"브레이크타임: {result['break_time']}")

if __name__ == "__main__":
    test_hours_parsing() 