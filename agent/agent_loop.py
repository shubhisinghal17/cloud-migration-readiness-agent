import json
import requests
from tools.inspection_tools import (
    load_inventory,
    inspect_app_overview,
    inspect_dependencies,
    inspect_database,
    inspect_security
)
from tools.validator import validate_proposal
from agent.prompt import SYSTEM_PROMPT

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"
MAX_STEPS = 10

def parse_model_reply(raw_reply: str) -> tuple[dict | None, str]:
    """Deserializes LLM output into a dictionary, stripping thinking tags and markdown fences."""
    clean_text = raw_reply.strip()

    # Strip <think>...</think> reasoning blocks if emitted by Qwen3
    if "<think>" in clean_text and "</think>" in clean_text:
        clean_text = clean_text.split("</think>")[-1].strip()

    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        proposal = json.loads(clean_text)
        return proposal, "Parsing succeeded."
    except json.JSONDecodeError:
        return None, "PARSER ERROR: Model output was not valid JSON. Return strictly one raw JSON object."

def run_readiness_agent(app_id: str, mock_responses: list = None) -> tuple[dict, list]:
    """
    Runs the Sense-Think-Act agent loop for a single application.
    Supports either live Ollama endpoint or deterministic mock traces for automated testing.
    """
    is_live = mock_responses is None

    user_goal = (
        f"Perform a migration readiness review for application '{app_id}'. "
        "Inspect all dimensions: overview, dependencies, database, and security. "
        "Determine if the record is complete and ready for review, blocked, or missing critical info."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal}
    ]
    
    trace = []
    step = 0
    finished = False
    stop_reason = ""
    final_assessment = None

    # Track distinct inspection gates completed
    inspected_dimensions = set()

    while step < MAX_STEPS and not finished:
        step += 1

        
        # 1. THINK: Model call
        if not is_live:
            if step <= len(mock_responses):
                raw_reply = mock_responses[step - 1]
            else:
                stop_reason = "mock_sequence_exhausted"
                break
        else:
            print(f"  [Step {step}] Thinking (querying {MODEL_NAME})...", flush=True)
            try:
                res = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL_NAME,
                        "messages": messages,
                        "stream": False,
                        "think": False
                    },
                    timeout=120
                )
                res.raise_for_status()
                raw_reply = res.json()["message"]["content"]
            except Exception as e:
                stop_reason = f"model_connection_error: {e}"
                print(f"  [Step {step}] ERROR: {stop_reason}")
                break
        messages.append({"role": "assistant", "content": raw_reply})

        # 2. PARSE: Syntax check
        proposal, parse_note = parse_model_reply(raw_reply)
        if proposal is None:
            if is_live:
                print(f"  [Step {step}] Parse Failed -> Feeding error observation back to model.")
            messages.append({"role": "user", "content": f"TOOL OBSERVATION: {parse_note}"})
            trace.append({
                "step": step, "raw_reply": raw_reply, "action": None,
                "argument": None, "parse_ok": False, "validation_ok": False,
                "observation": parse_note, "check": "FAILED: Invalid JSON syntax", "status": "continue"
            })
            continue

        # 3. VALIDATE: Semantic check
        val_ok, val_note = validate_proposal(proposal)
        action = proposal["action"]
        argument = proposal["argument"]

        if not val_ok:
            obs_feedback = f"VALIDATION ERROR: {val_note}"
            if is_live:
                print(f"  [Step {step}] Proposed '{action}' -> BLOCKED by validator ({val_note})")
            messages.append({"role": "user", "content": f"TOOL OBSERVATION: {obs_feedback}"})
            trace.append({
                "step": step, "raw_reply": raw_reply, "action": action,
                "argument": argument, "parse_ok": True, "validation_ok": False,
                "observation": obs_feedback, "check": "FAILED: Schema/Whitelist validation", "status": "continue"
            })
            continue

        # 4. TERMINAL STOPPING VERIFICATION (declare_assessment)
        if action == "declare_assessment":
            required_areas = {"inspect_app_overview", "inspect_dependencies", "inspect_database", "inspect_security"}
            missing_audits = required_areas - inspected_dimensions

            # Gate Check 1: Must run all 4 tools first
            if len(missing_audits) > 0:
                obs_feedback = f"GOAL CHECK FAILED: You cannot declare an assessment before inspecting all areas. Unchecked: {sorted(list(missing_audits))}."
                if is_live:
                    print(f"  [Step {step}] Proposed 'declare_assessment' -> BLOCKED (missing gates: {sorted(list(missing_audits))})")
                messages.append({"role": "user", "content": f"TOOL OBSERVATION: {obs_feedback}"})
                trace.append({
                    "step": step, "raw_reply": raw_reply, "action": action, "argument": argument,
                    "parse_ok": True, "validation_ok": True, "observation": obs_feedback,
                    "check": "FAILED: Incomplete inspection gates", "status": "continue"
                })
                continue

            # Gate Check 2: Ground-truth verification against inventory data
            inv = load_inventory()
            target_app_id = argument.get("app_id")
            app_data = inv.get(target_app_id, {})
            declared_status = argument.get("status")

            has_nulls = (
                app_data.get("dependencies") is None or
                not app_data.get("runtime") or
                app_data.get("database", {}).get("type") in [None, "Unknown"] or
                app_data.get("database", {}).get("managed_cloud_supported") is None or
                app_data.get("security") is None or
                app_data.get("security", {}).get("tls_version") is None
            )

            if has_nulls and declared_status != "NEEDS_MORE_INFO":
                obs_feedback = (
                    f"GOAL CHECK FAILED: You declared status='{declared_status}', which is invalid because "
                    "inventory data contains null or Unknown fields. "
                    "You MUST resubmit 'declare_assessment' with \"status\": \"NEEDS_MORE_INFO\" and list the missing fields."
                )
                if is_live:
                    print(f"  [Step {step}] Proposed '{declared_status}' -> BLOCKED by Ground-Truth Gate (must be NEEDS_MORE_INFO)")
                messages.append({"role": "user", "content": f"TOOL OBSERVATION: {obs_feedback}"})
                trace.append({
                    "step": step, "raw_reply": raw_reply, "action": action, "argument": argument,
                    "parse_ok": True, "validation_ok": True, "observation": obs_feedback,
                    "check": "FAILED: Incomplete record must be classified as NEEDS_MORE_INFO", "status": "continue"
                })
                continue

            # Verified clean exit
            finished = True
            stop_reason = "success"
            final_assessment = argument
            if is_live:
                print(f"  [Step {step}] Proposed 'declare_assessment' ({declared_status}) -> VERIFIED & ACCEPTED.")
            trace.append({
                "step": step, "raw_reply": raw_reply, "action": action, "argument": argument,
                "parse_ok": True, "validation_ok": True, "observation": "Assessment verified and recorded.",
                "check": "PASSED: All inspection gates completed and verified against ground truth.", "status": "stop"
            })
            break

        # 5. ACT: Execute tool
        tool_result = {"ok": False, "observation": "Unknown action"}
        if action == "inspect_app_overview":
            tool_result = inspect_app_overview(argument["app_id"])
            inspected_dimensions.add("inspect_app_overview")
        elif action == "inspect_dependencies":
            tool_result = inspect_dependencies(argument["app_id"])
            inspected_dimensions.add("inspect_dependencies")
        elif action == "inspect_database":
            tool_result = inspect_database(argument["app_id"])
            inspected_dimensions.add("inspect_database")
        elif action == "inspect_security":
            tool_result = inspect_security(argument["app_id"])
            inspected_dimensions.add("inspect_security")

        # 6. SENSE: Deterministic check & memory feedback
        obs_text = tool_result.get("observation", "")
        obs_feedback = f"TOOL OBSERVATION: {obs_text}"
        messages.append({"role": "user", "content": obs_feedback})

        if is_live:
            print(f"  [Step {step}] Action: {action} -> Observation: {obs_text}")

        trace.append({
            "step": step,
            "raw_reply": raw_reply,
            "action": action,
            "argument": argument,
            "parse_ok": True,
            "validation_ok": True,
            "observation": obs_text,
            "check": f"Executed successfully (ok={tool_result.get('ok')})",
            "status": "continue"
        })

    if not finished and step >= MAX_STEPS:
        stop_reason = "budget_exceeded"

    return {
        "app_id": app_id,
        "finished": finished,
        "stop_reason": stop_reason,
        "assessment": final_assessment,
        "inspected_dimensions": list(inspected_dimensions)
    }, trace