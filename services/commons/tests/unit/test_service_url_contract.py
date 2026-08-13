# Copyright 2026 masa@kugel
"""Cross-service contract for BASE_URL_* configuration (#159).

Three sets have to agree, and until this test existed only one edge was checked:

    code  ──?──>  REQUIRED_SERVICE_URLS  ──verified at startup──>  configuration

`kugel_common.config.service_urls.verify_service_urls` runs at startup and
compares the declaration against the environment. Nothing compared the
declaration against the call sites, so adding a `get_service_client("...")`
without updating `REQUIRED_SERVICE_URLS` silently reopened the defect class:
the setting falls back to the `settings_web.py` default, which resolves to
nothing inside a container.

This lives in commons because commons owns the resolution mechanism
(`http_client_helper._get_service_url` and `service_urls.verify_service_urls`),
even though it reads files from sibling services.

Everything here is static analysis over the checked-out tree: no service, no
MongoDB, no docker.

Call sites are found with `ast`, not grep, for two reasons learnt the hard way:

  * both `get_service_client("cart")` and `get_service_client(service_name="cart")`
    occur, and a pattern matching only the positional form under-reports. That is
    how `report`->cart and `journal`->cart were missed when #159 was first written.
  * example calls appear inside docstrings. `ast` only sees real Call nodes, so
    they cannot produce false positives.
"""
import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SERVICES_DIR = REPO_ROOT / "services"
COMMONS_SRC = SERVICES_DIR / "commons" / "src"

# Services that own an app/ package. account is included even though its own
# routes call nobody: its middleware does, which is exactly the case that slipped
# through while attribution stopped at the first import hop.
SERVICES = ["account", "terminal", "master-data", "cart", "report", "journal", "stock"]

# Helpers that take a service name and resolve it through _get_service_url.
RESOLVER_FUNCS = {"get_service_client", "get_pooled_client", "create_service_client"}

# The sidecar address, not an inter-service URL: it is never subject to the
# declaration contract.
NOT_A_SERVICE_URL = {"BASE_URL_DAPR"}

pytestmark = pytest.mark.skipif(
    not SERVICES_DIR.is_dir(), reason="repository layout not available"
)


def _setting_name(service_name: str) -> str:
    return f"BASE_URL_{service_name.replace('-', '_').upper()}"


def _python_files(root: Path):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _settings_used_in_file(path: Path) -> set[str]:
    """BASE_URL_* this file causes to be resolved, from real Call/Attribute nodes."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()

    for node in ast.walk(tree):
        # get_service_client("cart") / get_service_client(service_name="cart")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in RESOLVER_FUNCS:
                arg = None
                if node.args and isinstance(node.args[0], ast.Constant):
                    arg = node.args[0].value
                for kw in node.keywords:
                    if kw.arg == "service_name" and isinstance(kw.value, ast.Constant):
                        arg = kw.value.value
                if isinstance(arg, str):
                    found.add(_setting_name(arg))

        # settings.BASE_URL_CART
        elif isinstance(node, ast.Attribute) and node.attr.startswith("BASE_URL_"):
            found.add(node.attr)

    return found - NOT_A_SERVICE_URL


def _commons_module_requirements() -> dict[str, set[str]]:
    """
    Map a kugel_common module path to the BASE_URL_* it resolves, transitively.

    A service's own app/ never mentions BASE_URL_TERMINAL, yet every service
    doing X-API-KEY auth needs it: kugel_common.security calls
    get_pooled_client("terminal") on their behalf. Those inherited requirements
    have to be attributed to the importer, or the contract under-reports exactly
    the setting whose absence is hardest to diagnose.

    Attribution must follow the import chain, not just the first hop.
    kugel_common.middleware.log_requests resolves nothing itself but imports
    kugel_common.security, so a service importing only the middleware still
    resolves BASE_URL_TERMINAL at runtime. Stopping at one level let `account`
    slip through: it imports the middleware and not security, declared nothing,
    and answered 500 after three retries — plus a false "Invalid api_key attempt"
    audit entry — for any request carrying an X-API-KEY header and a terminal_id.
    """
    direct: dict[str, set[str]] = {}
    imports: dict[str, set[str]] = {}
    for path in _python_files(COMMONS_SRC / "kugel_common"):
        module = ".".join(path.relative_to(COMMONS_SRC).with_suffix("").parts)
        direct[module] = _settings_used_in_file(path)
        imports[module] = _imported_commons_modules(path)

    # Fixpoint rather than recursion: the import graph may contain cycles.
    requirements = {m: set(v) for m, v in direct.items()}
    changed = True
    while changed:
        changed = False
        for module, imported in imports.items():
            grown = set(requirements[module])
            for dep in imported:
                grown |= requirements.get(dep, set())
            if grown != requirements[module]:
                requirements[module] = grown
                changed = True

    return {m: v for m, v in requirements.items() if v}



def _imported_commons_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("kugel_common"):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("kugel_common"):
                    modules.add(alias.name)
    return modules


# Built after _imported_commons_modules, which the transitive walk above needs.
COMMONS_REQUIREMENTS = _commons_module_requirements()


def used_settings(service: str) -> set[str]:
    """Every BASE_URL_* the service resolves, directly or through commons."""
    app_dir = SERVICES_DIR / service / "app"
    used: set[str] = set()
    for path in _python_files(app_dir):
        used |= _settings_used_in_file(path)
        for module in _imported_commons_modules(path):
            used |= COMMONS_REQUIREMENTS.get(module, set())
    return used


def declared_settings(service: str) -> set[str]:
    """REQUIRED_SERVICE_URLS as declared in the service's app/main.py."""
    main = SERVICES_DIR / service / "app" / "main.py"
    tree = ast.parse(main.read_text(), filename=str(main))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REQUIRED_SERVICE_URLS":
                    return {
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant)
                    }
    return set()


def _compose_environments(path: Path) -> dict[str, set[str]]:
    """
    Environment keys per service.

    Hand-rolled rather than PyYAML: commons has no yaml dependency and adding one
    for a test that reads two well-known files is not worth it. Handles both the
    `- KEY=value` list form and the `KEY: value` mapping form.
    """
    envs: dict[str, set[str]] = {}
    service = None
    in_env = False
    for raw in path.read_text().splitlines():
        if re.match(r"^  [a-z0-9_-]+:\s*$", raw):
            service = raw.strip().rstrip(":")
            envs.setdefault(service, set())
            in_env = False
            continue
        if re.match(r"^    environment:", raw):
            in_env = True
            continue
        if re.match(r"^    [a-z_]+:", raw):
            in_env = False
            continue
        if in_env and service:
            m = re.match(r"^      -?\s*([A-Z_]+)[=:]", raw)
            if m:
                envs[service].add(m.group(1))
    return envs


def _env_sample_keys(service: str) -> set[str] | None:
    path = SERVICES_DIR / service / ".env.sample"
    if not path.is_file():
        return None
    return set(re.findall(r"^([A-Z_]+)=", path.read_text(), re.M))


@pytest.mark.parametrize("service", SERVICES)
def test_declaration_matches_call_sites(service):
    """REQUIRED_SERVICE_URLS must be exactly what the service resolves.

    Under-declaring reopens the defect class the startup check exists to close.
    Over-declaring blocks startup on a setting nobody reads, which is how stock
    ended up requiring BASE_URL_MASTER_DATA it never used.
    """
    used = used_settings(service)
    declared = declared_settings(service)
    assert declared == used, (
        f"{service}: REQUIRED_SERVICE_URLS disagrees with the call sites.\n"
        f"  missing from the declaration: {sorted(used - declared) or 'none'}\n"
        f"  declared but never resolved:  {sorted(declared - used) or 'none'}"
    )


@pytest.mark.parametrize("compose", ["docker-compose.yaml", "docker-compose.prod.yaml"])
@pytest.mark.parametrize("service", SERVICES)
def test_compose_supplies_declared_settings(service, compose):
    """Both compose profiles must supply everything a service declares.

    Extra keys are fine; a missing one means the service falls back to a
    localhost default that resolves to nothing inside its container.
    """
    envs = _compose_environments(SERVICES_DIR / compose)
    assert service in envs, f"{compose} does not define service '{service}'"
    missing = declared_settings(service) - envs[service]
    assert not missing, f"{compose}: {service} is missing {sorted(missing)}"


@pytest.mark.parametrize("service", SERVICES)
def test_env_sample_supplies_declared_settings(service):
    """.env.sample is copied to .env for host-run services, so it must be complete."""
    keys = _env_sample_keys(service)
    declared = declared_settings(service)
    if keys is None:
        assert not declared, (
            f"{service} declares {sorted(declared)} but has no .env.sample, so the "
            f"documented `cp .env.sample .env` step cannot satisfy its startup check"
        )
        return
    missing = declared - keys
    assert not missing, f"{service}/.env.sample is missing {sorted(missing)}"


def test_commons_terminal_dependency_is_still_inherited():
    """Guards the inheritance rule the other tests depend on.

    If kugel_common.security stops resolving "terminal", every service's inherited
    requirement silently disappears and the contract above would still pass while
    checking less. Fail here instead, so the change is noticed rather than assumed.
    """
    assert COMMONS_REQUIREMENTS.get("kugel_common.security") == {"BASE_URL_TERMINAL"}, (
        "kugel_common.security no longer resolves exactly BASE_URL_TERMINAL; "
        "revisit how inherited requirements are attributed"
    )
