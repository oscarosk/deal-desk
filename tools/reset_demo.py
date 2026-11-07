"""Delete the files a demo run creates, so the next run starts clean.

Run it in each agent's folder, or in the project folder:
    python tools/reset_demo.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for name in ("deals", "approvals", "out"):
    path = ROOT / name
    if path.exists():
        shutil.rmtree(path)
        print(f"removed {name}/")
for name in ("deals", "approvals", "out"):
    (ROOT / name).mkdir()
print("ready for a new demo run")
