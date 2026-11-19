import argparse
import json
from agent.agent_loop import run_readiness_agent

def run_evaluation_suite(live_mode: bool = False, specific_app: str = None):
    print("=" * 80)
    print("CLOUD MIGRATION READINESS REVIEW AGENT: ARCHETYPE EVALUATION SUITE")
    print(f"Mode: {'LIVE OLLAMA INFERENCE' if live_mode else 'DETERMINISTIC EVALUATION / MOCK'}")
    print("=" * 80)

    test_cases = [
        ("APP-01", "APP-01", "Archetype 1: Complete & Meets Checklist (Ready for Review)"),
        ("APP-05", "APP-05", "Archetype 2: Complete but Incompatible (Not Ready / Blocked)"),
        ("APP-08", "APP-08", "Archetype 3: Incomplete Data (Needs More Information)"),
        ("APP-01-RECOVERY", "APP-01", "Archetype 4: Guardrail Recovery (Invalid Tool & Premature Stop)")
    ]

    if specific_app:
        test_cases = [tc for tc in test_cases if tc[0] == specific_app or tc[1] == specific_app]
        if not test_cases:
            test_cases = [(specific_app, specific_app, f"Custom Run: {specific_app}")]

    scripted_walkthroughs = {
        "APP-01": [
            '{"action": "inspect_app_overview", "argument": {"app_id": "APP-01"}}',
            '{"action": "inspect_dependencies", "argument": {"app_id": "APP-01"}}',
            '{"action": "inspect_database", "argument": {"app_id": "APP-01"}}',
            '{"action": "inspect_security", "argument": {"app_id": "APP-01"}}',
            '{"action": "declare_assessment", "argument": {"app_id": "APP-01", "status": "READY_FOR_REVIEW", "missing_or_unknown_fields": [], "rationale": "Modern Node.js runtime, standard dependencies, managed PostgreSQL 15, and clean security specs."}}'
        ],
        "APP-05": [
            '{"action": "inspect_app_overview", "argument": {"app_id": "APP-05"}}',
            '{"action": "inspect_dependencies", "argument": {"app_id": "APP-05"}}',
            '{"action": "inspect_database", "argument": {"app_id": "APP-05"}}',
            '{"action": "inspect_security", "argument": {"app_id": "APP-05"}}',
            '{"action": "declare_assessment", "argument": {"app_id": "APP-05", "status": "NOT_READY", "missing_or_unknown_fields": [], "rationale": "Blocked by unsupported PHP 5.4, legacy Oracle 9i database, TLS 1.0, and hardcoded secrets."}}'
        ],
        "APP-08": [
            '{"action": "inspect_app_overview", "argument": {"app_id": "APP-08"}}',
            '{"action": "inspect_dependencies", "argument": {"app_id": "APP-08"}}',
            '{"action": "inspect_database", "argument": {"app_id": "APP-08"}}',
            '{"action": "inspect_security", "argument": {"app_id": "APP-08"}}',
            '{"action": "declare_assessment", "argument": {"app_id": "APP-08", "status": "NEEDS_MORE_INFO", "missing_or_unknown_fields": ["dependencies", "database.type", "database.version"], "rationale": "Dependency manifest is null and database engine is unrecorded. Readiness cannot be assumed."}}'
        ],
        "APP-01-RECOVERY": [
            # Turn 1: Model hallucinates an unauthorized tool -> Blocked by Validator
            '{"action": "estimate_cloud_cost", "argument": {"app_id": "APP-01"}}',
            # Turn 2: Agent reads error observation, self-corrects to inspect_app_overview
            '{"action": "inspect_app_overview", "argument": {"app_id": "APP-01"}}',
            # Turn 3: Agent attempts declare_assessment prematurely before checking other gates -> Blocked by Goal Check
            '{"action": "declare_assessment", "argument": {"app_id": "APP-01", "status": "READY_FOR_REVIEW", "missing_or_unknown_fields": [], "rationale": "Runtime looks fine."}}',
            # Turn 4: Agent inspects dependencies
            '{"action": "inspect_dependencies", "argument": {"app_id": "APP-01"}}',
            # Turn 5: Agent inspects database
            '{"action": "inspect_database", "argument": {"app_id": "APP-01"}}',
            # Turn 6: Agent inspects security
            '{"action": "inspect_security", "argument": {"app_id": "APP-01"}}',
            # Turn 7: Agent declares assessment after all gates pass -> Accepted
            '{"action": "declare_assessment", "argument": {"app_id": "APP-01", "status": "READY_FOR_REVIEW", "missing_or_unknown_fields": [], "rationale": "Completed all 4 inspection gates after initial validation errors."}}'
        ]
    }

    full_reports = []

    for test_key, target_app_id, description in test_cases:
        print(f"\n--- EVALUATING {test_key}: {description} ---")

        mock_seq = None if live_mode else scripted_walkthroughs.get(test_key)
        
        summary, trace = run_readiness_agent(
            target_app_id,
            mock_responses=mock_seq
        )

        assessment = summary.get("assessment") or {}
        print(f"Status: {summary['stop_reason'].upper()} (Steps: {len(trace)})")
        print(f"Inspected Gates: {summary['inspected_dimensions']}")
        print(f"Recommended Decision: {assessment.get('status')}")
        print(f"Unknown/Missing Fields: {assessment.get('missing_or_unknown_fields')}")
        print(f"Rationale: {assessment.get('rationale')}")

        full_reports.append({"test_case": test_key, "summary": summary, "trace": trace})

    with open("migration_report.json", "w", encoding="utf-8") as f:
        json.dump(full_reports, f, indent=2)

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE: Full audit traces saved to 'migration_report.json'")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud Migration Readiness Review Agent Runner")
    parser.add_argument("--live", action="store_true", help="Run against a live Ollama endpoint")
    parser.add_argument("--app", type=str, default=None, help="Run a specific test case (e.g. APP-01, APP-05, APP-08, APP-01-RECOVERY)")
    args = parser.parse_args()

    run_evaluation_suite(live_mode=args.live, specific_app=args.app)