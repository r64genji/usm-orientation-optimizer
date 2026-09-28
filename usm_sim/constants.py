"""Stable identifiers for the movement simulator."""

SOFTWARE_REVISION = "6df8fee-fleet-8-loop"
ENGINE_VERSION = f"0.7.0-{SOFTWARE_REVISION}"
FORMAT_VERSION = "usm-sim-scenario-v1"
TIMEZONE_NAME = "Asia/Kuala_Lumpur"

# Same-time processing order from spec section 9.
PHASE_COMPLETION_RELEASE = 0
PHASE_ARRIVAL_EXTERNAL = 1
PHASE_REPORT_DECISION = 2
PHASE_START_DEPART = 3

STAGE_KINDS = frozenset(
    {
        "hold",
        "travel",
        "vehicle_travel",
        "queue_service",
        "batch_service",
        "manual_count",
    }
)

EVENT_TYPES = frozenset(
    {
        "part_ready",
        "calendar_open",
        "resource_available",
        "hold_start",
        "hold_end",
        "departure",
        "arrival",
        "service_start",
        "service_complete",
        "batch_start",
        "batch_complete",
        "resource_release",
        "hall_area_arrival",
        "entrance_completion",
        "seated_completion",
        "stage_complete",
        "part_split",
        "vehicle_return_complete",
        "cohort_diverted",
        "vehicle_turnaround_complete",
        "count_start",
        "count_complete",
        "count_disagreement",
        "recount_start",
        "recount_complete",
        "count_unresolved",
        "worker_reserved",
        "worker_released",
        "handover",
        "worker_travel_complete",
        "worker_available",
        "operating_limit_exceeded",
        "operating_limit_cleared",
        "report_delivered",
        "policy_hold",
        "policy_resume",
        "physical_block",
        "denied_entry",
        "calendar_close",
        "condition_change",
        "assembly_start",
        "assembly_complete",
        "assembly_travel_complete",
        "withdrawal",
        "part_withdrawn",
        "queue_jump_attempt",
        "queue_jump_enacted",
        "station_intercept",
        "station_miss",
    }
)

DESTINATION_SPACE_RULES = frozenset(
    {
        "reserve_before_departure",
        "allow_approach_wait",
    }
)
VEHICLE_DISPATCH_RULES = frozenset(
    {
        "none",
        "shared_fleet",
        "board_when_available",
        "fixed_interval",
        "headway",
    }
)

DESTINATION_RULES = frozenset(
    {
        "complete_after_stages",
        "service_then_complete",
        "immediate",
        "wait_for_imposed_opening",
    }
)

WAIT_CLASSES = frozenset(
    {
        "queue_waiting",
        "intentional_hold",
        "physical_blocking",
        "resource_waiting",
        "denied_entry",
        "synchronization",
    }
)

WAIT_CLASS_BY_CAUSE = {
    "waiting_for_server": "queue_waiting",
    "waiting_for_release": "intentional_hold",
    "waiting_for_opening": "intentional_hold",
    "waiting_for_hall_open": "intentional_hold",
    "waiting_for_regroup": "synchronization",
    "intentional_hold": "intentional_hold",
    "policy_hold": "intentional_hold",
    "shelter_hold": "intentional_hold",
    "headcount_staging": "intentional_hold",
    "waiting_for_headcount": "intentional_hold",
    "imposed_sequencing_wait": "intentional_hold",
    "physical_blocking": "physical_blocking",
    "waiting_to_alight": "physical_blocking",
    "waiting_for_path": "physical_blocking",
    "waiting_for_space": "physical_blocking",
    "waiting_for_vehicle": "resource_waiting",
    "waiting_for_counter": "resource_waiting",
    "waiting_for_escort": "resource_waiting",
    "waiting_for_worker": "resource_waiting",
    "waiting_for_stragglers": "intentional_hold",
    "waiting_assembly": "synchronization",
    "denied_entry": "denied_entry",
}

CONDITION_KINDS = frozenset(
    {
        "rain",
        "path_closure",
        "walking_rate",
        "bus_outage",
        "worker_availability",
        "hall_delay",
        "door_closure",
        "shelter",
    }
)

GROUPING_BASES = frozenset(
    {
        "hostel",
        "building",
        "floor",
        "wing",
        "floor_wing",
        "target_size",
        "mixed",
    }
)

GROUPING_MODES = frozenset(
    {
        "single_contingent",
        "explicit_parts",
        "from_source_units",
    }
)

SPLIT_POLICIES = frozenset(
    {
        "forbid",
        "keep_units_whole",
        "permit_supervised_split",
    }
)

MIXING_POLICIES = frozenset(
    {
        "same_group_only",
        "same_hostel",
        "permit_mixed_hostels",
    }
)

ADAPTATION_TYPES = frozenset(
    {
        "fixed",
        "release_ready",
    }
)

EXACT_SIZE_METHODS = frozenset(
    {
        "count_during_boarding",
        "previously_confirmed_count",
    }
)

HEADCOUNT_EVENT_TYPES = frozenset(
    {
        "headcount",
        "manual_count",
        "count_start",
        "count_complete",
        "checkpoint_count",
        "count_disagreement",
        "recount_start",
        "recount_complete",
        "count_unresolved",
    }
)

COUNT_METHODS = frozenset({"pass_through", "column"})

BEHAVIOR_ACTIONS = frozenset(
    {
        "wait",
        "wait_for_stragglers",
        "wait-for-stragglers",
        "split_and_go",
        "split-and-go",
        "bump_next_vehicle",
        "bump-next-vehicle",
        "bump_to_next_vehicle",
        "bump-to-next-vehicle",
        "hold_bus",
        "hold-bus",
        "hold_the_bus",
        "hold-the-bus",
        "refuse_unescorted_walk",
        "refuse-unescorted-walk",
        "deny",
        "deny_onward_service",
        "deny-onward-service",
        "intercept_at_station",
        "intercept-at-station",
        "refuse_queue_jump",
        "refuse-queue-jump",
        "allow_queue_jump",
        "allow-queue-jump",
    }
)

# Must not model these. Presence in a scenario or policy is an error.
FORBIDDEN_MODES = frozenset(
    {
        "bag_check",
        "security_service",
        "mechanical_clicker",
        "qr_scan",
        "rst_direct_walk",
        "direct_walk",
        "facial_recognition",
        "face_recognition",
        "personal_student_record",
        "qr_attendance",
        "clicker",
    }
)

ERROR_CATEGORIES = frozenset(
    {
        "missing_input",
        "invalid_value_or_unit",
        "unknown_reference",
        "unsupported_policy",
        "fixed_rule_violation",
        "impossible_static_requirement",
        "unresolved_assumption",
    }
)
