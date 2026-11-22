
import csv
from collections import defaultdict
from pathlib import Path

THRESHOLD_FILE = "data/thresholds.csv"
EXPERIMENT_FILE = "data/experiments.csv"
LOG_FILE = "logs/experiments_log.csv"

# Initial project version: idle traffic only.
BASELINE_FILES = {
    "idle": "data/baseline.csv",
}

OUTPUT_FILE = "data/bn_dataset.csv"

FAULTS = {
    "high_latency",
    "packet_loss",
    "inter_switch_link_failure",
}

ABNORMAL_RATIO = 0.50

# Require at least 3 valid measurements.
MIN_VALID_MEASUREMENTS = 2


def normalize_fault(fault):
    fault = fault.strip().lower()
    fault = fault.replace("-", "_").replace(" ", "_")

    if fault == "interswitch_link_failure":
        return "inter_switch_link_failure"

    return fault


def load_thresholds():
    thresholds = {}

    with open(THRESHOLD_FILE, newline="") as file:
        for row in csv.DictReader(file):

            condition = row["traffic_condition"].strip().lower()

            if condition != "idle":
                continue

            key = (
                condition,
                row["entity_type"].strip(),
                row["entity_name"].strip(),
                row["metric_name"].strip(),
            )

            thresholds[key] = (
                row["threshold_type"].strip().lower(),
                float(row["threshold"]),
            )

    return thresholds


def load_sessions(filename, default_condition=None):
    sessions = defaultdict(list)

    with open(filename, newline="") as file:
        for row in csv.DictReader(file):

            experiment_id = (
                row.get("experiment_id") or ""
            ).strip()

            if not experiment_id:
                continue

            condition = (
                row.get("traffic_condition") or ""
            ).strip().lower()

            if not condition:
                condition = default_condition

            row["_condition"] = condition

            sessions[experiment_id].append(row)

    return sessions


def load_valid_faults():
    """
    Read completed experiments from the experiment log.

    The experiment log does not contain traffic_condition.
    That information is obtained later from experiments.csv.
    """

    completed = {}

    with open(LOG_FILE, newline="") as file:
        for row in csv.DictReader(file):

            if (
                row.get("status") or ""
            ).strip().lower() != "completed":
                continue

            experiment_id = (
                row.get("experiment_id") or ""
            ).strip()

            fault = normalize_fault(
                row.get("fault_type") or ""
            )

            if not experiment_id or fault not in FAULTS:
                continue

            completed[experiment_id] = fault

    return completed


def parse_numeric(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def group_by_entity(rows, metric_names):
    """
    Group measurements by entity so that different paths
    or interfaces are evaluated independently.
    """

    groups = defaultdict(list)

    for row in rows:

        if row.get("metric_name", "").strip() not in metric_names:
            continue

        entity = (
            row.get("entity_name") or ""
        ).strip()

        if not entity:
            entity = (
                row.get("interface") or ""
            ).strip()

        if not entity:
            continue

        value = parse_numeric(row.get("metric_value"))

        if value is not None:
            groups[entity].append((row, value))

    return groups


def persistent_symptom(groups, comparison_function):
    """
    Return:
      yes     - persistent abnormal behaviour found
      no      - sufficient measurements, no persistent symptom
      unknown - insufficient measurements
    """

    valid_entities = 0

    for measurements in groups.values():

        if len(measurements) < MIN_VALID_MEASUREMENTS:
            continue

        valid_entities += 1

        abnormal_count = sum(
            comparison_function(row, value)
            for row, value in measurements
        )

        abnormal_ratio = abnormal_count / len(measurements)

        if abnormal_ratio >= ABNORMAL_RATIO:
            return "yes"

    if valid_entities == 0:
        return "unknown"

    return "no"


def threshold_symptom(rows, thresholds, metric_name):

    groups = group_by_entity(rows, {metric_name})

    def is_abnormal(row, value):

        key = (
            row["_condition"],
            row["entity_type"].strip(),
            row["entity_name"].strip(),
            metric_name,
        )

        if key not in thresholds:
            return False

        threshold_type, threshold = thresholds[key]

        if threshold_type == "upper":
            return value > threshold

        if threshold_type == "lower":
            return value < threshold

        return False

    # Only include measurements with matching thresholds.
    valid_groups = {}

    for entity, measurements in groups.items():

        eligible = [
            (row, value)
            for row, value in measurements
            if (
                row["_condition"],
                row["entity_type"].strip(),
                row["entity_name"].strip(),
                metric_name,
            ) in thresholds
        ]

        if eligible:
            valid_groups[entity] = eligible

    return persistent_symptom(valid_groups, is_abnormal)


def path_unreachable(rows):

    groups = group_by_entity(
        rows,
        {"path_reachability"}
    )

    return persistent_symptom(
        groups,
        lambda row, value: value <= 0
    )


def port_down(rows):

    admin_groups = group_by_entity(
        rows,
        {"admin_status"}
    )

    oper_groups = group_by_entity(
        rows,
        {"oper_status"}
    )

    admin_result = persistent_symptom(
        admin_groups,
        lambda row, value: value <= 0
    )

    oper_result = persistent_symptom(
        oper_groups,
        lambda row, value: value <= 0
    )

    if admin_result == "yes" or oper_result == "yes":
        return "yes"

    if admin_result == "no" and oper_result == "no":
        return "no"

    return "unknown"

def inter_switch_link_down(rows):

    inter_switch_ports = {
        "Switch1:Switch1-eth3",
        "Switch2:Switch2-eth1",
    }

    port_status = {}

    for port in inter_switch_ports:

        values = []

        for row in rows:

            if (
                row.get("entity_name", "").strip() == port
                and row.get("metric_name", "").strip() == "admin_status"
            ):
                value = parse_numeric(row.get("metric_value"))

                if value is not None:
                    values.append(value)

        if len(values) < MIN_VALID_MEASUREMENTS:
            port_status[port] = "unknown"
            continue

        down_count = sum(value <= 0 for value in values)
        down_ratio = down_count / len(values)

        if down_ratio >= ABNORMAL_RATIO:
            port_status[port] = "yes"
        else:
            port_status[port] = "no"

    if "yes" in port_status.values():
        return "yes"

    if all(status == "no" for status in port_status.values()):
        return "no"

    return "unknown"

def make_record(experiment_id, condition, fault, rows, thresholds):

    return {
        "experiment_id": experiment_id,
        "traffic_condition": condition,

        "high_rtt": threshold_symptom(
            rows, thresholds, "rtt_avg_ms"
        ),

        "high_jitter": threshold_symptom(
            rows, thresholds, "jitter_ms"
        ),

        "high_packet_loss": threshold_symptom(
            rows, thresholds, "packet_loss_pct"
        ),

        "path_unreachable": path_unreachable(rows),
        "path_unreachable": path_unreachable(rows),
        "inter_switch_link_down": inter_switch_link_down(rows),
        "fault_type": fault,
    }


def save_dataset(dataset):

    fields = [
        "experiment_id",
        "traffic_condition",
        "high_rtt",
        "high_jitter",
        "high_packet_loss",
        "path_unreachable",
        "inter_switch_link_down",
        "fault_type",
    ]

    Path(OUTPUT_FILE).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(dataset)


def main():

    print("Loading idle thresholds...")
    thresholds = load_thresholds()

    print("Threshold groups loaded:", len(thresholds))

    dataset = []

    # =============================================
    # 1. Healthy idle baseline sessions
    # =============================================

    print("\nProcessing healthy idle baseline sessions...")

    for condition, filename in BASELINE_FILES.items():

        if not Path(filename).exists():
            print(f"Warning: Missing baseline file: {filename}")
            continue

        sessions = load_sessions(filename, condition)

        for experiment_id, rows in sessions.items():

            dataset.append(
                make_record(
                    experiment_id,
                    condition,
                    "normal",
                    rows,
                    thresholds,
                )
            )

        print(f"  {condition}: {len(sessions)} sessions")

    # =============================================
    # 2. Completed idle fault experiments
    # =============================================

    print("\nProcessing completed idle fault experiments...")

    fault_sessions = load_sessions(EXPERIMENT_FILE)
    valid_faults = load_valid_faults()

    included_fault_sessions = 0
    skipped_fault_sessions = 0

    for experiment_id, fault in valid_faults.items():

        rows = fault_sessions.get(experiment_id)

        if not rows:
            skipped_fault_sessions += 1
            continue

        # Get traffic condition from experiments.csv,
        # not from experiments_log.csv.
        idle_rows = [
            row for row in rows
            if row["_condition"] == "idle"
        ]

        if not idle_rows:
            skipped_fault_sessions += 1
            continue

        dataset.append(
            make_record(
                experiment_id,
                "idle",
                fault,
                idle_rows,
                thresholds,
            )
        )

        included_fault_sessions += 1

    print("  Included idle fault sessions:", included_fault_sessions)
    print("  Skipped fault sessions:", skipped_fault_sessions)

    # =============================================
    # 3. Save dataset
    # =============================================

    if not dataset:
        print("\nNo records generated. Check the input files.")
        return

    save_dataset(dataset)

    # =============================================
    # 4. Dataset summary
    # =============================================

    print("\n===== BAYESIAN NETWORK DATASET =====")

    print("Total sessions:", len(dataset))

    fault_counts = defaultdict(int)

    for row in dataset:
        fault_counts[row["fault_type"]] += 1

    print("\nFault distribution:")

    for fault, count in sorted(fault_counts.items()):
        print(f"  {fault}: {count}")

    print("\nSymptom distribution:")

    symptom_names = [
        "high_rtt",
        "high_jitter",
        "high_packet_loss",
        "path_unreachable",
        "inter_switch_link_down"
    ]
    
    for symptom in symptom_names:

        counts = defaultdict(int)

        for row in dataset:
            counts[row[symptom]] += 1

        print(f"\n{symptom}")

        for value in ["yes", "no", "unknown"]:
            print(f"  {value}: {counts[value]}")

    print("\nOutput:", OUTPUT_FILE)


if __name__ == "__main__":
    main()

