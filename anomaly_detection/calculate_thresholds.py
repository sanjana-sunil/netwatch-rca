import csv
import statistics
from collections import defaultdict
from pathlib import Path

BASELINE_FILES = {
    "idle": Path("data/baseline.csv"),
    "tcp": Path("data/loaded_baseline.csv"),
    "udp": Path("data/udp_baseline.csv"),
}
OUTPUT_FILE = Path("data/thresholds.csv")

METRIC_DIRECTIONS = {
    "rtt_avg_ms": "upper",
    "jitter_ms": "upper",
    "packet_loss_pct": "upper",
    "throughput_mbps": "lower",
    "rx_throughput_mbps": "lower",
    "tx_throughput_mbps": "lower",
    "cpu_usage_pct": "upper",
    "memory_usage_pct": "upper",
}


def load_baselines():
    grouped_data = defaultdict(list)

    for traffic_condition, baseline_file in BASELINE_FILES.items():
        if not baseline_file.exists():
            raise FileNotFoundError(
                f"Missing {traffic_condition} baseline file: {baseline_file}"
            )

        with baseline_file.open("r", newline="") as file:
            reader = csv.DictReader(file)
            required = {
                "entity_type", "entity_name", "metric_name",
                "metric_value", "unit",
            }
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(
                    f"{baseline_file} is missing columns: {sorted(missing)}"
                )

            for row in reader:
                metric = (row.get("metric_name") or "").strip()
                if metric not in METRIC_DIRECTIONS:
                    continue

                raw_value = (row.get("metric_value") or "").strip()
                if not raw_value:
                    continue

                try:
                    value = float(raw_value)
                except ValueError:
                    continue

                key = (
                    traffic_condition,
                    row["entity_type"],
                    row["entity_name"],
                    metric,
                    row["unit"],
                )
                grouped_data[key].append(value)

    return grouped_data


def calculate_thresholds(grouped_data):
    results = []

    for key, values in sorted(grouped_data.items()):
        traffic_condition, entity_type, entity_name, metric, unit = key
        mean = statistics.mean(values)
        std_dev = statistics.pstdev(values)

        # A zero/near-zero interface direction is normally inactive.
        # Do not create a lower-throughput threshold for that direction.
        if metric in ("rx_throughput_mbps", "tx_throughput_mbps") and mean < 0.05:
            continue

        direction = METRIC_DIRECTIONS[metric]

        if direction == "upper":
            threshold = mean + (3 * std_dev)
            threshold_type = "upper"
        else:
            threshold = max(0, mean - (3 * std_dev))
            threshold_type = "lower"

        results.append({
            "traffic_condition": traffic_condition,
            "entity_type": entity_type,
            "entity_name": entity_name,
            "metric_name": metric,
            "unit": unit,
            "baseline_count": len(values),
            "mean": round(mean, 6),
            "std_dev": round(std_dev, 6),
            "threshold_type": threshold_type,
            "threshold": round(threshold, 6),
        })

    return results


def save_thresholds(results):
    if not results:
        raise ValueError("No valid baseline measurements found.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "traffic_condition", "entity_type", "entity_name", "metric_name",
        "unit", "baseline_count", "mean", "std_dev",
        "threshold_type", "threshold",
    ]

    with OUTPUT_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def main():
    grouped_data = load_baselines()
    results = calculate_thresholds(grouped_data)
    save_thresholds(results)

    print("\nThreshold calculation completed.")
    print(f"Condition/entity/metric groups processed: {len(results)}")
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

