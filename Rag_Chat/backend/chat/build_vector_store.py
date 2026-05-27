"""DEPRECATED — use chat.ingest.pipeline.ingest_path instead.

Phase 1~6 의 ingest layer (chat/ingest/) 가 이 파일의 기능을 전부 대체한다:
- CSV/XLSX 적재 → chat.ingest.loaders.structured.{csv,excel}
- 청킹       → chat.ingest.splitters
- Chroma 적재 → chat.ingest.sinks.ChromaSink
- ORM 적재   → chat.ingest.sinks.KnowledgeOrmSink (Phase 6)
- dedup     → chat.ingest.manifest (Phase 2 SHA256)

신규 호출 예:
    from chat.ingest.pipeline import ingest_path
    from chat.ingest.sinks import ChromaSink, KnowledgeOrmSink, CompositeSink
    ingest_path("galaxy_s25_data.csv",
                sink=CompositeSink([ChromaSink(), KnowledgeOrmSink()]))

이 파일은 후방 호환을 위해 남겨두며, 다음 정리 라운드에서 제거 예정.
"""
import warnings

warnings.warn(
    "chat.build_vector_store is deprecated; use chat.ingest.pipeline.ingest_path"
    " with sinks=CompositeSink([ChromaSink(), KnowledgeOrmSink()]) instead.",
    DeprecationWarning,
    stacklevel=2,
)

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import pandas as pd
import os
import sys
import django
from django.conf import settings
import uuid
import datetime
import logging

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'triple_chat_pjt.settings')
django.setup()

# Import after Django setup
from .vector_metadata import VectorMetadataManager
from .utils import MetaDataManager
from .providers import provider_manager

logger = logging.getLogger(__name__)

def load_excel_data(file_path: str):
    """
    Load data from Excel file and convert to Langchain documents
    with enhanced metadata for search optimization
    """
    # Read all sheets from Excel file
    sheets = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
    
    all_docs = []
    sheet_names = list(sheets.keys())
    second_sheet_name = sheet_names[1] if len(sheet_names) > 1 else None
    
    # Generate a batch ID for this import
    batch_id = str(uuid.uuid4())
    processing_time = datetime.datetime.now().isoformat()
    
    # Store batch metadata
    batch_metadata = {
        "source": "excel",
        "file_path": file_path,
        "sheet_count": len(sheet_names),
        "sheets": sheet_names,
        "processing_time": processing_time,
        "batch_id": batch_id
    }
    
    # Store this in the metadata system
    MetaDataManager.set(
        key=f"excel_import_{batch_id}",
        value=batch_metadata,
        description=f"Excel import metadata for batch {batch_id}"
    )
    
    # Process each sheet
    for sheet_name, df in sheets.items():
        for index, row in df.iterrows():
            # Create document text
            text = "\n".join(f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col]))
            
            # Create comprehensive metadata
            metadata = {
                "sheet": sheet_name,
                "row_index": index,
                "batch_id": batch_id,
                "doc_id": f"{batch_id}_{sheet_name}_{index}",
                "source": "excel",
                "processing_time": processing_time,
                "content_length": len(text),
                "column_count": len(df.columns)
            }
            
            # Extract all non-null values as separate metadata fields
            for col in df.columns:
                if pd.notna(row[col]):
                    # Use a prefix to avoid conflicts with standard metadata
                    safe_col_name = col.replace(" ", "_").lower()
                    metadata[f"field_{safe_col_name}"] = str(row[col])
            
            # Handle image paths specially
            if sheet_name == second_sheet_name and "Image Path" in df.columns:
                image_path = row.get("Image Path", None)
                if pd.notna(image_path):
                    metadata["image_path"] = image_path
            
            # Create the document
            doc = Document(page_content=text, metadata=metadata)
            all_docs.append(doc)
    
    # Store document metadata in the separate metadata system
    logger.info(f"Storing metadata for {len(all_docs)} documents from Excel")
    VectorMetadataManager.store_vector_batch_metadata(all_docs, f"excel_{batch_id}")
    
    return all_docs

def build_vector_store():
    '''
    RAG를 구축하는 시점과 RAG를 사용하는 시점을 분리
    서버 구동 시 한 번만 실행하기
    메타데이터를 별도로 저장하여 검색 성능 최적화
    '''
    try:
        # Generate an ID for this build process
        build_id = str(uuid.uuid4())
        build_time = datetime.datetime.now().isoformat()
        
        # 현재 작업 디렉토리 출력
        current_dir = settings.BASE_DIR
        logger.info(f"현재 작업 디렉토리: {current_dir}")
        
        # CSV 파일 경로 확인
        csv_path = os.path.join(current_dir, "galaxy_s25_data.csv")
        logger.info(f"CSV 파일 경로: {csv_path}")
        
        # 벡터 스토어 저장 경로 확인
        vector_store_path = os.path.join(current_dir, "vector_store")
        logger.info(f"벡터 스토어 저장 경로: {vector_store_path}")
        
        # Store build start metadata
        MetaDataManager.set(
            key="vector_build_latest",
            value={
                "build_id": build_id,
                "start_time": build_time,
                "status": "started",
                "csv_path": csv_path,
                "vector_store_path": vector_store_path
            },
            description="Latest vector store build information"
        )
        
        # 2. 문서 불러오기
        from langchain_community.document_loaders import CSVLoader
        loader = CSVLoader(file_path=csv_path)
        docs = loader.load()
        logger.info(f"로드된 문서 수: {len(docs)}")
        
        # Enhance documents with metadata before chunking
        enhanced_docs = []
        for i, doc in enumerate(docs):
            # Add comprehensive metadata
            doc.metadata.update({
                "doc_id": f"csv_{build_id}_{i}",
                "build_id": build_id,
                "source": "csv",
                "original_index": i,
                "content_length": len(doc.page_content),
                "processing_time": build_time
            })
            enhanced_docs.append(doc)
        
        # Store the original docs metadata
        VectorMetadataManager.store_vector_batch_metadata(
            enhanced_docs,
            f"csv_original_{build_id}"
        )
        
        # 문서 chunking
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(enhanced_docs)
        logger.info(f"청크 수: {len(splits)}")
        
        # Add chunk-specific metadata
        for i, chunk in enumerate(splits):
            chunk.metadata.update({
                "chunk_id": f"chunk_{build_id}_{i}",
                "chunk_index": i,
                "is_chunk": True
            })
        
        # Store the chunked docs metadata
        VectorMetadataManager.store_vector_batch_metadata(
            splits,
            f"csv_chunks_{build_id}"
        )
        
        # Chroma 벡터스토어 생성 및 저장
        vector_store = provider_manager.create_vector_store_from_documents(splits)
        
        # 저장 확인
        doc_count = vector_store._collection.count()
        logger.info(f"벡터 스토어 문서 수: {doc_count}")
        logger.info(f"📂 벡터스토어 저장 경로: {vector_store._persist_directory}")
        
        # Update build metadata with success status
        MetaDataManager.set(
            key="vector_build_latest",
            value={
                "build_id": build_id,
                "start_time": build_time,
                "end_time": datetime.datetime.now().isoformat(),
                "status": "completed",
                "document_count": doc_count,
                "chunk_count": len(splits),
                "vector_store_path": vector_store._persist_directory
            },
            description="Latest vector store build information"
        )
        
        # Create search index metadata
        VectorMetadataManager.create_search_index(
            "default",
            {
                "build_id": build_id,
                "document_count": doc_count,
                "last_updated": datetime.datetime.now().isoformat(),
                "embedding_model": os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004"),
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        )
        
        return {
            "status": "success",
            "build_id": build_id,
            "document_count": doc_count
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"에러 발생: {error_msg}")
        
        # Update build metadata with failure status
        MetaDataManager.set(
            key="vector_build_latest",
            value={
                "build_id": build_id if 'build_id' in locals() else "unknown",
                "status": "failed",
                "error": error_msg,
                "time": datetime.datetime.now().isoformat()
            },
            description="Latest vector store build information"
        )
        
        return {
            "status": "error",
            "error": error_msg
        }

# 해당 스크립트가 직접 실행될 때만 build_vector_store() 함수를 실행
if __name__ == "__main__":
    '''
    이 파일이 독립적인 실행 파일로 실행될 때만 build_vector_store()가 실행되고,
    다른 모듈에서 import될 때는 실행되지 않는다.
    '''
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Initialize metadata defaults
    MetaDataManager.set(
        key="current_time",
        value=datetime.datetime.now().isoformat(),
        description="Current time when the script ran"
    )
    
    # Build the vector store with metadata enhancements
    result = build_vector_store()
    
    if result['status'] == 'success':
        logger.info(f"Vector store build completed successfully. Build ID: {result['build_id']}")
        logger.info(f"Total documents indexed: {result['document_count']}")
    else:
        logger.error(f"Vector store build failed: {result['error']}")
