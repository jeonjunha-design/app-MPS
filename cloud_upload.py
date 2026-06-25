"""
cloud_upload.py
──────────────────────────────────────────────────────────────
지식 데이터를 Google Cloud에 업로드하는 스크립트

저장 구조:
  Firestore  → mps_knowledge/{doc_id}  (텍스트 청크 + 메타데이터)
  Cloud Storage → mps-knowledge-bucket/embeddings/{chunk_id}.json (임베딩 벡터)

실행:
  source venv/bin/activate
  python cloud_upload.py
──────────────────────────────────────────────────────────────
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# ── 환경 변수 로드 ────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

GCP_PROJECT   = os.getenv("GOOGLE_CLOUD_PROJECT", "mps-project-2026-0625")
KEY_PATH      = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/Users/juna/mps-key.json")
CRED_EXISTS   = Path(KEY_PATH).exists()

KNOWLEDGE_FILE = "mps_knowledge_base.txt"
FS_COLLECTION  = os.getenv("FIRESTORE_KNOWLEDGE_COLLECTION", "mps_knowledge")
BUCKET_NAME    = f"{GCP_PROJECT}-mps-knowledge"
CHUNK_SIZE     = 800
CHUNK_OVERLAP  = 100

if CRED_EXISTS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

# ── Google Cloud 클라이언트 ───────────────────────────────
def get_firestore():
    from google.cloud import firestore
    return firestore.Client(project=GCP_PROJECT)

def get_storage():
    from google.cloud import storage
    return storage.Client(project=GCP_PROJECT)

# ── 청킹 ──────────────────────────────────────────────────
def chunk_text(text: str) -> list[dict]:
    """섹션 단위 분할 후, 너무 긴 섹션은 CHUNK_SIZE 기준 재분할"""
    chunks = []
    raw_sections = text.split("\n[섹션")

    for sec_idx, section in enumerate(raw_sections):
        if sec_idx > 0:
            section = "[섹션" + section
        section = section.strip()
        if not section:
            continue

        title = section.split("\n")[0][:80]

        if len(section) <= CHUNK_SIZE:
            chunk_id = hashlib.md5(section.encode()).hexdigest()[:12]
            chunks.append({
                "id": f"sec{sec_idx:02d}_{chunk_id}",
                "text": section,
                "section_title": title,
                "section_idx": sec_idx,
                "char_count": len(section),
            })
        else:
            lines = section.split("\n")
            buf, buf_chars, sub_idx = [], 0, 0
            for line in lines:
                if buf_chars + len(line) > CHUNK_SIZE and buf:
                    chunk_text_str = "\n".join(buf)
                    chunk_id = hashlib.md5(chunk_text_str.encode()).hexdigest()[:12]
                    chunks.append({
                        "id": f"sec{sec_idx:02d}_sub{sub_idx:02d}_{chunk_id}",
                        "text": chunk_text_str,
                        "section_title": title,
                        "section_idx": sec_idx,
                        "sub_idx": sub_idx,
                        "char_count": len(chunk_text_str),
                    })
                    # overlap 처리
                    overlap_buf, overlap_chars = [], 0
                    for ol in reversed(buf):
                        if overlap_chars + len(ol) < CHUNK_OVERLAP:
                            overlap_buf.insert(0, ol)
                            overlap_chars += len(ol)
                        else:
                            break
                    buf = overlap_buf + [line]
                    buf_chars = sum(len(l) for l in buf)
                    sub_idx += 1
                else:
                    buf.append(line)
                    buf_chars += len(line)

            if buf:
                chunk_text_str = "\n".join(buf)
                chunk_id = hashlib.md5(chunk_text_str.encode()).hexdigest()[:12]
                chunks.append({
                    "id": f"sec{sec_idx:02d}_sub{sub_idx:02d}_{chunk_id}",
                    "text": chunk_text_str,
                    "section_title": title,
                    "section_idx": sec_idx,
                    "sub_idx": sub_idx,
                    "char_count": len(chunk_text_str),
                })

    return chunks

# ── 임베딩 생성 ───────────────────────────────────────────
def get_embeddings(texts: list[str]) -> list[list[float]]:
    """sentence-transformers로 임베딩 생성 (없으면 None 반환)"""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        embeddings = model.encode(texts, show_progress_bar=True)
        return embeddings.tolist()
    except ImportError:
        print("  ⚠ sentence-transformers 없음 → 임베딩 생략")
        return [None] * len(texts)

# ── Firestore 업로드 ──────────────────────────────────────
def upload_to_firestore(db, chunks: list[dict]):
    print(f"\n[Firestore] '{FS_COLLECTION}' 컬렉션에 업로드 중...")
    col = db.collection(FS_COLLECTION)

    # 기존 문서 삭제
    existing = col.stream()
    deleted = 0
    for doc in existing:
        doc.reference.delete()
        deleted += 1
    if deleted:
        print(f"  기존 문서 {deleted}개 삭제")

    # 메타 문서 (인덱스)
    col.document("_meta").set({
        "total_chunks": len(chunks),
        "source_file": KNOWLEDGE_FILE,
        "updated_at": datetime.now(timezone.utc),
        "version": "2.0",
        "description": "MPS 전문 지식 베이스 (논문+임상가이드라인 기반)"
    })

    # 청크 업로드
    batch = db.batch()
    count = 0
    for i, chunk in enumerate(chunks):
        doc_ref = col.document(chunk["id"])
        batch.set(doc_ref, {
            "text": chunk["text"],
            "section_title": chunk["section_title"],
            "section_idx": chunk["section_idx"],
            "char_count": chunk["char_count"],
            "uploaded_at": datetime.now(timezone.utc),
        })
        count += 1
        # Firestore 배치 최대 500
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {count}/{len(chunks)} 업로드...")

    batch.commit()
    print(f"  ✅ Firestore 업로드 완료: {len(chunks)}개 청크 + _meta")

# ── Cloud Storage 버킷 생성 & 임베딩 업로드 ───────────────
def upload_embeddings_to_gcs(gcs, chunks: list[dict], embeddings: list):
    if all(e is None for e in embeddings):
        print("\n[GCS] 임베딩 없음 → 건너뜀")
        return

    print(f"\n[GCS] 버킷 '{BUCKET_NAME}' 에 임베딩 업로드 중...")

    # 버킷 생성 (없으면)
    try:
        bucket = gcs.get_bucket(BUCKET_NAME)
        print(f"  기존 버킷 사용: {BUCKET_NAME}")
    except Exception:
        bucket = gcs.create_bucket(BUCKET_NAME, location="asia-northeast3")
        print(f"  버킷 생성: {BUCKET_NAME} (서울 리전)")

    # 임베딩 인덱스 JSON
    index = []
    for chunk, emb in zip(chunks, embeddings):
        if emb is None:
            continue
        blob_path = f"embeddings/{chunk['id']}.json"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps({
                "id": chunk["id"],
                "section_title": chunk["section_title"],
                "embedding": emb,
                "text_preview": chunk["text"][:100]
            }, ensure_ascii=False),
            content_type="application/json"
        )
        index.append({"id": chunk["id"], "blob": blob_path})

    # 인덱스 파일 업로드
    index_blob = bucket.blob("embeddings/_index.json")
    index_blob.upload_from_string(
        json.dumps({
            "total": len(index),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "chunks": index
        }, ensure_ascii=False),
        content_type="application/json"
    )
    print(f"  ✅ GCS 업로드 완료: {len(index)}개 임베딩")
    print(f"     gs://{BUCKET_NAME}/embeddings/")

# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  ☁️  MPS 지식 → Google Cloud 업로드")
    print("=" * 55)

    if not CRED_EXISTS:
        print(f"\n❌ 서비스 계정 키 파일 없음: {KEY_PATH}")
        print("   .env 파일에서 GOOGLE_APPLICATION_CREDENTIALS 경로를 확인하세요.")
        exit(1)

    # 1. 파일 로드
    print(f"\n[1/5] 지식 파일 로드: {KNOWLEDGE_FILE}")
    if not Path(KNOWLEDGE_FILE).exists():
        print(f"  ❌ 파일 없음: {KNOWLEDGE_FILE}")
        exit(1)
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    print(f"  총 {len(text):,} 글자")

    # 2. 청킹
    print("\n[2/5] 텍스트 청킹...")
    chunks = chunk_text(text)
    print(f"  총 {len(chunks)}개 청크 생성")

    # 3. 임베딩
    print("\n[3/5] 임베딩 생성 (시간이 걸릴 수 있습니다)...")
    texts_for_embed = [c["text"] for c in chunks]
    embeddings = get_embeddings(texts_for_embed)

    # 4. Firestore 업로드
    print("\n[4/5] Firestore 연결...")
    db = get_firestore()
    upload_to_firestore(db, chunks)

    # 5. Cloud Storage 업로드
    print("\n[5/5] Cloud Storage 연결...")
    gcs = get_storage()
    upload_embeddings_to_gcs(gcs, chunks, embeddings)

    print("\n" + "=" * 55)
    print("  ✅ 모든 데이터 업로드 완료!")
    print(f"  Firestore: {GCP_PROJECT} → {FS_COLLECTION}")
    print(f"  GCS: gs://{BUCKET_NAME}/embeddings/")
    print("=" * 55)
