import os
from dotenv import load_dotenv

load_dotenv()

MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "8"))
SEMANTIC_MODEL = os.getenv(
    "SEMANTIC_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
