from langgraph.graph import StateGraph, START
from pymongo import MongoClient
from typing import Dict
import logging

from app.core.config import get_settings
from app.graph.state import MyState
from app.graph.nodes import supervisor_node, profiler_node, retriever_node, recommender_node
from app.dependencies.llm import get_llm
from app.dependencies.collections import get_sync_collections
from app.services.vectorstore import get_vector_store_manager

# Logger 설정
logger = logging.getLogger(__name__)


class TravelRecommendationAgent:
    """여행 추천 에이전트 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.llm = get_llm()
        self._db_client = None
        self._db = None
        self._collections = None
        self._vector_manager = None
        
    def _get_db_connection(self):
        """MongoDB 연결 초기화"""
        if self._db_client is None:
            self._db_client = MongoClient(self.settings.mongodb_uri)
            self._db = self._db_client[self.settings.mongodb_db]
            self._collections = get_sync_collections(self._db)
            
            # 벡터스토어 초기화
            self._vector_manager = get_vector_store_manager()
            self._vector_manager.load_or_build_vector_store(
                self._collections["col_profile"], 
                force_rebuild=False
            )
            
        return self._collections
    
    def _create_node_wrapper(self, node_func):
        """노드 함수를 래핑하여 의존성 주입"""
        def wrapper(state):
            collections = self._get_db_connection()
            if node_func.__name__ == "supervisor_node":
                return node_func(state)
            elif node_func.__name__ == "retriever_node":
                return node_func(state, collections)
            else:
                return node_func(state, collections, self.llm)
        return wrapper
    
    def create_graph(self):
        """LangGraph 생성"""
        graph = StateGraph(MyState)

        # 노드 추가 (의존성 주입된 래퍼 사용)
        graph.add_node("supervisor", self._create_node_wrapper(supervisor_node))
        graph.add_node("profiler", self._create_node_wrapper(profiler_node))
        graph.add_node("retriever", self._create_node_wrapper(retriever_node))
        graph.add_node("recommender", self._create_node_wrapper(recommender_node))

        # 시작점
        graph.add_edge(START, "supervisor")

        return graph.compile()
    
    def recommend(self, user_id: str) -> Dict:
        """추천 실행"""
        app = self.create_graph()
        
        initial_state: MyState = {
            "user_id": user_id,
            "profile": "",
            "rec_people": [],
            "rec_travel": [],
            "top_100_ids": []
        }
        
        final_state = app.invoke(initial_state)
        return final_state
    
    def close(self):
        """리소스 정리"""
        if self._db_client:
            self._db_client.close()


def create_agent() -> TravelRecommendationAgent:
    """에이전트 팩토리 함수"""
    return TravelRecommendationAgent()


if __name__ == "__main__":
    # 테스트 실행
    agent = create_agent()
    
    try:
        result = agent.recommend(user_id="2asd")
        logger.info("=== 최종 결과 ===")
        logger.info(f"추천 동행자: {result.get('rec_people', [])}")
        logger.info(f"추천 여행지: {result.get('rec_travel', [])}")
    finally:
        agent.close()
