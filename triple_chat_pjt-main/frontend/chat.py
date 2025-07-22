# 웹 애플리케이션 UI를 만들기 위한 라이브러리
import streamlit as st
# 백엔드(DRF)에 HTTP 요청을 보내기 위한 라이브러리
import requests
# 상태코드
from rest_framework import status

def description():
    '''
    ✅ 사용자가 입력한 메시지를 Django REST Framework(DRF) 백엔드로 보내고, 백엔드에서 받은 응답을 화면에 표시하는 구조.
    ✅ DRF 엔드포인트 http://127.0.0.1:8000/api/v1/triple/chat/로 POST 요청을 보내서 챗봇 응답을 가져옴.
    ✅ 로그인 없이 chatbot 사용가능.
    ✅ 세션을 유지하는 이유는 사용자의 대화 기록을 저장하고 관리하기 위함.
    (st.session_state는 사용자의 대화 기록을 유지하는 데 사용되지만, 인증 정보는 저장하지 않음.
    즉, 사용자 식별 없이 누구든지 메시지를 입력하고 응답을 받을 수 있음.)
    '''
    pass

# DRF 백엔드 URL (이 URL로 사용자 메시지를 POST 요청해서 챗봇 응답을 받아옴)
API_URL = "http://127.0.0.1:8000/api/v1/triple/chat/"

# 앱 제목
st.title("🤖chatbot")

# 채팅 기록을 유지하기 위해 st.session_state(사용자의 세션 동안 데이터를 저장하고 유지) 사용
if "messages" not in st.session_state:
    # session_state는 딕셔너리처럼 동작하는 객체로, 데이터를 저장할 수 있음(💡기본적으로 딕셔너리처럼 작동하지만, 속성(.)처럼 접근할 수 있음)
    # messages라는 속성(키)을 리스트로 초기화
    st.session_state.messages = []

# 반복문을 돌며 이전 대화 표시
for message in st.session_state.messages:
    # chat_message(role)은 채팅 UI에서 말풍선을 생성하는 컨텍스트 매니저(with 블록을 사용해서 시작과 종료를 자동으로 처리. 블록 안의 코드가 말풍선 안에서 실행되도록 해줌.)
    # message["role"]에는 해당 key의 value인 "user" 또는 "assistant" 값이 들어감(user:사용자.오른쪽에 위치/assistant:챗봇.왼쪽에 위치)
    with st.chat_message(message["role"]):
        # 컨텍스트 블록 안에서 st.write() 등을 사용하여 내용 표시
        # message["content"]는 실제 채팅 메시지
        st.write(message["content"])

# 사용자 입력 받기
# st.chat_input()은 엔터를 치면 입력한 값이 반환됨
user_input = st.chat_input("메시지를 입력하세요...")

# 사용자가 입력했다면
if user_input:
    # 사용자의 입력 메시지를 messages에 저장
    st.session_state.messages.append({"role": "user", "content": user_input})
    # 사용자의 입력 메시지를 바로 말풍선에 표시
    with st.chat_message("user"):
        st.write(user_input)

    # ⭐️ DRF 백엔드에 POST 요청 보내기
    # response 에 최종적으로 담기는 것은 사용자의 입력 메시지에 대한 모델의 응답
    response = requests.post(API_URL, json={"topic": user_input})

    # 요청이 성공했다면
    if response.status_code == status.HTTP_200_OK:
        # 응답 전문(response.json())에서 'reply'라는 key의 value로 모델이 생성한 응답을 받아온다고 가정.
        # 'reply'라는 키의 값이 없다면 "응답을 받을 수 없습니다."로 기본값 설정
        bot_reply = response.json().get("response", "응답을 받을 수 없습니다.")
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        bot_reply = response.json().get("error", "응답을 받을 수 없습니다.")
        
    # 요청이 실패했다면
    else:
        bot_reply = response.json().get("error", "응답을 받을 수 없습니다.")

    # 챗봇의 응답을 messages에 저장
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    # 챗봇의 응답을 바로 말풍선에 표시
    with st.chat_message("assistant"):
        st.write(bot_reply)
    
    
# # 💊 디버깅(대화가 잘 저장되고 있는지 확인하기)
# st.write(st.session_state.messages)
## Stream lit  message classifictaion
