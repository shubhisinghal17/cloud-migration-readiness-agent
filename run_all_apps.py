import argparse
import json
from agent.agent_loop import run_readiness_agent
from tools.inspection_tools import load_inventory

def build_scripted_walkthroughs() -> dict[str, list[str]]:
    """
    Deterministic walkthroughs for all 10 applications in data/inventory.json.
    Enables instant, offline, zero-GPU evaluation across the full portfolio.
    """
    assessments = {
        "APP-01": {
            "status": "READY_FOR_REVIEW",
            "missing": [],
            "rationale": "Modern Node.js runtime, standard dependencies, managed PostgreSQL 15, and clean security specs."
        },
        "APP-02": {
            "status": "READY_FOR_REVIEW",
            "missing": [],
            "rationale": "Python 3.11 runtime, modern FastAPI stack, managed PostgreSQL 16, and clean TLS 1.3 security."
        },
        "APP-03": {
            "status": "READY_FOR_REVIEW",
            "missing": [],
            "rationale": "Go 1.22 runtime, Gin framework dependencies, managed MySQL 8.0, and compliant TLS 1.2 SAML auth."
        },
        "APP-04": {
            "status": "READY_FOR_REVIEW",
            "missing": [],
            "rationale": "Java 21 runtime, Spring Boot dependencies, managed PostgreSQL 15.2, and mTLS security specs."
        },
        "APP-05": {
            "status": "NOT_READY",
            "missing": [],
            "rationale": "Blocked by unsupported PHP 5.4, legacy Oracle 9i database, TLS 1.0, and hardcoded secrets."
        },
        "APP-06": {
            "status": "NOT_READY",
            "missing": [],
            "rationale": "Blocked by deprecated .NET 3.5 runtime, legacy SQL Server 2008 R2, ActiveX dependencies, and TLS 1.1."
        },
        "APP-07": {
            "status": "NOT_READY",
            "missing": [],
            "rationale": "Blocked by unsupported Python 2.7, unmanaged PostgreSQL 9.4, deprecated pycrypto, and static API keys."
        },
        "APP-08": {
            "status": "NEEDS_MORE_INFO",
            "missing": ["dependencies", "database.type", "database.version"],
            "rationale": "Dependency manifest is null and database engine is unrecorded. Readiness cannot be assumed."
        },
        "APP-09": {
            "status": "NEEDS_MORE_INFO",
            "missing": ["security"],
            "rationale": "Security profile is completely undocumented in inventory. Readiness cannot be assumed."
        },
        "APP-10": {
            "status": "NEEDS_MORE_INFO",
            "missing": ["runtime", "framework", "dependencies", "database.version", "security.tls_version"],
            "rationale": "Critical fields unrecorded: runtime, dependencies, database version, and TLS configuration are null."
        }
    }

    walkthroughs = {}
    for app_id, data in assessments.items():
        walkthroughs[app_id] = [
            f'{{"action": "inspect_app_overview", "argument": {{"app_id": "{app_id}"}}}}',
            f'{{"action": "inspect_dependencies", "argument": {{"app_id": "{app_id}"}}}}',
            f'{{"action": "inspect_database", "argument": {{"app_id": "{app_id}"}}}}',
            f'{{"action": "inspect_security", "argument": {{"app_id": "{app_id}"}}}}',
            json.dumps({
                "action": "declare_assessment",
                "argument": {
                    "app_id": app_id,
                    "status": data["status"],
                    "missing_or_unknown_fields": data["missing"],
                    "rationale": data["rationale"]
                }
            })
        ]
    return walkthroughs

def run_portfolio_audit(live_mode: bool = False, output_file: str = "full_migration_report.json"):
    print("=" * 85)
    print("CLOUD MIGRATION READINESS REVIEW: 10-APP PORTFOLIO BATCH AUDIT")
    print(f"Execution Mode: {'LIVE OLLAMA INFERENCE' if live_mode else 'DETERMINISTIC OFFLINE SUITE'}")
    print("=" * 85)

    inventory = load_inventory()
    app_ids = sorted(list(inventory.keys()))
    scripted_walkthroughs = build_scripted_walkthroughs()

    full_reports = []
    portfolio_summary = []

    for app_id in app_ids:
        app_meta = inventory[app_id]
        app_name = app_meta.get("name", "Unnamed Workload")
        print(f"\n[AUDITING {app_id}] {app_name}")

        mock_seq = None if live_mode else scripted_walkthroughs.get(app_id)
        summary, trace = run_readiness_agent(app_id, mock_responses=mock_seq)

        assessment = summary.get("assessment") or {}
        decision = assessment.get("status", "UNKNOWN")
        missing = assessment.get("missing_or_unknown_fields", [])
        rationale = assessment.get("rationale", "N/A")

        print(f"  Result: {decision} (Audit Gates: {len(summary['inspected_dimensions'])}/4, Steps: {len(trace)})")
        print(f"  Missing Fields: {missing if missing else 'None'}")
        print(f"  Rationale: {rationale}")

        full_reports.append({
            "app_id": app_id,
            "name": app_name,
            "owner": app_meta.get("owner", "Unassigned"),
            "summary": summary,
            "trace": trace
        })

        portfolio_summary.append({
            "id": app_id,
            "name": app_name,
            "decision": decision,
            "missing_count": len(missing)
        })

    # Save to dedicated full migration report
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_reports, f, indent=2)

    # Print Executive Summary Table
    print("\n" + "=" * 85)
    print(f"{'APP ID':<10} | {'NAME':<28} | {'READINESS DECISION':<20} | {'MISSING FIELDS'}")
    print("-" * 85)
    for item in portfolio_summary:
        print(f"{item['id']:<10} | {item['name']:<28} | {item['decision']:<20} | {item['missing_count']}")
    print("=" * 85)

    # Aggregate counts
    ready_count = sum(1 for x in portfolio_summary if x["decision"] == "READY_FOR_REVIEW")
    blocked_count = sum(1 for x in portfolio_summary if x["decision"] == "NOT_READY")
    incomplete_count = sum(1 for x in portfolio_summary if x["decision"] == "NEEDS_MORE_INFO")

    print(f"PORTFOLIO METRICS: Total Apps: {len(app_ids)} | Ready: {ready_count} | Blocked: {blocked_count} | Incomplete: {incomplete_count}")
    print(f"All audit traces successfully saved to '{output_file}'")
    print("=" * 85)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Portfolio Cloud Migration Readiness Runner")
    parser.add_argument("--live", action="store_true", help="Run against a live Ollama endpoint")
    parser.add_argument("--output", type=str, default="full_migration_report.json", help="Path to destination JSON file")
    args = parser.parse_args()

    run_portfolio_audit(live_mode=args.live, output_file=args.output)