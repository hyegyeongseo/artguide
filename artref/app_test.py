# streamlit run app_test.py
import streamlit as st, requests
st.title("그림 코칭 테스트")
msg = st.text_input("메시지 (예: 손이 어색해요)")
img = st.file_uploader("그림 업로드", type=["png", "jpg", "jpeg"])
if st.button("분석") and img:
    r = requests.post("http://localhost:8000/guide",
                      files={"file": (img.name, img.getvalue())},
                      data={"message": msg})
    st.json(r.json())
