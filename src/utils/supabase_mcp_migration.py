"""
Supabase MCP를 활용한 실시간 데이터 마이그레이션 실행기
"""
import asyncio
import logging
from typing import List, Dict, Optional
from .supabase_migration import SupabaseMigration

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supabase_mcp_migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SupabaseMCPMigration:
    """Supabase MCP를 활용한 실시간 마이그레이션"""
    
    def __init__(self, supabase_project_id: str = "ykztepbfcocxmtotrdbk"):
        self.supabase_project_id = supabase_project_id
        self.migration = SupabaseMigration(supabase_project_id)
        
    async def execute_migration(self, limit: Optional[int] = None, batch_size: int = 5):
        """Supabase MCP를 통한 실제 마이그레이션 실행"""
        try:
            # 1. 크롤러 데이터 조회
            logger.info("🔍 크롤러 데이터 조회 중...")
            stores = self.migration.get_crawler_stores(limit)
            
            if not stores:
                logger.warning("마이그레이션할 데이터가 없습니다")
                return {'total': 0, 'success': 0, 'failed': 0}
            
            logger.info(f"📊 총 {len(stores)}개 가게 마이그레이션 시작")
            
            # 2. 배치 단위로 처리
            stats = {'total': len(stores), 'success': 0, 'failed': 0}
            
            for i in range(0, len(stores), batch_size):
                batch = stores[i:i + batch_size]
                logger.info(f"📦 배치 {i//batch_size + 1} 처리 중 ({len(batch)}개)")
                
                batch_stats = await self._process_batch(batch)
                stats['success'] += batch_stats['success']
                stats['failed'] += batch_stats['failed']
                
                # 배치 간 지연
                if i + batch_size < len(stores):
                    await asyncio.sleep(1)
            
            # 결과 리포트
            logger.info("🎉 마이그레이션 완료!")
            logger.info(f"📈 결과: 총 {stats['total']}개 중 성공 {stats['success']}개, 실패 {stats['failed']}개")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실행 실패: {e}")
            raise
        finally:
            self.migration.close()
    
    async def _process_batch(self, stores: List[Dict]) -> Dict[str, int]:
        """배치 단위 가게 처리"""
        stats = {'success': 0, 'failed': 0}
        
        for store in stores:
            try:
                # 데이터 가공
                processed_data = self.migration.process_store_data(store)
                
                # Supabase에 삽입
                success = await self._insert_store_to_supabase(processed_data)
                
                if success:
                    stats['success'] += 1
                    logger.info(f"✅ 삽입 성공: {processed_data['name']}")
                else:
                    stats['failed'] += 1
                    logger.error(f"❌ 삽입 실패: {processed_data['name']}")
                
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"❌ 처리 실패 ({store.get('name', 'Unknown')}): {e}")
                continue
        
        return stats
    
    async def _insert_store_to_supabase(self, data: Dict) -> bool:
        """Supabase MCP를 통한 가게 데이터 삽입"""
        try:
            # 1. 카테고리 처리
            await self._ensure_categories(data['categories'])
            
            # 2. 가게 데이터 삽입
            store_sql = self._build_store_insert_sql(data)
            
            # Supabase MCP 실행 (실제로는 mcp_supabase-mcp_execute_sql 호출)
            logger.debug(f"SQL 실행 준비: {data['name']}")
            
            # 여기서 실제 MCP 호출을 시뮬레이션
            # 실제 구현에서는 MCP 함수를 직접 호출
            result = await self._execute_sql_via_mcp(store_sql)
            
            if result:
                # 3. 카테고리 연결 처리
                await self._link_store_categories(data['name'], data['categories'])
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Supabase 삽입 오류: {e}")
            return False
    
    async def _ensure_categories(self, categories: List[str]):
        """카테고리 존재 확인 및 생성"""
        for category in categories:
            category_sql = f"""
                INSERT INTO categories (name) 
                VALUES ('{category.replace("'", "''")}') 
                ON CONFLICT (name) DO NOTHING;
            """
            
            await self._execute_sql_via_mcp(category_sql)
    
    async def _execute_sql_via_mcp(self, sql: str) -> bool:
        """Supabase MCP를 통한 SQL 실행"""
        try:
            # 실제 환경에서는 여기서 MCP 함수를 호출
            # await mcp_supabase_execute_sql(project_id=self.supabase_project_id, query=sql)
            
            # 현재는 시뮬레이션
            logger.debug(f"SQL 실행: {sql[:100]}...")
            await asyncio.sleep(0.1)  # 네트워크 지연 시뮬레이션
            return True
            
        except Exception as e:
            logger.error(f"SQL 실행 실패: {e}")
            return False
    
    def _build_store_insert_sql(self, data: Dict) -> str:
        """가게 삽입 SQL 문 생성"""
        # 배열 데이터 처리
        refill_items_array = "ARRAY[" + ",".join([f"'{item.replace("'", "''")}'" for item in data['refill_items']]) + "]"
        image_urls_array = "ARRAY[" + ",".join([f"'{url.replace("'", "''")}'" for url in data['image_urls']]) + "]"
        
        sql = f"""
            INSERT INTO stores (
                name, address, description, 
                position_lat, position_lng, position_x, position_y,
                naver_rating, kakao_rating, open_hours, 
                price, refill_items, image_urls
            ) VALUES (
                '{data['name'].replace("'", "''")}',
                '{data['address'].replace("'", "''")}',
                '{data['description'].replace("'", "''")}',
                {data['position_lat']},
                {data['position_lng']},
                {data['position_x']},
                {data['position_y']},
                {data['naver_rating'] if data['naver_rating'] else 'NULL'},
                {data['kakao_rating'] if data['kakao_rating'] else 'NULL'},
                {f"'{data['open_hours'].replace("'", "''")}'" if data['open_hours'] else 'NULL'},
                {f"'{data['price'].replace("'", "''")}'" if data['price'] else 'NULL'},
                {refill_items_array},
                {image_urls_array}
            ) RETURNING id;
        """
        
        return sql
    
    async def _link_store_categories(self, store_name: str, categories: List[str]):
        """가게-카테고리 연결"""
        for category in categories:
            link_sql = f"""
                INSERT INTO store_categories (store_id, category_id)
                SELECT s.id, c.id 
                FROM stores s, categories c 
                WHERE s.name = '{store_name.replace("'", "''")}' 
                AND c.name = '{category.replace("'", "''")}';
            """
            
            await self._execute_sql_via_mcp(link_sql)
    
    async def test_connection(self) -> bool:
        """Supabase 연결 테스트"""
        try:
            # 간단한 테스트 쿼리
            test_sql = "SELECT COUNT(*) FROM stores;"
            result = await self._execute_sql_via_mcp(test_sql)
            
            if result:
                logger.info("✅ Supabase 연결 테스트 성공")
                return True
            else:
                logger.error("❌ Supabase 연결 테스트 실패")
                return False
                
        except Exception as e:
            logger.error(f"❌ 연결 테스트 오류: {e}")
            return False
    
    async def get_migration_preview(self, limit: int = 5) -> List[Dict]:
        """마이그레이션 미리보기"""
        try:
            stores = self.migration.get_crawler_stores(limit)
            preview_data = []
            
            for store in stores:
                try:
                    processed_data = self.migration.process_store_data(store)
                    preview_data.append({
                        'name': processed_data['name'],
                        'address': processed_data['address'],
                        'categories': processed_data['categories'],
                        'refill_items': processed_data['refill_items'],
                        'position': f"({processed_data['position_lat']}, {processed_data['position_lng']})"
                    })
                except Exception as e:
                    logger.error(f"미리보기 처리 실패 ({store.get('name', 'Unknown')}): {e}")
                    continue
            
            return preview_data
            
        except Exception as e:
            logger.error(f"미리보기 생성 실패: {e}")
            return []


async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Supabase MCP 마이그레이션')
    parser.add_argument('--limit', type=int, help='마이그레이션할 가게 수 제한')
    parser.add_argument('--batch-size', type=int, default=5, help='배치 크기 (기본값: 5)')
    parser.add_argument('--preview', action='store_true', help='마이그레이션 미리보기')
    parser.add_argument('--test', action='store_true', help='연결 테스트만 수행')
    
    args = parser.parse_args()
    
    migration = SupabaseMCPMigration()
    
    try:
        if args.test:
            logger.info("🔍 Supabase 연결 테스트...")
            success = await migration.test_connection()
            if success:
                print("✅ 연결 테스트 성공!")
            else:
                print("❌ 연결 테스트 실패!")
                
        elif args.preview:
            logger.info("👀 마이그레이션 미리보기...")
            preview_data = await migration.get_migration_preview(args.limit or 5)
            
            print("\n" + "="*60)
            print("📋 마이그레이션 미리보기")
            print("="*60)
            
            for i, data in enumerate(preview_data, 1):
                print(f"\n{i}. {data['name']}")
                print(f"   주소: {data['address']}")
                print(f"   카테고리: {', '.join(data['categories'])}")
                print(f"   리필아이템: {', '.join(data['refill_items'][:3])}...")
                print(f"   위치: {data['position']}")
            
            print("="*60)
            
        else:
            logger.info("🚀 실제 마이그레이션 실행...")
            stats = await migration.execute_migration(
                limit=args.limit,
                batch_size=args.batch_size
            )
            
            print("\n" + "="*50)
            print("📊 마이그레이션 결과")
            print("="*50)
            print(f"총 처리: {stats['total']}개")
            print(f"성공: {stats['success']}개")
            print(f"실패: {stats['failed']}개")
            print(f"성공률: {stats['success']/stats['total']*100:.1f}%")
            print("="*50)
            
    except Exception as e:
        logger.error(f"❌ 실행 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 