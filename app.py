import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="MPS AI 처방 시스템", page_icon="🏥", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    padding: 1.5rem; border-radius: 12px; color: white; text-align: center; margin-bottom: 1.5rem;
}
.warning-card {
    background: #fff8e1; border-left: 4px solid #f0a500;
    padding: 0.8rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0;
    color: #333333;
}
.expert-card {
    background: #e8f4fd; border-left: 4px solid #2d6a9f;
    padding: 1rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.95rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏥 근막통증증후군(MPS) AI 처방 시스템</h1>
    <p>증상을 입력하면 임상 가이드라인 기반 맞춤 처방을 제공합니다</p>
</div>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

# 사이드바
with st.sidebar:
    st.header("⚙️ 시스템 상태")
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        h = r.json()
        st.success("✅ 서버 연결됨")
        st.caption(f"Ollama: {'✅' if h['ollama']['running'] else '❌'} {', '.join(h['ollama']['models'])}")
        st.caption(f"ChromaDB: {'✅' if h['chroma_db']['ready'] else '❌'}")
        st.caption(f"Firestore: {'✅' if h['firestore']['connected'] else '❌'} ({h['firestore']['knowledge_chunks']}개 청크)")
    except:
        st.error("❌ 서버 연결 실패")

    st.divider()
    st.subheader("📚 참고 자료")
    st.caption("• Travell & Simons' Trigger Point Manual")
    st.caption("• APTA Neck Pain CPG 2017")
    st.caption("• Canadian Physiotherapy Association")
    st.caption("• NIH StatPearls 2025")
    st.caption("• PubMed Meta-Analysis 2023-2025")
    st.caption("• Frontiers in Physiology 2026")

# 전문가 상담 고지
# 입력 폼
st.subheader("📋 증상 입력")

col1, col2 = st.columns([1, 1])
with col1:
    part = st.text_input("🎯 통증 부위", placeholder="예: 목, 어깨 / 허리 / 무릎 / 발바닥 등 자유롭게 입력")
    level = st.slider("😣 통증 강도 (1=미약 / 10=극심)", 1, 10, 5)
    duration = st.selectbox("📅 지속 기간",
        ["오늘 발생", "2~3일", "1주일", "2~4주", "1~3개월", "3개월 이상 (만성)"])

with col2:
    symptoms = st.text_area("📝 증상 상세 설명",
        placeholder="예: 뒷목이 뻐근하고 두통이 있어요\n예: 오른쪽 어깨가 결리고 팔이 저려요\n예: 허리가 끊어질 것 같고 앉았다 일어나기 힘들어요",
        height=120)
    occupation = st.text_input("💼 직업 / 주요 활동 (선택)", placeholder="예: 사무직, 간호사, 학생, 택배기사...")
    aggravating = st.text_input("📈 악화 요인 (선택)", placeholder="예: 오래 앉아있을 때, 스트레스 받을 때...")
    relieving = st.text_input("📉 완화 요인 (선택)", placeholder="예: 온찜질 후, 누웠을 때...")

if st.button("🔍 AI 맞춤 루틴 생성하기", type="primary", use_container_width=True):
    if not symptoms.strip():
        st.warning("증상 설명을 입력해주세요.")
    elif not part.strip():
        st.warning("통증 부위를 입력해주세요.")
    else:
        with st.spinner("🤖 전문 지식을 검색하고 처방을 생성 중입니다... (1~2분 소요)"):
            try:
                payload = {
                    "body_part": part, "symptoms": symptoms,
                    "pain_level": level, "duration": duration,
                    "occupation": occupation or None,
                    "aggravating": aggravating or None,
                    "relieving": relieving or None
                }
                response = requests.post(f"{API_URL}/prescription", json=payload, timeout=180)

                if response.status_code == 200:
                    data = response.json()
                    st.success("✅ 처방이 생성되었습니다!")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("통증 부위", data["body_part"])
                    m2.metric("통증 강도", f"{data['pain_level']}/10")
                    m3.metric("참조 지식", f"{data['rag_chunks_used']}개 섹션")

                    st.markdown("---")
                    st.subheader("📄 맞춤 처방")
                    st.markdown(data["prescription"])

                    # 전문가 상담 고지
                    # 출처 (접기)
                    with st.expander("📚 참고 자료 출처"):
                        st.write("**전문 서적**")
                        st.write("- Travell & Simons' Myofascial Pain and Dysfunction: The Trigger Point Manual (1999)")
                        st.write("- Hoppenfeld, S. Physical Examination of the Spine and Extremities (1976)")
                        st.write("- Clay & Pounds. Basic Clinical Massage Therapy, 2nd Ed. LWW (2008)")
                        st.write("")
                        st.write("**임상 가이드라인**")
                        st.write("- APTA Neck Pain Clinical Practice Guidelines 2017")
                        st.write("- Canadian Physiotherapy Association (CPA) Guidelines")
                        st.write("- IASP Pain Management Standards 2024")
                        st.write("")
                        st.write("**PubMed 논문 (2023-2025)**")
                        st.write("- Dua & Chang. Myofascial Pain Syndrome. StatPearls NIH 2025")
                        st.write("- Simati et al. Multimodal Physiotherapy for Cervical MPS. Cureus 2025")
                        st.write("- Anwar et al. Treatment of MPS. Medicine 2024")
                        st.write("- He et al. Therapeutic Physical Modalities on MPS. BMC Musculoskeletal Disorders 2023")
                        st.write("- Needling trigger points for MPS: Meta-analysis. ScienceDirect 2025")
                        st.write("- Bau et al. Myofascial Treatment for Microcirculation. Diagnostics 2021")
                        st.write("- Frontiers in Physiology. Myofascial Release Mechanisms 2026")

                    # 다운로드
                    full_text = f"""MPS AI 처방 결과
생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}
통증 부위: {data['body_part']} | 강도: {data['pain_level']}/10 | 기간: {duration}
증상: {symptoms}
직업: {occupation or '미입력'}

처방 내용:
{data['prescription']}

⚠️ 본 처방은 참고용이며 의학적 진단을 대체하지 않습니다.
정확한 진단과 치료는 물리치료사, 재활의학과, 정형외과 전문의와 상담하시기 바랍니다.
"""
                    st.download_button(
                        "📥 처방전 다운로드",
                        full_text,
                        file_name=f"MPS처방_{part}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain"
                    )

                elif response.status_code == 503:
                    st.error("❌ Ollama가 실행되지 않았습니다. Ollama 앱을 실행하세요.")
                else:
                    st.error(f"서버 오류 ({response.status_code})")

            except requests.exceptions.ConnectionError:
                st.error("❌ 백엔드 서버에 연결할 수 없습니다. uvicorn main:app --reload 실행하세요.")
            except requests.exceptions.Timeout:
                st.warning("⏳ 응답 시간 초과. 다시 시도하세요.")

st.divider()
st.caption("📖 출처: Travell & Simons | APTA CPG 2017 | CPA | NIH StatPearls 2025 | PubMed 2023-2025")
st.caption("⚠️ 본 시스템은 교육·참고 목적이며 의학적 진단 및 치료를 대체하지 않습니다.")
