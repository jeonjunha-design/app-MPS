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

# 목표 선택 옵션 (위젯/구버전 복원에서 공용)
GOAL_SHORT_OPTS = ["NRS 7→4", "NRS 6→3", "NRS 5→2", "NRS 8→5",
    "경추 ROM 증가", "요추 ROM 증가", "어깨 ROM 증가",
    "통증 완화", "압통역치 향상", "일상생활 기능 향상",
    "수면 개선", "근육 긴장 완화"]
GOAL_LONG_OPTS = ["TrP 비활성화", "ROM 정상 범위 회복", "정상 자세 회복",
    "근력 정상화", "일상생활 완전 복귀", "통증 없는 생활",
    "재발 방지", "자가 관리 능력 향상", "약물 의존도 감소",
    "운동 기능 회복", "직업 복귀"]

# 특수검사: 부위별 (표시 라벨, session_state key). key 는 "af_" 접두어를 떼면 soap_json key.
TEST_OPTS = ["미시행", "양성 (+)", "음성 (-)"]
SPECIAL_TESTS = [
    ("경추", [
        ("Spurling test", "af_test_cx_spurling"),
        ("경추 견인검사 (Distraction test)", "af_test_cx_distraction"),
        ("Valsalva test", "af_test_cx_valsalva"),
        ("상지 긴장검사 (ULTT)", "af_test_cx_ultt"),
    ]),
    ("견관절", [
        ("Drop arm test", "af_test_sh_droparm"),
        ("Yergason test", "af_test_sh_yergason"),
        ("Hawkins-Kennedy test", "af_test_sh_hawkins"),
        ("Neer test", "af_test_sh_neer"),
        ("Empty can test (Jobe test)", "af_test_sh_emptycan"),
        ("Apprehension test", "af_test_sh_apprehension"),
        ("Sulcus sign", "af_test_sh_sulcus"),
    ]),
    ("주관절", [
        ("Cozen test (테니스 엘보)", "af_test_el_cozen"),
        ("Golfer elbow test", "af_test_el_golfer"),
        ("Tinel sign (주관절)", "af_test_el_tinel"),
    ]),
    ("수근관절", [
        ("Phalen test", "af_test_wr_phalen"),
        ("Tinel sign (수근관절)", "af_test_wr_tinel"),
        ("Finkelstein test", "af_test_wr_finkelstein"),
        ("Grip strength test", "af_test_wr_grip"),
    ]),
    ("요추", [
        ("SLR test (직거상 검사)", "af_test_lx_slr"),
        ("Bragard test", "af_test_lx_bragard"),
        ("Slump test", "af_test_lx_slump"),
        ("FABER test", "af_test_lx_faber"),
        ("Gaenslen test", "af_test_lx_gaenslen"),
        ("요추 신전 검사", "af_test_lx_extension"),
    ]),
    ("고관절", [
        ("FABER test", "af_test_hip_faber"),
        ("Thomas test", "af_test_hip_thomas"),
        ("Ober test", "af_test_hip_ober"),
        ("Trendelenburg test", "af_test_hip_trendelenburg"),
    ]),
    ("슬관절", [
        ("McMurray test", "af_test_knee_mcmurray"),
        ("Anterior drawer test", "af_test_knee_adrawer"),
        ("Valgus/Varus stress test", "af_test_knee_valgusvarus"),
        ("Lachman test", "af_test_knee_lachman"),
        ("Patellar grind test", "af_test_knee_patellargrind"),
    ]),
    ("족관절", [
        ("Thompson test", "af_test_ankle_thompson"),
        ("Anterior drawer test (족관절)", "af_test_ankle_adrawer"),
        ("Talar tilt test", "af_test_ankle_talartilt"),
        ("Homan sign", "af_test_ankle_homan"),
    ]),
]

# 특수검사 참고 가이드 (부위 → [(검사명, 방법/양성/의미)])
TEST_GUIDE = [
    ("경추", [
        ("Spurling test", "방법: 머리를 신전+환측 측굴 후 정수리 하방 압박. · 양성: 동측 상지로 방사통·저림. · 의미: 경추 신경근병증(추간공 협착)."),
        ("경추 견인검사 (Distraction test)", "방법: 턱과 후두부를 잡고 머리를 위로 견인. · 양성: 상지 증상 완화. · 의미: 추간공성 신경근 압박 시사."),
        ("Valsalva test", "방법: 숨을 참고 복압을 올리도록 힘주기. · 양성: 경추/상지 방사통 유발. · 의미: 추간판 탈출·척수강내 점유병변."),
        ("상지 긴장검사 (ULTT)", "방법: 견갑 하강→외전·외회전→주관절·손목 신전으로 단계적 긴장. · 양성: 신경 주행 따라 방사통·저림. · 의미: 상완신경총/신경근 자극."),
    ]),
    ("견관절", [
        ("Drop arm test", "방법: 팔을 90° 외전 후 천천히 내리게 함. · 양성: 지탱 못하고 뚝 떨어짐. · 의미: 극상근/회전근개 파열."),
        ("Yergason test", "방법: 주관절 90° 굴곡, 저항하며 전완 회외+외회전. · 양성: 결절간구 통증. · 의미: 이두근 장두 건염·횡인대 불안정."),
        ("Hawkins-Kennedy test", "방법: 어깨·주관절 90° 굴곡 후 내회전. · 양성: 통증. · 의미: 견봉하 충돌증후군."),
        ("Neer test", "방법: 견갑 고정, 내회전 상태로 수동 전방 거상. · 양성: 통증. · 의미: 견봉하 충돌."),
        ("Empty can test (Jobe test)", "방법: 90° 외전·30° 수평굴곡·엄지 아래로 후 하방저항. · 양성: 통증/근력약화. · 의미: 극상근 병변."),
        ("Apprehension test", "방법: 어깨 90° 외전+외회전. · 양성: 탈구 불안감·회피. · 의미: 전방 견관절 불안정."),
        ("Sulcus sign", "방법: 팔을 아래로 견인. · 양성: 견봉-골두 사이 고랑(함몰). · 의미: 하방 견관절 불안정."),
    ]),
    ("주관절", [
        ("Cozen test (테니스 엘보)", "방법: 주관절 신전 상태로 손목 신전에 저항. · 양성: 외측 상과 통증. · 의미: 외측 상과염."),
        ("Golfer elbow test", "방법: 손목 굴곡·전완 회내에 저항(또는 수동 신전). · 양성: 내측 상과 통증. · 의미: 내측 상과염."),
        ("Tinel sign (주관절)", "방법: 주관절 내측 척골신경구를 타진. · 양성: 4·5수지 저림. · 의미: 척골신경 포착(주관터널증후군)."),
    ]),
    ("수근관절", [
        ("Phalen test", "방법: 양 손등을 맞대고 손목을 최대 굴곡 60초 유지. · 양성: 정중신경 분포 저림. · 의미: 수근관증후군."),
        ("Tinel sign (수근관절)", "방법: 손목 정중신경(수근관) 부위를 타진. · 양성: 1~3수지 저림. · 의미: 수근관증후군."),
        ("Finkelstein test", "방법: 엄지를 주먹으로 감싼 뒤 손목을 척측 편위. · 양성: 요골 경상돌기 통증. · 의미: 드꿰르뱅 건초염."),
        ("Grip strength test", "방법: 악력계로 좌우 악력 측정·비교. · 양성: 환측 근력 저하. · 의미: 신경·건·통증성 근력저하 평가."),
    ]),
    ("요추", [
        ("SLR test (직거상 검사)", "방법: 앙와위, 무릎 편 채 하지를 거상. · 양성: 30~70°에서 하지 방사통. · 의미: 좌골신경/L4-S1 신경근 자극(추간판 탈출)."),
        ("Bragard test", "방법: SLR 양성 각도 직전으로 낮춘 뒤 발목 족배굴곡. · 양성: 방사통 재현. · 의미: 신경근성 통증 확인(근육성 감별)."),
        ("Slump test", "방법: 앉아서 척추·경부 굴곡 후 무릎 신전+족배굴곡. · 양성: 신경 긴장성 방사통. · 의미: 신경근/경막 긴장."),
        ("FABER test", "방법: 굴곡-외전-외회전(figure-4) 자세. · 양성: 서혜부 또는 후방 천장관절 통증. · 의미: 고관절/천장관절 병변."),
        ("Gaenslen test", "방법: 한쪽 고관절 최대 굴곡, 반대 하지는 침대 밖으로 신전. · 양성: 천장관절 통증. · 의미: 천장관절 기능장애."),
        ("요추 신전 검사", "방법: 서서 요추를 신전하며 환측 측굴·회전. · 양성: 동측 하지 방사통·국소통. · 의미: 후관절 증후군/추간공 협착."),
    ]),
    ("고관절", [
        ("FABER test", "방법: figure-4 자세로 굴곡-외전-외회전. · 양성: 서혜부(고관절) 통증. · 의미: 고관절 관절내 병변."),
        ("Thomas test", "방법: 앙와위, 한쪽 무릎을 가슴으로 당기고 반대 하지 관찰. · 양성: 반대 대퇴가 침대에서 뜸. · 의미: 장요근/고관절 굴곡 구축."),
        ("Ober test", "방법: 측와위, 상측 하지를 외전·신전 후 내전 유도. · 양성: 내전되지 않고 떠 있음. · 의미: 장경인대/대퇴근막장근 단축."),
        ("Trendelenburg test", "방법: 한 다리로 서기(편측 지지). · 양성: 반대측 골반이 하강. · 의미: 중둔근 약화(외전근 부전)."),
    ]),
    ("슬관절", [
        ("McMurray test", "방법: 무릎을 굴곡했다가 회전하며 신전. · 양성: 관절선 클릭+통증. · 의미: 반월연골판 파열."),
        ("Anterior drawer test", "방법: 무릎 90° 굴곡에서 경골을 전방으로 당김. · 양성: 전방 전위 증가. · 의미: 전방십자인대(ACL) 손상."),
        ("Valgus/Varus stress test", "방법: 무릎 0·30° 굴곡에서 외반/내반 부하. · 양성: 내측/외측 관절 벌어짐·통증. · 의미: 내측(MCL)/외측(LCL) 측부인대 손상."),
        ("Lachman test", "방법: 무릎 20~30° 굴곡에서 경골 전방 당김. · 양성: 단단한 끝점 소실·전위 증가. · 의미: ACL 손상(가장 민감)."),
        ("Patellar grind test", "방법: 슬개골을 하방 압박한 채 대퇴사두근 수축. · 양성: 슬개골 후면 통증·염발음. · 의미: 슬개대퇴 통증증후군/연골연화증."),
    ]),
    ("족관절", [
        ("Thompson test", "방법: 복와위에서 종아리(비복근)를 압박. · 양성: 발의 저측굴곡이 없음. · 의미: 아킬레스건 완전 파열."),
        ("Anterior drawer test (족관절)", "방법: 경골 고정 후 종골을 전방으로 당김. · 양성: 거골 전방 전위. · 의미: 전거비인대(ATFL) 손상."),
        ("Talar tilt test", "방법: 종골에 내반 부하. · 양성: 거골 경사각 증가. · 의미: 종비인대(CFL) 손상."),
        ("Homan sign", "방법: 무릎 신전 상태로 발목 족배굴곡. · 양성: 종아리 통증. · 의미: 심부정맥혈전증(DVT) 의심(특이도 낮아 참고용)."),
    ]),
]

# ══════════════════════════════════════════════════════════════
# 차트 불러오기 인프라
#   - 모든 위젯 값은 session_state 가 단일 소스(single source of truth).
#   - 위젯에는 value=/index=/default= 를 넘기지 않고 key 로만 제어한다.
#   - 저장된 soap_json 은 "pending_soap" 슬롯에 넣고, 다음 실행에서
#     어떤 위젯도 생성되기 전(탭 최상단)에 session_state 로 주입한다.
#     → "widget instantiated 후 수정 불가" 예외를 원천 차단.
# ══════════════════════════════════════════════════════════════

# session_state key : (soap_json key, 기본값)
SOAP_STATE_MAP = {
    "s_nrs_now": ("nrs_now", 5),
    "s_nrs_worst": ("nrs_worst", 7),
    "s_nrs_best": ("nrs_best", 2),
    "s_duration": ("duration", "오늘 발생"),
    "af_complaint": ("complaint", ""),
    "af_pain_quality": ("pain_quality", []),
    "af_pain_quality_etc": ("pain_quality_etc", ""),
    "af_aggravating": ("aggravating", ""),
    "af_relieving": ("relieving", ""),
    "af_adl": ("adl", ""),
    "af_posture_fhp": ("posture_fhp", "없음"),
    "af_posture_shoulder": ("posture_shoulder", "좌우 대칭"),
    "af_posture_pelvis_lr": ("posture_pelvis_lr", "좌우 대칭"),
    "af_posture_pelvis_fb": ("posture_pelvis_fb", "정상"),
    "af_posture_spine": ("posture_spine", "없음"),
    "af_posture_etc": ("posture_etc", ""),
    "af_rom_area": ("rom_area", "경추"),
    "rom_c_flex": ("rom_c_flex", 40), "rom_c_ext": ("rom_c_ext", 45),
    "rom_c_lf": ("rom_c_lf", 35), "rom_c_rf": ("rom_c_rf", 35),
    "rom_c_lr": ("rom_c_lr", 60), "rom_c_rr": ("rom_c_rr", 60),
    "rom_l_flex": ("rom_l_flex", 60), "rom_l_ext": ("rom_l_ext", 25),
    "rom_l_lf": ("rom_l_lf", 30), "rom_l_rf": ("rom_l_rf", 30),
    "rom_l_lr": ("rom_l_lr", 25), "rom_l_rr": ("rom_l_rr", 25),
    "rom_s_abd": ("rom_s_abd", 160), "rom_s_flex": ("rom_s_flex", 160),
    "rom_s_er": ("rom_s_er", 70), "rom_s_ir": ("rom_s_ir", 70),
    "rom_s_ext": ("rom_s_ext", 40),
    "af_rom_free": ("rom_free", ""),
    "trp_neck": ("trp_neck", []),
    "trp_shoulder": ("trp_shoulder", []),
    "trp_lower": ("trp_lower", []),
    "af_trp_etc": ("trp_etc", ""),
    "af_trp_intensity": ("trp_intensity", "중등도 (++)"),
    "af_trp_referred": ("trp_referred", ""),
    "af_diagnosis": ("diagnosis", ""),
    "af_problem": ("problem", ""),
    "af_cause": ("cause", ""),
    "af_t_hot": ("t_hot", False),
    "af_t_cold": ("t_cold", False),
    "af_t_us": ("t_us", "미시행"),
    "af_t_tens": ("t_tens", "미시행"),
    "af_t_laser": ("t_laser", False),
    "af_t_eswt": ("t_eswt", False),
    "af_t_traction": ("t_traction", False),
    "af_t_maitland": ("t_maitland", []),
    "af_t_maitland_area": ("t_maitland_area", ""),
    "af_t_met": ("t_met", False),
    "met_sel": ("t_met_area_sel", []),
    "met_etc": ("t_met_area_etc", ""),
    "af_t_ic": ("t_ic", False),
    "ic_sel": ("t_ic_area_sel", []),
    "ic_etc": ("t_ic_area_etc", ""),
    "af_t_prt": ("t_prt", False),
    "prt_sel": ("t_prt_area_sel", []),
    "prt_etc": ("t_prt_area_etc", ""),
    "af_t_mfr": ("t_mfr", False),
    "mfr_sel": ("t_mfr_area_sel", []),
    "mfr_etc": ("t_mfr_area_etc", ""),
    "af_t_init": ("t_init", False),
    "af_t_massage": ("t_massage", []),
    "mas_sel": ("t_massage_area_sel", []),
    "mas_etc": ("t_massage_area_etc", ""),
    "af_home_program": ("home_program", ""),
    "af_p_freq": ("freq", "주 1회"),
    "af_p_total": ("total", "2주"),
    "af_next_visit": ("next_visit", ""),
    "af_note": ("note", ""),
    "af_ms_left": ("ms_left", "5/5 (정상)"),
    "af_ms_right": ("ms_right", "5/5 (정상)"),
    "af_test_etc": ("test_etc", ""),
    "af_goal_short_pre": ("goal_short_pre", []),
    "af_goal_short_etc": ("goal_short_etc", ""),
    "af_goal_long_pre": ("goal_long_pre", []),
    "af_goal_long_etc": ("goal_long_etc", ""),
    "af_pt_age": ("pt_age", 40),
    "af_pt_gender": ("pt_gender", "남"),
    "af_pt_therapist": ("pt_therapist", ""),
    "af_pt_dx": ("pt_dx", ""),
}

# 특수검사 key 를 매핑에 자동 등록 (soap_json key = "af_" 제거)
for _region, _tests in SPECIAL_TESTS:
    for _label, _tkey in _tests:
        SOAP_STATE_MAP[_tkey] = (_tkey[3:], "미시행")


def init_soap_state():
    """모든 위젯 key 의 기본값을 session_state 에 보장 (위젯 생성 전 호출)."""
    for skey, (_jkey, default) in SOAP_STATE_MAP.items():
        if skey not in st.session_state:
            st.session_state[skey] = list(default) if isinstance(default, list) else default


def apply_soap_json(sj):
    """저장된 soap_json 값을 위젯 key 로 주입 (위젯 생성 전 호출)."""
    if not sj:
        return
    for skey, (jkey, default) in SOAP_STATE_MAP.items():
        if jkey not in sj or sj[jkey] is None:
            continue
        val = sj[jkey]
        if isinstance(default, bool):
            val = bool(val)
        elif isinstance(default, int):
            try:
                val = int(val)
            except (TypeError, ValueError):
                val = default
        elif isinstance(default, list):
            val = list(val) if isinstance(val, (list, tuple)) else default
        st.session_state[skey] = val

    # ── 구버전 데이터 호환 복원 ─────────────────────────────
    # 적용 부위: _sel 리스트가 없고 합쳐진 _area 문자열만 있으면 분해해서 복원
    for sel_key, area_jkey in [("met_sel", "t_met_area"), ("ic_sel", "t_ic_area"),
                               ("prt_sel", "t_prt_area"), ("mfr_sel", "t_mfr_area"),
                               ("mas_sel", "t_massage_area")]:
        sel_jkey = SOAP_STATE_MAP[sel_key][0]
        if not sj.get(sel_jkey) and sj.get(area_jkey):
            parts = [p.strip() for p in str(sj[area_jkey]).split(",") if p.strip()]
            if parts:
                st.session_state[sel_key] = parts
    # ROM 자유입력 부위: rom_free 없고 rom_text 만 있으면 채움
    if sj.get("rom_area") not in ("경추", "요추", "어깨(견관절)") \
            and not sj.get("rom_free") and sj.get("rom_text"):
        st.session_state["af_rom_free"] = sj["rom_text"]
    # 목표: pre 리스트가 없고 합쳐진 goal 문자열만 있으면 옵션/기타로 분리
    for pre_key, etc_key, joined_jkey, opts in [
            ("af_goal_short_pre", "af_goal_short_etc", "goal_short", GOAL_SHORT_OPTS),
            ("af_goal_long_pre", "af_goal_long_etc", "goal_long", GOAL_LONG_OPTS)]:
        pre_jkey = SOAP_STATE_MAP[pre_key][0]
        if not sj.get(pre_jkey) and sj.get(joined_jkey):
            items = [p.strip() for p in str(sj[joined_jkey]).split(",") if p.strip()]
            pre = [i for i in items if i in opts]
            etc = [i for i in items if i not in opts]
            if pre:
                st.session_state[pre_key] = pre
            if etc and not sj.get(SOAP_STATE_MAP[etc_key][0]):
                st.session_state[etc_key] = ", ".join(etc)


def request_chart_load(pt_key):
    """차트를 불러와 최근 회차 soap_json 을 다음 실행에서 위젯에 주입하도록 예약."""
    load_res = requests.get(f"{API_URL}/chart/load/{pt_key}", timeout=5).json()
    if load_res.get("sessions"):
        st.session_state["loaded_chart"] = load_res["sessions"]
        st.session_state["loaded_pt_key"] = pt_key
        st.session_state["pending_soap"] = load_res["sessions"][0].get("soap_json", {}) or {}
        return True
    return False


def ms_options(base, *state_keys):
    """multiselect 옵션 목록에 현재 저장된 선택값을 합쳐, 옵션에 없어서
    선택이 사라지거나 예외가 나는 것을 방지한다."""
    opts = list(dict.fromkeys(base))
    for k in state_keys:
        for v in (st.session_state.get(k) or []):
            if v not in opts:
                opts.append(v)
    return opts


def sel_state(key, options):
    """selectbox / select_slider 의 현재 값이 옵션에 없으면 첫 옵션으로 보정."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]


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
    # ── 위젯 생성 전에 상태 초기화 + 대기 중인 불러오기 적용 ──
    init_soap_state()
    if st.session_state.get("pending_soap") is not None:
        apply_soap_json(st.session_state.pop("pending_soap"))

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
                        if request_chart_load(pt_key):
                            st.success("✅ 차트를 불러왔습니다. 입력란에 반영됩니다.")
                            st.rerun()
                        else:
                            st.warning("불러올 세션이 없습니다.")
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
        # 최근 차트 참고용 표시
        if sessions:
            latest = sessions[0]
            st.markdown("### 📌 최근 차트 참고용 (읽기 전용)")
            st.info(f"📅 {latest.get('pt_date')} | {latest.get('pt_session')}회차 | {latest.get('pt_dx','')}")
            st.code(latest.get("chart_content",""), language=None)
            st.download_button(
                "📥 최근 차트 다운로드",
                latest.get("chart_content",""),
                file_name=f"최근차트_{pt_name_loaded}_{latest.get('pt_date','')}.txt",
                mime="text/plain",
                key="latest_download"
            )
        if st.button("❌ 닫기", key="chart_close_btn"):
            del st.session_state["loaded_chart"]
            st.rerun()
        st.markdown("---")

    with st.expander("👤 환자 기본 정보", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pt_chart_no = st.text_input("차트번호",
                key="input_chart_no",
                placeholder="입력 후 Enter")
            pt_name = st.text_input("환자명",
                key="input_pt_name",
                placeholder="입력 후 Enter")

            # 차트번호 또는 환자명 입력 시 자동 불러오기
            auto_search = pt_chart_no.strip() or pt_name.strip()
            if auto_search and auto_search != st.session_state.get("last_auto_search"):
                st.session_state["last_auto_search"] = auto_search
                try:
                    res = requests.get(f"{API_URL}/chart/search",
                        params={"q": auto_search}, timeout=3).json()
                    if res.get("results"):
                        pt_key = res["results"][0]["pt_key"]
                        if request_chart_load(pt_key):
                            st.rerun()
                except Exception:
                    pass

            if st.session_state.get("loaded_chart"):
                _lc = st.session_state["loaded_chart"][0]
                st.success(f"✅ {_lc.get('pt_name')} 최근 기록 불러옴 ({_lc.get('pt_date')})")
        with c2:
            if st.session_state.get("af_pt_age", 40) < 1:
                st.session_state["af_pt_age"] = 40
            pt_age = st.number_input("나이", min_value=1, max_value=120, key="af_pt_age")
            sel_state("af_pt_gender", ["남", "여"])
            pt_gender = st.selectbox("성별", ["남", "여"], key="af_pt_gender")
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
        s_nrs_now = st.slider("현재 NRS", 0, 10, key="s_nrs_now")
    with c2:
        s_nrs_worst = st.slider("최악 NRS", 0, 10, key="s_nrs_worst")
    with c3:
        s_nrs_best = st.slider("최선 NRS", 0, 10, key="s_nrs_best")
    _dur_opts = ["오늘 발생", "2~3일", "1주일", "2~4주", "1~3개월", "3개월 이상"]
    sel_state("s_duration", _dur_opts)
    s_duration = st.selectbox("지속 기간", _dur_opts, key="s_duration")
    st.write("**통증 양상** (해당되는 것 모두 선택)")
    _pain_q_opts = ["아프다 (통증)", "저린다 (저림)", "쑤신다 (심부통)", "멍멍한 느낌이다",
         "타는 듯하다 (작열감)", "찌르는 듯하다 (자통)", "당긴다 (긴장감)",
         "뻐근하다 (둔통)", "시큰거린다", "감각이 없다 (무감각)",
         "전기 오는 느낌이다 (방전감)", "무겁다 (중압감)", "욱신거린다 (박동통)",
         "칼로 베는 느낌이다 (예리한 통증)", "기타"]
    pain_quality = st.multiselect("통증 양상 선택",
        ms_options(_pain_q_opts, "af_pain_quality"),
        key="af_pain_quality")
    pain_quality_etc = st.text_input("기타 통증 양상 직접 입력", key="af_pain_quality_etc",
        placeholder="예: 바늘로 찌르는 느낌, 모래가 들어간 느낌")
    s_aggravating = st.text_input("악화 요인", key="af_aggravating", placeholder="예: 오래 앉아있을 때, 고개 돌릴 때")
    s_relieving = st.text_input("완화 요인", key="af_relieving", placeholder="예: 온찜질 후, 누웠을 때")
    s_adl = st.text_area("일상생활 장애", key="af_adl", placeholder="예: 컴퓨터 작업 30분 이상 어려움, 수면 장애", height=60)
    st.divider()
    st.markdown('<div class="soap-label">O - 객관적 소견 (Objective)</div>', unsafe_allow_html=True)
    st.write("**자세 평가**")
    c1, c2, c3 = st.columns(3)
    with c1:
        _fhp_opts = ["없음", "+1cm", "+2cm", "+3cm 이상"]
        sel_state("af_posture_fhp", _fhp_opts)
        o_fhp = st.selectbox("전방 두부 자세", _fhp_opts, key="af_posture_fhp")
        _sh_opts = ["좌우 대칭", "우측 하강", "좌측 하강"]
        sel_state("af_posture_shoulder", _sh_opts)
        o_shoulder = st.selectbox("어깨 높이", _sh_opts, key="af_posture_shoulder")
    with c2:
        _plr_opts = ["좌우 대칭", "우측 하강 (좌측 상승)", "좌측 하강 (우측 상승)"]
        sel_state("af_posture_pelvis_lr", _plr_opts)
        o_pelvis_lr = st.selectbox("골반 좌우 경사", _plr_opts, key="af_posture_pelvis_lr")
        _pfb_opts = ["정상", "전방 경사 (anterior tilt)", "후방 경사 (posterior tilt)"]
        sel_state("af_posture_pelvis_fb", _pfb_opts)
        o_pelvis_fb = st.selectbox("골반 전후 경사", _pfb_opts, key="af_posture_pelvis_fb")
    with c3:
        _spine_opts = ["없음", "우측 만곡", "좌측 만곡", "S자형"]
        sel_state("af_posture_spine", _spine_opts)
        o_spine = st.selectbox("척추 측만", _spine_opts, key="af_posture_spine")
        o_posture_etc = st.text_input("기타 자세 소견", key="af_posture_etc")
    st.write("**관절 가동범위 (ROM)**")
    _rom_opts = ["경추", "흉추", "요추", "어깨(견관절)", "팔꿈치", "손목", "고관절", "무릎", "발목"]
    sel_state("af_rom_area", _rom_opts)
    rom_area = st.selectbox("측정 부위", _rom_opts, key="af_rom_area")
    if rom_area == "경추":
        c1, c2, c3 = st.columns(3)
        with c1:
            rf = st.number_input("굴곡 (정상 45°)", 0, 90, key="rom_c_flex")
            re = st.number_input("신전 (정상 55°)", 0, 90, key="rom_c_ext")
        with c2:
            rlf = st.number_input("좌측굴 (정상 40°)", 0, 60, key="rom_c_lf")
            rrf = st.number_input("우측굴 (정상 40°)", 0, 60, key="rom_c_rf")
        with c3:
            rlr = st.number_input("좌회전 (정상 70°)", 0, 90, key="rom_c_lr")
            rrr = st.number_input("우회전 (정상 70°)", 0, 90, key="rom_c_rr")
        rom_text = f"굴곡 {rf}°/ 신전 {re}°/ 좌측굴 {rlf}°/ 우측굴 {rrf}°/ 좌회전 {rlr}°/ 우회전 {rrr}°"
    elif rom_area == "요추":
        c1, c2, c3 = st.columns(3)
        with c1:
            rf = st.number_input("굴곡 (정상 75°)", 0, 90, key="rom_l_flex")
            re = st.number_input("신전 (정상 30°)", 0, 60, key="rom_l_ext")
        with c2:
            rlf = st.number_input("좌측굴 (정상 35°)", 0, 60, key="rom_l_lf")
            rrf = st.number_input("우측굴 (정상 35°)", 0, 60, key="rom_l_rf")
        with c3:
            rlr = st.number_input("좌회전 (정상 30°)", 0, 60, key="rom_l_lr")
            rrr = st.number_input("우회전 (정상 30°)", 0, 60, key="rom_l_rr")
        rom_text = f"굴곡 {rf}°/ 신전 {re}°/ 좌측굴 {rlf}°/ 우측굴 {rrf}°/ 좌회전 {rlr}°/ 우회전 {rrr}°"
    elif rom_area == "어깨(견관절)":
        c1, c2, c3 = st.columns(3)
        with c1:
            ra = st.number_input("외전 (정상 180°)", 0, 180, key="rom_s_abd")
            rf2 = st.number_input("굴곡 (정상 180°)", 0, 180, key="rom_s_flex")
        with c2:
            rer = st.number_input("외회전 (정상 90°)", 0, 90, key="rom_s_er")
            rir = st.number_input("내회전 (정상 90°)", 0, 90, key="rom_s_ir")
        with c3:
            re2 = st.number_input("신전 (정상 45°)", 0, 60, key="rom_s_ext")
        rom_text = f"외전 {ra}°/ 굴곡 {rf2}°/ 외회전 {rer}°/ 내회전 {rir}°/ 신전 {re2}°"
    else:
        rom_text = st.text_area("ROM 직접 입력", key="af_rom_free",
            placeholder="예: 굴곡 130°/ 신전 10°/ 외전 40°", height=60)
    st.write("**근력 검사**")
    c1, c2 = st.columns(2)
    _ms_opts = ["5/5 (정상)", "4/5 (양호)", "3/5 (보통)", "2/5 (불량)", "1/5 (미약)", "0/5 (없음)"]
    with c1:
        sel_state("af_ms_left", _ms_opts)
        ms_left = st.selectbox("좌측 근력", _ms_opts, key="af_ms_left")
    with c2:
        sel_state("af_ms_right", _ms_opts)
        ms_right = st.selectbox("우측 근력", _ms_opts, key="af_ms_right")
    st.write("**트리거 포인트 (TrP) 압통 부위**")
    _trp_neck_opts = ["상부 승모근 우", "상부 승모근 좌", "중부 승모근 우", "중부 승모근 좌",
         "하부 승모근 우", "하부 승모근 좌", "견갑거근 우", "견갑거근 좌",
         "흉쇄유돌근 우", "흉쇄유돌근 좌", "사각근 우", "사각근 좌",
         "후두하근 우", "후두하근 좌", "반극근 우", "반극근 좌",
         "경장근 우", "경장근 좌"]
    _trp_shoulder_opts = ["극상근 우", "극상근 좌", "극하근 우", "극하근 좌",
         "소원근 우", "소원근 좌", "견갑하근 우", "견갑하근 좌",
         "능형근 우", "능형근 좌", "전거근 우", "전거근 좌",
         "대흉근 우", "대흉근 좌", "소흉근 우", "소흉근 좌",
         "광배근 우", "광배근 좌", "삼각근 우", "삼각근 좌",
         "이두근 우", "이두근 좌", "삼두근 우", "삼두근 좌",
         "전완 신전근 우", "전완 신전근 좌", "전완 굴근 우", "전완 굴근 좌"]
    _trp_lower_opts = ["요방형근 우", "요방형근 좌", "장요근 우", "장요근 좌",
         "다열근 우", "다열근 좌", "척추기립근 우", "척추기립근 좌",
         "이상근 우", "이상근 좌", "대둔근 우", "대둔근 좌",
         "중둔근 우", "중둔근 좌", "소둔근 우", "소둔근 좌",
         "대퇴사두근 우", "대퇴사두근 좌", "슬괵근 우", "슬괵근 좌",
         "장경인대 우", "장경인대 좌", "비복근 우", "비복근 좌",
         "가자미근 우", "가자미근 좌", "족저근막 우", "족저근막 좌"]
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.write("🔵 목/어깨")
        trp_neck = st.multiselect("목/어깨 근육",
            ms_options(_trp_neck_opts, "trp_neck"), key="trp_neck")
    with col_b:
        st.write("🔵 어깨/등/팔")
        trp_shoulder = st.multiselect("어깨/등/팔 근육",
            ms_options(_trp_shoulder_opts, "trp_shoulder"), key="trp_shoulder")
    with col_c:
        st.write("🔵 허리/하지")
        trp_lower = st.multiselect("허리/하지 근육",
            ms_options(_trp_lower_opts, "trp_lower"), key="trp_lower")
    trp_etc = st.text_input("기타 압통 부위 직접 입력", key="af_trp_etc", placeholder="예: 우측 측두근, 좌측 저작근, 오구완근 우")
    c1, c2 = st.columns(2)
    with c1:
        _trp_int_opts = ["경증 (+)", "중등도 (++)", "중증 (+++)"]
        sel_state("af_trp_intensity", _trp_int_opts)
        trp_intensity = st.select_slider("압통 강도", options=_trp_int_opts, key="af_trp_intensity")
    with c2:
        trp_referred = st.text_input("연관통 패턴", key="af_trp_referred", placeholder="예: 우측 측두부, 팔 외측, 엄지/검지")
    # 클릭 가능한 "특수검사" 타이틀 → 참고 가이드 토글
    _th1, _th2 = st.columns([1.4, 4])
    with _th1:
        if st.button("🔎 특수검사 📖", key="btn_test_guide",
                     help="클릭하면 부위별 검사 방법·양성·의미 가이드가 열립니다"):
            st.session_state["show_test_guide"] = not st.session_state.get("show_test_guide", False)
    with _th2:
        st.caption("부위별 · 시행한 검사만 선택 · 타이틀을 누르면 참고 가이드")
    if st.session_state.get("show_test_guide", False):
        with st.expander("📖 특수검사 참고 가이드 (방법 · 양성 소견 · 임상적 의미)", expanded=True):
            for _gregion, _gitems in TEST_GUIDE:
                st.markdown(f"**🔹 {_gregion}**")
                for _gname, _gdesc in _gitems:
                    st.markdown(f"- **{_gname}** — {_gdesc}")
                st.markdown("")
    for _region, _tests in SPECIAL_TESTS:
        _done_cnt = sum(1 for _l, _sk in _tests
                        if st.session_state.get(_sk, "미시행") != "미시행")
        with st.expander(f"🔎 {_region}" + (f"  ·  시행 {_done_cnt}건" if _done_cnt else ""),
                         expanded=_done_cnt > 0):
            # 한 줄에 2개씩 배치 (행마다 새 컬럼 생성)
            for _i in range(0, len(_tests), 2):
                _cc = st.columns(2)
                for _j, (_tlabel, _tkey) in enumerate(_tests[_i:_i + 2]):
                    with _cc[_j]:
                        sel_state(_tkey, TEST_OPTS)
                        st.selectbox(_tlabel, TEST_OPTS, key=_tkey)
    test_etc = st.text_input("기타 검사 직접 입력", key="af_test_etc",
        placeholder="예: Hawkins (+), Neer (-)")
    # 차트 텍스트용: 시행한(미시행 아닌) 검사만 부위별로 정리
    _st_lines = []
    for _region, _tests in SPECIAL_TESTS:
        _done = [f"{_l}: {st.session_state.get(_sk)}"
                 for _l, _sk in _tests if st.session_state.get(_sk, "미시행") != "미시행"]
        if _done:
            _st_lines.append(f"  [{_region}] " + " | ".join(_done))
    if test_etc:
        _st_lines.append(f"  [기타] {test_etc}")
    special_tests_text = "\n".join(_st_lines) if _st_lines else "  시행한 특수검사 없음"
    st.divider()
    st.markdown('<div class="soap-label">A - 평가 (Assessment)</div>', unsafe_allow_html=True)
    a_diagnosis = st.text_input("진단/소견", key="af_diagnosis", placeholder="예: 경추 MPS, C4-5 분절 관련")
    a_problem = st.text_area("주요 문제점", key="af_problem", placeholder="예: 우측 상부 승모근 활성 TrP, 경추 ROM 제한", height=60)
    a_cause = st.text_area("연관 요인", key="af_cause", placeholder="예: 장시간 컴퓨터 작업, 전방 두부 자세", height=60)
    c1, c2 = st.columns(2)
    with c1:
        a_goal_short_pre = st.multiselect("단기 목표 선택",
            ms_options(GOAL_SHORT_OPTS, "af_goal_short_pre"), key="af_goal_short_pre")
        a_goal_short_etc = st.text_input("단기 목표 직접 입력", key="af_goal_short_etc",
            placeholder="예: NRS 7→4, 경추 회전 50°→70°")
        a_goal_short = ', '.join(a_goal_short_pre) + (f', {a_goal_short_etc}' if a_goal_short_etc else '')
    with c2:
        a_goal_long_pre = st.multiselect("장기 목표 선택",
            ms_options(GOAL_LONG_OPTS, "af_goal_long_pre"), key="af_goal_long_pre")
        a_goal_long_etc = st.text_input("장기 목표 직접 입력", key="af_goal_long_etc",
            placeholder="예: TrP 비활성화, 정상 자세 유지")
        a_goal_long = ', '.join(a_goal_long_pre) + (f', {a_goal_long_etc}' if a_goal_long_etc else '')
    st.divider()
    st.markdown('<div class="soap-label">P - 치료 계획 (Plan)</div>', unsafe_allow_html=True)
    st.write("**치료 기법 체크리스트**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("🌡️ 물리치료")
        t_hot = st.checkbox("온찜질 (15분)", key="af_t_hot")
        t_cold = st.checkbox("냉찜질 (15분)", key="af_t_cold")
        _us_opts = ["미시행", "1MHz 연속", "3MHz 연속", "1MHz 맥동", "3MHz 맥동"]
        sel_state("af_t_us", _us_opts)
        t_us = st.selectbox("초음파", _us_opts, key="af_t_us")
        _tens_opts = ["미시행", "고주파 80~100Hz", "저주파 2~4Hz", "혼합파"]
        sel_state("af_t_tens", _tens_opts)
        t_tens = st.selectbox("TENS", _tens_opts, key="af_t_tens")
        t_laser = st.checkbox("레이저 치료", key="af_t_laser")
        t_eswt = st.checkbox("체외충격파 (ESWT)", key="af_t_eswt")
        t_traction = st.checkbox("견인 치료", key="af_t_traction")
    with c2:
        st.write("🤲 도수치료")
        t_maitland = st.multiselect("Maitland 가동술",
            ms_options(["Grade I", "Grade II", "Grade III", "Grade IV", "Grade V (Thrust)"], "af_t_maitland"),
            key="af_t_maitland")
        t_maitland_area = st.text_input("Maitland 적용 부위", key="af_t_maitland_area", placeholder="예: C4-5 우측 PA glide")
        t_met = st.checkbox("MET (근에너지 기법)", key="af_t_met")
        _trp_all = trp_neck + trp_shoulder + trp_lower + ([trp_etc] if trp_etc else [])
        t_met_area_sel = st.multiselect("MET 적용 부위 (TrP 목록)",
            ms_options(_trp_all, "met_sel"), key="met_sel")
        t_met_area_etc = st.text_input("MET 직접 입력", placeholder="예: 상부 승모근 PIR 6초×5회", key="met_etc")
        t_met_area = ', '.join(t_met_area_sel) + (f', {t_met_area_etc}' if t_met_area_etc else '')
        t_ic = st.checkbox("허혈성 압박 (TrP)", key="af_t_ic")
        t_ic_area_sel = st.multiselect("허혈성 압박 부위 (TrP 목록)",
            ms_options(_trp_all, "ic_sel"), key="ic_sel")
        t_ic_area_etc = st.text_input("허혈성 압박 직접 입력", placeholder="예: 견갑거근 TrP 10초×5회", key="ic_etc")
        t_ic_area = ', '.join(t_ic_area_sel) + (f', {t_ic_area_etc}' if t_ic_area_etc else '')
        t_prt = st.checkbox("위치해제 (PRT)", key="af_t_prt")
        t_prt_area_sel = st.multiselect("PRT 적용 부위 (TrP 목록)",
            ms_options(_trp_all, "prt_sel"), key="prt_sel")
        t_prt_area_etc = st.text_input("PRT 직접 입력", placeholder="예: 상부 승모근 90초", key="prt_etc")
        t_prt_area = ', '.join(t_prt_area_sel) + (f', {t_prt_area_etc}' if t_prt_area_etc else '')
    with c3:
        st.write("🔧 기타 기법")
        t_iastm = False
        t_iastm_area = ""
        t_mfr = st.checkbox("근막 이완 (MFR)", key="af_t_mfr")
        t_mfr_area_sel = st.multiselect("MFR 적용 부위 (TrP 목록)",
            ms_options(_trp_all, "mfr_sel"), key="mfr_sel")
        t_mfr_area_etc = st.text_input("MFR 직접 입력", placeholder="예: 흉요근막 J-스트로크 3분", key="mfr_etc")
        t_mfr_area = ', '.join(t_mfr_area_sel) + (f', {t_mfr_area_etc}' if t_mfr_area_etc else '')
        t_init = st.checkbox("INIT 통합기법", key="af_t_init")
        t_massage = st.multiselect("마사지 기법",
            ms_options(["경찰법 (Effleurage)", "유날법 (Petrissage)", "마찰법 (Friction)", "스트리핑 (Stripping)", "교차 마찰 (Cross-fiber)"], "af_t_massage"),
            key="af_t_massage")
        t_massage_area_sel = st.multiselect("마사지 적용 부위 (TrP 목록)",
            ms_options(_trp_all, "mas_sel"), key="mas_sel")
        t_massage_area_etc = st.text_input("마사지 직접 입력", placeholder="예: 상부 승모근, 경추 주변", key="mas_etc")
        t_massage_area = ', '.join(t_massage_area_sel) + (f', {t_massage_area_etc}' if t_massage_area_etc else '')
    st.write("**홈 프로그램**")
    p_home = st.text_area("홈 운동 처방",
        key="af_home_program",
        placeholder="예:\n- 경추 측방 굴곡 스트레칭: 30초×3회, 하루 3세트\n- 턱당김 운동: 10초×10회, 하루 2회",
        height=150)
    c1, c2, c3 = st.columns(3)
    with c1:
        _freq_opts = ["주 1회", "주 2회", "주 3회", "격일", "매일"]
        sel_state("af_p_freq", _freq_opts)
        p_freq = st.selectbox("치료 빈도", _freq_opts, key="af_p_freq")
    with c2:
        _total_opts = ["2주", "4주", "6주", "8주", "12주", "기타"]
        sel_state("af_p_total", _total_opts)
        p_total = st.selectbox("총 치료 기간", _total_opts, key="af_p_total")
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
{special_tests_text}

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
                    save_soap_json = {
                            "nrs_now": s_nrs_now,
                            "nrs_worst": s_nrs_worst,
                            "nrs_best": s_nrs_best,
                            "t_maitland": t_maitland,
                            "t_maitland_area": t_maitland_area,
                            "t_met_area_sel": t_met_area_sel,
                            "t_ic_area_sel": t_ic_area_sel,
                            "t_prt_area_sel": t_prt_area_sel,
                            "t_mfr_area_sel": t_mfr_area_sel,
                            "t_massage_area_sel": t_massage_area_sel,
                            "t_met_area_etc": t_met_area_etc,
                            "t_ic_area_etc": t_ic_area_etc,
                            "t_prt_area_etc": t_prt_area_etc,
                            "t_mfr_area_etc": t_mfr_area_etc,
                            "t_massage_area_etc": t_massage_area_etc,
                            "t_met": t_met,
                            "t_met_area": t_met_area,
                            "t_ic": t_ic,
                            "t_ic_area": t_ic_area,
                            "t_prt": t_prt,
                            "t_prt_area": t_prt_area,
                            "t_mfr": t_mfr,
                            "t_mfr_area": t_mfr_area,
                            "t_init": t_init,
                            "t_massage": t_massage,
                            "t_massage_area": t_massage_area,
                            "t_hot": t_hot,
                            "t_cold": t_cold,
                            "t_laser": t_laser,
                            "t_eswt": t_eswt,
                            "t_traction": t_traction,
                            "t_us": t_us,
                            "t_tens": t_tens,
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
                            "rom_c_flex": st.session_state.get("rom_c_flex", 40),
                            "rom_c_ext": st.session_state.get("rom_c_ext", 45),
                            "rom_c_lf": st.session_state.get("rom_c_lf", 35),
                            "rom_c_rf": st.session_state.get("rom_c_rf", 35),
                            "rom_c_lr": st.session_state.get("rom_c_lr", 60),
                            "rom_c_rr": st.session_state.get("rom_c_rr", 60),
                            "rom_l_flex": st.session_state.get("rom_l_flex", 60),
                            "rom_l_ext": st.session_state.get("rom_l_ext", 25),
                            "rom_l_lf": st.session_state.get("rom_l_lf", 30),
                            "rom_l_rf": st.session_state.get("rom_l_rf", 30),
                            "rom_l_lr": st.session_state.get("rom_l_lr", 25),
                            "rom_l_rr": st.session_state.get("rom_l_rr", 25),
                            "rom_s_abd": st.session_state.get("rom_s_abd", 160),
                            "rom_s_flex": st.session_state.get("rom_s_flex", 160),
                            "rom_s_er": st.session_state.get("rom_s_er", 70),
                            "rom_s_ir": st.session_state.get("rom_s_ir", 70),
                            "rom_s_ext": st.session_state.get("rom_s_ext", 40),
                            "rom_free": st.session_state.get("af_rom_free", ""),
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
                            "goal_short_pre": a_goal_short_pre,
                            "goal_short_etc": a_goal_short_etc,
                            "goal_long_pre": a_goal_long_pre,
                            "goal_long_etc": a_goal_long_etc,
                            "ms_left": ms_left,
                            "ms_right": ms_right,
                            "test_etc": test_etc,
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
                    # 특수검사 결과 전체 포함
                    for _region, _tests in SPECIAL_TESTS:
                        for _label, _tkey in _tests:
                            save_soap_json[_tkey[3:]] = st.session_state.get(_tkey, "미시행")
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
                        "soap_json": save_soap_json,
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
{special_tests_text}

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
