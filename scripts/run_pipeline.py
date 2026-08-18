#!/usr/bin/env python3
"""
Thin CLI entrypoint. Run from the project root:

    python scripts/run_pipeline.py --niche beauty --limit 30

If you installed the package (pip install -e .), you can also just run:

    rle-pipeline --niche beauty --limit 30
"""
import sys
from pathlib import Path

# Allow running without 'pip install -e .' by adding src/ to the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from revenue_leak_engine.pipeline import cli  # noqa: E402

if __name__ == "__main__":
    cli()
