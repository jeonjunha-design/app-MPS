#!/bin/bash
# =====================================================
#  GitHub 저장소 초기 설정 스크립트
#  사용법: chmod +x git_setup.sh && ./git_setup.sh
# =====================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========================================"
echo "  🐙 GitHub 저장소 설정"
echo "========================================"

# ── GitHub 저장소 URL 입력 ────────────────────────────────
echo ""
echo "GitHub 저장소 URL을 입력하세요."
echo "예시: https://github.com/jeonjunha-design/app-MPS.git"
read -p "URL: " GITHUB_URL

if [ -z "$GITHUB_URL" ]; then
    echo "❌ URL이 입력되지 않았습니다."
    exit 1
fi

# ── Git 초기화 ────────────────────────────────────────────
echo ""
echo "[1/5] Git 초기화..."
if [ ! -d ".git" ]; then
    git init
    echo "  git init 완료"
else
    echo "  이미 초기화된 저장소"
fi

# ── .env 파일 생성 확인 ───────────────────────────────────
echo ""
echo "[2/5] .env 파일 확인..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env.example → .env 복사 완료"
    echo "  ⚠  .env 파일에 실제 값을 입력하세요!"
else
    echo "  .env 파일 이미 존재"
fi

# ── 첫 커밋 ──────────────────────────────────────────────
echo ""
echo "[3/5] 첫 커밋 준비..."
git add \
    mps_knowledge_base.txt \
    setup_rag.py \
    cloud_upload.py \
    main.py \
    app.py \
    requirements.txt \
    start.sh \
    git_setup.sh \
    .gitignore \
    .env.example \
    README.md

git status --short

git commit -m "feat: MPS AI 처방 시스템 v2.1 초기 설정

- 지식 데이터: mps_knowledge_base.txt (9개 섹션, 10개 부위)
- 벡터 DB: ChromaDB (RAG 로컬 캐시)
- 클라우드: Google Firestore + Cloud Storage
- 백엔드: FastAPI + Ollama llama3
- 프론트엔드: Streamlit
- 업로드 스크립트: cloud_upload.py" 2>/dev/null || \
git commit --allow-empty -m "feat: MPS AI 처방 시스템 v2.1 초기 설정"

# ── 원격 저장소 연결 ──────────────────────────────────────
echo ""
echo "[4/5] 원격 저장소 연결..."
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$GITHUB_URL"
    echo "  origin URL 업데이트"
else
    git remote add origin "$GITHUB_URL"
    echo "  origin 추가"
fi

# ── Push ─────────────────────────────────────────────────
echo ""
echo "[5/5] GitHub에 Push..."
git branch -M main
git push -u origin main

echo ""
echo "========================================"
echo "  ✅ GitHub 설정 완료!"
echo "  🔗 $GITHUB_URL"
echo ""
echo "  앞으로 코드 변경 후:"
echo "  git add ."
echo "  git commit -m '변경 내용 설명'"
echo "  git push"
echo "========================================"
