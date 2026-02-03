# update views.py
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from django.conf import settings
from .models import User, Chat, RagData, SearchLog
from .serializers import ChatSerializer, RagDataSerializer
import logging
from langchain.schema.runnable import RunnablePassthrough
import os
from langchain.vectorstores import Chroma

logger = logging.getLogger(__name__)

class ChatRateThrottle(UserRateThrottle):
    rate = '5/minute'


# 수정된 코드
# generate_rag_response 함수 매개변수 수정
def generate_rag_response(docs, topic, chat_instance):
    if not docs:
        return "검색된 정보가 없습니다."
    
    # 매개변수로 받은 docs 정제
    context = "\n".join(doc.page_content for doc in docs)
    
    # 🚨 수정
    # RagData 모델 인스턴스 생성 후, chat_instance 의 data_id 필드 채워주기
    rag_data = {
        "data_text": context,
    }
    serializer = RagDataSerializer(data=rag_data)
    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    rag_instance = serializer.save()
    
    chat_instance.data_id = rag_instance.data_id
    chat_instance.save()
    # 🚨 수정 끝
    
    # AI에게 질문을 던질 때 사용할 프롬프트(입력 메시지)
    prompt = ChatPromptTemplate.from_template("""
    Answer the question based solely on the context below. 
    If you don't know, say you don't know

    Context:
    {context}

    Question:
    {topic}
    """)
    
    # model
    model = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
    
    # parser
    output_parser = StrOutputParser()
    
    # chain
    chain = (
        {
            "context": RunnablePassthrough(), 
            "topic": RunnablePassthrough()   
        }
        | prompt
        | model
        | output_parser
    )
    
    response = chain.invoke({"context": context, "topic": topic})
    
    return response


class ChatAPIView(APIView):
    throttle_classes = [ChatRateThrottle]
        
    def post(self, request):
        try:
            topic = request.data.get("topic")
            if not topic:
                return Response(
                    {"error": "Topic is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_id = request.COOKIES.get('user_id')
            if not user_id:
                return Response(
                    {"error": "User ID is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            chat_data = {
                "user": user_id,
                "question_text": topic
            }
            serializer = ChatSerializer(data=chat_data)
            if not serializer.is_valid():
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            chat_instance = serializer.save()
            
            # 🚨 수정
            # 벡터DB 경로 설정("vector_store" 폴더 경로)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            vector_store_path = os.path.join(base_dir, "vector_store")
            
            # 임베딩 도구 설정
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            # 백터 DB 설정
            vector_store = Chroma(persist_directory=vector_store_path, embedding_function=embeddings)
            
            # 문서 청크(chunk) 개수
            num_docs = vector_store._collection.count()
            print(f"\n현재 벡터 저장소 문서 개수: {num_docs}\n")
            if num_docs == 0:
                return Response({"error": "No data found in vector store"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # retriever
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            # retriever가 찾아온 문서 리스트
            docs = retriever.invoke(topic)

            print(f"검색된 문서 개수: {len(docs)}")
            for doc in docs:
                print(f"검색된 문서 내용: {doc.page_content}")
            
            if not docs:
                return Response({"error": "No relevant documents found in vector store"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            chat_model_output = generate_rag_response(docs, topic, chat_instance)
            # 🚨 수정 끝
            
            # Update chat instance with response
            chat_instance.response_text = chat_model_output
            chat_instance.save()
            
            return Response({
                "answer": chat_model_output,
                "chat_id": chat_instance.question_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in ChatAPIView: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
            
class ChatUserAPIView(APIView):
    
    def post(self, request):
        try:
            user_id = request.COOKIES.get('user_id') 
                            
            if not user_id:
                user = User.objects.create()
                user_id = user.user_id
                
            return Response({
                "user_id": user_id
            }, 
            status=status.HTTP_200_OK)    
        except Exception as e:
            logger.error(f"Error in ChatUserAPIView: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
