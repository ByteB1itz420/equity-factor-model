"""Re-hash every frozen artifact and compare against results/manifest.json."""
import hashlib
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"


def main() -> int:
    manifest = json.loads((RESULTS / "manifest.json").read_text())
    ok = True
    for name, digest in sorted(manifest.items()):
        path = RESULTS / name
        if not path.exists():
            print(f"MISSING  {name}")
            ok = False
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        status = "OK     " if actual == digest else "CHANGED"
        if actual != digest:
            ok = False
        print(f"{status} {name}")
    print("AUDIT PASS" if ok else "AUDIT FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
