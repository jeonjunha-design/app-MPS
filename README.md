# 🏥 근막통증증후군(MPS) AI 처방 시스템

## 아키텍처
```
[사용자] → [Streamlit UI]
               ↓
         [FastAPI 백엔드]
           ↙         ↘
  [ChromaDB RAG]   [Ollama llama3]
  (로컬 벡터 캐시)  (한국어 처방 생성)
       ↑                  ↓
  [Firestore]       [Firestore 상담 로그]
  (지식 원본)
       ↑
  [Cloud Storage]
  (임베딩 벡터)
```

## 파일 구조
```
app-MPS/
├── mps_knowledge_base.txt  ← 전문 지식 원본 (GitHub 관리)
├── cloud_upload.py         ← 지식 → Firestore/GCS 업로드
├── setup_rag.py            ← 로컬 ChromaDB 구축 (오프라인용)
├── main.py                 ← FastAPI 백엔드
├── app.py                  ← Streamlit 웹 UI
├── requirements.txt
├── start.sh                ← 원클릭 실행
├── git_setup.sh            ← GitHub 초기 설정
├── .env.example            ← 환경 변수 템플릿 (GitHub 공개)
├── .env                    ← 실제 환경 변수 (GitHub 비공개)
└── .gitignore
```

## 처음 설치 (순서대로)

```bash
# 1. 저장소 클론
git clone https://github.com/jeonjunha-design/app-MPS.git
cd app-MPS

# 2. 가상환경
python3 -m venv venv
source venv/bin/activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 실제 값 입력

# 5. 지식 → Google Cloud 업로드 (최초 1회)
python cloud_upload.py

# 6. Ollama 모델 준비
ollama pull llama3

# 7. 실행
./start.sh
```

## 지식 데이터 업데이트

```bash
# mps_knowledge_base.txt 수정 후
python cloud_upload.py      # Firestore + GCS 업데이트
# 서버 실행 중이면 /sync-from-cloud 엔드포인트 호출
```

## GitHub 작업 흐름

```bash
# 코드 수정 후
git add .
git commit -m "feat: 기능 설명"
git push

# 지식 데이터 업데이트 후
python cloud_upload.py
git add mps_knowledge_base.txt
git commit -m "data: 지식 베이스 업데이트"
git push
```

## 참고 자료
- Travell & Simons' Myofascial Pain and Dysfunction Manual
- Cleveland Clinic MPS Guidelines
- IASP Pain Management Standards 2024
- PubMed Meta-Analysis: Needling for MPS (2024)
