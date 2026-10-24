# Emergent preview adapter: loads local env, maps platform MONGO_URL -> DATABASE_URL, serves api/lambda_function.py.
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
os.environ["DATABASE_URL"] = os.environ["MONGO_URL"]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from lambda_function import app  # noqa: E402,F401
