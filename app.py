import streamlit as st
import requests

st.title("근막통증증후군(MPS) 자가 관리 가이드")

part = st.text_input("아픈 부위 (예: 목, 어깨)")
level = st.slider("통증 강도", 1, 10, 5)
symptoms = st.text_area("증상 설명")

if st.button("AI 맞춤 루틴 생성하기"):
    try:
        response = requests.post("http://localhost:8000/get-routine", 
                                 json={"part": part, "level": level, "symptoms": symptoms})
        if response.status_code == 200:
            st.write(response.json().get("routine"))
        else:
            st.error("서버 응답 오류")
    except Exception as e:
        st.error(f"연결 오류: {e}")
