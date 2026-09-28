"""Compare simulated Restu milestones with the reviewed 17 September references."""

from __future__ import annotations


def _matches(event: dict, spec: dict) -> bool:
    return all(event.get(key) == value for key, value in spec.items())


def first_match(trace: list[dict], spec: dict) -> dict | None:
    for event in trace:
        if _matches(event, spec):
            return event
    return None


def evaluate_accuracy(scenario: dict, trace: list[dict]) -> list[dict]:
    checks = []
    is_estimated_scenario = bool(
        scenario.get("estimated_scenario")
        or scenario.get("scenario_type") == "estimated"
        or scenario.get("status") == "estimated"
        or scenario.get("is_estimated")
    )
    for raw in scenario.get("accuracy_references") or []:
        check = {
            "id": raw["id"],
            "role": raw["role"],
            "endpoint_definition": raw.get("endpoint_definition"),
            "observation_ref": raw.get("observation_ref"),
            "imposed_input": bool(raw.get("imposed_input")),
            "counted_as_predicted_success": False,
            "measured_accuracy_pass": False,
        }
        # Extract uncertainty range if present
        range_s = None
        if "uncertainty_range_s" in raw:
            r = raw["uncertainty_range_s"]
            range_s = (r[1] - r[0]) if isinstance(r, (list, tuple)) else float(r)
        elif "range_s" in raw:
            range_s = float(raw["range_s"])
        elif "allowed_range_s" in raw and raw["role"] in ("unverified", "unmeasured", "estimated"):
            r = raw["allowed_range_s"]
            range_s = (r[1] - r[0]) if isinstance(r, (list, tuple)) else float(r)

        if range_s is not None:
            check["range_s"] = range_s
            check["uncertainty_range_s"] = range_s

        if raw["role"] in ("unverified", "unmeasured", "estimated") or raw.get("unmeasured"):
            check["verified"] = False
            check["label"] = raw["role"]
            check["passed"] = False
            check["counted_as_predicted_success"] = False
            check["measured_accuracy_pass"] = False
            check["eligible_measured_accuracy"] = False
            check["hostel_id"] = raw.get("hostel_id")
            check["note"] = raw.get("note")
            if range_s is not None and range_s > 600.0:
                check["accuracy_status"] = "not_demonstrated"
                check["status"] = "not_demonstrated"
                check["demonstrated"] = False
            else:
                check["accuracy_status"] = "unverified"
            checks.append(check)
            continue
        if raw["role"] == "predicted_duration":
            start_event = first_match(trace, raw["start_match"])
            end_event = first_match(trace, raw["end_match"])
            check["start_event_id"] = start_event["event_id"] if start_event else None
            check["end_event_id"] = end_event["event_id"] if end_event else None
            if start_event and end_event:
                predicted_s = (end_event["time_ms"] - start_event["time_ms"]) / 1000.0
                check["predicted_s"] = predicted_s
                if "allowed_range_s" in raw:
                    low, high = raw["allowed_range_s"]
                    check["allowed_range_s"] = [low, high]
                    check["passed"] = low <= predicted_s <= high
                else:
                    observed_s = float(raw["observed_s"])
                    limit_s = float(raw.get("limit_s", 600))
                    error_s = predicted_s - observed_s
                    check["observed_s"] = observed_s
                    check["limit_s"] = limit_s
                    check["signed_error_s"] = error_s
                    check["abs_error_s"] = abs(error_s)
                    check["passed"] = abs(error_s) <= limit_s
                if is_estimated_scenario:
                    check["counted_as_predicted_success"] = False
                    check["measured_accuracy_pass"] = False
                    check["eligible_measured_accuracy"] = False
                    check["accuracy_status"] = "not_demonstrated" if (range_s and range_s > 600) else "unverified"
                elif raw.get("imposed_input") or raw["role"] == "imposed_input":
                    check["imposed_input"] = True
                    check["counted_as_predicted_success"] = False
                    check["measured_accuracy_pass"] = False
                    check["role"] = "imposed_input"
                else:
                    check["counted_as_predicted_success"] = bool(check.get("passed"))
                    check["measured_accuracy_pass"] = bool(check.get("passed"))
                    check["eligible_measured_accuracy"] = True
            else:
                check["passed"] = False
                check["counted_as_predicted_success"] = False
                check["measured_accuracy_pass"] = False
                if raw.get("imposed_input") or raw["role"] == "imposed_input":
                    check["imposed_input"] = True
                    check["role"] = "imposed_input"
        elif raw["role"] in ("evidence_boundary", "unverified_endpoint"):
            event = first_match(trace, raw.get("event_match") or {})
            check["event_id"] = event["event_id"] if event else None
            check["role"] = raw["role"]
            check["verified"] = False
            check["passed"] = False
            check["counted_as_predicted_success"] = False
            check["measured_accuracy_pass"] = False
            check["eligible_measured_accuracy"] = False
            check["accuracy_status"] = "unverified"
            check["status"] = "unverified"
            check["hostel_id"] = raw.get("hostel_id")
            check["note"] = raw.get("note")
            if event is not None:
                predicted_s = event["time_ms"] / 1000.0
                observed_s = float(raw["observed_s"])
                limit_s = float(raw.get("limit_s", 600))
                error_s = predicted_s - observed_s
                check["predicted_s"] = predicted_s
                check["predicted_local"] = event.get("time_local")
                check["observed_s"] = observed_s
                check["observed_local"] = raw.get("observed_local")
                check["limit_s"] = limit_s
                check["signed_error_s"] = error_s
                check["abs_error_s"] = abs(error_s)
        else:
            event = first_match(trace, raw["event_match"])
            check["event_id"] = event["event_id"] if event else None
            if event is not None:
                predicted_s = event["time_ms"] / 1000.0
                observed_s = float(raw["observed_s"])
                limit_s = float(raw.get("limit_s", 600))
                error_s = predicted_s - observed_s
                check["predicted_s"] = predicted_s
                check["predicted_local"] = event.get("time_local")
                check["observed_s"] = observed_s
                check["observed_local"] = raw.get("observed_local")
                check["limit_s"] = limit_s
                check["signed_error_s"] = error_s
                check["abs_error_s"] = abs(error_s)
                check["passed"] = abs(error_s) <= limit_s
            else:
                check["passed"] = False
            if raw.get("imposed_input") or raw["role"] == "imposed_input":
                check["imposed_input"] = True
                check["counted_as_predicted_success"] = False
                check["measured_accuracy_pass"] = False
                check["role"] = "imposed_input"
            elif event is not None:
                if is_estimated_scenario:
                    check["counted_as_predicted_success"] = False
                    check["measured_accuracy_pass"] = False
                    check["eligible_measured_accuracy"] = False
                    check["accuracy_status"] = "not_demonstrated" if (range_s and range_s > 600) else "unverified"
                else:
                    check["counted_as_predicted_success"] = bool(check.get("passed"))
                    check["measured_accuracy_pass"] = bool(check.get("passed"))
                    check["eligible_measured_accuracy"] = True
            else:
                check["counted_as_predicted_success"] = False
                check["measured_accuracy_pass"] = False
        checks.append(check)
    return checks
