
import csv
import math
from collections import defaultdict
from pathlib import Path

THRESHOLD_FILE = Path("data/thresholds.csv")
EXPERIMENT_FILE = Path("data/experiments.csv")
OUTPUT_FILE = Path("data/anomalies.csv")

SUPPORTED_CONDITIONS = {"idle"}

STATUS_METRICS = {
    "path_reachability",
    "oper_status",
    "admin_status",
    "link_status",
}


def load_thresholds():
    """Load thresholds grouped by traffic condition and metric."""

    thresholds = {}

    with THRESHOLD_FILE.open("r", newline="") as file:
        reader = csv.DictReader(file)

        required = {
            "traffic_condition", "entity_type", "entity_name",
            "metric_name", "unit", "threshold_type", "threshold",
        }

        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{THRESHOLD_FILE} is missing columns: {sorted(missing)}"
            )

        for row in reader:
            condition = row["traffic_condition"].strip()

            if condition not in SUPPORTED_CONDITIONS:
                continue

            key = (
                condition,
                row["entity_type"],
                row["entity_name"],
                row["metric_name"],
                row["unit"],
            )

            thresholds[key] = {
                "threshold_type": row["threshold_type"],
                "threshold": float(row["threshold"]),
            }

    return thresholds


def is_down(value):
    return value.strip().lower() in {
        "0", "false", "down", "no", "failed"
    }


def check_status_anomaly(metric, value):
    """Check direct status-based anomalies."""

    if metric in STATUS_METRICS and is_down(value):
        return True, f"{metric} indicates a down or failed state"

    return False, ""


def check_threshold_anomaly(value, threshold_info):
    """Compare a measurement against its statistical threshold."""

    threshold = threshold_info["threshold"]
    direction = threshold_info["threshold_type"]

    if direction == "upper" and value > threshold:
        return True, "Measurement exceeded upper threshold"

    if direction == "lower" and value < threshold:
        return True, "Measurement fell below lower threshold"

    return False, ""


def detect_anomalies():
    thresholds = load_thresholds()

    anomalies = []
    total_measurements = 0
    skipped = defaultdict(int)

    with EXPERIMENT_FILE.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:

            traffic_condition = (
                row.get("traffic_condition") or ""
            ).strip()

# Process only explicitly labelled idle experiments.
            if traffic_condition not in SUPPORTED_CONDITIONS:
                skipped["unsupported traffic condition"] += 1
                continue
            metric = (row.get("metric_name") or "").strip()
            raw_value = (row.get("metric_value") or "").strip()

            if not raw_value:
                skipped["missing measurements"] += 1
                continue

            total_measurements += 1

            # Direct status checks do not require statistical thresholds.
            if metric in STATUS_METRICS:
                is_anomaly, reason = check_status_anomaly(
                    metric, raw_value
                )

                if is_anomaly:
                    anomalies.append({
                        **row,
                        "threshold_type": "direct_rule",
                        "threshold": "",
                        "anomaly": "yes",
                        "anomaly_reason": reason,
                    })

                continue

            key = (
                traffic_condition,
                row.get("entity_type", ""),
                row.get("entity_name", ""),
                metric,
                row.get("unit", ""),
            )

            threshold_info = thresholds.get(key)

            if threshold_info is None:
                skipped["missing threshold"] += 1
                continue

            try:
                value = float(raw_value)
            except ValueError:
                skipped["invalid measurements"] += 1
                continue

            if not math.isfinite(value):
                skipped["invalid measurements"] += 1
                continue

            is_anomaly, reason = check_threshold_anomaly(
                value, threshold_info
            )

            if is_anomaly:
                anomalies.append({
                    **row,
                    "threshold_type": threshold_info["threshold_type"],
                    "threshold": threshold_info["threshold"],
                    "anomaly": "yes",
                    "anomaly_reason": reason,
                })

    return anomalies, total_measurements, skipped


def save_anomalies(anomalies):
    """Save detected anomalies to CSV."""

    fieldnames = [
        "timestamp", "experiment_id", "mode", "traffic_condition",
        "entity_type", "entity_name", "source_host", "destination_host",
        "interface", "metric_name", "metric_value", "unit", "fault_type",
        "threshold_type", "threshold", "anomaly", "anomaly_reason",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(anomalies)


def main():
    anomalies, total, skipped = detect_anomalies()

    save_anomalies(anomalies)

    print("\nAnomaly detection completed.")
    print(f"Measurements processed: {total}")
    print(f"Measurements skipped: {sum(skipped.values())}")
    print(f"Anomalies detected: {len(anomalies)}")
    print(f"Output saved to: {OUTPUT_FILE}")

    if skipped:
        print("\nSkipped measurements:")
        for reason, count in sorted(skipped.items()):
            print(f"{reason:30} {count}")

    if anomalies:
        print("\nDetected anomalies by metric:")
        counts = defaultdict(int)

        for anomaly in anomalies:
            counts[anomaly["metric_name"]] += 1

        for metric, count in sorted(counts.items()):
            print(f"{metric:25} {count}")


if __name__ == "__main__":
    main()

