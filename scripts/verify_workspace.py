"""Offline checks for the workspace instruction map; no model or network calls."""

from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = ("AGENTS.md", "ARCHITECTURE.md", "docs/README.md", "docs/agent-workflow.md")
FORBIDDEN = ("data/private/", "artifacts/", ".venv/", "output/", "tmp/")


def check(root):
    """Return actionable errors for the maintained map, notes, plans and Git index."""
    root = Path(root).resolve()
    errors = []
    files = [root / name for name in ENTRYPOINTS]
    for folder in ("docs/knowledge", "docs/plans"):
        files.extend(p for p in (root / folder).rglob("*.md") if "history" not in p.parts)
        if not (root / folder / "README.md").is_file():
            errors.append(f"{folder}/README.md: add the directory index")
    agents = root / "AGENTS.md"
    if agents.is_file():
        raw = agents.read_bytes()
        if len(raw) > 12000 or len(raw.splitlines()) > 120:
            errors.append("AGENTS.md: keep within 120 lines / 12000 bytes; move history to docs")
    for path in files:
        name = path.relative_to(root).as_posix()
        if not path.is_file():
            errors.append(f"{name}: missing required entrypoint")
            continue
        content = path.read_text(encoding="utf-8-sig")
        # Only inline Markdown destinations outside fenced examples; anchors aren't checked.
        prose = re.sub(r"```.*?```", "", content, flags=re.S)
        for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", prose):
            target = target.strip().strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            resolved = (path.parent / unquote(url.path)).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                errors.append(f"{name}: broken/outside local link {target}")
        if name.startswith("docs/knowledge/") and path.name != "README.md":
            for marker in ("상태:", "검토일:", "근거:"):
                if marker not in content:
                    errors.append(f"{name}: add {marker}")
            index = root / "docs/knowledge/README.md"
            if index.is_file() and f"]({path.name})" not in index.read_text(encoding="utf-8-sig"):
                errors.append(f"{name}: link this note from docs/knowledge/README.md")
        if name.startswith("docs/plans/") and path.name != "README.md":
            for marker in ("상태:", "검토일:"):
                if marker not in content:
                    errors.append(f"{name}: add {marker}")
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False
    )
    if result.returncode:
        errors.append("Git index: unable to inspect tracked paths")
    else:
        for name in result.stdout.decode("utf-8").split("\0"):
            if name.startswith(FORBIDDEN) or (name.startswith(".env") and name != ".env.example"):
                errors.append(f"Git index: untrack private/generated path {name}; keep local data")
    return errors


if __name__ == "__main__":
    failures = check(ROOT)
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"{'FAIL' if failures else 'PASS'}: workspace map / notes / Git paths (offline)")
    sys.exit(bool(failures))
