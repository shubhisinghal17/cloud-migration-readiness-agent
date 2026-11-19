ALLOWED_ACTIONS = {
    "inspect_app_overview",
    "inspect_dependencies",
    "inspect_database",
    "inspect_security",
    "declare_assessment"
}

ALLOWED_STATUSES = {"READY_FOR_REVIEW", "NOT_READY", "NEEDS_MORE_INFO"}

def validate_proposal(proposal: any) -> tuple[bool, str]:
    """Deterministically validates LLM tool proposals against the schema."""
    # Check 1: Must be a dictionary
    if not isinstance(proposal, dict):
        return False, f"Proposal must be a JSON object (dict), got {type(proposal).__name__}."

    # Check 2: Required keys
    if "action" not in proposal or "argument" not in proposal:
        return False, "Proposal missing required 'action' or 'argument' key."

    action = proposal["action"]
    argument = proposal["argument"]

    # Check 3: Types
    if not isinstance(action, str) or not isinstance(argument, dict):
        return False, f"'action' must be a str and 'argument' must be a dict."

    # Check 4: Action whitelist
    if action not in ALLOWED_ACTIONS:
        return False, f"Action '{action}' is not on the allowed whitelist: {list(ALLOWED_ACTIONS)}."

    # Check 5: Argument schemas
    if "app_id" not in argument or not isinstance(argument["app_id"], str):
        return False, f"Action '{action}' requires an 'app_id' string argument."

    if action == "declare_assessment":
        if "status" not in argument or argument["status"] not in ALLOWED_STATUSES:
            return False, f"'declare_assessment' status must be one of {list(ALLOWED_STATUSES)}."
        if "missing_or_unknown_fields" not in argument or not isinstance(argument["missing_or_unknown_fields"], list):
            return False, "'declare_assessment' requires a 'missing_or_unknown_fields' list."
        if "rationale" not in argument or not isinstance(argument["rationale"], str):
            return False, "'declare_assessment' requires a 'rationale' string."

    return True, "Validation succeeded."