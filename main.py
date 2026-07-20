"""
main.py — MPS AI 처방 FastAPI 서버
데이터: Firestore(원본) + ChromaDB 로컬 캐시 + Ollama llama3
실행: uvicorn main:app --reload --port 8000
"""

import os
import re
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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:latest")
FS_KNOW_COL  = os.getenv("FIRESTORE_KNOWLEDGE_COLLECTION", "mps_knowledge")
FS_LOG_COL   = os.getenv("FIRESTORE_LOG_COLLECTION", "mps_consultations")
CHROMA_PATH  = os.getenv("CHROMA_DB_PATH", "./chroma_mps_db")
TOP_K        = 8

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
        {"id": d.id, "text": d.to_dict().get("text", ""),
         "section_title": d.to_dict().get("section_title", "")}
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
        col.add(ids=[c["id"] for c in b], documents=[c["text"] for c in b],
                metadatas=[{"section_title": c["section_title"]} for c in b])
    print(f"ChromaDB 빌드 완료: {col.count()}개 청크 (메타데이터 포함)")

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

# body_part 라벨 → 섹션 제목에서 찾을 키워드. 다국어 임베딩만으로는 "자세/동작/횟수" 같은
# 공통 서식 문구에 묻혀 부위 변별력이 약해서(예: 팔꿈치 쿼리에 요추/경추 청크가 섞여 나옴),
# 시맨틱 검색 결과를 넉넉히 뽑은 뒤 섹션 제목 키워드로 재정렬하는 하이브리드 검색을 쓴다.
BODY_PART_KEYWORDS = {
    "허리(요추)": ["요추"],
    "목(경추)": ["경추"],
    "어깨(견관절)": ["견관절", "어깨"],
    "무릎(슬관절)": ["슬관절", "무릎"],
    "고관절/골반": ["고관절", "골반"],
    "발목(족관절)": ["족관절", "발목"],
    "손목(수근관절)": ["수근관절", "손목"],
    "팔꿈치(주관절)": ["주관절", "팔꿈치"],
}
MAX_RETRIEVE_CANDIDATES = 300  # 코퍼스가 매우 커질 경우를 대비한 상한선


def _body_part_keywords(body_part: str) -> list:
    kws = BODY_PART_KEYWORDS.get(body_part)
    if kws:
        return kws
    # 부분 매칭: 입력이 키의 일부를 포함하면 해당 키워드 반환
    for key, vals in BODY_PART_KEYWORDS.items():
        if body_part in key or any(v in body_part for v in vals):
            return vals
    # 고정 라벨에 없는 자유 입력은 조각을 키워드 후보로 사용
    parts = [p.strip() for p in re.split(r"[()/·,\s]+", body_part) if p.strip()]
    return parts or [body_part]


def retrieve_context(query: str, body_part: str) -> tuple:
    col = get_chroma()
    n_candidates = min(col.count(), MAX_RETRIEVE_CANDIDATES)

    # 부위별 TrP·치료 키워드 매핑
    trp_keywords = {
        "요추": "요방형근 이상근 다열근 QL TrP 허혈성압박 McGill 코어 요통",
        "허리": "요방형근 이상근 다열근 QL TrP 허혈성압박 McGill 코어 요통",
        "경추": "상부승모근 견갑거근 후두하근 흉쇄유돌근 TrP 친턱 DNF 경부통",
        "목": "상부승모근 견갑거근 후두하근 흉쇄유돌근 TrP 친턱 DNF 경부통",
        "어깨": "극상근 극하근 소흉근 전거근 TrP 회전근개 충돌증후군 외회전",
        "견관절": "극상근 극하근 소흉근 전거근 TrP 회전근개 충돌증후군 외회전",
        "무릎": "외측광근 슬와근 VMO TrP 슬개골 PFPS 장경인대 클램쉘",
        "슬관절": "외측광근 슬와근 VMO TrP 슬개골 PFPS 장경인대 클램쉘",
        "발목": "비복근 가자미근 전경골근 TrP 족저근막 아킬레스 균형",
        "족관절": "비복근 가자미근 전경골근 TrP 족저근막 아킬레스 균형",
        "고관절": "이상근 중둔근 대둔근 TFL TrP 클램쉘 글루트브릿지",
        "팔꿈치": "ECRB 원회내근 FCR TrP 외측상과염 테니스엘보 편심성",
        "주관절": "ECRB 원회내근 FCR TrP 외측상과염 테니스엘보 편심성",
        "손목": "수근관 정중신경 FCR FCU TrP CTS 신경가동술",
        "수근관절": "수근관 정중신경 FCR FCU TrP CTS 신경가동술",
    }

    # 부위 매칭 TrP 키워드 찾기
    extra_kw = ""
    for k, v in trp_keywords.items():
        if k in body_part or k in (query or ""):
            extra_kw = v
            break

    # 다중 쿼리로 검색 (부위+TrP+치료 조합)
    queries = [
        f"{body_part} TrP 트리거포인트 허혈성압박 치료",
        f"{body_part} 스트레칭 운동치료 도수치료 처방",
        f"{extra_kw} 처방 프로토콜" if extra_kw else f"{body_part} MPS 처방",
    ]

    all_docs = {}
    for q in queries:
        try:
            res = col.query(
                query_texts=[q],
                n_results=min(n_candidates, 50),
                include=["documents", "distances", "metadatas"]
            )
            for doc, dist, meta in zip(
                res["documents"][0],
                res["distances"][0],
                res["metadatas"][0]
            ):
                if doc not in all_docs or dist < all_docs[doc][0]:
                    all_docs[doc] = (dist, meta)
        except Exception:
            pass

    keywords = _body_part_keywords(body_part)
    # extra_kw도 키워드에 추가
    if extra_kw:
        keywords = keywords + extra_kw.split()

    def matches(doc, meta):
        title = (meta or {}).get("section_title") or ""
        text = doc[:800]
        return any(kw in title or kw in text for kw in keywords)

    # 거리 기준 정렬 후 키워드 매치 우선
    ranked = sorted(all_docs.items(), key=lambda x: x[1][0])
    keyword_hits = [doc for doc, (dist, meta) in ranked if matches(doc, meta)]
    fallback = [doc for doc, (dist, meta) in ranked if not matches(doc, meta)]

    if keyword_hits:
        filtered = keyword_hits[:TOP_K]
    else:
        filtered = fallback[:TOP_K] if fallback else list(all_docs.keys())[:3]

    return "\n\n---\n\n".join(filtered), len(filtered)

# body_part 라벨(app.py 가 만들어내는 문자열과 동일) → 부위별 빠른 선택과 같은 이모지.
# AI 처방의 "<이모지 부위>" 헤더가 홈 처방 빠른 선택의 부위 헤더와 시각적으로 일치하도록 맞춘다.
BODY_PART_EMOJI = {
    "허리(요추)": "요추", "목(경추)": "경추", "어깨(견관절)": "견관절",
    "무릎(슬관절)": "슬관절", "고관절/골반": "고관절", "발목(족관절)": "족관절",
    "손목(수근관절)": "수근관절", "팔꿈치(주관절)": "주관절",
}


def build_prompt(req: SymptomRequest, context: str) -> str:
    extras = ""
    if req.occupation:  extras += f"\n- 직업: {req.occupation}"
    if req.aggravating: extras += f"\n- 악화 요인: {req.aggravating}"
    if req.relieving:   extras += f"\n- 완화 요인: {req.relieving}"

    # 통증 단계 자동 판별
    if req.pain_level >= 7:
        pain_stage = "급성기(NRS 7~10): 수동 치료 중심, 강한 운동 금지"
        stage_guide = "부드러운 ROM·등척성 운동·핫팩·ICT 위주로 처방"
    elif req.pain_level >= 4:
        pain_stage = "아급성기(NRS 4~7): 능동 운동 도입, 도수치료 병행"
        stage_guide = "TrP 치료·Maitland Gr.III·스트레칭·초기 강화 운동 처방"
    else:
        pain_stage = "만성기(NRS 1~4): 운동치료 중심, 도수치료 보조"
        stage_guide = "McGill Big3·강화운동·자세교정·재발방지 홈운동 처방"

    # 직업별 특화 가이드
    occ_guide = ""
    if req.occupation:
        occ_map = {
            "사무직": "모니터 높이·키보드 위치·1시간마다 기립 교육 포함",
            "간호사": "팀 리프팅·환자 이송 자세·허리 보호대 교육 포함",
            "의료직": "장시간 고정 자세·어깨 거상 예방 교육 포함",
            "교사": "장시간 기립·칠판 작업 자세 교육 포함",
            "운전직": "운전 자세·헤드레스트 높이·2시간마다 스트레칭 포함",
            "요리사": "주방 높이·반복 동작 보호 교육 포함",
            "학생": "책상 자세·스마트폰 자세·50분 공부 후 스트레칭 포함",
        }
        for k, v in occ_map.items():
            if k in req.occupation:
                occ_guide = f"\n- 직업 특화: {v}"
                break
        if not occ_guide:
            occ_guide = f"\n- 직업 특화: {req.occupation} 종사자의 작업 자세 교정 포함"

    part_name = BODY_PART_EMOJI.get(req.body_part, req.body_part)
    part_header = f"<{part_name}>"

    return f"""[역할]
당신은 한국어로만 답변하는 MPS 전문 물리치료사입니다.
TrP(트리거포인트) 치료·Maitland 가동술·MET·IASTM·운동치료 전문가입니다.

[참고 지식 - 반드시 이 내용 기반으로만 처방]
{context}

[환자 정보]
- 통증 부위: {req.body_part}
- 통증 강도: {req.pain_level}/10 → {pain_stage}
- 처방 방향: {stage_guide}
- 지속 기간: {req.duration}
- 증상: {req.symptoms}{extras}{occ_guide}

[엄격한 규칙]
1. 반드시 한국어로만 작성
2. {req.body_part} 부위만 처방. 다른 부위는 언급 금지
3. 위 참고 지식에서 {req.body_part} 관련 TrP·가동술·운동 내용 우선 사용
4. 통증 단계({pain_stage})에 맞는 강도로 처방
5. 각 항목은 근육명·기법명·횟수·세트 구체적으로 명시

[출력 형식 - 반드시 아래 형식 그대로]
- 첫 줄은 정확히 "{part_header}" 로 시작
- 빈 줄 1개 후 5개 카테고리 순서대로 작성
- 각 카테고리는 "[카테고리명]" 한 줄, 바로 "- "로 시작하는 항목들
- 항목 사이 빈 줄 없음, 카테고리 사이만 빈 줄 1개
- 각 항목은 한 줄로 (중간 줄바꿈 금지)
- 다른 문구(설명·인사말·번호) 추가 금지

{part_header}

[TrP 치료]
- ({req.body_part} 핵심 TrP 근육명: 허혈성압박/IASTM/건침 기법, 압박 시간·포인트 수 명시, 한 줄로)
- ({req.body_part} 두 번째 TrP 근육, 한 줄로)

[스트레칭]
- ({req.body_part} 전용 스트레칭, 자세/동작/유지시간/횟수 명시, 한 줄로)
- ({req.body_part} 두 번째 스트레칭, 한 줄로)
- ({req.body_part} 세 번째 스트레칭, 한 줄로)

[운동치료]
- ({req.body_part} 강화운동, 자세/동작/횟수/세트 명시, 한 줄로)
- ({req.body_part} 두 번째 운동, 한 줄로)
- ({req.body_part} 세 번째 운동, 한 줄로)

[자세교정]
- ({req.body_part} 자세교정 및 생활습관, 직업 특화 포함, 한 줄로)
- (홈운동 루틴 추천, 한 줄로)

[도수치료 권고]
- (Maitland 가동술 레벨·방향·횟수 명시, 한 줄로)
- (MET 또는 MFR 기법, 한 줄로)
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
    context_full, chunks_used = retrieve_context(req.symptoms, req.body_part)
    context = context_full[:1500]
    prescription = call_ollama(build_prompt(req, context))
    return PrescriptionResponse(
        body_part=req.body_part, pain_level=req.pain_level,
        rag_chunks_used=chunks_used,
        data_source="Firestore + ChromaDB (RAG)" if USE_CLOUD else "ChromaDB local (RAG)",
        prescription=prescription,
        disclaimer="⚠️ 이 정보는 교육 목적이며 의학적 진단·처방을 대체하지 않습니다."
    )

@app.post("/knowledge_search")
async def knowledge_search(req: dict):
    query = req.get("query", "").strip()
    n_results = req.get("n_results", 5)
    if not query:
        return {"answer": "질문을 입력해주세요.", "chunks_found": 0}

    # ChromaDB에서 관련 청크 검색
    try:
        col = get_chroma()
        results = col.query(query_texts=[query], n_results=n_results)
        docs = results["documents"][0] if results["documents"] else []
        chunks_found = len(docs)
        context = "\n\n---\n\n".join(docs)
    except Exception as e:
        return {"answer": f"검색 오류: {e}", "chunks_found": 0}

    if not context:
        return {"answer": "관련 지식을 찾지 못했습니다.", "chunks_found": 0}

    # EXAONE으로 답변 생성
    prompt = f"""반드시 한국어로만 답변하세요. Do not use English. 한국어 답변만 허용됩니다.

당신은 도수치료 전문 AI 어시스턴트입니다.
아래 참고 자료를 바탕으로 질문에 대해 정확하고 상세하게 한국어로 답변하세요.

[참고 자료]
{context}

[질문]
{query}

[답변 지침]
- 반드시 한국어로만 답변하세요
- 참고 자료에 있는 내용을 중심으로 답변하세요
- 근육명, 신경명, 검사명은 한국어(영어병기) 형식으로 표기하세요 예: 전경골근(tibialis anterior)
- 임상적으로 중요한 내용은 **굵게** 강조하세요
- 마크다운 형식으로 구조화하여 답변하세요
- 참고 자료에 없는 내용은 "추가 확인 필요"로 표시하세요

한국어 답변:"""

    answer = call_ollama(prompt)
    return {"answer": answer, "chunks_found": chunks_found}


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
    chart_type: str = "도수치료"  # "도수치료" 또는 "운동치료"
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

        # 같은 날짜+회차+차트유형 있으면 업데이트, 없으면 추가
        # (운동치료는 "_ex" 접미어를 붙여 같은 날짜라도 도수치료와 분리 저장)
        type_suffix = "_ex" if data.chart_type == "운동치료" else ""
        session_key = f"{data.pt_date}_{data.pt_session:03d}{type_suffix}"
        existing_idx = next((i for i, s in enumerate(pt_data["sessions"])
                             if s.get("session_key") == session_key), None)
        session_record = {
            "session_key": session_key,
            "chart_no": data.chart_no,
            "chart_type": data.chart_type,
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
        type_suffix = "_ex" if data.chart_type == "운동치료" else ""
        doc_id = f"{data.pt_date}_{data.pt_session:03d}{type_suffix}"
        db.collection("pt_charts").document(pt_key).collection("sessions").document(doc_id).set({
            "chart_no": data.chart_no,
            "chart_type": data.chart_type,
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

@app.put("/chart/update/{chart_id}")
async def update_chart(chart_id: str, data: ChartData):
    """기존 차트를 새 차트 생성이 아닌 chart_id(=session_key)로 덮어쓰기.
    /chart/save 와 동일한 구조를 받되, 세션 키를 요청 데이터(날짜+회차)로 재계산하지 않고
    URL 의 chart_id 를 그대로 사용해 같은 레코드/문서를 갱신한다."""
    now_str = datetime.now(timezone.utc).isoformat()
    results = {}

    # 1. JSON 파일 업데이트
    try:
        patients_dir = Path(__file__).parent / "patients"
        patients_dir.mkdir(exist_ok=True)
        pt_key = make_pt_key(data.pt_name, data.chart_no)
        json_path = patients_dir / f"{pt_key}.json"

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                pt_data = json.load(f)
        else:
            pt_data = {
                "pt_name": data.pt_name,
                "chart_no": data.chart_no,
                "sessions": []
            }

        session_record = {
            "session_key": chart_id,
            "chart_no": data.chart_no,
            "chart_type": data.chart_type,
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
        existing_idx = next((i for i, s in enumerate(pt_data["sessions"])
                             if s.get("session_key") == chart_id), None)
        if existing_idx is not None:
            pt_data["sessions"][existing_idx] = session_record
        else:
            pt_data["sessions"].append(session_record)

        pt_data["sessions"].sort(key=lambda x: x["session_key"], reverse=True)
        pt_data["pt_name"] = data.pt_name
        pt_data["chart_no"] = data.chart_no
        pt_data["last_visit"] = data.pt_date
        pt_data["pt_dx"] = data.pt_dx

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(pt_data, f, ensure_ascii=False, indent=2)

        results["json"] = f"✅ 로컬 업데이트 완료 ({json_path.name})"
    except Exception as e:
        results["json"] = f"❌ 로컬 업데이트 실패: {e}"

    # 2. Firestore 업데이트
    try:
        db = get_firestore()
        pt_key = make_pt_key(data.pt_name, data.chart_no)
        db.collection("pt_charts").document(pt_key).collection("sessions").document(chart_id).set({
            "chart_no": data.chart_no,
            "chart_type": data.chart_type,
            "pt_name": data.pt_name,
            "pt_age": data.pt_age,
            "pt_gender": data.pt_gender,
            "pt_date": data.pt_date,
            "pt_session": data.pt_session,
            "pt_therapist": data.pt_therapist,
            "pt_dx": data.pt_dx,
            "chart_content": data.chart_content,
            "soap_json": data.soap_json,
            "updated_at": datetime.now(timezone.utc),
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
        results["firestore"] = "✅ 클라우드 업데이트 완료"
    except Exception as e:
        results["firestore"] = f"❌ 클라우드 업데이트 실패: {e}"

    return {"status": "완료", "results": results}


@app.get("/chart/load/{pt_key}")
async def load_chart(pt_key: str, chart_type: str = None):
    # JSON 파일에서 먼저 로드 (chart_type 지정 시 해당 유형만)
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
                s.setdefault("chart_type", "도수치료")
                sessions.append(s)
            # chart_type 지정 시: 같은 유형 세션을 앞으로 정렬(없으면 다른 유형).
            # 전체 세션은 그대로 반환 → 앱에서 S/O/A(전체 최근)·P(동일 유형) 분리 적용.
            if chart_type:
                same = [s for s in sessions if s["chart_type"] == chart_type]
                other = [s for s in sessions if s["chart_type"] != chart_type]
                sessions = same + other
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
            d.setdefault("chart_type", "도수치료")
            sessions.append(d)
        if chart_type:
            same = [s for s in sessions if s["chart_type"] == chart_type]
            other = [s for s in sessions if s["chart_type"] != chart_type]
            sessions = same + other
        return {"status": "ok", "sessions": sessions, "count": len(sessions), "source": "firestore"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/chart/search")
async def search_chart(q: str, chart_type: str = None):
    results = []
    # JSON 파일 검색 (chart_type 지정 시 해당 유형 차트가 있는 환자만)
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
                sessions = pt_data.get("sessions", [])
                if chart_type and not any(
                        s.get("chart_type", "도수치료") == chart_type for s in sessions):
                    continue
                if q.lower() in pt_name.lower() or (q and q in chart_no):
                    results.append({
                        "pt_name": pt_name,
                        "chart_no": chart_no,
                        "pt_dx": pt_data.get("pt_dx", ""),
                        "last_visit": pt_data.get("last_visit", ""),
                        "manual_count": sum(1 for s in sessions
                                            if s.get("chart_type", "도수치료") == "도수치료"),
                        "exercise_count": sum(1 for s in sessions
                                              if s.get("chart_type") == "운동치료"),
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
                if json_file.stat().st_size == 0:
                    continue
                with open(json_file, 'r', encoding='utf-8') as f:
                    pt_data = json.load(f)
                sessions = pt_data.get("sessions", [])
                results.append({
                    "pt_name": pt_data.get("pt_name", ""),
                    "chart_no": pt_data.get("chart_no", ""),
                    "pt_dx": pt_data.get("pt_dx", ""),
                    "last_visit": pt_data.get("last_visit", ""),
                    "visits": len(sessions),
                    "manual_count": sum(1 for s in sessions
                                        if s.get("chart_type", "도수치료") == "도수치료"),
                    "exercise_count": sum(1 for s in sessions
                                          if s.get("chart_type") == "운동치료"),
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


@app.delete("/patient/{pt_key}")
async def delete_patient(pt_key: str):
    """환자 전체 삭제: 로컬 JSON 파일 + Firestore 문서/하위 세션 컬렉션."""
    results = {}
    # 1. 로컬 JSON 파일 삭제
    try:
        json_path = Path(__file__).parent / "patients" / f"{pt_key}.json"
        if json_path.exists():
            json_path.unlink()
            results["json"] = "✅ 로컬 파일 삭제 완료"
        else:
            results["json"] = "로컬 파일 없음"
    except Exception as e:
        results["json"] = f"❌ {e}"

    # 2. Firestore 문서 + 하위 sessions 컬렉션 전체 삭제
    try:
        db = get_firestore()
        doc_ref = db.collection("pt_charts").document(pt_key)
        for sdoc in doc_ref.collection("sessions").stream():
            sdoc.reference.delete()
        doc_ref.delete()
        results["firestore"] = "✅ 클라우드 삭제 완료"
    except Exception as e:
        results["firestore"] = f"❌ {e}"

    return {"status": "삭제 완료", "results": results}
