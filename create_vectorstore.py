from langchain_community.vectorstores import FAISS
import os, json, time
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

"""
환경 변수 설정: Open API key 
"""
def _set_env(var: str) -> None:
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")
load_dotenv(override=True)
_set_env("OPENAI_API_KEY")

"""
FAISS 설정
"""
FAISS_DIR = "./faiss_user_profiles"
FAISS_META = os.path.join(FAISS_DIR, "meta.json")
EMBED_MODEL_NAME = "text-embedding-3-small"
embedding = OpenAIEmbeddings(model=EMBED_MODEL_NAME)

"""
벡터 DB 생성: 유저 profile의 embedding DB
"""
def _profile_query_and_projection():
    query = {"ID": {"$exists": True}, "Profile": {"$type": "string", "$ne": ""}}
    projection = {"ID": 1, "Profile": 1}
    return query, projection

def _load_profile_docs_from_mongoDB(col_profile) -> list[Document]:
    query, projection = _profile_query_and_projection()
    cursor = col_profile.find(query, projection)
    docs: list[Document] = []
    for doc in cursor:
        p = doc.get("Profile", "")
        if not p:
            continue
        docs.append(Document(page_content=p, metadata={"id": doc["ID"]}))
    return docs

def build_vector_store_from_mongo(col_profile) -> FAISS:
    docs = _load_profile_docs_from_mongoDB(col_profile)
    if not docs:
        raise RuntimeError("user_profile 컬렉션에 벡터화할 Profile이 없습니다.")
    return FAISS.from_documents(docs, embedding)

def _write_meta(col_profile):
    # 무결성 체크: 개수 + 모델명만 기록
    query, _ = _profile_query_and_projection()
    count = col_profile.count_documents(query)
    meta = {
        "count": count,
        "embedding_model": EMBED_MODEL_NAME,
        "saved_at": time.time(),
    }
    os.makedirs(FAISS_DIR, exist_ok=True)
    with open(FAISS_META, "w", encoding="utf-8") as f:
        json.dump(meta, f)

def _read_meta():
    if not os.path.exists(FAISS_META):
        return None
    try:
        with open(FAISS_META, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
    
def _needs_rebuild(col_profile) -> bool:
    meta = _read_meta()
    if not meta:
        return True
    
    # 현재 DB 상태와 저장된 메타 비교
    query, _ = _profile_query_and_projection()
    current_count = col_profile.count_documents(query)
    if current_count != meta.get("count"):
        return True
    if meta.get("embedding_model") != EMBED_MODEL_NAME:
        return True
    return False

def load_or_build_vector_store(col_profile, embedding, force_rebuild: bool = False) -> FAISS:
    """
    1) 로컬에 저장된 FAISS가 있고(force_rebuild=False) 메타가 유효하면 -> 로드
    2) 아니면 Mongo에서 새로 빌드 -> 저장 -> 로드
    """
    if (not force_rebuild) and os.path.exists(FAISS_DIR) and (not _needs_rebuild(col_profile)):
        vs = FAISS.load_local(FAISS_DIR, embedding, allow_dangerous_deserialization=True)
        return vs

    # 빌드
    vs = build_vector_store_from_mongo(col_profile)
    os.makedirs(FAISS_DIR, exist_ok=True)
    vs.save_local(FAISS_DIR)
    _write_meta(col_profile)
    return vs