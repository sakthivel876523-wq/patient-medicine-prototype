"""Prepare static assets for Flask hosting. Never copy database files."""
from pathlib import Path
import shutil

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    shutil.copytree(root / 'static', root / 'public' / 'static', dirs_exist_ok=True)
