import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="MPS 도수치료 시스템", page_icon="🏥", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    padding: 1.2rem; border-radius: 12px; color: white;
    text-align: center; margin-bottom: 1.5rem;
}
.expert-card {
    background: #155724; border-left: 4px solid #28a745;
    padding: 0.8rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0;
    color: #ffffff;
}
.soap-label {
    font-weight: bold; color: #1e3a5f;
    font-size: 1.1rem; margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏥 MPS 도수치료 처방 시스템</h1>
    <p>AI 맞춤 처방 · 도수치료 차트 작성</p>
</div>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

with st.sidebar:
    st.header("⚙️ 시스템 상태")
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        h = r.json()
        st.success("✅ 서버 연결됨")
        st.caption(f"AI 모델: {', '.join(h['ollama']['models'])}")
        st.caption(f"지식 청크: {h['firestore']['knowledge_chunks']}개")
    except:
        st.error("❌ 서버 연결 실패")
    st.divider()
    st.caption("📖 Travell & Simons | APTA 2017 | CPA | NIH 2025")

tab2, tab1 = st.tabs(["📋 도수치료 차트", "🤖 AI 맞춤 처방"])

with tab1:
    st.markdown("""
    <div class="expert-card">
    🩺 <strong>전문가 상담 안내:</strong> 본 시스템은 참고용입니다.
    정확한 진단과 치료를 위해 반드시 의사에게 진료 및 처방을 받으시고, 의사와 물리치료사의 지도에 따라 치료를 진행하시기 바랍니다.
    </div>
    """, unsafe_allow_html=True)
    st.subheader("📋 증상 입력")
    col1, col2 = st.columns([1, 1])
    with col1:
        part = st.text_input("🎯 통증 부위", placeholder="예: 목, 어깨 / 허리 / 손가락 / 무릎")
        level = st.slider("😣 통증 강도 (1=미약 / 10=극심)", 1, 10, 5)
        duration = st.selectbox("📅 지속 기간", ["오늘 발생", "2~3일", "1주일", "2~4주", "1~3개월", "3개월 이상 (만성)"])
    with col2:
        symptoms = st.text_area("📝 증상 설명", placeholder="예: 뒷목이 뻐근하고 두통이 있어요", height=100)
        occupation = st.text_input("💼 직업 (선택)", placeholder="예: 사무직, 간호사, 학생...")
        aggravating = st.text_input("📈 악화 요인 (선택)", placeholder="예: 오래 앉아있을 때...")
        relieving = st.text_input("📉 완화 요인 (선택)", placeholder="예: 온찜질 후...")
    if st.button("🔍 AI 맞춤 루틴 생성하기", type="primary", use_container_width=True):
        if not symptoms.strip() or not part.strip():
            st.warning("통증 부위와 증상 설명을 입력해주세요.")
        else:
            with st.spinner("🤖 처방 생성 중... (1~2분 소요)"):
                try:
                    payload = {"body_part": part, "symptoms": symptoms, "pain_level": level, "duration": duration, "occupation": occupation or None, "aggravating": aggravating or None, "relieving": relieving or None}
                    response = requests.post(f"{API_URL}/prescription", json=payload, timeout=180)
                    if response.status_code == 200:
                        data = response.json()
                        st.success("✅ 처방이 생성되었습니다!")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("통증 부위", data["body_part"])
                        m2.metric("통증 강도", f"{data['pain_level']}/10")
                        m3.metric("참조 지식", f"{data['rag_chunks_used']}개 섹션")
                        st.markdown("---")
                        st.markdown(data["prescription"])
                        st.markdown('<div class="expert-card">🩺 <strong>전문가 상담을 권장합니다</strong><br>위 내용은 참고용입니다. 정확한 진단과 치료를 위해 반드시 의사에게 진료 및 처방을 받으시고, 의사와 물리치료사의 지도에 따라 치료를 진행하시기 바랍니다.</div>', unsafe_allow_html=True)
                        with st.expander("📚 참고 자료 출처"):
                            st.write("- Travell & Simons' Myofascial Pain and Dysfunction (1999)")
                            st.write("- Hoppenfeld. Physical Examination of the Spine and Extremities (1976)")
                            st.write("- APTA Neck Pain CPG 2017 | CPA Guidelines | NIH StatPearls 2025")
                        full_text = f"MPS AI 처방 결과\n생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n통증 부위: {data['body_part']} | 강도: {data['pain_level']}/10\n\n{data['prescription']}"
                        st.download_button("📥 처방전 다운로드", full_text, file_name=f"MPS처방_{part}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain")
                    else:
                        st.error(f"서버 오류 ({response.status_code})")
                except requests.exceptions.ConnectionError:
                    st.error("❌ 백엔드 서버에 연결할 수 없습니다.")
                except requests.exceptions.Timeout:
                    st.warning("⏳ 응답 시간 초과.")

with tab2:
    col_title, col_search = st.columns([3, 2])
    with col_title:
        col_title, col_search = st.columns([2, 3])
    with col_title:
        st.subheader("📋 도수치료 SOAP 차트")
    with col_search:
        search_q = st.text_input("🔍 환자명 또는 차트번호 입력 후 Enter",
            placeholder="예: 홍길동  또는  0001", key="chart_pt_search")
        if search_q:
            try:
                res = requests.get(f"{API_URL}/chart/search",
                    params={"q": search_q}, timeout=5).json()
                if res.get("results"):
                    pt_options = [
                        f"{r['pt_name']} (차트:{r.get('chart_no','')}) 최근:{r.get('last_visit','')} [{r.get('source','')}]"
                        for r in res["results"]
                    ]
                    selected = st.selectbox("검색 결과", pt_options, key="chart_pt_select")
                    if st.button("📂 차트 불러오기", key="chart_load_btn", type="primary"):
                        idx = pt_options.index(selected)
                        pt_key = res["results"][idx]["pt_key"]
                        load_res = requests.get(f"{API_URL}/chart/load/{pt_key}", timeout=5).json()
                        if load_res.get("sessions"):
                            st.session_state["loaded_chart"] = load_res["sessions"]
                            st.session_state["loaded_pt_key"] = pt_key
                            # 최근 session의 soap_json으로 입력란 채우기
                            latest = load_res["sessions"][0]
                            sj = latest.get("soap_json", {})
                            if sj:
                                st.session_state["af_nrs_now"] = int(sj.get("nrs_now", 5))
                                st.session_state["af_nrs_worst"] = int(sj.get("nrs_worst", 7))
                                st.session_state["af_nrs_best"] = int(sj.get("nrs_best", 2))
                                st.session_state["af_duration"] = sj.get("duration", "오늘 발생")
                                st.session_state["af_pain_quality"] = sj.get("pain_quality", [])
                                st.session_state["af_complaint"] = sj.get("complaint", "")
                                st.session_state["af_aggravating"] = sj.get("aggravating", "")
                                st.session_state["af_relieving"] = sj.get("relieving", "")
                                st.session_state["af_adl"] = sj.get("adl", "")
                                st.session_state["af_posture_fhp"] = sj.get("posture_fhp", "없음")
                                st.session_state["af_posture_shoulder"] = sj.get("posture_shoulder", "좌우 대칭")
                                st.session_state["af_posture_pelvis_lr"] = sj.get("posture_pelvis_lr", "좌우 대칭")
                                st.session_state["af_posture_pelvis_fb"] = sj.get("posture_pelvis_fb", "정상")
                                st.session_state["af_posture_spine"] = sj.get("posture_spine", "없음")
                                st.session_state["af_posture_etc"] = sj.get("posture_etc", "")
                                st.session_state["af_trp_neck"] = sj.get("trp_neck", [])
                                st.session_state["af_trp_shoulder"] = sj.get("trp_shoulder", [])
                                st.session_state["af_trp_lower"] = sj.get("trp_lower", [])
                                st.session_state["af_trp_etc"] = sj.get("trp_etc", "")
                                st.session_state["af_trp_referred"] = sj.get("trp_referred", "")
                                st.session_state["af_diagnosis"] = sj.get("diagnosis", "")
                                st.session_state["af_problem"] = sj.get("problem", "")
                                st.session_state["af_cause"] = sj.get("cause", "")
                                st.session_state["af_home_program"] = sj.get("home_program", "")
                                st.session_state["af_next_visit"] = sj.get("next_visit", "")
                                st.session_state["af_note"] = sj.get("note", "")
                                st.session_state["af_pt_therapist"] = sj.get("pt_therapist", "")
                                st.session_state["af_pt_dx"] = sj.get("pt_dx", "")
                                st.session_state["af_aggravating"] = sj.get("aggravating","")
                                st.session_state["af_relieving"] = sj.get("relieving","")
                                st.session_state["af_adl"] = sj.get("adl","")
                                st.session_state["af_posture_etc"] = sj.get("posture_etc","")
                                st.session_state["af_trp_referred"] = sj.get("trp_referred","")
                                st.session_state["af_trp_etc"] = sj.get("trp_etc","")
                                st.session_state["af_diagnosis"] = sj.get("diagnosis","")
                                st.session_state["af_problem"] = sj.get("problem","")
                                st.session_state["af_cause"] = sj.get("cause","")
                                st.session_state["af_home_program"] = sj.get("home_program","")
                                st.session_state["af_next_visit"] = sj.get("next_visit","")
                                st.session_state["af_note"] = sj.get("note","")
                                st.session_state["af_pt_therapist"] = sj.get("pt_therapist","")
                                st.session_state["af_pt_dx"] = sj.get("pt_dx","")
                                st.session_state["af_loaded_key"] = f"{latest.get('pt_name','')}_{latest.get('pt_date','')}"
                            st.rerun()
                else:
                    st.warning("검색 결과가 없습니다.")
            except Exception as e:
                st.error(f"검색 오류: {e}")

    # 불러온 차트 목록 표시
    if st.session_state.get("loaded_chart"):
        sessions = st.session_state["loaded_chart"]
        pt_name_loaded = sessions[0].get("pt_name","") if sessions else ""
        st.markdown(f"---")
        st.markdown(f"### 📁 {pt_name_loaded} 님 차트 ({len(sessions)}회차)")
        for i, session in enumerate(sessions):
            date_str = session.get("pt_date","")
            session_no = session.get("pt_session","")
            dx = session.get("pt_dx","")
            therapist = session.get("pt_therapist","")
            source = "☁️ 클라우드" if session.get("source") == "cloud" else "💾 로컬"
            with st.expander(f"📅 {date_str}  |  {session_no}회차  |  {dx}  |  {therapist}  {source}"):
                st.text(session.get("chart_content",""))
                c1, c2 = st.columns(2)
                with c1:
                    c_dl, c_del = st.columns(2)
                    with c_dl:
                        st.download_button(
                            "🖨️ 인쇄용 다운로드",
                            session.get("chart_content",""),
                            file_name=f"차트_{pt_name_loaded}_{date_str}_{session_no}회차.txt",
                            mime="text/plain",
                            key=f"print_{i}_{id(session)}"
                        )
                    with c_del:
                        if st.button("🗑️ 삭제", key=f"del_{i}_{id(session)}", type="secondary"):
                            try:
                                import os as _os
                                os_environ = _os.environ.copy()
                                os_environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/juna/mps-key.json'
                                del_res = requests.delete(
                                    f"{API_URL}/chart/delete",
                                    json={"pt_key": st.session_state.get('loaded_pt_key',''),
                                          "session_key": f"{date_str}_{int(session_no):03d}"},
                                    timeout=5
                                )
                                st.session_state["loaded_chart"] = None
                                st.success("삭제 완료!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
        if st.button("❌ 닫기", key="chart_close_btn"):
            del st.session_state["loaded_chart"]
            st.rerun()
        st.markdown("---")
    with col_search:
        search_q = st.text_input("🔍 환자명/차트번호 검색 후 Enter",
            placeholder="예: 홍길동 또는 0001", key="chart_pt_search2")
        if search_q:
            try:
                res = requests.get(f"{API_URL}/chart/search", params={"q": search_q}, timeout=5).json()
                if res["results"]:
                    st.success(f"{len(res['results'])}명 검색됨")
                    selected = st.selectbox("환자 선택",
                        [f"{r['pt_name']} ({r.get('chart_no','')}) - 최근:{r.get('last_visit','')}" for r in res["results"]],
                        key="chart_pt_select")
                    if st.button("📂 불러오기", key="chart_load_btn"):
                        idx = [f"{r['pt_name']} ({r.get('chart_no','')}) - 최근:{r.get('last_visit','')}" for r in res["results"]].index(selected)
                        pt_key = res["results"][idx]["pt_key"]
                        load_res = requests.get(f"{API_URL}/chart/load/{pt_key}", timeout=5).json()
                        if load_res["sessions"]:
                            st.session_state["loaded_chart"] = load_res["sessions"]
                            st.session_state["loaded_pt_key"] = pt_key
                            st.rerun()
                else:
                    st.warning("검색 결과 없음")
            except:
                st.error("서버 연결 오류")

    with st.expander("👤 환자 기본 정보", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pt_chart_no = st.text_input("차트번호",
                key="input_chart_no",
                on_change=None,
                placeholder="입력 후 Enter")
            pt_name = st.text_input("환자명",
                key="input_pt_name",
                placeholder="입력 후 Enter")

            # 차트번호 또는 환자명 입력 시 자동 불러오기
            auto_search = pt_chart_no.strip() or pt_name.strip()
            if auto_search and auto_search != st.session_state.get("last_auto_search"):
                st.session_state["last_auto_search"] = auto_search
                try:
                    import requests as _req
                    res = _req.get(f"{API_URL}/chart/search",
                        params={"q": auto_search}, timeout=3).json()
                    if res.get("results"):
                        # 가장 최근 환자 데이터 자동 로드
                        pt_key = res["results"][0]["pt_key"]
                        load_res = _req.get(f"{API_URL}/chart/load/{pt_key}", timeout=3).json()
                        if load_res.get("sessions"):
                            latest = load_res["sessions"][0]
                            st.session_state["auto_loaded"] = latest
                            st.session_state["loaded_chart"] = load_res["sessions"]
                except:
                    pass

            # 자동 불러온 데이터 알림
            if st.session_state.get("auto_loaded"):
                latest = st.session_state["auto_loaded"]
                st.success(f"✅ {latest.get('pt_name')} 최근 기록 불러옴 ({latest.get('pt_date')})")
                # soap_json에서 값 복원
                sj = latest.get("soap_json", {})
                if sj:
                    already_set = st.session_state.get("af_loaded_key","")
                    current_key = f"{latest.get('pt_name','')}_{latest.get('pt_date','')}"
                    if already_set != current_key:
                        st.session_state["af_nrs_now"] = int(sj.get("nrs_now", 5))
                        st.session_state["af_nrs_worst"] = int(sj.get("nrs_worst", 7))
                        st.session_state["af_nrs_best"] = int(sj.get("nrs_best", 2))
                        st.session_state["af_duration"] = sj.get("duration", "오늘 발생")
                        st.session_state["af_pain_quality"] = sj.get("pain_quality", [])
                        st.session_state["af_complaint"] = sj.get("complaint", "")
                        st.session_state["af_aggravating"] = sj.get("aggravating", "")
                        st.session_state["af_relieving"] = sj.get("relieving", "")
                        st.session_state["af_adl"] = sj.get("adl", "")
                        st.session_state["af_posture_fhp"] = sj.get("posture_fhp", "없음")
                        st.session_state["af_posture_shoulder"] = sj.get("posture_shoulder", "좌우 대칭")
                        st.session_state["af_posture_pelvis_lr"] = sj.get("posture_pelvis_lr", "좌우 대칭")
                        st.session_state["af_posture_pelvis_fb"] = sj.get("posture_pelvis_fb", "정상")
                        st.session_state["af_posture_spine"] = sj.get("posture_spine", "없음")
                        st.session_state["af_posture_etc"] = sj.get("posture_etc", "")
                        st.session_state["af_trp_neck"] = sj.get("trp_neck", [])
                        st.session_state["af_trp_shoulder"] = sj.get("trp_shoulder", [])
                        st.session_state["af_trp_lower"] = sj.get("trp_lower", [])
                        st.session_state["af_trp_etc"] = sj.get("trp_etc", "")
                        st.session_state["af_trp_referred"] = sj.get("trp_referred", "")
                        st.session_state["af_diagnosis"] = sj.get("diagnosis", "")
                        st.session_state["af_problem"] = sj.get("problem", "")
                        st.session_state["af_cause"] = sj.get("cause", "")
                        st.session_state["af_home_program"] = sj.get("home_program", "")
                        st.session_state["af_next_visit"] = sj.get("next_visit", "")
                        st.session_state["af_note"] = sj.get("note", "")
                        st.session_state["af_pt_therapist"] = sj.get("pt_therapist", "")
                        st.session_state["af_pt_dx"] = sj.get("pt_dx", "")
                        st.session_state["af_loaded_key"] = current_key
                        st.rerun()
        with c2:
            pt_age = st.number_input("나이", min_value=1, max_value=120, value=40)
            pt_gender = st.selectbox("성별", ["남", "여"])
        with c3:
            pt_date = st.date_input("치료일", datetime.now())
            pt_session = st.number_input("회차", min_value=1, value=1)
        with c4:
            pt_therapist = st.text_input("치료사", key="af_pt_therapist")
            pt_dx = st.text_input("진단명", key="af_pt_dx", placeholder="예: 경추 MPS")
    st.divider()
    st.markdown('<div class="soap-label">S - 주관적 소견 (Subjective)</div>', unsafe_allow_html=True)
    s_complaint = st.text_input("주호소", key="af_complaint", placeholder="예: 우측 목/어깨 통증, 두통")
    c1, c2, c3 = st.columns(3)
    with c1:
        s_nrs_now = st.slider("현재 NRS", 0, 10, int(st.session_state.get("af_nrs_now", 5)))
    with c2:
        s_nrs_worst = st.slider("최악 NRS", 0, 10, int(st.session_state.get("af_nrs_worst", 7)))
    with c3:
        s_nrs_best = st.slider("최선 NRS", 0, 10, int(st.session_state.get("af_nrs_best", 2)))
    _dur_opts = ["오늘 발생", "2~3일", "1주일", "2~4주", "1~3개월", "3개월 이상"]
    _dur_v = st.session_state.get("af_duration", "오늘 발생")
    _dur_idx = _dur_opts.index(_dur_v) if _dur_v in _dur_opts else 0
    s_duration = st.selectbox("지속 기간", _dur_opts, index=_dur_idx, key="s_duration")
    st.write("**통증 양상** (해당되는 것 모두 선택)")
    pain_quality = st.multiselect("통증 양상 선택",
        ["아프다 (통증)", "저린다 (저림)", "쑤신다 (심부통)", "멍멍한 느낌이다",
         "타는 듯하다 (작열감)", "찌르는 듯하다 (자통)", "당긴다 (긴장감)",
         "뻐근하다 (둔통)", "시큰거린다", "감각이 없다 (무감각)",
         "전기 오는 느낌이다 (방전감)", "무겁다 (중압감)", "욱신거린다 (박동통)",
         "칼로 베는 느낌이다 (예리한 통증)", "기타"],
        default=st.session_state.get("af_pain_quality", []))
    pain_quality_etc = st.text_input("기타 통증 양상 직접 입력", placeholder="예: 바늘로 찌르는 느낌, 모래가 들어간 느낌")
    s_aggravating = st.text_input("악화 요인", key="af_aggravating", placeholder="예: 오래 앉아있을 때, 고개 돌릴 때")
    s_relieving = st.text_input("완화 요인", key="af_relieving", placeholder="예: 온찜질 후, 누웠을 때")
    s_adl = st.text_area("일상생활 장애", key="af_adl", placeholder="예: 컴퓨터 작업 30분 이상 어려움, 수면 장애", height=60)
    st.divider()
    st.markdown('<div class="soap-label">O - 객관적 소견 (Objective)</div>', unsafe_allow_html=True)
    st.write("**자세 평가**")
    c1, c2, c3 = st.columns(3)
    with c1:
        o_fhp = st.selectbox("전방 두부 자세", ["없음", "+1cm", "+2cm", "+3cm 이상"])
        o_shoulder = st.selectbox("어깨 높이", ["좌우 대칭", "우측 하강", "좌측 하강"])
    with c2:
        o_pelvis_lr = st.selectbox("골반 좌우 경사", ["좌우 대칭", "우측 하강 (좌측 상승)", "좌측 하강 (우측 상승)"])
        o_pelvis_fb = st.selectbox("골반 전후 경사", ["정상", "전방 경사 (anterior tilt)", "후방 경사 (posterior tilt)"])
    with c3:
        o_spine = st.selectbox("척추 측만", ["없음", "우측 만곡", "좌측 만곡", "S자형"])
        o_posture_etc = st.text_input("기타 자세 소견", key="af_posture_etc")
    st.write("**관절 가동범위 (ROM)**")
    rom_area = st.selectbox("측정 부위", ["경추", "흉추", "요추", "어깨(견관절)", "팔꿈치", "손목", "고관절", "무릎", "발목"])
    if rom_area == "경추":
        c1, c2, c3 = st.columns(3)
        with c1:
            rf = st.number_input("굴곡 (정상 45°)", 0, 90, 40)
            re = st.number_input("신전 (정상 55°)", 0, 90, 45)
        with c2:
            rlf = st.number_input("좌측굴 (정상 40°)", 0, 60, 35)
            rrf = st.number_input("우측굴 (정상 40°)", 0, 60, 35)
        with c3:
            rlr = st.number_input("좌회전 (정상 70°)", 0, 90, 60)
            rrr = st.number_input("우회전 (정상 70°)", 0, 90, 60)
        rom_text = f"굴곡 {rf}°/ 신전 {re}°/ 좌측굴 {rlf}°/ 우측굴 {rrf}°/ 좌회전 {rlr}°/ 우회전 {rrr}°"
    elif rom_area == "요추":
        c1, c2, c3 = st.columns(3)
        with c1:
            rf = st.number_input("굴곡 (정상 75°)", 0, 90, 60)
            re = st.number_input("신전 (정상 30°)", 0, 60, 25)
        with c2:
            rlf = st.number_input("좌측굴 (정상 35°)", 0, 60, 30)
            rrf = st.number_input("우측굴 (정상 35°)", 0, 60, 30)
        with c3:
            rlr = st.number_input("좌회전 (정상 30°)", 0, 60, 25)
            rrr = st.number_input("우회전 (정상 30°)", 0, 60, 25)
        rom_text = f"굴곡 {rf}°/ 신전 {re}°/ 좌측굴 {rlf}°/ 우측굴 {rrf}°/ 좌회전 {rlr}°/ 우회전 {rrr}°"
    elif rom_area == "어깨(견관절)":
        c1, c2, c3 = st.columns(3)
        with c1:
            ra = st.number_input("외전 (정상 180°)", 0, 180, 160)
            rf2 = st.number_input("굴곡 (정상 180°)", 0, 180, 160)
        with c2:
            rer = st.number_input("외회전 (정상 90°)", 0, 90, 70)
            rir = st.number_input("내회전 (정상 90°)", 0, 90, 70)
        with c3:
            re2 = st.number_input("신전 (정상 45°)", 0, 60, 40)
        rom_text = f"외전 {ra}°/ 굴곡 {rf2}°/ 외회전 {rer}°/ 내회전 {rir}°/ 신전 {re2}°"
    else:
        rom_text = st.text_area("ROM 직접 입력", placeholder="예: 굴곡 130°/ 신전 10°/ 외전 40°", height=60)
    st.write("**근력 검사**")
    c1, c2 = st.columns(2)
    with c1:
        ms_left = st.selectbox("좌측 근력", ["5/5 (정상)", "4/5 (양호)", "3/5 (보통)", "2/5 (불량)", "1/5 (미약)", "0/5 (없음)"])
    with c2:
        ms_right = st.selectbox("우측 근력", ["5/5 (정상)", "4/5 (양호)", "3/5 (보통)", "2/5 (불량)", "1/5 (미약)", "0/5 (없음)"])
    st.write("**트리거 포인트 (TrP) 압통 부위**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.write("🔵 목/어깨")
        trp_neck = st.multiselect("목/어깨 근육",
            ["상부 승모근 우", "상부 승모근 좌", "중부 승모근 우", "중부 승모근 좌",
             "하부 승모근 우", "하부 승모근 좌", "견갑거근 우", "견갑거근 좌",
             "흉쇄유돌근 우", "흉쇄유돌근 좌", "사각근 우", "사각근 좌",
             "후두하근 우", "후두하근 좌", "반극근 우", "반극근 좌",
             "경장근 우", "경장근 좌"], default=st.session_state.get("af_trp_neck",[]), key="trp_neck")
    with col_b:
        st.write("🔵 어깨/등/팔")
        trp_shoulder = st.multiselect("어깨/등/팔 근육",
            ["극상근 우", "극상근 좌", "극하근 우", "극하근 좌",
             "소원근 우", "소원근 좌", "견갑하근 우", "견갑하근 좌",
             "능형근 우", "능형근 좌", "전거근 우", "전거근 좌",
             "대흉근 우", "대흉근 좌", "소흉근 우", "소흉근 좌",
             "광배근 우", "광배근 좌", "삼각근 우", "삼각근 좌",
             "이두근 우", "이두근 좌", "삼두근 우", "삼두근 좌",
             "전완 신전근 우", "전완 신전근 좌", "전완 굴근 우", "전완 굴근 좌"], default=st.session_state.get("af_trp_shoulder",[]), key="trp_shoulder")
    with col_c:
        st.write("🔵 허리/하지")
        trp_lower = st.multiselect("허리/하지 근육",
            ["요방형근 우", "요방형근 좌", "장요근 우", "장요근 좌",
             "다열근 우", "다열근 좌", "척추기립근 우", "척추기립근 좌",
             "이상근 우", "이상근 좌", "대둔근 우", "대둔근 좌",
             "중둔근 우", "중둔근 좌", "소둔근 우", "소둔근 좌",
             "대퇴사두근 우", "대퇴사두근 좌", "슬괵근 우", "슬괵근 좌",
             "장경인대 우", "장경인대 좌", "비복근 우", "비복근 좌",
             "가자미근 우", "가자미근 좌", "족저근막 우", "족저근막 좌"], default=st.session_state.get("af_trp_lower",[]), key="trp_lower")
    trp_etc = st.text_input("기타 압통 부위 직접 입력", key="af_trp_etc", placeholder="예: 우측 측두근, 좌측 저작근, 오구완근 우")
    c1, c2 = st.columns(2)
    with c1:
        trp_intensity = st.select_slider("압통 강도", options=["경증 (+)", "중등도 (++)", "중증 (+++)"])
    with c2:
        trp_referred = st.text_input("연관통 패턴", key="af_trp_referred", placeholder="예: 우측 측두부, 팔 외측, 엄지/검지")
    st.write("**특수검사**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        test_spurling = st.selectbox("Spurling", ["미시행", "음성 (-)", "양성 (+)"])
        test_distraction = st.selectbox("견인검사", ["미시행", "음성 (-)", "양성 (+)"])
    with c2:
        test_drop = st.selectbox("Drop arm", ["미시행", "음성 (-)", "양성 (+)"])
        test_yergason = st.selectbox("Yergason", ["미시행", "음성 (-)", "양성 (+)"])
    with c3:
        test_slr = st.selectbox("SLR", ["미시행", "음성 (-)", "양성 (+)"])
        test_phalen = st.selectbox("Phalen", ["미시행", "음성 (-)", "양성 (+)"])
    with c4:
        test_faber = st.selectbox("FABER", ["미시행", "음성 (-)", "양성 (+)"])
        test_etc = st.text_input("기타 검사", placeholder="예: Hawkins (+), Neer (-)")
    st.divider()
    st.markdown('<div class="soap-label">A - 평가 (Assessment)</div>', unsafe_allow_html=True)
    a_diagnosis = st.text_input("진단/소견", key="af_diagnosis", placeholder="예: 경추 MPS, C4-5 분절 관련")
    a_problem = st.text_area("주요 문제점", key="af_problem", placeholder="예: 우측 상부 승모근 활성 TrP, 경추 ROM 제한", height=60)
    a_cause = st.text_area("연관 요인", key="af_cause", placeholder="예: 장시간 컴퓨터 작업, 전방 두부 자세", height=60)
    c1, c2 = st.columns(2)
    with c1:
        a_goal_short_pre = st.multiselect("단기 목표 선택",
            ["NRS 7→4", "NRS 6→3", "NRS 5→2", "NRS 8→5",
             "경추 ROM 증가", "요추 ROM 증가", "어깨 ROM 증가",
             "통증 완화", "압통역치 향상", "일상생활 기능 향상",
             "수면 개선", "근육 긴장 완화"])
        a_goal_short_etc = st.text_input("단기 목표 직접 입력", placeholder="예: NRS 7→4, 경추 회전 50°→70°")
        a_goal_short = ', '.join(a_goal_short_pre) + (f', {a_goal_short_etc}' if a_goal_short_etc else '')
    with c2:
        a_goal_long_pre = st.multiselect("장기 목표 선택",
            ["TrP 비활성화", "ROM 정상 범위 회복", "정상 자세 회복",
             "근력 정상화", "일상생활 완전 복귀", "통증 없는 생활",
             "재발 방지", "자가 관리 능력 향상", "약물 의존도 감소",
             "운동 기능 회복", "직업 복귀"])
        a_goal_long_etc = st.text_input("장기 목표 직접 입력", placeholder="예: TrP 비활성화, 정상 자세 유지")
        a_goal_long = ', '.join(a_goal_long_pre) + (f', {a_goal_long_etc}' if a_goal_long_etc else '')
    st.divider()
    st.markdown('<div class="soap-label">P - 치료 계획 (Plan)</div>', unsafe_allow_html=True)
    st.write("**치료 기법 체크리스트**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("🌡️ 물리치료")
        t_hot = st.checkbox("온찜질 (15분)")
        t_cold = st.checkbox("냉찜질 (15분)")
        t_us = st.selectbox("초음파", ["미시행", "1MHz 연속", "3MHz 연속", "1MHz 맥동", "3MHz 맥동"])
        t_tens = st.selectbox("TENS", ["미시행", "고주파 80~100Hz", "저주파 2~4Hz", "혼합파"])
        t_laser = st.checkbox("레이저 치료")
        t_eswt = st.checkbox("체외충격파 (ESWT)")
        t_traction = st.checkbox("견인 치료")
    with c2:
        st.write("🤲 도수치료")
        t_maitland = st.multiselect("Maitland 가동술", ["Grade I", "Grade II", "Grade III", "Grade IV", "Grade V (Thrust)"])
        t_maitland_area = st.text_input("Maitland 적용 부위", placeholder="예: C4-5 우측 PA glide")
        t_met = st.checkbox("MET (근에너지 기법)", value=bool(st.session_state.get("met_sel") or st.session_state.get("met_etc")))
        _trp_all = trp_neck + trp_shoulder + trp_lower + ([trp_etc] if trp_etc else [])
        t_met_area_sel = st.multiselect("MET 적용 부위 (TrP 목록)", _trp_all, key="met_sel")
        t_met_area_etc = st.text_input("MET 직접 입력", placeholder="예: 상부 승모근 PIR 6초×5회", key="met_etc")
        t_met_area = ', '.join(t_met_area_sel) + (f', {t_met_area_etc}' if t_met_area_etc else '')
        t_ic = st.checkbox("허혈성 압박 (TrP)", value=bool(st.session_state.get("ic_sel") or st.session_state.get("ic_etc")))
        t_ic_area_sel = st.multiselect("허혈성 압박 부위 (TrP 목록)", _trp_all, key="ic_sel")
        t_ic_area_etc = st.text_input("허혈성 압박 직접 입력", placeholder="예: 견갑거근 TrP 10초×5회", key="ic_etc")
        t_ic_area = ', '.join(t_ic_area_sel) + (f', {t_ic_area_etc}' if t_ic_area_etc else '')
        t_prt = st.checkbox("위치해제 (PRT)", value=bool(st.session_state.get("prt_sel") or st.session_state.get("prt_etc")))
        t_prt_area_sel = st.multiselect("PRT 적용 부위 (TrP 목록)", _trp_all, key="prt_sel")
        t_prt_area_etc = st.text_input("PRT 직접 입력", placeholder="예: 상부 승모근 90초", key="prt_etc")
        t_prt_area = ', '.join(t_prt_area_sel) + (f', {t_prt_area_etc}' if t_prt_area_etc else '')
    with c3:
        st.write("🔧 기타 기법")
        t_iastm = False
        t_iastm_area = ""
        t_mfr = st.checkbox("근막 이완 (MFR)", value=bool(st.session_state.get("mfr_sel") or st.session_state.get("mfr_etc")))
        t_mfr_area_sel = st.multiselect("MFR 적용 부위 (TrP 목록)", _trp_all, key="mfr_sel")
        t_mfr_area_etc = st.text_input("MFR 직접 입력", placeholder="예: 흉요근막 J-스트로크 3분", key="mfr_etc")
        t_mfr_area = ', '.join(t_mfr_area_sel) + (f', {t_mfr_area_etc}' if t_mfr_area_etc else '')
        t_init = st.checkbox("INIT 통합기법")
        t_massage = st.multiselect("마사지 기법", ["경찰법 (Effleurage)", "유날법 (Petrissage)", "마찰법 (Friction)", "스트리핑 (Stripping)", "교차 마찰 (Cross-fiber)"])
        t_massage_area_sel = st.multiselect("마사지 적용 부위 (TrP 목록)", _trp_all, key="mas_sel")
        t_massage_area_etc = st.text_input("마사지 직접 입력", placeholder="예: 상부 승모근, 경추 주변", key="mas_etc")
        t_massage_area = ', '.join(t_massage_area_sel) + (f', {t_massage_area_etc}' if t_massage_area_etc else '')
    st.write("**홈 프로그램**")
    p_home = st.text_area("홈 운동 처방",
        key="af_home_program",
        placeholder="예:\n- 경추 측방 굴곡 스트레칭: 30초×3회, 하루 3세트\n- 턱당김 운동: 10초×10회, 하루 2회",
        height=150)
    if st.session_state.get("home_program"):
        st.info("💡 위 내용은 AI가 생성한 홈 운동 처방입니다. 필요 시 수정하세요.")
    c1, c2, c3 = st.columns(3)
    with c1:
        p_freq = st.selectbox("치료 빈도", ["주 1회", "주 2회", "주 3회", "격일", "매일"])
    with c2:
        p_total = st.selectbox("총 치료 기간", ["2주", "4주", "6주", "8주", "12주", "기타"])
    with c3:
        p_next = st.text_input("다음 방문", key="af_next_visit", placeholder="예: 3일 후")
    p_note = st.text_area("특이사항 / 메모", key="af_note", placeholder="예: 통증에 민감, Grade II 이상 주의.", height=60)
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        btn_chart = st.button("📄 차트 생성 & 다운로드", type="primary", use_container_width=True)
    with col_btn2:
        btn_ai = st.button("🤖 AI 맞춤 루틴 생성하기", type="secondary", use_container_width=True)
    with col_btn3:
        btn_save = st.button("💾 차트 저장 (환자 DB)", type="secondary", use_container_width=True)

    if btn_ai:
        if not s_complaint.strip():
            st.warning("주호소를 입력해주세요.")
        else:
            with st.spinner("🤖 AI 처방 생성 중... (1~2분 소요)"):
                try:
                    pain_q_str = ", ".join(pain_quality) + (f", {pain_quality_etc}" if pain_quality_etc else "")
                    payload = {
                        "body_part": s_complaint,
                        "symptoms": f"{pain_q_str} | {s_aggravating}",
                        "pain_level": s_nrs_now,
                        "duration": s_duration,
                        "aggravating": s_aggravating or None,
                        "relieving": s_relieving or None
                    }
                    response = requests.post(f"{API_URL}/prescription", json=payload, timeout=180)
                    if response.status_code == 200:
                        data = response.json()
                        st.success("✅ AI 맞춤 루틴이 생성되었습니다!")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("통증 부위", s_complaint[:10])
                        m2.metric("통증 강도", f"{s_nrs_now}/10")
                        m3.metric("참조 지식", f"{data['rag_chunks_used']}개 섹션")
                        st.markdown("---")
                        st.subheader("🤖 AI 맞춤 루틴 미리보기")
                        st.markdown(data["prescription"])
                        st.divider()
                        st.caption("📋 아래 복사용 텍스트박스에서 Ctrl+A → Ctrl+C 로 복사하세요")
                        st.text_area("전체 처방 복사용", value=data["prescription"], height=300, key="full_copy")
                        import re
                        prescription = data["prescription"]
                        section_patterns = [
                            ("🔍 증상 분석", r"\*{1,2}🔍\s*증상 분석\*{0,2}(.*?)(?=\*{1,2}🔥|\*{1,2}🧘|\*{1,2}💪|\*{1,2}🏥|\*{1,2}🏠|##|\Z)"),
                            ("🔥 즉시 적용", r"\*{1,2}🔥\s*즉시 적용\*{0,2}(.*?)(?=\*{1,2}🧘|\*{1,2}💪|\*{1,2}🏥|\*{1,2}🏠|##|\Z)"),
                            ("🧘 스트레칭 프로그램", r"\*{1,2}🧘\s*스트레칭[^*]*\*{0,2}(.*?)(?=\*{1,2}💪|\*{1,2}🏥|\*{1,2}🏠|##|\Z)"),
                            ("💪 운동 치료", r"\*{1,2}💪\s*운동 치료\*{0,2}(.*?)(?=\*{1,2}🏥|\*{1,2}🏠|##|\Z)"),
                            ("🏥 도수치료 권고", r"\*{1,2}🏥\s*도수치료[^*]*\*{0,2}(.*?)(?=\*{1,2}🏠|##|\Z)"),
                            ("🏠 자세 교정 & 예방", r"\*{1,2}🏠\s*자세 교정[^*]*\*{0,2}(.*?)(?=##|\Z)"),
                        ]
                        for title, pattern in section_patterns:
                            match = re.search(pattern, prescription, re.DOTALL)
                            if match:
                                section_text = match.group(1).strip()
                                if section_text:
                                    full_text = f"{title}\n{section_text}"
                                    st.markdown(f"### {title}")
                                    st.markdown(section_text)
                                    st.text_area(
                                        f"📋 복사용 - {title}",
                                        value=full_text,
                                        height=100,
                                        key=f"copy_{title}",
                                        help="전체 선택(Ctrl+A) 후 복사(Ctrl+C)하세요"
                                    )
                                    st.divider()
                        ai_text = f"""AI 맞춤 루틴 처방
================================================================
차트번호: {pt_chart_no} | 환자명: {pt_name} | 치료일: {pt_date} | 회차: {pt_session}회차
주호소: {s_complaint} | NRS: {s_nrs_now}/10 | 기간: {s_duration}
통증 양상: {pain_q_str}
================================================================

{data['prescription']}

정확한 진단과 치료를 위해 반드시 의사에게 진료 및 처방을 받으시고,
의사와 물리치료사의 지도에 따라 치료를 진행하시기 바랍니다.
"""
                        st.download_button(
                            "📥 AI 맞춤 루틴 다운로드",
                            ai_text,
                            file_name=f"AI루틴_{pt_name}_{str(pt_date)}_{pt_session}회차.txt",
                            mime="text/plain",
                            key="ai_download"
                        )
                    else:
                        st.error(f"서버 오류 ({response.status_code})")
                except requests.exceptions.ConnectionError:
                    st.error("❌ 백엔드 서버에 연결할 수 없습니다.")
                except requests.exceptions.Timeout:
                    st.warning("⏳ 응답 시간 초과. 다시 시도하세요.")

    if btn_save:
        if not pt_name.strip():
            st.warning("환자명을 입력해야 저장할 수 있습니다.")
        else:
            try:
                # 차트 텍스트 생성 (btn_chart와 동일한 로직)
                all_trp_save = trp_neck + trp_shoulder + trp_lower
                if trp_etc: all_trp_save.append(f"기타: {trp_etc}")
                pain_q_save = ', '.join(pain_quality) + (f", {pain_quality_etc}" if pain_quality_etc else "")
                chart_save_text = f"""================================================================
도수치료 SOAP 차트
================================================================
차트번호: {pt_chart_no}  |  환자명: {pt_name}  |  나이: {pt_age}세  |  성별: {pt_gender}
치료일: {pt_date}  |  회차: {pt_session}회차  |  치료사: {pt_therapist}
진단명: {pt_dx}
================================================================

[S - 주관적 소견]
주호소: {s_complaint}
NRS: 현재 {s_nrs_now}/10 | 최악 {s_nrs_worst}/10 | 최선 {s_nrs_best}/10
지속 기간: {s_duration}
통증 양상: {pain_q_save}
악화 요인: {s_aggravating}
완화 요인: {s_relieving}
일상생활 장애: {s_adl}

[O - 객관적 소견]
TrP 압통 부위: {', '.join(all_trp_save) if all_trp_save else '없음'}
압통 강도: {trp_intensity} | 연관통: {trp_referred}

[A - 평가]
진단: {a_diagnosis}
단기 목표: {a_goal_short} | 장기 목표: {a_goal_long}

[P - 치료 계획]
빈도: {p_freq} | 기간: {p_total}
홈 프로그램: {p_home}
================================================================
작성일시: {str(pt_date)}"""
                save_payload = {
                    "chart_no": pt_chart_no,
                    "pt_name": pt_name,
                    "pt_age": pt_age,
                    "pt_gender": pt_gender,
                    "pt_date": str(pt_date),
                    "pt_session": pt_session,
                    "pt_therapist": pt_therapist,
                    "pt_dx": pt_dx,
                    "chart_content": chart_save_text,
                    "soap_json": {
                        "nrs_now": s_nrs_now,
                        "nrs_worst": s_nrs_worst,
                        "duration": s_duration,
                        "trp": all_trp_save,
                        "diagnosis": a_diagnosis,
                    }
                }
                save_res = requests.post(f"{API_URL}/chart/save", json=save_payload, timeout=10).json()
                st.success(f"✅ {pt_name} 님 차트가 저장되었습니다! ({str(pt_date)} {pt_session}회차)")
            except Exception as e:
                st.error(f"저장 실패: {e}")

    if btn_save:
        if not pt_name.strip():
            st.warning("⚠️ 환자명을 입력해야 저장할 수 있습니다.")
        else:
            with st.spinner("💾 저장 중..."):
                try:
                    all_trp_s = trp_neck + trp_shoulder + trp_lower
                    if trp_etc: all_trp_s.append(f"기타: {trp_etc}")
                    pain_q_s = ', '.join(pain_quality) + (f", {pain_quality_etc}" if pain_quality_etc else "")
                    save_techniques = []
                    if t_hot: save_techniques.append("온찜질 15분")
                    if t_cold: save_techniques.append("냉찜질 15분")
                    if t_us != "미시행": save_techniques.append(f"초음파 {t_us}")
                    if t_tens != "미시행": save_techniques.append(f"TENS {t_tens}")
                    if t_laser: save_techniques.append("레이저 치료")
                    if t_eswt: save_techniques.append("체외충격파 ESWT")
                    if t_traction: save_techniques.append("견인 치료")
                    if t_maitland: save_techniques.append("Maitland " + ", ".join(t_maitland) + " → " + t_maitland_area)
                    if t_met: save_techniques.append(f"MET PIR → {t_met_area}")
                    if t_ic: save_techniques.append(f"허혈성 압박 → {t_ic_area}")
                    if t_prt: save_techniques.append(f"PRT → {t_prt_area}")
                    if t_mfr: save_techniques.append(f"근막 이완 MFR → {t_mfr_area}")
                    if t_init: save_techniques.append("INIT 통합기법")
                    if t_massage: save_techniques.append("마사지 (" + ", ".join(t_massage) + ") → " + t_massage_area)
                    save_chart_text = f"""================================================================
도수치료 SOAP 차트
================================================================
차트번호: {pt_chart_no}  |  환자명: {pt_name}  |  나이: {pt_age}세  |  성별: {pt_gender}
치료일: {pt_date}  |  회차: {pt_session}회차  |  치료사: {pt_therapist}
진단명: {pt_dx}
================================================================

[S - 주관적 소견]
주호소: {s_complaint}
NRS: 현재 {s_nrs_now}/10 | 최악 {s_nrs_worst}/10 | 최선 {s_nrs_best}/10
지속 기간: {s_duration}
통증 양상: {pain_q_s}
악화 요인: {s_aggravating}
완화 요인: {s_relieving}
일상생활 장애: {s_adl}

[O - 객관적 소견]
■ 자세
  전방 두부 자세: {o_fhp} | 어깨 높이: {o_shoulder}
  골반 좌우: {o_pelvis_lr} | 골반 전후: {o_pelvis_fb}
  척추 측만: {o_spine} | 기타: {o_posture_etc}

■ ROM ({rom_area}): {rom_text if 'rom_text' in dir() else ''}
■ 근력: 좌 {ms_left} | 우 {ms_right}

■ TrP 압통: {', '.join(all_trp_s) if all_trp_s else '없음'}
  압통 강도: {trp_intensity} | 연관통: {trp_referred}

■ 특수검사
  Spurling: {test_spurling} | 견인: {test_distraction}
  Drop arm: {test_drop} | SLR: {test_slr} | FABER: {test_faber}
  기타: {test_etc}

[A - 평가]
진단: {a_diagnosis}
주요 문제: {a_problem}
단기 목표: {a_goal_short} | 장기 목표: {a_goal_long}

[P - 치료 계획]
■ 적용 기법:
{chr(10).join(f"  - {t}" for t in save_techniques) if save_techniques else "  없음"}

홈 프로그램:
{p_home}
빈도: {p_freq} | 기간: {p_total} | 다음 방문: {p_next}
특이사항: {p_note}
================================================================
작성일시: {str(pt_date)}"""
                    save_res = requests.post(f"{API_URL}/chart/save", json={
                        "chart_no": pt_chart_no,
                        "pt_name": pt_name,
                        "pt_age": pt_age,
                        "pt_gender": pt_gender,
                        "pt_date": str(pt_date),
                        "pt_session": pt_session,
                        "pt_therapist": pt_therapist,
                        "pt_dx": pt_dx,
                        "chart_content": save_chart_text,
                        "soap_json": {
                            "nrs_now": s_nrs_now,
                            "nrs_worst": s_nrs_worst,
                            "nrs_best": s_nrs_best,
                            "complaint": s_complaint,
                            "duration": s_duration,
                            "pain_quality": pain_quality,
                            "pain_quality_etc": pain_quality_etc,
                            "aggravating": s_aggravating,
                            "relieving": s_relieving,
                            "adl": s_adl,
                            "posture_fhp": o_fhp,
                            "posture_shoulder": o_shoulder,
                            "posture_pelvis_lr": o_pelvis_lr,
                            "posture_pelvis_fb": o_pelvis_fb,
                            "posture_spine": o_spine,
                            "posture_etc": o_posture_etc,
                            "rom_area": rom_area,
                            "rom_text": rom_text if "rom_text" in dir() else "",
                            "trp_neck": trp_neck,
                            "trp_shoulder": trp_shoulder,
                            "trp_lower": trp_lower,
                            "trp_etc": trp_etc,
                            "trp_intensity": trp_intensity,
                            "trp_referred": trp_referred,
                            "diagnosis": a_diagnosis,
                            "problem": a_problem,
                            "cause": a_cause,
                            "goal_short": a_goal_short,
                            "goal_long": a_goal_long,
                            "home_program": p_home,
                            "freq": p_freq,
                            "total": p_total,
                            "next_visit": p_next,
                            "note": p_note,
                            "pt_age": pt_age,
                            "pt_gender": pt_gender,
                            "pt_therapist": pt_therapist,
                            "pt_dx": pt_dx,
                        }
                    }, timeout=10).json()
                    r = save_res.get("results", {})
                    st.success(f"💾 저장 완료!")
                    st.write(f"- {r.get('json','')}")
                    st.write(f"- {r.get('firestore','')}")
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    if btn_chart:
        all_trp = trp_neck + trp_shoulder + trp_lower
        if trp_etc:
            all_trp.append(f"기타: {trp_etc}")
        techniques = []
        if t_hot: techniques.append("온찜질 15분")
        if t_cold: techniques.append("냉찜질 15분")
        if t_us != "미시행": techniques.append(f"초음파 {t_us}")
        if t_tens != "미시행": techniques.append(f"TENS {t_tens}")
        if t_laser: techniques.append("레이저 치료")
        if t_eswt: techniques.append("체외충격파 ESWT")
        if t_traction: techniques.append("견인 치료")
        if t_maitland: techniques.append(f"Maitland {', '.join(t_maitland)} → {t_maitland_area}")
        if t_met: techniques.append(f"MET PIR → {t_met_area}")
        if t_ic: techniques.append(f"허혈성 압박 → {t_ic_area}")
        if t_prt: techniques.append(f"PRT → {t_prt_area}")
        if t_iastm: techniques.append(f"IASTM Graston → {t_iastm_area}")
        if t_mfr: techniques.append(f"근막 이완 MFR → {t_mfr_area}")
        if t_init: techniques.append("INIT 통합기법")
        if t_massage: techniques.append(f"마사지 ({', '.join(t_massage)}) → {t_massage_area}")
        pain_q_text = ', '.join(pain_quality)
        if pain_quality_etc:
            pain_q_text += f", {pain_quality_etc}"
        chart_text = f"""================================================================
도수치료 SOAP 차트
================================================================
차트번호: {pt_chart_no}  |  환자명: {pt_name}  |  나이: {pt_age}세  |  성별: {pt_gender}
치료일: {pt_date}  |  회차: {pt_session}회차  |  치료사: {pt_therapist}
진단명: {pt_dx}
================================================================

[S - 주관적 소견]
주호소: {s_complaint}
NRS: 현재 {s_nrs_now}/10 | 최악 {s_nrs_worst}/10 | 최선 {s_nrs_best}/10
지속 기간: {s_duration}
통증 양상: {pain_q_text}
악화 요인: {s_aggravating}
완화 요인: {s_relieving}
일상생활 장애: {s_adl}

[O - 객관적 소견]
■ 자세
  전방 두부 자세: {o_fhp} | 어깨 높이: {o_shoulder}
  골반 좌우: {o_pelvis_lr} | 골반 전후: {o_pelvis_fb}
  척추 측만: {o_spine} | 기타: {o_posture_etc}

■ ROM ({rom_area}): {rom_text}
■ 근력: 좌 {ms_left} | 우 {ms_right}

■ TrP 압통 부위: {', '.join(all_trp) if all_trp else '없음'}
  압통 강도: {trp_intensity} | 연관통: {trp_referred}

■ 특수검사
  Spurling: {test_spurling} | 견인: {test_distraction}
  Drop arm: {test_drop} | Yergason: {test_yergason}
  SLR: {test_slr} | Phalen: {test_phalen} | FABER: {test_faber}
  기타: {test_etc}

[A - 평가]
진단: {a_diagnosis}
주요 문제: {a_problem}
연관 요인: {a_cause}
단기 목표: {a_goal_short} | 장기 목표: {a_goal_long}

[P - 치료 계획]
■ 적용 기법:
{chr(10).join(f"  - {t}" for t in techniques) if techniques else "  없음"}

■ 홈 프로그램:
{p_home}

■ 빈도: {p_freq} | 기간: {p_total} | 다음 방문: {p_next}
■ 특이사항: {p_note}
================================================================
작성일시: {str(pt_date)}
"""
        st.success("✅ 차트가 생성되었습니다!")
        st.text_area("차트 미리보기", chart_text, height=400)
        st.download_button("📥 차트 다운로드", chart_text,
            file_name=f"도수치료차트_{pt_name}_{str(pt_date)}_{pt_session}회차.txt",
            mime="text/plain")

st.divider()
st.caption("⚠️ 본 시스템은 교육·참고 목적이며 의학적 진단 및 치료를 대체하지 않습니다.")
