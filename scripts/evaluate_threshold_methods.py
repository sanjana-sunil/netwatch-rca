
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================

BASELINE_FILE = "data/baseline.csv"
EXPERIMENT_FILE = "data/experiments.csv"
OUTPUT_FILE = "data/idle_detection_evaluation.csv"

TRAIN_RATIO = 0.70

TRAFFIC_CONDITION = "idle"

METRIC_DIRECTIONS = {
    "rtt_avg_ms": "upper",
    "jitter_ms": "upper",
    "packet_loss_pct": "upper",
}

STATUS_METRICS = {
    "path_reachability",
    "oper_status",
    "admin_status",
    "link_status",
}

EXCLUDED_FAULTS = {
    "bandwidth_limitation",
}


# ==========================================
# CSV LOADING
# ==========================================

def read_csv(filename):
    if not Path(filename).exists():
        raise FileNotFoundError(f"File not found: {filename}")

    with open(filename, "r", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"Empty CSV file: {filename}")

        return list(reader)


def get_session_key(row):
    experiment_id = (row.get("experiment_id") or "").strip()

    if not experiment_id:
        raise ValueError("A row is missing experiment_id.")

    return experiment_id


def load_healthy_data():
    sessions = defaultdict(list)

    rows = read_csv(BASELINE_FILE)

    for row in rows:
        row["traffic_condition"] = TRAFFIC_CONDITION

        session_key = get_session_key(row)
        sessions[session_key].append(row)

    return sessions


def load_fault_data():
    sessions = defaultdict(list)

    rows = read_csv(EXPERIMENT_FILE)

    for row in rows:
        condition = (
            row.get("traffic_condition") or ""
        ).strip().lower()

        # Process idle experiments only.
        if condition != TRAFFIC_CONDITION:
            continue

        fault_type = (
            row.get("fault_type") or ""
        ).strip()

        if not fault_type or fault_type.lower() == "normal":
            continue

        # Exclude faults unsuitable for idle evaluation.
        if fault_type in EXCLUDED_FAULTS:
            continue

        row["traffic_condition"] = TRAFFIC_CONDITION

        session_key = get_session_key(row)
        sessions[session_key].append(row)

    return sessions


# ==========================================
# NUMERIC DATA
# ==========================================

def numeric_values(rows):
    grouped = defaultdict(list)

    for row in rows:
        metric = (row.get("metric_name") or "").strip()

        if metric not in METRIC_DIRECTIONS:
            continue

        try:
            value = float(row["metric_value"])
        except (ValueError, TypeError, KeyError):
            continue

        if not math.isfinite(value):
            continue

        key = (
            row.get("entity_type", ""),
            row.get("entity_name", ""),
            metric,
            row.get("unit", ""),
        )

        grouped[key].append(value)

    return grouped


# ==========================================
# THRESHOLD CALCULATION
# ==========================================

def calculate_threshold(values):
    if not values:
        raise ValueError("Cannot calculate threshold from empty values.")

    mean = statistics.mean(values)
    std_dev = statistics.pstdev(values)

    return mean + (3 * std_dev)


def build_thresholds(training_sessions):
    all_training_rows = []

    for rows in training_sessions.values():
        all_training_rows.extend(rows)

    grouped = numeric_values(all_training_rows)

    thresholds = {}

    for key, values in grouped.items():
        entity_type, entity_name, metric, unit = key

        threshold = calculate_threshold(values)

        if metric == "packet_loss_pct":
            threshold = min(100, threshold)

        thresholds[key] = threshold

    return thresholds


# ==========================================
# ANOMALY DETECTION
# ==========================================

def is_down(raw_value):
    value = raw_value.strip().lower()

    if value in {"false", "down", "no", "failed"}:
        return True

    try:
        return float(value) == 0
    except ValueError:
        return False


def measurement_has_anomaly(row, thresholds):
    metric = (row.get("metric_name") or "").strip()
    raw_value = (row.get("metric_value") or "").strip()

    if not raw_value:
        return False

    # Direct status checks.
    if metric in STATUS_METRICS:
        return is_down(raw_value)

    if metric not in METRIC_DIRECTIONS:
        return False

    try:
        value = float(raw_value)
    except (ValueError, TypeError):
        return False

    if not math.isfinite(value):
        return False

    key = (
        row.get("entity_type", ""),
        row.get("entity_name", ""),
        metric,
        row.get("unit", ""),
    )

    threshold = thresholds.get(key)

    if threshold is None:
        return False

    return value > threshold


def session_has_anomaly(rows, thresholds):
    return any(
        measurement_has_anomaly(row, thresholds)
        for row in rows
    )


def count_measurement_anomalies(rows, thresholds):
    tested = 0
    flagged = 0

    for row in rows:
        metric = (row.get("metric_name") or "").strip()

        # Count only metrics with statistical thresholds.
        if metric not in METRIC_DIRECTIONS:
            continue

        raw_value = (row.get("metric_value") or "").strip()

        if not raw_value:
            continue

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            continue

        if not math.isfinite(value):
            continue

        key = (
            row.get("entity_type", ""),
            row.get("entity_name", ""),
            metric,
            row.get("unit", ""),
        )

        # Ignore measurements without matching thresholds.
        if key not in thresholds:
            continue

        tested += 1

        if value > thresholds[key]:
            flagged += 1

    return tested, flagged


# ==========================================
# TRAIN / TEST SPLIT
# ==========================================

def split_healthy_sessions(healthy_sessions):
    ordered_sessions = sorted(healthy_sessions)

    count = len(ordered_sessions)

    if count < 2:
        raise ValueError(
            f"Need at least 2 healthy sessions, found {count}."
        )

    split_index = int(count * TRAIN_RATIO)
    split_index = max(1, min(split_index, count - 1))

    training = {
        key: healthy_sessions[key]
        for key in ordered_sessions[:split_index]
    }

    testing = {
        key: healthy_sessions[key]
        for key in ordered_sessions[split_index:]
    }

    return training, testing


# ==========================================
# EVALUATION
# ==========================================

def evaluate_healthy_sessions(testing, thresholds):
    total_sessions = len(testing)

    flagged_sessions = sum(
        session_has_anomaly(rows, thresholds)
        for rows in testing.values()
    )

    total_measurements = 0
    flagged_measurements = 0

    for rows in testing.values():
        tested, flagged = count_measurement_anomalies(
            rows, thresholds
        )

        total_measurements += tested
        flagged_measurements += flagged

    session_fpr = (
        flagged_sessions / total_sessions * 100
        if total_sessions else 0
    )

    measurement_fpr = (
        flagged_measurements / total_measurements * 100
        if total_measurements else 0
    )

    return [
        {
            "traffic_condition": TRAFFIC_CONDITION,
            "result_type": "healthy_false_positive_rate",
            "evaluation_level": "session",
            "category": "healthy",
            "items_tested": total_sessions,
            "items_flagged": flagged_sessions,
            "rate_percent": round(session_fpr, 2),
        },
        {
            "traffic_condition": TRAFFIC_CONDITION,
            "result_type": "healthy_false_positive_rate",
            "evaluation_level": "measurement",
            "category": "healthy",
            "items_tested": total_measurements,
            "items_flagged": flagged_measurements,
            "rate_percent": round(measurement_fpr, 2),
        },
    ]


def evaluate_fault_sessions(fault_sessions, thresholds):
    fault_groups = defaultdict(list)

    for rows in fault_sessions.values():
        fault_types = {
            (row.get("fault_type") or "").strip()
            for row in rows
            if (row.get("fault_type") or "").strip()
        }

        for fault_type in fault_types:
            fault_groups[fault_type].append(rows)

    results = []

    for fault_type, sessions in sorted(fault_groups.items()):
        total = len(sessions)

        detected = sum(
            session_has_anomaly(rows, thresholds)
            for rows in sessions
        )

        coverage = detected / total * 100 if total else 0

        results.append({
            "traffic_condition": TRAFFIC_CONDITION,
            "result_type": "fault_detection_coverage",
            "evaluation_level": "session",
            "category": fault_type,
            "items_tested": total,
            "items_flagged": detected,
            "rate_percent": round(coverage, 2),
        })

    return results


# ==========================================
# SAVE RESULTS
# ==========================================

def save_results(results):
    if not results:
        raise ValueError("No evaluation results were generated.")

    fieldnames = [
        "traffic_condition",
        "result_type",
        "evaluation_level",
        "category",
        "items_tested",
        "items_flagged",
        "rate_percent",
    ]

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


# ==========================================
# MAIN
# ==========================================

def main():
    print("\n========== IDLE-ONLY DETECTION EVALUATION ==========")

    print("\nLoading healthy idle baseline...")
    healthy_sessions = load_healthy_data()

    print(f"Healthy idle sessions: {len(healthy_sessions)}")

    print("\nSplitting healthy sessions...")
    training, testing = split_healthy_sessions(healthy_sessions)

    print(f"Training sessions: {len(training)}")
    print(f"Testing sessions:  {len(testing)}")

    print("\nTraining session IDs:")
    for session_id in training:
        print(f"  {session_id}")

    print("\nTesting session IDs:")
    for session_id in testing:
        print(f"  {session_id}")

    print("\nCalculating mean + 3σ thresholds from training data...")
    thresholds = build_thresholds(training)

    print(f"Threshold groups generated: {len(thresholds)}")

    print("\nLoading idle fault experiments...")
    fault_sessions = load_fault_data()

    print(f"Idle fault sessions: {len(fault_sessions)}")

    print("\nEvaluating healthy test sessions...")
    results = evaluate_healthy_sessions(testing, thresholds)

    print("\nEvaluating idle fault sessions...")
    results.extend(
        evaluate_fault_sessions(fault_sessions, thresholds)
    )

    save_results(results)

    print("\n========== EVALUATION RESULTS ==========")

    for result in results:
        print(
            f"{result['evaluation_level']:12} "
            f"{result['result_type']:30} "
            f"{result['category']:30} "
            f"{result['items_flagged']}/"
            f"{result['items_tested']} "
            f"({result['rate_percent']}%)"
        )

    print(f"\nResults saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

