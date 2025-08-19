from langchain_community.vectorstores import FAISS
import os
import json
import time
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from typing import Optional
from ..core.config import get_settings


class VectorStoreManager:
    """벡터스토어 관리 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.faiss_dir = self.settings.faiss_dir
        self.faiss_meta_path = os.path.join(self.faiss_dir, "meta.json")
        self.embedding = OpenAIEmbeddings(
            model=self.settings.embedding_model,
            api_key=self.settings.openai_api_key
        )
        self._vector_store: Optional[FAISS] = None
    
    @property
    def vector_store(self) -> FAISS:
        """벡터스토어 인스턴스 반환 (지연 로딩)"""
        if self._vector_store is None:
            raise RuntimeError("벡터스토어가 초기화되지 않았습니다. load_or_build_vector_store()를 먼저 호출하세요.")
        return self._vector_store
    
    def _profile_query_and_projection(self):
        """프로필 쿼리 및 프로젝션 반환"""
        query = {"ID": {"$exists": True}, "Profile": {"$type": "string", "$ne": ""}}
        projection = {"ID": 1, "Profile": 1}
        return query, projection
    
    def _load_profile_docs_from_mongodb(self, col_profile) -> list[Document]:
        """MongoDB에서 프로필 문서 로드"""
        query, projection = self._profile_query_and_projection()
        cursor = col_profile.find(query, projection)
        docs: list[Document] = []
        
        for doc in cursor:
            profile_text = doc.get("Profile", "")
            if not profile_text:
                continue
            docs.append(Document(
                page_content=profile_text, 
                metadata={"id": doc["ID"]}
            ))
        return docs
    
    def build_vector_store_from_mongo(self, col_profile) -> FAISS:
        """MongoDB에서 벡터스토어 빌드"""
        docs = self._load_profile_docs_from_mongodb(col_profile)
        if not docs:
            raise RuntimeError("user_profile 컬렉션에 벡터화할 Profile이 없습니다.")
        return FAISS.from_documents(docs, self.embedding)
    
    def _write_meta(self, col_profile):
        """메타데이터 파일 작성"""
        query, _ = self._profile_query_and_projection()
        count = col_profile.count_documents(query)
        meta = {
            "count": count,
            "embedding_model": self.settings.embedding_model,
            "saved_at": time.time(),
        }
        os.makedirs(self.faiss_dir, exist_ok=True)
        with open(self.faiss_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
    
    def _read_meta(self) -> Optional[dict]:
        """메타데이터 파일 읽기"""
        if not os.path.exists(self.faiss_meta_path):
            return None
        try:
            with open(self.faiss_meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def _needs_rebuild(self, col_profile) -> bool:
        """벡터스토어 재빌드 필요 여부 판단"""
        meta = self._read_meta()
        if not meta:
            return True
        
        # 현재 DB 상태와 저장된 메타 비교
        query, _ = self._profile_query_and_projection()
        current_count = col_profile.count_documents(query)
        if current_count != meta.get("count"):
            return True
        if meta.get("embedding_model") != self.settings.embedding_model:
            return True
        return False
    
    def load_or_build_vector_store(self, col_profile, force_rebuild: bool = False) -> FAISS:
        """
        벡터스토어 로드 또는 빌드
        1) 로컬에 저장된 FAISS가 있고(force_rebuild=False) 메타가 유효하면 -> 로드
        2) 아니면 Mongo에서 새로 빌드 -> 저장 -> 로드
        """
        if (not force_rebuild and 
            os.path.exists(self.faiss_dir) and 
            not self._needs_rebuild(col_profile)):
            
            self._vector_store = FAISS.load_local(
                self.faiss_dir, 
                self.embedding, 
                allow_dangerous_deserialization=True
            )
            return self._vector_store
        
        # 빌드
        self._vector_store = self.build_vector_store_from_mongo(col_profile)
        os.makedirs(self.faiss_dir, exist_ok=True)
        self._vector_store.save_local(self.faiss_dir)
        self._write_meta(col_profile)
        
        return self._vector_store


# 전역 인스턴스
vector_store_manager = VectorStoreManager()


def get_vector_store_manager() -> VectorStoreManager:
    """벡터스토어 매니저 반환"""
    return vector_store_manager
