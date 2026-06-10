"""
Vercel WSGI entry point.
@vercel/python looks for a variable named `app` in this file.
We insert the project root onto sys.path so that `main.py` and the
`python_simulation` package can be imported correctly.
"""
import sys
import os

# Make the project root (parent of api/) importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import app  # noqa: F401  – re-exported for Vercel's WSGI runner
