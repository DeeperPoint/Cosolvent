import os
import motor.motor_asyncio
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = mongo_client.get_default_database()  # uses db name from URI
files_collection = db.get_collection("files")
chunks_collection = db.get_collection("chunks")

async def create_mongo_indexes():
    await files_collection.create_index("file_id", unique=True)
    await chunks_collection.create_index("chunk_id", unique=True)
    await chunks_collection.create_index("file_id")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = chroma_client.get_or_create_collection(name="my_collection")

#chroma_client = chromadb.Client(Settings(
 #   chroma_db_impl="duckdb+parquet",
  #  persist_directory=VECTOR_DB_PATH,
   # anonymized_telemetry=False,
#))
collection_name = "document_chunks"
try:
    chroma_collection = chroma_client.get_collection(name=collection_name)
except Exception:
    chroma_collection = chroma_client.create_collection(name=collection_name)

embedder = SentenceTransformer(EMBEDDING_MODEL)

async def get_embedding(text: str):
    return embedder.encode(text).tolist()