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
import re
from datetime import datetime
from supabase import create_client

logger = logging.getLogger(__name__)

class ImageManager:
    """이미지 다운로드 및 관리 클래스"""
    
    def __init__(self, config: dict = None):
        """
        Args:
            config: 이미지 스토리지 설정 딕셔너리
        """
        # 기본 설정
        self.config = config or {
            "enabled": True,
            "bucket_name": "refill-spot-images",
            "cleanup_after_upload": False,
            "upload_timeout": 30,
            "max_file_size": 5242880,  # 5MB
            "allowed_formats": ['jpg', 'jpeg', 'png', 'webp'],
            "quality": 85,
            "max_dimension": 1200
        }
        
        self.storage_path = "data/images"
        self.max_size_bytes = self.config.get("max_file_size", 5242880)
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
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 통계
        self.stats = {
            'images_processed': 0,
            'images_uploaded': 0,
            'upload_failures': 0,
            'download_failures': 0
        }
    
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
        """파일명에서 특수문자 제거 및 한글을 영문으로 변환"""
        # 한글을 영문으로 변환하는 매핑
        korean_to_english = {
            '명륜진사갈비': 'myeongryun_galbi',
            '강남': 'gangnam',
            '홍대': 'hongdae',
            '마포': 'mapo',
            '송파': 'songpa',
            '강북': 'gangbuk',
            '무한리필': 'unlimited_refill',
            '고기집': 'meat_restaurant',
            '뷔페': 'buffet',
            '전문점': 'specialty_store',
            '점': 'store',
            '가게': 'restaurant',
            '식당': 'restaurant',
            '갈비': 'galbi',
            '삼겹살': 'samgyeopsal',
            '소고기': 'beef',
            '돼지고기': 'pork',
            '치킨': 'chicken',
            '피자': 'pizza',
            '족발': 'jokbal',
            '보쌈': 'bossam'
        }
        
        # 한글을 영문으로 변환
        for korean, english in korean_to_english.items():
            filename = filename.replace(korean, english)
        
        # 남은 한글 제거
        filename = re.sub(r'[가-힣]', '', filename)
        
        # 특수문자 제거하고 공백을 언더스코어로 변경
        safe_name = re.sub(r'[^\w\s-]', '', filename.strip())
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        
        # 연속된 언더스코어 정리
        safe_name = re.sub(r'_+', '_', safe_name)
        safe_name = safe_name.strip('_')
        
        return safe_name or 'store'
    
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
    
    def upload_to_supabase(self, local_path: str, store_name: str = None) -> Optional[str]:
        """
        로컬 이미지를 Supabase Storage에 업로드
        
        Args:
            local_path: 로컬 이미지 파일 경로
            store_name: 가게명 (파일명 생성용)
            
        Returns:
            업로드된 이미지의 공개 URL, 실패시 None
        """
        if not self.config.get("enabled", False):
            logger.info("이미지 스토리지가 비활성화되어 있습니다.")
            return None
            
        try:
            # Supabase 클라이언트 생성
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
            bucket_name = self.config.get("bucket_name", "refill-spot-images")
            
            if not all([supabase_url, supabase_service_key]):
                logger.error("Supabase 환경 변수가 설정되지 않았습니다.")
                return None
                
            supabase = create_client(supabase_url, supabase_service_key)
            
            # 파일 읽기
            if not os.path.exists(local_path):
                logger.error(f"로컬 파일이 존재하지 않습니다: {local_path}")
                return None
                
            with open(local_path, 'rb') as f:
                file_data = f.read()
            
            # 파일명 생성 (가게명 + 타임스탬프)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = os.path.splitext(local_path)[1].lower() or '.jpg'
            
            if store_name:
                # 가게명을 안전한 영문 파일명으로 변환
                safe_name = self._sanitize_filename(store_name)
                filename = f"{safe_name}_{timestamp}{file_ext}"
            else:
                filename = f"image_{timestamp}{file_ext}"
            
            # 업로드
            response = supabase.storage.from_(bucket_name).upload(
                path=filename,
                file=file_data,
                file_options={
                    "content-type": f"image/{file_ext[1:]}",
                    "cache-control": "3600"
                }
            )
            
            # 공개 URL 생성
            public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
            
            logger.info(f"이미지 업로드 성공: {filename}")
            logger.info(f"공개 URL: {public_url}")
            
            # 로컬 파일 정리 (설정에 따라)
            if self.config.get("cleanup_after_upload", False):
                try:
                    os.remove(local_path)
                    logger.info(f"로컬 파일 삭제: {local_path}")
                except Exception as e:
                    logger.warning(f"로컬 파일 삭제 실패: {e}")
            
            return public_url
            
        except Exception as e:
            logger.error(f"Supabase 업로드 실패: {e}")
            return None

    def download_and_process_image(self, image_url: str) -> Optional[str]:
        """이미지 다운로드 및 처리"""
        try:
            self.stats['images_processed'] += 1
            
            if not image_url or not image_url.startswith(('http://', 'https://')):
                self.stats['download_failures'] += 1
                return None
            
            # URL 해시로 파일명 생성 (중복 방지)
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"temp_{url_hash}_{timestamp}.jpg"
            temp_path = os.path.join(self.storage_path, temp_filename)
            
            # 이미지 다운로드
            response = self.session.get(image_url, timeout=10, stream=True)
            response.raise_for_status()
            
            # 파일 크기 체크
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_size_bytes:
                logger.warning(f"이미지 크기가 너무 큼: {image_url}")
                self.stats['download_failures'] += 1
                return None
            
            # 임시 파일 저장
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 이미지 최적화
            optimized_path = self._optimize_image(temp_path)
            if optimized_path and optimized_path != temp_path:
                # 최적화된 파일로 교체
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return optimized_path
            
            return temp_path
            
        except Exception as e:
            logger.error(f"이미지 다운로드 실패: {image_url} - {e}")
            self.stats['download_failures'] += 1
            return None

    def create_thumbnail(self, image_path: str, size: Tuple[int, int] = (300, 300)) -> Optional[str]:
        """썸네일 생성"""
        try:
            if not os.path.exists(image_path):
                return None
                
            with Image.open(image_path) as img:
                # 썸네일 생성
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # 썸네일 파일명
                base_name = os.path.splitext(image_path)[0]
                thumbnail_path = f"{base_name}_thumb.jpg"
                
                # RGB로 변환 후 저장
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    
                img.save(thumbnail_path, 'JPEG', quality=80, optimize=True)
                
                return thumbnail_path
                
        except Exception as e:
            logger.error(f"썸네일 생성 실패: {image_path} - {e}")
            return None

    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        return self.stats.copy()

    def process_and_upload_image(self, image_url: str, store_name: str = None) -> Dict[str, Optional[str]]:
        """
        이미지 URL에서 다운로드 → 처리 → Supabase 업로드까지 전체 프로세스
        
        Args:
            image_url: 원본 이미지 URL
            store_name: 가게명
            
        Returns:
            {
                'local_path': 로컬 파일 경로,
                'storage_url': Supabase Storage URL,
                'thumbnail_path': 썸네일 경로 (로컬),
                'error': 오류 메시지 (실패시)
            }
        """
        result = {
            'local_path': None,
            'storage_url': None,
            'thumbnail_path': None,
            'error': None
        }
        
        try:
            # 1. 이미지 다운로드 및 처리
            local_path = self.download_and_process_image(image_url)
            if not local_path:
                result['error'] = "이미지 다운로드 실패"
                return result
                
            result['local_path'] = local_path
            
            # 2. 썸네일 생성
            thumbnail_path = self.create_thumbnail(local_path)
            result['thumbnail_path'] = thumbnail_path
            
            # 3. Supabase Storage에 업로드
            storage_url = self.upload_to_supabase(local_path, store_name)
            if storage_url:
                result['storage_url'] = storage_url
                self.stats['images_uploaded'] += 1
            else:
                result['error'] = "Storage 업로드 실패"
                self.stats['upload_failures'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"이미지 전체 처리 실패: {e}")
            result['error'] = str(e)
            self.stats['upload_failures'] += 1
            return result 