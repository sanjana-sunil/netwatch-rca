
import csv
import math
from collections import defaultdict

THRESHOLD_FILE = "data/thresholds.csv"
EXPERIMENT_FILE = "data/experiments.csv"
OUTPUT_FILE = "data/anomalies.csv"

# Metrics handled through direct status rules instead of statistical thresholds.
STATUS_METRICS = {
    "path_reachability",
    "oper_status",
    "admin_status",
    "link_status",
}


def load_thresholds():
    """Load calculated thresholds, indexed by entity and metric."""

    thresholds = {}

    with open(THRESHOLD_FILE, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            key = (
                row["entity_type"],
                row["entity_name"],
                row["metric_name"],
                row["unit"]
            )

            thresholds[key] = {
                "threshold_type": row["threshold_type"],
                "threshold": float(row["threshold"])
            }

    return thresholds


def is_down(value):
    """Check whether a status value represents a down/failed state."""

    return value.strip().lower() in {
        "0", "false", "down", "no", "failed"
    }


def check_status_anomaly(metric, value):
    """Apply direct rules to network status measurements."""

    normalized_value = value.strip().lower()

    if metric in STATUS_METRICS and is_down(normalized_value):
        return True, f"{metric} indicates a down or failed state"

    return False, ""


def check_threshold_anomaly(value, threshold_info):
    """Compare a numeric measurement against its threshold."""

    threshold = threshold_info["threshold"]
    direction = threshold_info["threshold_type"]

    if direction == "upper" and value > threshold:
        return True, "Measurement exceeded upper threshold"

    if direction == "lower" and value < threshold:
        return True, "Measurement fell below lower threshold"

    return False, ""


def detect_anomalies():
    """Read experiments and identify anomalous measurements."""

    thresholds = load_thresholds()
    anomalies = []

    total_measurements = 0
    skipped_measurements = 0

    with open(EXPERIMENT_FILE, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            metric = row["metric_name"]
            raw_value = row["metric_value"].strip()

            if not raw_value:
                skipped_measurements += 1
                continue

            total_measurements += 1

            # Direct checks for network status metrics.
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
                        "anomaly_reason": reason
                    })

                continue

            # Find the matching statistical threshold.
            if metric == "cpu_usage_pct":
                skipped_measurements += 1
                continue

            key = (
                row["entity_type"],
                row["entity_name"],
                metric,
                row["unit"]
            )

            threshold_info = thresholds.get(key)

            # No matching healthy baseline threshold.
            if threshold_info is None:
                skipped_measurements += 1
                continue

            try:
                value = float(raw_value)
            except ValueError:
                skipped_measurements += 1
                continue

            if not math.isfinite(value):
                skipped_measurements += 1
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
                    "anomaly_reason": reason
                })

    return anomalies, total_measurements, skipped_measurements


def save_anomalies(anomalies):
    """Save detected anomalies to a CSV file."""

    fieldnames = [
        "timestamp",
        "experiment_id",
        "mode",
        "entity_type",
        "entity_name",
        "source_host",
        "destination_host",
        "interface",
        "metric_name",
        "metric_value",
        "unit",
        "fault_type",
        "threshold_type",
        "threshold",
        "anomaly",
        "anomaly_reason"
    ]

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(anomalies)


def main():
    anomalies, total, skipped = detect_anomalies()

    save_anomalies(anomalies)

    print("\nAnomaly detection completed.")
    print(f"Measurements processed: {total}")
    print(f"Measurements skipped: {skipped}")
    print(f"Anomalies detected: {len(anomalies)}")
    print(f"Output saved to: {OUTPUT_FILE}")

    if anomalies:
        print("\nDetected anomalies by metric:")

        counts = defaultdict(int)

        for anomaly in anomalies:
            counts[anomaly["metric_name"]] += 1

        for metric, count in sorted(counts.items()):
            print(f"{metric:25} {count}")


if __name__ == "__main__":
    main()

