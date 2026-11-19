# Cloud Migration Readiness Review Agent

An autonomous Sense-Think-Act agent that audits enterprise web applications across four technical gates (runtime/framework, dependencies, database compatibility, and security posture) prior to cloud migration.

## Project Structure
- `data/inventory.json`: Sample inventory of 10 web applications (`APP-01` through `APP-10`).
- `tools/inspection_tools.py`: Four read-only inspection tools evaluating cloud compliance baselines.
- `tools/validator.py`: JSON schema and action allowlist guardrail.
- `agent/prompt.py`: Behavioral system prompt and classification rules.
- `agent/agent_loop.py`: Bounded Sense-Think-Act control loop with ground-truth stopping gates.
- `run_review.py`: Evaluates the 4 core workload archetypes and saves `migration_report.json`.
- `run_all_apps.py`: Audits all 10 applications and saves `full_migration_report.json`.

## How to Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt