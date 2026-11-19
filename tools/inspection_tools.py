import json
from pathlib import Path


INVENTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "inventory.json"

# Ground truth baseline rules for pre-migration review
CLOUD_COMPLIANT_RUNTIMES = ["Node.js 18.x", "Node.js 20.x", "Python 3.10", "Python 3.11", "Go 1.22", "Java 21"]
DISQUALIFYING_SECURITY_ISSUES = ["hardcoded_secrets", "tls_version_1.0", "tls_version_1.1"]

def load_inventory():
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Inventory file not found at {INVENTORY_PATH}")
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def inspect_app_overview(app_id: str) -> dict:
    """Inspects runtime and framework specifications."""
    inv = load_inventory()
    if app_id not in inv:
        return {"ok": False, "observation": f"App ID '{app_id}' not found in inventory."}
    
    app = inv[app_id]
    runtime = app.get("runtime")
    framework = app.get("framework")

    if not runtime or not framework:
        return {
            "ok": True,
            "status": "INCOMPLETE",
            "observation": f"Record exists but runtime specifications are incomplete: runtime={runtime}, framework={framework}."
        }
    
    is_supported = any(supported in runtime for supported in CLOUD_COMPLIANT_RUNTIMES)
    return {
        "ok": True,
        "status": "VALID" if is_supported else "DEPRECATED",
        "observation": f"Runtime: {runtime}, Framework: {framework}. Target runtime cloud support: {is_supported}."
    }

def inspect_dependencies(app_id: str) -> dict:
    """Inspects package dependencies and flags missing manifests."""
    inv = load_inventory()
    if app_id not in inv:
        return {"ok": False, "observation": f"App ID '{app_id}' not found in inventory."}

    deps = inv[app_id].get("dependencies")
    if deps is None:
        return {
            "ok": True,
            "status": "MISSING_DATA",
            "observation": "CRITICAL: Dependency list is NULL or manifest not recorded in inventory."
        }
    if len(deps) == 0:
        return {
            "ok": True,
            "status": "EMPTY",
            "observation": "Dependency manifest is empty."
        }

    deprecated_pkgs = [p for p in deps if "legacy" in p or "activex" in p or "pycrypto" in p]
    return {
        "ok": True,
        "status": "DEPRECATED_DEPENDENCIES" if deprecated_pkgs else "OK",
        "observation": f"Found {len(deps)} dependencies: {deps}. Blocked/legacy packages: {deprecated_pkgs}."
    }

def inspect_database(app_id: str) -> dict:
    """Inspects database engine, version, and managed cloud target feasibility."""
    inv = load_inventory()
    if app_id not in inv:
        return {"ok": False, "observation": f"App ID '{app_id}' not found in inventory."}

    db = inv[app_id].get("database")
    if not db or db.get("type") == "Unknown" or db.get("managed_cloud_supported") is None:
        return {
            "ok": True,
            "status": "MISSING_DATA",
            "observation": "Database configuration is unknown or lacks managed service support flags."
        }

    supported = db.get("managed_cloud_supported")
    return {
        "ok": True,
        "status": "COMPATIBLE" if supported else "INCOMPATIBLE",
        "observation": f"Database: {db.get('type')} v{db.get('version')}. Direct managed cloud compatibility: {supported}."
    }

def inspect_security(app_id: str) -> dict:
    """Inspects authentication standard, TLS minimum, and secrets management."""
    inv = load_inventory()
    if app_id not in inv:
        return {"ok": False, "observation": f"App ID '{app_id}' not found in inventory."}

    sec = inv[app_id].get("security")
    if sec is None:
        return {
            "ok": True,
            "status": "MISSING_DATA",
            "observation": "CRITICAL: Security profile is completely undocumented in inventory."
        }

    issues = []
    missing_fields = []

    if sec.get("tls_version") is None:
        missing_fields.append("tls_version")
    elif sec.get("tls_version") in ["1.0", "1.1"]:
        issues.append(f"Insecure TLS version: {sec.get('tls_version')}")

    if sec.get("auth_standard") is None:
        missing_fields.append("auth_standard")
    elif sec.get("auth_standard") in ["NTLM / Basic Auth", "Basic Auth"]:
        issues.append(f"Legacy authentication protocol: {sec.get('auth_standard')}")

    if sec.get("hardcoded_secrets") is True:
        issues.append("Hardcoded secrets detected in repository")

    if missing_fields:
        return {
            "ok": True,
            "status": "INCOMPLETE",
            "observation": f"Security specs partially missing: {missing_fields}. Detected issues: {issues}."
        }

    return {
        "ok": True,
        "status": "FLAGGED" if issues else "CLEAR",
        "observation": f"Security specs: TLS={sec.get('tls_version')}, Auth={sec.get('auth_standard')}, SecretsClean={not sec.get('hardcoded_secrets')}. Issues: {issues}."
    }