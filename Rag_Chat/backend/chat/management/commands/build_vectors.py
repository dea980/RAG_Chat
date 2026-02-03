from django.core.management.base import BaseCommand
from django.conf import settings
from langchain_community.document_loaders import CSVLoader
from langchain.document_loaders.excel import UnstructuredExcelLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import pandas as pd
from langchain.schema import Document

from ...providers import provider_manager

# %pip install --upgrade --quiet  langchain langchain-community azure-ai-documentintelligence

# from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader

# file_path = "<filepath>"
# endpoint = "<endpoint>"
# key = "<key>"
# loader = AzureAIDocumentIntelligenceLoader(
#     api_endpoint=endpoint, api_key=key, file_path=file_path, api_model="prebuilt-layout"
# )

# documents = loader.load()


class Command(BaseCommand):
    help = 'Build vector store from xlsx and Excel data'

    def handle(self, *args, **options):
        try:
            all_docs = []
            
            # Load CSV data
            csv_path = os.path.join(settings.BASE_DIR, "db", "galaxy_s25_data.csv")
            if os.path.exists(csv_path):
                self.stdout.write(f"Loading CSV file: {csv_path}")
                loader = CSVLoader(
                    file_path=csv_path,
                    source_column="Feature_Description",
                    metadata_columns=["ID(SKU)", "Product_Name", "Main_Feature"]
                )
                csv_docs = loader.load()
                all_docs.extend(csv_docs)
                self.stdout.write(f"Loaded {len(csv_docs)} documents from CSV")

            # Load Excel data
            excel_path = os.path.join(settings.BASE_DIR, "db", "galaxy_s25_data.xlsx")
            if os.path.exists(excel_path):
                self.stdout.write(f"Loading Excel file: {excel_path}")
                df = pd.read_excel(excel_path, engine="openpyxl")
                
                for _, row in df.iterrows():
                    # Create a document for each row
                    content = f"제품명: {row['Product_Name']}\n"
                    content += f"주요 특징: {row['Main_Feature']}\n"
                    content += f"상세 설명: {row['Feature_Description']}"
                    
                    metadata = {
                        "ID": str(row['ID(SKU)']),
                        "Product_Name": row['Product_Name'],
                        "Main_Feature": row['Main_Feature'],
                        "source": "excel"
                    }
                    
                    doc = Document(
                        page_content=content,
                        metadata=metadata
                    )
                    all_docs.append(doc)
                self.stdout.write(f"Loaded {len(df)} documents from Excel")

            if not all_docs:
                raise Exception("No documents found in either CSV or Excel files")

            # Split documents with Korean-aware settings
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                keep_separator=True
            )
            splits = text_splitter.split_documents(all_docs)
            self.stdout.write(f"Created {len(splits)} total chunks")

            # Create embeddings
            api_key = os.getenv("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", "")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY is not configured. Set it in the environment or settings.")

            vector_store = provider_manager.create_vector_store_from_documents(splits)
            
            self.stdout.write(f"Vector store created with {vector_store._collection.count()} documents")
            self.stdout.write(f"Vector store saved at: {vector_store._persist_directory}")
            
        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
