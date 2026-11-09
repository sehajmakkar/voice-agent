"""Architecture rules from CLAUDE.md, enforced as tests so they can't drift."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "swar"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_core_never_imports_pipecat() -> None:
    """D-005: swar.core is plain asyncio so it stays framework-independent."""
    offenders = [
        f"{path.relative_to(SRC)} imports {module}"
        for path in (SRC / "core").rglob("*.py")
        for module in _imported_modules(path)
        if module == "pipecat" or module.startswith("pipecat.")
    ]
    assert not offenders, "swar.core must not import Pipecat:\n" + "\n".join(offenders)
