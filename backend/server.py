# Emergent preview adapter: loads local env and serves api/lambda_function.py.
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from lambda_function import app  # noqa: E402,F401
