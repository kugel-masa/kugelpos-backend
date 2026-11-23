"""The staff PIN is compared in one place only (issue #323, spec SC-006 / FR-009).

Hashing the stored PIN, limiting attempts and locking out are to be added at
that one place. A second comparison anywhere - a terminal checking a PIN it
fetched, a helper in commons - would bypass all three, so this scans every
service's application code and commons for one.

A comparison is a `compare_digest(...)` call, or an `==` / `!=`, with an
operand named `pin` (a name or an attribute). Do not loosen the check to make
it pass: move the comparison into StaffMasterService.verify_staff_async.
"""

import ast
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[3]
ALLOWED = (SERVICES / "master-data" / "app" / "services" / "staff_master_service.py", "verify_staff_async")


def _sources():
    roots = [p / "app" for p in SERVICES.iterdir() if (p / "app").is_dir()]
    roots.append(SERVICES / "commons" / "src")
    for root in roots:
        for path in root.rglob("*.py"):
            if ".venv" not in path.parts and "site-packages" not in path.parts:
                yield path


def _names_pin(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "pin":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "pin":
            return True
    return False


def _is_compare_digest(call: ast.Call) -> bool:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return name == "compare_digest"


def _pin_comparisons(tree: ast.AST):
    """(line, enclosing function) of every PIN comparison in a module."""
    found = []

    def visit(node, function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if isinstance(node, ast.Call) and _is_compare_digest(node) and any(_names_pin(a) for a in node.args):
            found.append((node.lineno, function))
        if isinstance(node, ast.Compare) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            if any(_names_pin(operand) for operand in [node.left, *node.comparators]):
                found.append((node.lineno, function))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, None)
    return found


def test_the_pin_is_compared_only_in_verify_staff_async():
    allowed_path, allowed_function = ALLOWED
    offending = []
    allowed_hits = 0
    for path in _sources():
        for line, function in _pin_comparisons(ast.parse(path.read_text(encoding="utf-8"))):
            if path == allowed_path and function == allowed_function:
                allowed_hits += 1
            else:
                offending.append(f"{path.relative_to(SERVICES)}:{line} ({function})")

    assert offending == [], "the staff PIN is compared outside master-data's verify_staff_async:\n" + "\n".join(offending)
    assert allowed_hits == 1, "verify_staff_async should hold exactly one PIN comparison"


def test_the_scan_catches_a_comparison():
    """The scanner itself is not vacuous."""
    tree = ast.parse(
        "def check(staff, given):\n"
        "    if staff.pin != given:\n"
        "        return False\n"
        "    return hmac.compare_digest(pin, given)\n"
    )

    assert [f for _, f in _pin_comparisons(tree)] == ["check", "check"]
