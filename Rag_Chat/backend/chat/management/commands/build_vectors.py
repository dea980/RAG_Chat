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

            # CSV / Excel can live either next to manage.py (current layout)
            # or in a dedicated db/ folder (legacy layout).
            candidate_dirs = [settings.BASE_DIR, os.path.join(settings.BASE_DIR, "db")]

            for base in candidate_dirs:
                csv_path = os.path.join(base, "galaxy_s25_data.csv")
                if os.path.exists(csv_path):
                    self.stdout.write(f"Loading CSV file: {csv_path}")
                    # CSVLoader without source_column joins every row's columns into
                    # the page_content automatically — exactly what we want for the
                    # galaxy_s25_data schema (Model/Color/Storage/RAM/Camera/...).
                    loader = CSVLoader(file_path=csv_path)
                    csv_docs = loader.load()
                    all_docs.extend(csv_docs)
                    self.stdout.write(f"Loaded {len(csv_docs)} documents from CSV")
                    break

            for base in candidate_dirs:
                excel_path = os.path.join(base, "galaxy_s25_data.xlsx")
                if os.path.exists(excel_path):
                    self.stdout.write(f"Loading Excel file: {excel_path}")
                    df = pd.read_excel(excel_path, engine="openpyxl")
                    for _, row in df.iterrows():
                        content = "\n".join(f"{col}: {row[col]}" for col in df.columns)
                        metadata = {"source": "excel", **{c: str(row[c]) for c in df.columns}}
                        all_docs.append(Document(page_content=content, metadata=metadata))
                    self.stdout.write(f"Loaded {len(df)} documents from Excel")
                    break

            if not all_docs:
                raise Exception("No documents found in either CSV or Excel files")

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                keep_separator=True,
            )
            splits = text_splitter.split_documents(all_docs)
            self.stdout.write(f"Created {len(splits)} total chunks")

            # Provider-agnostic key check — Gemini, Qwen direct, or OpenRouter.
            embedding_provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
            required_env = {
                "gemini": "GOOGLE_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "qwen": "QWEN_API_KEY",
            }.get(embedding_provider)
            if required_env and not os.getenv(required_env):
                raise RuntimeError(
                    f"{required_env} is not configured (EMBEDDING_PROVIDER={embedding_provider})."
                )

            vector_store = provider_manager.create_vector_store_from_documents(splits)
            self.stdout.write(f"Vector store created with {vector_store._collection.count()} documents")
            self.stdout.write(f"Vector store saved at: {vector_store._persist_directory}")

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
