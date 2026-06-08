from qdrant_client import QdrantClient
from config import settings

qc = QdrantClient(url=settings.qdrant_url)
