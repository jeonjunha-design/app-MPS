import os, hashlib
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

GCP_PROJECT   = os.getenv("GOOGLE_CLOUD_PROJECT", "mps-project-2026-0625")
KEY_PATH      = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/Users/juna/mps-key.json")
FS_COLLECTION = "mps_knowledge"
KNOWLEDGE_FILE = "mps_knowledge_base.txt"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

if Path(KEY_PATH).exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

def chunk_text(text):
    chunks = []
    sections = text.split("\n[섹션")
    for i, sec in enumerate(sections):
        if i > 0:
            sec = "[섹션" + sec
        sec = sec.strip()
        if not sec:
            continue
        title = sec.split("\n")[0][:80]
        if len(sec) <= CHUNK_SIZE:
            cid = hashlib.md5(sec.encode()).hexdigest()[:12]
            chunks.append({"id": f"sec{i:02d}_{cid}", "text": sec, "title": title, "idx": i})
        else:
            lines = sec.split("\n")
            buf, buf_chars, sub = [], 0, 0
            for line in lines:
                if buf_chars + len(line) > CHUNK_SIZE and buf:
                    ct = "\n".join(buf)
                    cid = hashlib.md5(ct.encode()).hexdigest()[:12]
                    chunks.append({"id": f"sec{i:02d}_s{sub:02d}_{cid}", "text": ct, "title": title, "idx": i})
                    ob, oc = [], 0
                    for ol in reversed(buf):
                        if oc + len(ol) < CHUNK_OVERLAP:
                            ob.insert(0, ol); oc += len(ol)
                        else:
                            break
                    buf = ob + [line]; buf_chars = sum(len(l) for l in buf); sub += 1
                else:
                    buf.append(line); buf_chars += len(line)
            if buf:
                ct = "\n".join(buf)
                cid = hashlib.md5(ct.encode()).hexdigest()[:12]
                chunks.append({"id": f"sec{i:02d}_s{sub:02d}_{cid}", "text": ct, "title": title, "idx": i})
    return chunks

print("=" * 50)
print("  MPS 지식 -> Firestore 업로드")
print("=" * 50)

with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
    text = f.read()
print(f"\n[1/3] 로드 완료: {len(text):,} 글자")

chunks = chunk_text(text)
print(f"[2/3] 청킹 완료: {len(chunks)}개")

from google.cloud import firestore
db = firestore.Client(project=GCP_PROJECT)
col = db.collection(FS_COLLECTION)

for doc in col.stream():
    doc.reference.delete()

col.document("_meta").set({
    "total_chunks": len(chunks),
    "source_file": KNOWLEDGE_FILE,
    "updated_at": datetime.now(timezone.utc),
    "version": "2.0",
    "total_chars": len(text)
})

batch = db.batch()
for i, chunk in enumerate(chunks):
    batch.set(col.document(chunk["id"]), {
        "text": chunk["text"],
        "section_title": chunk["title"],
        "section_idx": chunk["idx"],
        "char_count": len(chunk["text"]),
        "uploaded_at": datetime.now(timezone.utc),
    })
    if (i + 1) % 400 == 0:
        batch.commit(); batch = db.batch()
        print(f"  {i+1}/{len(chunks)} 저장...")
batch.commit()

print(f"[3/3] 완료: {len(chunks)}개 청크 -> Firestore")
print(f"\n✅ 업로드 성공!")
print(f"   프로젝트: {GCP_PROJECT}")
print(f"   컬렉션: {FS_COLLECTION}")
