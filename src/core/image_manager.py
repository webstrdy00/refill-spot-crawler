#!/usr/bin/env python3
"""
이미지 다운로드 및 관리 모듈
"""
import os
import hashlib
import requests
import time
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
from PIL import Image
import logging
import base64
import io

logger = logging.getLogger(__name__)

class ImageManager:
    """이미지 다운로드 및 관리 클래스"""
    
    def __init__(self, storage_path: str = "data/images", max_size_mb: int = 5):
        """
        Args:
            storage_path: 이미지 저장 경로
            max_size_mb: 최대 이미지 크기 (MB)
        """
        self.storage_path = storage_path
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.session = requests.Session()
        
        # User-Agent 설정 (차단 방지)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 저장 디렉토리 생성
        os.makedirs(storage_path, exist_ok=True)
    
    def download_store_images(self, store_info: Dict) -> Dict:
        """가게 대표 이미지만 다운로드"""
        result = {
            'main_image': '',
            'download_stats': {
                'total_attempted': 0,
                'successful': 0,
                'failed': 0
            }
        }
        
        try:
            store_name = store_info.get('name', 'unknown')
            
            # 대표 이미지 다운로드
            main_image_url = store_info.get('main_image', '')
            if main_image_url:
                logger.info(f"🖼️ 대표 이미지 다운로드 시작: {store_name}")
                
                # 가게 이름으로 파일명 생성
                downloaded_path = self._download_single_image(
                    main_image_url, store_name, store_name
                )
                if downloaded_path:
                    result['main_image'] = downloaded_path
                    result['download_stats']['successful'] += 1
                    logger.info(f"✅ 대표 이미지 다운로드 성공: {os.path.basename(downloaded_path)}")
                else:
                    result['download_stats']['failed'] += 1
                    logger.warning(f"❌ 대표 이미지 다운로드 실패")
                result['download_stats']['total_attempted'] += 1
            else:
                logger.warning(f"⚠️ 대표 이미지 URL이 없음: {store_name}")
            
            # 다운로드 결과
            if result['download_stats']['successful'] > 0:
                logger.info(f"🎉 대표 이미지 다운로드 완료: {store_name}")
            else:
                logger.warning(f"⚠️ 대표 이미지 다운로드 실패: {store_name}")
            
        except Exception as e:
            logger.error(f"❌ 이미지 다운로드 중 오류 발생: {e}")
        
        return result
    
    def _download_single_image(self, url: str, store_name: str, filename_base: str) -> Optional[str]:
        """단일 이미지 다운로드"""
        try:
            if not url or not url.startswith(('http://', 'https://')):
                return None
            
            # 가게 이름으로 안전한 파일명 생성
            safe_filename = self._sanitize_filename(store_name)
            
            # 이미 다운로드된 파일이 있는지 확인
            existing_file = os.path.join(self.storage_path, f"{safe_filename}.jpg")
            if os.path.exists(existing_file):
                logger.debug(f"이미 존재하는 이미지 사용: {existing_file}")
                return existing_file
            
            # 이미지 다운로드
            response = self.session.get(url, timeout=10, stream=True)
            response.raise_for_status()
            
            # 파일 크기 체크
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_size_bytes:
                logger.warning(f"이미지 크기가 너무 큼: {url} ({content_length} bytes)")
                return None
            
            # 파일 저장 (.jpg로 통일)
            file_path = os.path.join(self.storage_path, f"{safe_filename}.jpg")
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 이미지 검증 및 최적화
            optimized_path = self._optimize_image(file_path)
            if optimized_path:
                file_path = optimized_path
            
            logger.debug(f"이미지 다운로드 성공: {store_name} - {os.path.basename(file_path)}")
            return file_path
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"이미지 다운로드 실패 (네트워크): {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"이미지 다운로드 실패: {url} - {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """파일명에서 특수문자 제거"""
        import re
        # 특수문자 제거하고 공백을 언더스코어로 변경
        safe_name = re.sub(r'[^\w\s-]', '', filename.strip())
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        # 길이 제한 (최대 100자)
        return safe_name[:100] if safe_name else 'unknown'
    
    def _optimize_image(self, file_path: str) -> Optional[str]:
        """이미지 최적화 (크기 조정, 압축)"""
        try:
            with Image.open(file_path) as img:
                # 이미지 포맷 확인
                if img.format not in ['JPEG', 'PNG', 'WEBP']:
                    logger.warning(f"지원하지 않는 이미지 포맷: {img.format}")
                    return None
                
                # 이미지 크기 조정 (최대 1200x1200)
                max_size = (1200, 1200)
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    logger.debug(f"이미지 크기 조정: {file_path}")
                
                # JPEG로 변환 및 압축
                if img.format != 'JPEG':
                    # PNG나 WEBP를 JPEG로 변환
                    rgb_img = img.convert('RGB')
                    jpeg_path = file_path.rsplit('.', 1)[0] + '.jpg'
                    rgb_img.save(jpeg_path, 'JPEG', quality=85, optimize=True)
                    
                    # 원본 파일 삭제
                    if os.path.exists(file_path) and file_path != jpeg_path:
                        os.remove(file_path)
                    
                    return jpeg_path
                else:
                    # 이미 JPEG인 경우 품질 조정
                    img.save(file_path, 'JPEG', quality=85, optimize=True)
                    return file_path
                    
        except Exception as e:
            logger.error(f"이미지 최적화 실패: {file_path} - {e}")
            return file_path  # 원본 반환
    

    
    def get_image_info(self, image_path: str) -> Dict:
        """이미지 정보 조회"""
        try:
            if not os.path.exists(image_path):
                return {}
            
            with Image.open(image_path) as img:
                return {
                    'path': image_path,
                    'size': img.size,
                    'format': img.format,
                    'mode': img.mode,
                    'file_size': os.path.getsize(image_path)
                }
                
        except Exception as e:
            logger.error(f"이미지 정보 조회 실패: {image_path} - {e}")
            return {}
    
    def cleanup_old_images(self, days: int = 30):
        """오래된 이미지 파일 정리"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days * 24 * 60 * 60)
            
            removed_count = 0
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        removed_count += 1
            
            logger.info(f"오래된 이미지 {removed_count}개 정리 완료")
            
        except Exception as e:
            logger.error(f"이미지 정리 실패: {e}")
    
    def get_storage_stats(self) -> Dict:
        """저장소 통계 정보"""
        try:
            total_files = 0
            total_size = 0
            
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_files += 1
                    total_size += os.path.getsize(file_path)
            
            return {
                'total_files': total_files,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'storage_path': self.storage_path
            }
            
        except Exception as e:
            logger.error(f"저장소 통계 조회 실패: {e}")
            return {} 