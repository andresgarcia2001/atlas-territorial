import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

for path in (ROOT_DIR, BACKEND_DIR):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
