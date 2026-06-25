"""
main.py — MPS AI 처방 FastAPI 서버
데이터: Firestore(원본) + ChromaDB 로컬 캐시 + Ollama llama3
실행: uvicorn main:app --reload --port 8000
"""

import os
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ──────────────────────────────────────────────────
GCP_PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT", "mps-project-2026-0625")
KEY_PATH     = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/Users/juna/mps-key.json")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
FS_KNOW_COL  = os.getenv("FIRESTORE_KNOWLEDGE_COLLECTION", "mps_knowledge")
FS_LOG_COL   = os.getenv("FIRESTORE_LOG_COLLECTION", "mps_consultations")
CHROMA_PATH  = os.getenv("CHROMA_DB_PATH", "./chroma_mps_db")
TOP_K        = 5

if Path(KEY_PATH).exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH
    USE_CLOUD = True
else:
    USE_CLOUD = False
    print("⚠ GCP 키 파일 없음 → 로컬 ChromaDB만 사용")

# ── Firestore / ChromaDB lazy init ────────────────────────
_fs_client = None
_chroma_col = None

def get_firestore():
    global _fs_client
    if _fs_client is None and USE_CLOUD:
        from google.cloud import firestore
        _fs_client = firestore.Client(project=GCP_PROJECT)
    return _fs_client

def _build_chroma_from_firestore():
    import shutil
    import chromadb
    from chromadb.utils import embedding_functions
    print("Firestore → ChromaDB 동기화 시작...")
    db = get_firestore()
    docs = list(db.collection(FS_KNOW_COL).stream())
    chunks = [
        {"id": d.id, "text": d.to_dict().get("text", "")}
        for d in docs
        if d.id != "_meta" and d.to_dict().get("text")
    ]
    if not chunks:
        raise RuntimeError("Firestore에 지식 데이터 없음. cloud_upload.py 먼저 실행하세요.")
    if Path(CHROMA_PATH).exists():
        shutil.rmtree(CHROMA_PATH)
    try:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
    except Exception:
        ef = embedding_functions.DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = client.get_or_create_collection(
        name="mps_knowledge", embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )
    batch = 100
    for i in range(0, len(chunks), batch):
        b = chunks[i:i+batch]
        col.add(ids=[c["id"] for c in b], documents=[c["text"] for c in b])
    print(f"ChromaDB 빌드 완료: {col.count()}개 청크")

def get_chroma():
    global _chroma_col
    if _chroma_col is not None:
        return _chroma_col
    if not Path(CHROMA_PATH).exists():
        if USE_CLOUD:
            _build_chroma_from_firestore()
        else:
            raise RuntimeError("ChromaDB 없음. setup_rag.py 또는 cloud_upload.py 실행 필요.")
    import chromadb
    from chromadb.utils import embedding_functions
    try:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
    except Exception:
        ef = embedding_functions.DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    _chroma_col = client.get_collection(name="mps_knowledge", embedding_function=ef)
    return _chroma_col

# ── FastAPI ───────────────────────────────────────────────
app = FastAPI(title="MPS AI 처방 서버", version="2.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class SymptomRequest(BaseModel):
    body_part: str
    symptoms: str
    pain_level: int = 5
    duration: str = "알 수 없음"
    occupation: Optional[str] = None
    aggravating: Optional[str] = None
    relieving: Optional[str] = None

class PrescriptionResponse(BaseModel):
    body_part: str
    pain_level: int
    rag_chunks_used: int
    data_source: str
    prescription: str
    disclaimer: str

def retrieve_context(query: str, body_part: str) -> tuple:
    col = get_chroma()
    results = col.query(
        query_texts=[f"{body_part} {query}"],
        n_results=TOP_K,
        include=["documents", "distances"]
    )
    docs = results["documents"][0]
    distances = results["distances"][0]
    filtered = [d for d, dist in zip(docs, distances) if dist < 0.85] or docs[:3]
    return "\n\n---\n\n".join(filtered), len(filtered)

def build_prompt(req: SymptomRequest, context: str) -> str:
    extras = ""
    if req.occupation:  extras += f"\n- 직업: {req.occupation}"
    if req.aggravating: extras += f"\n- 악화 요인: {req.aggravating}"
    if req.relieving:   extras += f"\n- 완화 요인: {req.relieving}"
    return f"""당신은 근막통증증후군(MPS) 전문 물리치료사입니다. 반드시 한국어로만 답변하세요. You MUST respond ONLY in Korean. English is absolutely forbidden.
아래 [전문 지식]을 반드시 참고하여 처방을 완벽한 한국어로 작성하세요.

[규칙] 1.한국어만 사용 2.전문지식 기반 처방만 3.의학적 진단 금지 4.구체적 횟수/시간 명시

[전문 지식]
{context}

[환자 정보]
- 통증 부위: {req.body_part} | 강도: {req.pain_level}/10 | 기간: {req.duration}
- 증상: {req.symptoms}{extras}

## 🔍 증상 분석
## 🔥 즉시 적용 (오늘부터)
## 🧘 스트레칭 프로그램 (3~5가지, 자세·시간·횟수 포함)
## 💪 운동 치료 (3~5가지, 구체적 방법)
## 🏥 물리치료 / 도수치료 권고
## 🏠 자세 교정 & 일상 예방
## ⚠️ 병원 방문 기준"""

def call_ollama(prompt: str) -> str:
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": 1500, "temperature": 0.3}},
            timeout=180
        )
        r.raise_for_status()
        return r.json().get("response", "응답 없음")
    except requests.exceptions.ConnectionError:
        raise HTTPException(503, "Ollama 연결 실패. ollama serve 실행 필요.")
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Ollama 응답 시간 초과.")

def save_log(req: SymptomRequest, prescription: str):
    if not USE_CLOUD:
        return
    try:
        get_firestore().collection(FS_LOG_COL).add({
            "body_part": req.body_part, "symptoms": req.symptoms,
            "pain_level": req.pain_level, "duration": req.duration,
            "occupation": req.occupation,
            "prescription_preview": prescription[:300],
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        print(f"로그 저장 실패(무시): {e}")

@app.get("/")
async def root():
    return {"service": "MPS AI 처방 서버 v2.1", "status": "running"}

@app.get("/health")
async def health():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
        models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        ollama_ok, models = False, []
    chroma_ok = Path(CHROMA_PATH).exists()
    fs_ok, fs_chunks = False, 0
    if USE_CLOUD:
        try:
            meta = get_firestore().collection(FS_KNOW_COL).document("_meta").get()
            fs_ok = meta.exists
            fs_chunks = meta.to_dict().get("total_chunks", 0) if fs_ok else 0
        except Exception:
            pass
    return {
        "status": "ok" if (ollama_ok and (chroma_ok or fs_ok)) else "degraded",
        "ollama": {"running": ollama_ok, "models": models},
        "chroma_db": {"ready": chroma_ok, "path": CHROMA_PATH},
        "firestore": {"connected": fs_ok, "knowledge_chunks": fs_chunks, "project": GCP_PROJECT},
        "data_source": "Firestore + ChromaDB" if (fs_ok and chroma_ok) else
                       "ChromaDB local" if chroma_ok else "없음"
    }

@app.post("/prescription", response_model=PrescriptionResponse)
async def get_prescription(req: SymptomRequest):
    context, chunks_used = retrieve_context(req.symptoms, req.body_part)
    prescription = call_ollama(build_prompt(req, context))
    save_log(req, prescription)
    return PrescriptionResponse(
        body_part=req.body_part, pain_level=req.pain_level,
        rag_chunks_used=chunks_used,
        data_source="Firestore + ChromaDB (RAG)" if USE_CLOUD else "ChromaDB local (RAG)",
        prescription=prescription,
        disclaimer="⚠️ 이 정보는 교육 목적이며 의학적 진단·처방을 대체하지 않습니다."
    )

@app.get("/db-stats")
async def db_stats():
    stats = {}
    try:
        stats["chroma"] = {"chunks": get_chroma().count(), "path": CHROMA_PATH}
    except Exception as e:
        stats["chroma"] = {"error": str(e)}
    if USE_CLOUD:
        try:
            meta = get_firestore().collection(FS_KNOW_COL).document("_meta").get()
            stats["firestore"] = meta.to_dict() if meta.exists else {"status": "메타 없음"}
        except Exception as e:
            stats["firestore"] = {"error": str(e)}
    return stats

@app.post("/sync-from-cloud")
async def sync_from_cloud():
    if not USE_CLOUD:
        raise HTTPException(400, "GCP 키 없음.")
    global _chroma_col
    _chroma_col = None
    _build_chroma_from_firestore()
    return {"status": "동기화 완료"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
