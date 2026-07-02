"""
main.py — MPS AI 처방 FastAPI 서버
데이터: Firestore(원본) + ChromaDB 로컬 캐시 + Ollama llama3
실행: uvicorn main:app --reload --port 8000
"""

import os
import json
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
    return f"""당신은 한국어로만 답변하는 근막통증증후군(MPS) 전문 물리치료사입니다.

[참고 지식]
{context}

[환자]
통증 부위: {req.body_part} | 강도: {req.pain_level}/10 | 기간: {req.duration} | 증상: {req.symptoms}{extras}

[지시사항]
- 반드시 한국어로만 작성하세요
- {req.body_part} 부위에 맞는 처방만 작성하세요
- 기간({req.duration})에 맞게: 오늘/2~3일=냉찜질+가벼운운동, 1주~4주=온찜질+스트레칭, 1개월이상=복합치료
- 각 운동과 스트레칭마다 자세, 동작, 횟수, 세트를 구체적으로 명시하세요
- 도수치료 권고 시 Maitland/MET PIR/허혈성 압박/IASTM 기법명을 포함하세요

아래 6개 항목으로 처방을 작성하세요:

## 🔍 증상 분석
## 🔥 즉시 적용
## 🧘 스트레칭 프로그램
## 💪 운동 치료
## 🏥 도수치료 권고
## 🏠 자세 교정 & 예방
"""


def call_ollama(prompt: str) -> str:
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": 3000, "temperature": 0.4}},
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

# ==================== 차트 저장/불러오기 ====================
from fastapi import Body
from typing import Optional

class ChartData(BaseModel):
    chart_no: str = ""
    pt_name: str
    pt_age: int = 0
    pt_gender: str = ""
    pt_date: str = ""
    pt_session: int = 1
    pt_therapist: str = ""
    pt_dx: str = ""
    chart_content: str  # 전체 차트 텍스트
    soap_json: dict = {}  # 구조화된 SOAP 데이터

def make_pt_key(pt_name: str, chart_no: str) -> str:
    """환자 식별 키 = 이름 + 차트번호.
    이름·차트번호가 모두 같으면 같은 환자(같은 파일)로 취급하고,
    차트번호가 다르면 동명이인이라도 다른 환자로 분리한다."""
    name = (pt_name or "").strip().replace(" ", "_")
    cn = (chart_no or "").strip().replace(" ", "_").replace("/", "_")
    if name and cn:
        return f"{name}_{cn}"
    return name or cn or "unknown"


@app.post("/chart/save")
async def save_chart(data: ChartData):
    now_str = datetime.now(timezone.utc).isoformat()
    results = {}

    # 1. JSON 파일 저장
    try:
        patients_dir = Path(__file__).parent / "patients"
        patients_dir.mkdir(exist_ok=True)
        pt_key = make_pt_key(data.pt_name, data.chart_no)
        json_path = patients_dir / f"{pt_key}.json"

        # 기존 데이터 로드
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                pt_data = json.load(f)
        else:
            pt_data = {
                "pt_name": data.pt_name,
                "chart_no": data.chart_no,
                "sessions": []
            }

        # 같은 날짜+회차 있으면 업데이트, 없으면 추가
        session_key = f"{data.pt_date}_{data.pt_session:03d}"
        existing_idx = next((i for i, s in enumerate(pt_data["sessions"])
                             if s.get("session_key") == session_key), None)
        session_record = {
            "session_key": session_key,
            "chart_no": data.chart_no,
            "pt_date": data.pt_date,
            "pt_session": data.pt_session,
            "pt_therapist": data.pt_therapist,
            "pt_dx": data.pt_dx,
            "pt_age": data.pt_age,
            "pt_gender": data.pt_gender,
            "chart_content": data.chart_content,
            "soap_json": data.soap_json,
            "saved_at": now_str
        }
        if existing_idx is not None:
            pt_data["sessions"][existing_idx] = session_record
        else:
            pt_data["sessions"].append(session_record)

        # 날짜 내림차순 정렬
        pt_data["sessions"].sort(key=lambda x: x["session_key"], reverse=True)
        pt_data["pt_name"] = data.pt_name
        pt_data["chart_no"] = data.chart_no
        pt_data["last_visit"] = data.pt_date
        pt_data["pt_dx"] = data.pt_dx

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(pt_data, f, ensure_ascii=False, indent=2)

        results["json"] = f"✅ 로컬 저장 완료 ({json_path.name})"
    except Exception as e:
        results["json"] = f"❌ 로컬 저장 실패: {e}"

    # 2. Firestore 저장
    try:
        db = get_firestore()
        pt_key = make_pt_key(data.pt_name, data.chart_no)
        doc_id = f"{data.pt_date}_{data.pt_session:03d}"
        db.collection("pt_charts").document(pt_key).collection("sessions").document(doc_id).set({
            "chart_no": data.chart_no,
            "pt_name": data.pt_name,
            "pt_age": data.pt_age,
            "pt_gender": data.pt_gender,
            "pt_date": data.pt_date,
            "pt_session": data.pt_session,
            "pt_therapist": data.pt_therapist,
            "pt_dx": data.pt_dx,
            "chart_content": data.chart_content,
            "soap_json": data.soap_json,
            "saved_at": datetime.now(timezone.utc),
        })
        db.collection("pt_charts").document(pt_key).set({
            "pt_name": data.pt_name,
            "chart_no": data.chart_no,
            "pt_age": data.pt_age,
            "pt_gender": data.pt_gender,
            "pt_dx": data.pt_dx,
            "last_visit": data.pt_date,
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)
        results["firestore"] = "✅ 클라우드 저장 완료"
    except Exception as e:
        results["firestore"] = f"❌ 클라우드 저장 실패: {e}"

    return {"status": "완료", "results": results}

@app.get("/chart/load/{pt_key}")
async def load_chart(pt_key: str):
    # JSON 파일에서 먼저 로드
    try:
        patients_dir = Path(__file__).parent / "patients"
        json_path = patients_dir / f"{pt_key}.json"
        if not json_path.exists():
            # pt_key에 공백이 있을 수 있으므로 대체 시도
            alt_key = pt_key.replace("_", " ")
            json_path = patients_dir / f"{alt_key}.json"
        if json_path.exists() and json_path.stat().st_size > 0:
            with open(json_path, 'r', encoding='utf-8') as f:
                pt_data = json.load(f)
            sessions = []
            for s in pt_data.get("sessions", []):
                s["pt_name"] = pt_data.get("pt_name", pt_key)
                s["source"] = "local"
                sessions.append(s)
            if sessions:
                return {"status": "ok", "sessions": sessions,
                        "count": len(sessions), "source": "json"}
    except Exception as e:
        pass

    # SQLite 실패 시 Firestore에서 로드
    try:
        db = get_firestore()
        sessions_ref = db.collection("pt_charts").document(pt_key).collection("sessions")
        sessions_docs = sessions_ref.order_by("pt_date", direction="DESCENDING").stream()
        sessions = []
        for s in sessions_docs:
            d = s.to_dict()
            d["doc_id"] = s.id
            d["source"] = "cloud"
            sessions.append(d)
        return {"status": "ok", "sessions": sessions, "count": len(sessions), "source": "firestore"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/chart/search")
async def search_chart(q: str):
    results = []
    # JSON 파일 검색
    try:
        patients_dir = Path(__file__).parent / "patients"
        if patients_dir.exists():
            for json_file in sorted(patients_dir.glob("*.json"),
                                    key=lambda f: f.stat().st_mtime, reverse=True):
                # 빈/손상 파일은 개별적으로 건너뛴다 (검색 전체가 멈추지 않도록)
                try:
                    if json_file.stat().st_size == 0:
                        continue
                    with open(json_file, 'r', encoding='utf-8') as f:
                        pt_data = json.load(f)
                except Exception:
                    continue
                pt_name = pt_data.get("pt_name", "")
                chart_no = pt_data.get("chart_no", "")
                if q.lower() in pt_name.lower() or (q and q in chart_no):
                    results.append({
                        "pt_name": pt_name,
                        "chart_no": chart_no,
                        "pt_dx": pt_data.get("pt_dx", ""),
                        "last_visit": pt_data.get("last_visit", ""),
                        "pt_key": json_file.stem,
                        "source": "local"
                    })
    except Exception as e:
        pass

    # Firestore 검색 (SQLite 결과 없을 때)
    if not results:
        try:
            db = get_firestore()
            docs = db.collection("pt_charts").stream()
            for doc in docs:
                d = doc.to_dict()
                if q.lower() in d.get("pt_name","").lower() or q in d.get("chart_no",""):
                    d["pt_key"] = doc.id
                    d["source"] = "cloud"
                    results.append(d)
        except:
            pass

    return {"status": "ok", "results": results}

@app.get("/chart/list")
async def list_charts():
    results = []
    try:
        patients_dir = Path(__file__).parent / "patients"
        if patients_dir.exists():
            for json_file in sorted(patients_dir.glob("*.json"),
                                    key=lambda f: f.stat().st_mtime, reverse=True)[:50]:
                with open(json_file, 'r', encoding='utf-8') as f:
                    pt_data = json.load(f)
                results.append({
                    "pt_name": pt_data.get("pt_name", ""),
                    "chart_no": pt_data.get("chart_no", ""),
                    "pt_dx": pt_data.get("pt_dx", ""),
                    "last_visit": pt_data.get("last_visit", ""),
                    "visits": len(pt_data.get("sessions", [])),
                    "pt_key": json_file.stem,
                    "source": "local"
                })
    except:
        pass
    return {"status": "ok", "results": results}

class DeleteChart(BaseModel):
    pt_key: str
    session_key: str

@app.delete("/chart/delete")
async def delete_chart(data: DeleteChart):
    results = {}
    # JSON 파일에서 삭제
    try:
        patients_dir = Path(__file__).parent / "patients"
        json_path = patients_dir / f"{data.pt_key}.json"
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                pt_data = json.load(f)
            pt_data["sessions"] = [s for s in pt_data["sessions"]
                                   if s.get("session_key") != data.session_key]
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(pt_data, f, ensure_ascii=False, indent=2)
            results["json"] = "✅ 로컬 삭제 완료"
    except Exception as e:
        results["json"] = f"❌ {e}"

    # Firestore에서 삭제
    try:
        db = get_firestore()
        db.collection("pt_charts").document(data.pt_key).collection("sessions").document(data.session_key).delete()
        results["firestore"] = "✅ 클라우드 삭제 완료"
    except Exception as e:
        results["firestore"] = f"❌ {e}"

    return {"status": "완료", "results": results}
