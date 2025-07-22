from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from .models import User, Chat, RagData, SearchLog
from .serializers import ChatSerializer, RagDataSerializer, SearchLogSerializer
import logging
from langchain.schema import Document
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pathlib import Path
import pandas as pd
import os
from openai import OpenAIError
from .redis_manager import RedisMessageManager

# Ensure OpenAI API key is set
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

logger = logging.getLogger(__name__)

def get_message_store() -> RedisMessageManager:
    """Get or create a Redis message manager instance with error handling"""
    try:
        return RedisMessageManager()
    except Exception as e:
        logger.error(f"Failed to initialize RedisMessageManager: {str(e)}")
        raise

from .utils import RAGUtils

# For backward compatibility
def get_rag_context(question: str) -> Dict[str, Any]:
    """Backwards compatibility wrapper for the RAGUtils class method"""
    return RAGUtils.get_rag_context(question)

class RedisMessageHistory(BaseChatMessageHistory):
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Return a list of messages from Redis"""
        try:
            message_store = get_message_store()
            raw_messages = message_store.get_messages(self.user_id)
            
            # Convert raw messages to LangChain BaseMessage objects
            result = []
            for msg in raw_messages:
                if msg.get("role") == "assistant":
                    result.append(AIMessage(content=msg.get("content", "")))
                else:
                    result.append(HumanMessage(content=msg.get("content", "")))
            
            return result
        except Exception as e:
            logger.error(f"Error retrieving messages from history: {str(e)}")
            return []
        
    def add_message(self, message: BaseMessage) -> None:
        try:
            message_data = {
                "role": "assistant" if isinstance(message, AIMessage) else "user",
                "content": message.content
            }
            message_store = get_message_store()
            message_store.save_message(self.user_id, message_data)
        except Exception as e:
            logger.error(f"Error adding message to history: {str(e)}")
            
    def clear(self) -> None:
        try:
            message_store = get_message_store()
            message_store.clear_messages(self.user_id)
        except Exception as e:
            logger.error(f"Error clearing message history: {str(e)}")

def history_session_handler(session_id: str) -> BaseChatMessageHistory:
    return RedisMessageHistory(session_id)

class ChatRateThrottle(UserRateThrottle):
    rate = '60/minute'  # Increased for development

from rest_framework.permissions import AllowAny

class ChatAPIView(APIView):
    throttle_classes = [ChatRateThrottle]
        
    def post(self, request):
        try:
            question = request.data.get("question")
            if not question:
                return Response(
                    {"error": "질문을 입력해주세요."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get user_id from JSON payload instead of cookies
            user_id = request.data.get('user_id')
            if not user_id:
                return Response(
                    {"error": "사용자 ID가 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Question Data Save
            chat_data = {
                "user": user_id,
                "question_text": question
            }
            chat_serializer = ChatSerializer(data=chat_data)
            if not chat_serializer.is_valid():
                return Response(
                    chat_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            chat_instance = chat_serializer.save()
            
            # RAG Context
            rag_context = get_rag_context(question)
            context = rag_context["context"]
            image_paths = rag_context["image_paths"]
            
            images = []
            for image_path in image_paths:
                cleaned_images = [img.strip() for img in image_path.split("\n") if img.strip()]
                images.extend(cleaned_images)
    
            # RagData Save
            rag_data = {
                "data_text": context,
                "image_urls": image_paths,
            }
            rag_serializer = RagDataSerializer(data=rag_data)
            if not rag_serializer.is_valid():
                return Response(
                    rag_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            rag_instance = rag_serializer.save()
    
            # Update chat instance with response
            chat_instance.data_id = rag_instance.data_id
            chat_instance.save()

            # SearchLog Data Save
            search_log_data = {
                "data": rag_instance.data_id,
                "question": chat_instance.question_id
            }
            search_log_serializer = SearchLogSerializer(data=search_log_data)
            if not search_log_serializer.is_valid():
                return Response(
                    search_log_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            search_log_serializer.save()

            # Update history
            history = history_session_handler(user_id)
            history.add_message(AIMessage(content=question))
            
            # Generate response
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a friendly assistant. Use the following context to inform your answer: {context}"),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ])
            
            # Import API key from utils
            from .utils import API_KEY
            
            output_parser = StrOutputParser()
            model = ChatOpenAI(
                model="gpt-4o-mini",  # 'mini' 모델 사용
                temperature=0.7,
                request_timeout=30,
                openai_api_key=API_KEY
            )
            
            chain = prompt | model | output_parser
            chain_with_history = RunnableWithMessageHistory(
                chain,
                history_session_handler,
                input_messages_key="question",
                history_messages_key="history",
            )

            chat_model_output = chain_with_history.invoke(
                {
                    "context": context,
                    "question": question
                },
                config={"configurable": {"session_id": user_id}}
            )
            
            # Save response
            chat_instance.response_text = chat_model_output
            chat_instance.save()
            
            return Response({
                "response": chat_model_output,
                "chat_id": chat_instance.question_id,
                "images": images
            }, status=status.HTTP_200_OK)
                
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return Response(
                {"error": "OpenAI API error occurred. Please check your API key or try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
                
        except Exception as e:
            logger.error(f"Error in ChatAPIView: {str(e)}")
            return Response(
                {"error": "죄송합니다. 서비스 처리 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

            
class ChatUserAPIView(APIView):
    
    def post(self, request):
        try:
            # Check for existing user_id in the request
            existing_user_id = request.data.get("user_id")
            
            # If user_id is provided, check if the user exists
            if existing_user_id:
                logger.info(f"Checking for existing user with ID: {existing_user_id}")
                try:
                    user = User.objects.get(user_id=existing_user_id)
                    
                    # Update the session in Redis
                    redis_manager = get_message_store()
                    redis_manager.set_session(existing_user_id)
                    
                    return Response({
                        "user_id": user.user_id
                    }, status=status.HTTP_200_OK)
                except User.DoesNotExist:
                    logger.warning(f"User with ID {existing_user_id} not found, creating new user")
                    # Continue to create a new user
            
            # If we're here, either no user_id was provided or the user wasn't found
            
            # Mark previous user as expired
            latest_user = User.objects.order_by('-created_datetime').first()
            if latest_user:
                User.objects.filter(user_id=latest_user.user_id).update(expired_datetime=timezone.now())
                
                # Clear message history for previous user
                try:
                    message_store = get_message_store()
                    message_store.clear_messages(latest_user.user_id)
                except Exception as e:
                    logger.warning(f"Failed to clear message history: {str(e)}")

            # Create new user - User model doesn't have username field
            logger.info("Creating new user")
            user = User()
            user.save()
            
            # Initialize session in Redis
            try:
                redis_manager = get_message_store()
                redis_manager.set_session(user.user_id)
                logger.info(f"Set new session in Redis for user {user.user_id}")
            except Exception as e:
                logger.error(f"Failed to set session in Redis: {e}")
                
            return Response({
                "user_id": user.user_id
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in ChatUserAPIView: {str(e)}")
            return Response(
                {"error": "사용자 생성 중 오류가 발생했습니다"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateActivityAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "사용자 ID가 필요합니다"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get Redis manager
            redis_manager = get_message_store()
            
            # Check if session exists in Redis
            if not redis_manager.check_session(user_id):
                logger.warning(f"No active Redis session found for user {user_id}")
                return Response(
                    {"error": "Session expired"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Update user's last activity time in database
            # last_activity 필드가 auto_now=True로 설정되어 있으므로
            # 객체를 불러와서 저장만 해도 자동으로 현재 시간으로 업데이트됨
            try:
                user = User.objects.get(user_id=user_id)
                user.save(update_fields=['last_activity'])
                logger.debug(f"Updated last_activity for user {user_id}")
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found when updating activity")
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Refresh Redis session
            if redis_manager.set_session(user_id):
                logger.debug(f"Activity updated for user {user_id}")
                return Response(status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to refresh Redis session for user {user_id}")
                return Response(
                    {"error": "Failed to update session"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            logger.error(f"Error in UpdateActivityAPIView: {str(e)}")
            return Response(
                {"error": "활동 시간 업데이트 중 오류가 발생했습니다"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ChatRagAPIView(APIView):
    """
    API view for handling RAG operations:
    - Process CSV data (mode=1)
    - Process Excel data (mode=2)
    - Test similarity search (mode=3)
    """
    
    def _create_vector_store(self, documents, embedding_model="text-embedding-ada-002"):
        """Create and persist a vector store from documents"""
        # Use the RAGUtils from utils.py to leverage shared code
        return RAGUtils.create_vector_store_from_documents(documents, embedding_model)
        
    def _process_csv_data(self):
        """Process CSV data into vector store"""
        # Load CSV documents
        loader = CSVLoader(file_path=os.path.join(settings.BASE_DIR, "galaxy_s25_data.csv"))
        docs = loader.load()
        logger.info(f"CSV 로드된 문서 수: {len(docs)}")
        
        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        logger.info(f"청크 수: {len(splits)}")
        
        # Create vector store
        self._create_vector_store(splits)
        return Response({}, status=status.HTTP_200_OK)
    
    def _process_excel_data(self):
        """Process Excel data into vector store with image metadata"""
        # Load Excel data
        excel_path = os.path.join(settings.BASE_DIR, "galaxy_s25_data.xlsx")
        sheets = pd.read_excel(excel_path, sheet_name=None, engine="openpyxl")
        all_docs = []
        
        # Determine sheet with images
        sheet_names = list(sheets.keys())
        second_sheet_name = sheet_names[1] if len(sheet_names) > 1 else None
        
        # Process each sheet
        for sheet_name, df in sheets.items():
            for _, row in df.iterrows():
                # Create document text
                text = "\n".join(f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col]))
                metadata = {"sheet": sheet_name}
                
                # Add image path if available
                if sheet_name == second_sheet_name and "Image Path" in df.columns:
                    image_path = row.get("Image Path", None)
                    if pd.notna(image_path):
                        metadata["image_path"] = image_path
                
                # Create document
                doc = Document(page_content=text, metadata=metadata)
                all_docs.append(doc)
        
        logger.info(f"📌 총 문서 수: {len(all_docs)}")
        
        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(all_docs)
        logger.info(f"📌 총 청크 수: {len(splits)}")
        
        # Create vector store
        self._create_vector_store(splits)
        return Response({}, status=status.HTTP_200_OK)
    
    def _test_similarity_search(self):
        """Test similarity search functionality"""
        try:
            # Get vector store using the utility class
            vector_store = RAGUtils.get_vector_store()
            
            # Perform similarity search
            query = "갤럭시 S25 실버 모델 정보"
            search_results = vector_store.similarity_search(query, k=3)
            
            # Process results using the utility class
            rag_context = RAGUtils.process_search_results(search_results)
            
            # Format response with images
            response_data = []
            static_url = "/static/images/"
            
            for result in search_results:
                metadata = result.metadata
                image_paths = metadata.get("image_path", "")
                
                # Process image paths
                image_filenames = image_paths.split("\n") if isinstance(image_paths, str) else []
                image_urls = [static_url + filename.strip() for filename in image_filenames if filename.strip()]
                
                # Add to response
                response_data.append({
                    "content": result.page_content,
                    "image_url": image_urls
                })
            
            return Response({"response_data": response_data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            raise
    
    def _handle_openai_error(self, e, operation):
        """Centralized OpenAI error handling"""
        logger.error(f"OpenAI API error in {operation}: {str(e)}")
        return Response(
            {"error": f"OpenAI API error occurred during {operation}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    def post(self, request):
        """Handle POST requests based on mode parameter"""
        try:
            # Determine mode from request data
            mode = request.data.get("mode")
            
            try:
                # Process based on mode
                if mode == 1:
                    return self._process_csv_data()
                elif mode == 2:
                    return self._process_excel_data()
                elif mode == 3:
                    return self._test_similarity_search()
                else:
                    return Response(
                        {"error": f"Invalid mode: {mode}. Must be 1, 2, or 3."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except OpenAIError as e:
                operation = {
                    1: "CSV processing",
                    2: "Excel processing",
                    3: "similarity search"
                }.get(mode, "unknown operation")
                return self._handle_openai_error(e, operation)
                    
        except Exception as e:
            logger.error(f"Error in ChatRagAPIView: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SearchLogAPIView(APIView):
    """
    API view for accessing and managing search logs
    """
    
    def get(self, request):
        """Get search logs with optional filtering"""
        try:
            search_logs = SearchLog.objects.all().order_by('-searching_time')
            
            # Apply filters if provided
            user_id = request.query_params.get('user_id')
            if user_id:
                search_logs = search_logs.filter(question__user__user_id=user_id)
                
            # Limit results
            limit = int(request.query_params.get('limit', 100))
            search_logs = search_logs[:limit]
            
            serializer = SearchLogSerializer(search_logs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in SearchLogAPIView.get: {str(e)}")
            return Response(
                {"error": "Failed to retrieve search logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MetaDataAPIView(APIView):
    """
    API view for accessing and managing system metadata
    """
    
    def get(self, request, key=None):
        """
        Get metadata.
        If key is provided, return specific entry; otherwise return all metadata
        """
        try:
            from .models import MetaData
            from .utils import MetaDataManager
            
            # Return specific metadata entry if key is provided
            if key:
                value = MetaDataManager.get(key)
                if value is None:
                    return Response(
                        {"error": f"Metadata key '{key}' not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response({
                    "key": key,
                    "value": value
                })
                
            # Return all metadata
            all_metadata = MetaData.objects.all().order_by('key')
            result = []
            
            for metadata in all_metadata:
                result.append({
                    "key": metadata.key,
                    "value": metadata.get_value(),
                    "description": metadata.description,
                    "last_updated": metadata.last_updated
                })
                
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error retrieving metadata: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve metadata: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Create or update metadata"""
        try:
            from .utils import MetaDataManager
            
            # Extract data from request
            key = request.data.get('key')
            value = request.data.get('value')
            description = request.data.get('description')
            
            # Validate key
            if not key:
                return Response(
                    {"error": "Key is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Set metadata
            success = MetaDataManager.set(key, value, description)
            
            if success:
                return Response({
                    "message": f"Metadata '{key}' set successfully",
                    "key": key,
                    "value": value
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": f"Failed to set metadata '{key}'"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error setting metadata: {str(e)}")
            return Response(
                {"error": f"Failed to set metadata: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, key):
        """Delete metadata entry"""
        try:
            from .utils import MetaDataManager
            
            # Validate key exists
            if not MetaDataManager.get(key):
                return Response(
                    {"error": f"Metadata key '{key}' not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Delete metadata
            success = MetaDataManager.delete(key)
            
            if success:
                return Response({
                    "message": f"Metadata '{key}' deleted successfully"
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": f"Failed to delete metadata '{key}'"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error deleting metadata: {str(e)}")
            return Response(
                {"error": f"Failed to delete metadata: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
