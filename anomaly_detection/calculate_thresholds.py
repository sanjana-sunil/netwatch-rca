
import csv
import statistics
from collections import defaultdict

BASELINE_FILE = "data/baseline.csv"
OUTPUT_FILE = "data/thresholds.csv"

# Metrics for which statistical thresholds will be calculated.
METRIC_DIRECTIONS = {
    "rtt_avg_ms": "upper",
    "jitter_ms": "upper",
    "packet_loss_pct": "upper",
    "throughput_mbps": "lower",
    "cpu_usage_pct": "upper",
    "memory_usage_pct": "upper",
}


def load_baseline():
    """Load healthy baseline measurements grouped by entity and metric."""

    grouped_data = defaultdict(list)

    with open(BASELINE_FILE, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            metric = row["metric_name"]

            if metric not in METRIC_DIRECTIONS:
                continue

            value = row["metric_value"].strip()

            # Ignore missing measurements.
            if not value:
                continue

            try:
                value = float(value)
            except ValueError:
                continue

            key = (
                row["entity_type"],
                row["entity_name"],
                metric,
                row["unit"]
            )

            grouped_data[key].append(value)

    return grouped_data


def calculate_thresholds(grouped_data):
    """Calculate mean, standard deviation and anomaly thresholds."""

    results = []

    for key, values in sorted(grouped_data.items()):
        entity_type, entity_name, metric, unit = key

        mean = statistics.mean(values)
        std_dev = statistics.pstdev(values)

        direction = METRIC_DIRECTIONS[metric]

        if direction == "upper":
            threshold = mean + (3 * std_dev)
            threshold_type = "upper"

        else:
            threshold = max(0, mean - (3 * std_dev))
            threshold_type = "lower"

        results.append({
            "entity_type": entity_type,
            "entity_name": entity_name,
            "metric_name": metric,
            "unit": unit,
            "baseline_count": len(values),
            "mean": round(mean, 6),
            "std_dev": round(std_dev, 6),
            "threshold_type": threshold_type,
            "threshold": round(threshold, 6)
        })

    return results


def save_thresholds(results):
    """Save calculated thresholds to a CSV file."""

    if not results:
        raise ValueError("No valid baseline measurements found.")

    with open(OUTPUT_FILE, "w", newline="") as file:
        fieldnames = results[0].keys()
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)


def main():
    grouped_data = load_baseline()

    results = calculate_thresholds(grouped_data)

    save_thresholds(results)

    print("\nThreshold calculation completed.")
    print(f"Metrics/entities processed: {len(results)}")
    print(f"Output saved to: {OUTPUT_FILE}\n")

    for result in results:
        print(
            f"{result['entity_name']:25} "
            f"{result['metric_name']:20} "
            f"{result['threshold_type']:5} "
            f"{result['threshold']} {result['unit']}"
        )


if __name__ == "__main__":
    main()

