
import csv
import statistics
from collections import defaultdict

BASELINE_FILES = {
    "idle": "data/baseline.csv",
    "tcp": "data/loaded_baseline.csv",
}

OUTPUT_FILE = "data/thresholds.csv"

METRIC_DIRECTIONS = {
    "rtt_avg_ms": "upper",
    "jitter_ms": "upper",
    "packet_loss_pct": "upper",
    "throughput_mbps": "lower",
    "cpu_usage_pct": "upper",
    "memory_usage_pct": "upper",
    }


def load_baseline():
    """Load healthy measurements grouped by traffic condition,
    entity and metric.
    """

    grouped_data = defaultdict(list)

    for condition, filename in BASELINE_FILES.items():

        with open(filename, "r", newline="") as file:
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
                    condition,
                    row["entity_type"],
                    row["entity_name"],
                    metric,
                    row["unit"]
                )

                grouped_data[key].append(value)

    return grouped_data


def calculate_thresholds(grouped_data):
    """Calculate mean, standard deviation and thresholds."""

    results = []

    for key, values in sorted(grouped_data.items()):

        condition, entity_type, entity_name, metric, unit = key

        mean = statistics.mean(values)
        std_dev = statistics.pstdev(values)

        direction = METRIC_DIRECTIONS[metric]

        if direction == "upper":
            threshold = mean + (3 * std_dev)

            # Packet loss cannot exceed 100%.
            if metric == "packet_loss_pct":
                threshold = min(100, threshold)

            threshold_type = "upper"

        else:
            if metric == "throughput_mbps":
                threshold = mean * 0.70
            else:
                threshold = max(0, mean - (3 * std_dev))

            threshold_type = "lower"

        results.append({
            "traffic_condition": condition,
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
    """Save calculated thresholds to CSV."""

    if not results:
        raise ValueError("No valid baseline measurements found.")

    with open(OUTPUT_FILE, "w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys()
        )

        writer.writeheader()
        writer.writerows(results)


def main():
    grouped_data = load_baseline()

    results = calculate_thresholds(grouped_data)

    save_thresholds(results)

    print("\nThreshold calculation completed.")
    print(f"Traffic conditions: {', '.join(BASELINE_FILES.keys())}")
    print(f"Groups processed: {len(results)}")
    print(f"Output saved to: {OUTPUT_FILE}\n")

    for result in results:
        print(
            f"{result['traffic_condition']:5} "
            f"{result['entity_name']:25} "
            f"{result['metric_name']:20} "
            f"{result['threshold_type']:5} "
            f"{result['threshold']} {result['unit']}"
        )


if __name__ == "__main__":
    main()

