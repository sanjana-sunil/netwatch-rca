
import csv
from collections import defaultdict
from pathlib import Path

THRESHOLD_FILE = "data/thresholds.csv"
EXPERIMENT_FILE = "data/experiments.csv"
LOG_FILE = "logs/experiments_log.csv"

BASELINE_FILES = {
    "idle": "data/baseline.csv",
    "tcp": "data/loaded_baseline.csv",
}

OUTPUT_FILE = "data/bn_dataset.csv"

FAULTS = {
    "high_latency",
    "packet_loss",
    "bandwidth_limitation",
    "inter_switch_link_failure",
}


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
            key = (
                row["traffic_condition"].strip().lower(),
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
            experiment_id = row["experiment_id"]

            condition = row.get("traffic_condition", "")
            condition = condition.strip().lower()

            if not condition:
                condition = default_condition

            row["_condition"] = condition
            sessions[experiment_id].append(row)

    return sessions


def load_valid_faults():
    completed = {}

    with open(LOG_FILE, newline="") as file:
        for row in csv.DictReader(file):
            if row["status"].strip().lower() != "completed":
                continue

            fault = normalize_fault(row["fault_type"])
            condition = row["traffic_condition"].strip().lower()

            if fault not in FAULTS:
                continue

            if fault in {
                "high_latency",
                "packet_loss",
                "inter_switch_link_failure",
            }:
                if condition not in {"idle", "tcp"}:
                    continue

            elif fault == "bandwidth_limitation":
                if condition != "tcp":
                    continue

            completed[row["experiment_id"]] = (fault, condition)

    return completed


def numeric_values(rows, metric_name):
    values = []

    for row in rows:
        if row["metric_name"] != metric_name:
            continue

        try:
            values.append(float(row["metric_value"]))
        except (ValueError, TypeError):
            continue

    return values


def threshold_symptom(rows, thresholds, metric_name):
    comparisons = []

    for row in rows:
        if row["metric_name"] != metric_name:
            continue

        key = (
            row["_condition"],
            row["entity_type"].strip(),
            row["entity_name"].strip(),
            metric_name,
        )

        if key not in thresholds:
            continue

        try:
            value = float(row["metric_value"])
        except (ValueError, TypeError):
            continue

        threshold_type, threshold = thresholds[key]

        if threshold_type == "upper":
            comparisons.append(value > threshold)
        elif threshold_type == "lower":
            comparisons.append(value < threshold)

    if not comparisons:
        return "unknown"

    return "yes" if any(comparisons) else "no"


def path_unreachable(rows):
    values = numeric_values(rows, "path_reachability")

    if not values:
        return "unknown"

    return "yes" if any(value <= 0 for value in values) else "no"


def port_down(rows):
    values = (
        numeric_values(rows, "admin_status")
        + numeric_values(rows, "oper_status")
    )

    if not values:
        return "unknown"

    return "yes" if any(value <= 0 for value in values) else "no"


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
        "low_throughput": threshold_symptom(
            rows, thresholds, "throughput_mbps"
        ),
        "path_unreachable": path_unreachable(rows),
        "port_down": port_down(rows),
        "fault_type": fault,
    }


def main():
    thresholds = load_thresholds()
    dataset = []

    # Add healthy baseline sessions.
    for condition, filename in BASELINE_FILES.items():
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

    # Load fault experiment measurements.
    fault_sessions = load_sessions(EXPERIMENT_FILE)

    # Keep only validated completed experiments.
    valid_faults = load_valid_faults()

    for experiment_id, (fault, condition) in valid_faults.items():
        rows = fault_sessions.get(experiment_id)

        if not rows:
            continue

        dataset.append(
            make_record(
                experiment_id,
                condition,
                fault,
                rows,
                thresholds,
            )
        )

    if not dataset:
        print("No records generated. Check the input files.")
        return

    fields = [
        "experiment_id",
        "traffic_condition",
        "high_rtt",
        "high_jitter",
        "high_packet_loss",
        "low_throughput",
        "path_unreachable",
        "port_down",
        "fault_type",
    ]

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(dataset)

    print("\n===== BAYESIAN NETWORK DATASET =====")
    print("Total sessions:", len(dataset))

    counts = defaultdict(int)

    for row in dataset:
        counts[row["fault_type"]] += 1

    for fault, count in sorted(counts.items()):
        print(f"{fault}: {count}")

    print("\nOutput:", OUTPUT_FILE)


if __name__ == "__main__":
    main()

