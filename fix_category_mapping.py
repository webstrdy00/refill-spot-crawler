#!/usr/bin/env python3
"""
카테고리 매핑 수정 스크립트
raw_categories_diningcode를 7개 표준 카테고리로 매핑하고 store_categories 테이블에 연결
"""

import sys
import os
import logging
import psycopg2
import psycopg2.extras
from typing import Dict, List, Set
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

import config
from data_enhancement import CategoryMapper

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('category_mapping_fix.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class CategoryMappingFixer:
    """카테고리 매핑 수정 클래스"""
    
    def __init__(self, database_name: str = "refill_spot"):
        self.database_name = database_name
        self.connection = None
        self.category_mapper = CategoryMapper()
        self.connect_to_database()
        
    def connect_to_database(self):
        """데이터베이스 연결"""
        try:
            self.connection = psycopg2.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=self.database_name,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            self.connection.autocommit = True
            logger.info(f"'{self.database_name}' 데이터베이스 연결 성공")
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise
    
    def get_current_status(self) -> Dict:
        """현재 상태 확인"""
        cursor = self.connection.cursor()
        
        try:
            # 가게 수 확인
            cursor.execute("SELECT COUNT(*) FROM stores")
            stores_count = cursor.fetchone()[0]
            
            # 카테고리 수 확인
            cursor.execute("SELECT COUNT(*) FROM categories")
            categories_count = cursor.fetchone()[0]
            
            # store_categories 연결 수 확인
            cursor.execute("SELECT COUNT(*) FROM store_categories")
            store_categories_count = cursor.fetchone()[0]
            
            # raw_categories가 있는 가게 수 확인
            cursor.execute("""
                SELECT COUNT(*) FROM stores 
                WHERE raw_categories_diningcode IS NOT NULL 
                AND array_length(raw_categories_diningcode, 1) > 0
            """)
            stores_with_categories = cursor.fetchone()[0]
            
            # 고유한 raw category 확인
            cursor.execute("""
                SELECT DISTINCT unnest(raw_categories_diningcode) as category 
                FROM stores 
                WHERE raw_categories_diningcode IS NOT NULL
                ORDER BY category
            """)
            unique_raw_categories = [row[0] for row in cursor.fetchall()]
            
            return {
                'stores_count': stores_count,
                'categories_count': categories_count,
                'store_categories_count': store_categories_count,
                'stores_with_categories': stores_with_categories,
                'unique_raw_categories_count': len(unique_raw_categories),
                'unique_raw_categories': unique_raw_categories[:20]  # 처음 20개만
            }
            
        except Exception as e:
            logger.error(f"상태 확인 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def get_category_mappings(self) -> Dict[str, int]:
        """7개 표준 카테고리 ID 매핑 가져오기"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("SELECT id, name FROM categories ORDER BY id")
            categories = cursor.fetchall()
            
            category_map = {name: id for id, name in categories}
            logger.info(f"표준 카테고리: {category_map}")
            
            return category_map
            
        except Exception as e:
            logger.error(f"카테고리 매핑 조회 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def analyze_raw_categories(self) -> Dict:
        """raw_categories 분석"""
        cursor = self.connection.cursor()
        
        try:
            # raw category별 가게 수
            cursor.execute("""
                SELECT unnest(raw_categories_diningcode) as category, COUNT(*) as count
                FROM stores 
                WHERE raw_categories_diningcode IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
            raw_category_stats = cursor.fetchall()
            
            logger.info(f"가장 많이 사용된 raw categories (상위 10개):")
            for category, count in raw_category_stats[:10]:
                logger.info(f"  {category}: {count}개 가게")
            
            return {
                'raw_category_stats': raw_category_stats,
                'total_raw_categories': len(raw_category_stats)
            }
            
        except Exception as e:
            logger.error(f"raw 카테고리 분석 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def test_category_mapping(self) -> Dict:
        """카테고리 매핑 테스트"""
        cursor = self.connection.cursor()
        
        try:
            # 샘플 가게 데이터 가져오기
            cursor.execute("""
                SELECT id, name, raw_categories_diningcode 
                FROM stores 
                WHERE raw_categories_diningcode IS NOT NULL 
                AND array_length(raw_categories_diningcode, 1) > 0
                LIMIT 10
            """)
            sample_stores = cursor.fetchall()
            
            mapping_results = []
            
            for store_id, store_name, raw_categories in sample_stores:
                # CategoryMapper를 사용해서 매핑
                mapped_categories = self.category_mapper.map_categories(
                    raw_categories, 
                    {'name': store_name}
                )
                
                mapping_results.append({
                    'store_id': store_id,
                    'store_name': store_name,
                    'raw_categories': raw_categories,
                    'mapped_categories': mapped_categories
                })
                
                logger.info(f"테스트 매핑: {store_name}")
                logger.info(f"  원본: {raw_categories}")
                logger.info(f"  매핑: {mapped_categories}")
            
            return {'mapping_results': mapping_results}
            
        except Exception as e:
            logger.error(f"카테고리 매핑 테스트 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def execute_category_mapping(self, dry_run: bool = False) -> Dict:
        """전체 가게에 대해 카테고리 매핑 실행"""
        cursor = self.connection.cursor()
        
        try:
            # 7개 표준 카테고리 ID 매핑 가져오기
            category_map = self.get_category_mappings()
            if not category_map:
                raise Exception("표준 카테고리를 찾을 수 없습니다")
            
            # 기존 store_categories 데이터 삭제 (dry_run이 아닌 경우)
            if not dry_run:
                cursor.execute("DELETE FROM store_categories")
                logger.info("기존 store_categories 데이터 삭제 완료")
            
            # 모든 가게 데이터 가져오기
            cursor.execute("""
                SELECT id, name, raw_categories_diningcode, menu_items
                FROM stores 
                WHERE raw_categories_diningcode IS NOT NULL 
                AND array_length(raw_categories_diningcode, 1) > 0
            """)
            all_stores = cursor.fetchall()
            
            logger.info(f"카테고리 매핑 대상 가게: {len(all_stores)}개")
            
            # 매핑 통계
            mapping_stats = {
                'total_stores': len(all_stores),
                'successful_mappings': 0,
                'failed_mappings': 0,
                'category_distribution': {cat: 0 for cat in category_map.keys()}
            }
            
            # 배치 삽입을 위한 데이터 수집
            store_category_pairs = []
            
            for i, (store_id, store_name, raw_categories, menu_items) in enumerate(all_stores, 1):
                try:
                    # menu_items가 JSON 문자열인 경우 파싱
                    menu_items_parsed = []
                    if menu_items:
                        try:
                            if isinstance(menu_items, str):
                                menu_items_parsed = json.loads(menu_items)
                            elif isinstance(menu_items, list):
                                menu_items_parsed = menu_items
                        except:
                            menu_items_parsed = []
                    
                    # CategoryMapper를 사용해서 매핑
                    store_info = {
                        'name': store_name,
                        'menu_items': menu_items_parsed
                    }
                    
                    mapped_categories = self.category_mapper.map_categories(
                        raw_categories, 
                        store_info
                    )
                    
                    if mapped_categories:
                        # 매핑된 카테고리를 store_categories에 추가할 데이터로 변환
                        for category_name in mapped_categories:
                            if category_name in category_map:
                                category_id = category_map[category_name]
                                store_category_pairs.append((store_id, category_id))
                                mapping_stats['category_distribution'][category_name] += 1
                        
                        mapping_stats['successful_mappings'] += 1
                    else:
                        mapping_stats['failed_mappings'] += 1
                        logger.warning(f"매핑 실패: {store_name} - {raw_categories}")
                    
                    # 진행 상황 로그
                    if i % 50 == 0:
                        logger.info(f"진행 상황: {i}/{len(all_stores)} ({i/len(all_stores)*100:.1f}%)")
                
                except Exception as e:
                    mapping_stats['failed_mappings'] += 1
                    logger.error(f"가게 매핑 실패: {store_name} - {e}")
                    continue
            
            # store_categories 테이블에 배치 삽입
            if store_category_pairs and not dry_run:
                logger.info(f"store_categories 테이블에 {len(store_category_pairs)}개 관계 삽입 중...")
                
                psycopg2.extras.execute_values(
                    cursor,
                    "INSERT INTO store_categories (store_id, category_id) VALUES %s ON CONFLICT DO NOTHING",
                    store_category_pairs,
                    template=None,
                    page_size=1000
                )
                
                logger.info("store_categories 테이블 삽입 완료")
            
            # 결과 통계
            logger.info("=== 카테고리 매핑 완료 ===")
            logger.info(f"총 가게 수: {mapping_stats['total_stores']}")
            logger.info(f"성공적 매핑: {mapping_stats['successful_mappings']}")
            logger.info(f"실패한 매핑: {mapping_stats['failed_mappings']}")
            logger.info(f"생성된 store-category 관계: {len(store_category_pairs)}")
            
            logger.info("카테고리별 분포:")
            for category, count in mapping_stats['category_distribution'].items():
                logger.info(f"  {category}: {count}개 가게")
            
            mapping_stats['store_category_pairs_count'] = len(store_category_pairs)
            mapping_stats['dry_run'] = dry_run
            
            return mapping_stats
            
        except Exception as e:
            logger.error(f"카테고리 매핑 실행 실패: {e}")
            raise
        finally:
            cursor.close()
    
    def verify_results(self) -> Dict:
        """결과 검증"""
        cursor = self.connection.cursor()
        
        try:
            # 전체 통계
            cursor.execute("SELECT COUNT(*) FROM store_categories")
            total_relationships = cursor.fetchone()[0]
            
            # 카테고리별 가게 수
            cursor.execute("""
                SELECT c.name, COUNT(sc.store_id) as store_count
                FROM categories c
                LEFT JOIN store_categories sc ON c.id = sc.category_id
                GROUP BY c.id, c.name
                ORDER BY store_count DESC
            """)
            category_stats = cursor.fetchall()
            
            # 가게별 카테고리 수 분포
            cursor.execute("""
                SELECT category_count, COUNT(*) as store_count
                FROM (
                    SELECT store_id, COUNT(*) as category_count
                    FROM store_categories
                    GROUP BY store_id
                ) t
                GROUP BY category_count
                ORDER BY category_count
            """)
            categories_per_store = cursor.fetchall()
            
            # 샘플 결과 확인
            cursor.execute("""
                SELECT s.name, s.raw_categories_diningcode, 
                       array_agg(c.name ORDER BY c.name) as mapped_categories
                FROM stores s
                JOIN store_categories sc ON s.id = sc.store_id
                JOIN categories c ON sc.category_id = c.id
                WHERE s.raw_categories_diningcode IS NOT NULL
                GROUP BY s.id, s.name, s.raw_categories_diningcode
                LIMIT 10
            """)
            sample_results = cursor.fetchall()
            
            logger.info("=== 결과 검증 ===")
            logger.info(f"총 store-category 관계: {total_relationships}개")
            
            logger.info("카테고리별 가게 수:")
            for category_name, store_count in category_stats:
                logger.info(f"  {category_name}: {store_count}개 가게")
            
            logger.info("가게별 카테고리 수 분포:")
            for category_count, store_count in categories_per_store:
                logger.info(f"  {category_count}개 카테고리: {store_count}개 가게")
            
            logger.info("샘플 매핑 결과:")
            for store_name, raw_cats, mapped_cats in sample_results:
                logger.info(f"  {store_name}")
                logger.info(f"    원본: {raw_cats}")
                logger.info(f"    매핑: {mapped_cats}")
            
            return {
                'total_relationships': total_relationships,
                'category_stats': category_stats,
                'categories_per_store': categories_per_store,
                'sample_results': sample_results
            }
            
        except Exception as e:
            logger.error(f"결과 검증 실패: {e}")
            return {}
        finally:
            cursor.close()
    
    def close(self):
        """연결 종료"""
        if self.connection:
            self.connection.close()
            logger.info("데이터베이스 연결 종료")

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='카테고리 매핑 수정 스크립트')
    parser.add_argument('--dry-run', action='store_true', 
                       help='실제 데이터베이스 변경 없이 테스트만 실행')
    parser.add_argument('--database', default='refill_spot',
                       help='대상 데이터베이스 이름 (기본값: refill_spot)')
    
    args = parser.parse_args()
    
    logger.info("🏷️ 카테고리 매핑 수정 스크립트 시작")
    logger.info(f"대상 데이터베이스: {args.database}")
    logger.info(f"Dry run 모드: {args.dry_run}")
    
    fixer = None
    
    try:
        # CategoryMappingFixer 초기화
        fixer = CategoryMappingFixer(args.database)
        
        # 1. 현재 상태 확인
        logger.info("=== 1단계: 현재 상태 확인 ===")
        current_status = fixer.get_current_status()
        logger.info(f"가게 수: {current_status.get('stores_count', 0)}")
        logger.info(f"카테고리 수: {current_status.get('categories_count', 0)}")
        logger.info(f"store_categories 관계 수: {current_status.get('store_categories_count', 0)}")
        logger.info(f"카테고리 있는 가게 수: {current_status.get('stores_with_categories', 0)}")
        logger.info(f"고유 raw 카테고리 수: {current_status.get('unique_raw_categories_count', 0)}")
        
        # 2. Raw 카테고리 분석
        logger.info("=== 2단계: Raw 카테고리 분석 ===")
        fixer.analyze_raw_categories()
        
        # 3. 카테고리 매핑 테스트
        logger.info("=== 3단계: 카테고리 매핑 테스트 ===")
        fixer.test_category_mapping()
        
        # 4. 카테고리 매핑 실행
        logger.info("=== 4단계: 카테고리 매핑 실행 ===")
        mapping_results = fixer.execute_category_mapping(dry_run=args.dry_run)
        
        if args.dry_run:
            logger.info("⚠️ Dry run 모드로 실행되었습니다. 실제 데이터베이스는 변경되지 않았습니다.")
        else:
            # 5. 결과 검증
            logger.info("=== 5단계: 결과 검증 ===")
            fixer.verify_results()
            
            logger.info("✅ 카테고리 매핑 수정 완료!")
        
    except Exception as e:
        logger.error(f"❌ 카테고리 매핑 수정 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        if fixer:
            fixer.close()

if __name__ == "__main__":
    main()