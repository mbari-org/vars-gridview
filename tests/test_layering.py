"""Guard the lib -> ui layering: nothing under lib/ may import from ui/."""

from __future__ import annotations

import ast
from pathlib import Path

import vars_gridview

_PACKAGE_ROOT = Path(vars_gridview.__file__).parent
_LIB_DIR = _PACKAGE_ROOT / "lib"
_FORBIDDEN = "vars_gridview.ui"


def _is_forbidden(module: str) -> bool:
    return module == _FORBIDDEN or module.startswith(_FORBIDDEN + ".")


def _forbidden_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Return (lineno, module) for each import statement that reaches ui/."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            # The alias form catches "from vars_gridview import ui".
            candidates = [node.module] + [
                f"{node.module}.{alias.name}" for alias in node.names
            ]
        else:
            continue
        hit = next((m for m in candidates if _is_forbidden(m)), None)
        if hit is not None:
            found.append((node.lineno, hit))
    return found


def test_lib_does_not_import_ui() -> None:
    violations = []
    for path in sorted(_LIB_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for lineno, module in _forbidden_imports(tree):
            violations.append(f"{path.relative_to(_PACKAGE_ROOT)}:{lineno}: {module}")

    assert not violations, "lib/ must not import from ui/:\n" + "\n".join(violations)
