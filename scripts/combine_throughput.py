
import csv
from collections import defaultdict
from pathlib import Path

FILES = [
    "data/baseline.csv",
    "data/loaded_baseline.csv",
    "data/experiments.csv",
]


def combine_throughput(input_file):
    path = Path(input_file)
    output_file = path

    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Group RX and TX measurements belonging to the
    # same timestamp, experiment, entity and interface.
    grouped = defaultdict(dict)

    for row in rows:
        metric = row["metric_name"]

        if metric not in (
            "rx_throughput_mbps",
            "tx_throughput_mbps"
        ):
            continue

        # All fields except metric name and metric value
        # identify the measurement.
        key = tuple(
            row[column]
            for column in fieldnames
            if column not in ("metric_name", "metric_value")
        )

        try:
            value = float(row["metric_value"])
        except (ValueError, TypeError):
            continue

        grouped[key][metric] = value

    # Generate combined throughput records.
    new_rows = []

    existing_keys = set()

    for row in rows:
        if row["metric_name"] == "throughput_mbps":
            key = tuple(
                row[column]
                for column in fieldnames
                if column not in ("metric_name", "metric_value")
            )
            existing_keys.add(key)

    for key, measurements in grouped.items():

        if "rx_throughput_mbps" not in measurements:
            continue

        if "tx_throughput_mbps" not in measurements:
            continue

        # Avoid creating duplicate combined records.
        if key in existing_keys:
            continue

        combined = dict(zip(
            [
                column for column in fieldnames
                if column not in ("metric_name", "metric_value")
            ],
            key
        ))

        combined["metric_name"] = "throughput_mbps"
        combined["metric_value"] = str(round(
            measurements["rx_throughput_mbps"]
            + measurements["tx_throughput_mbps"],
            6
        ))

        new_rows.append(combined)

    # Preserve original records and append derived records.
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        writer.writerows(new_rows)

    print(f"\nFile: {path}")
    print(f"Original records: {len(rows)}")
    print(f"Combined records added: {len(new_rows)}")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    for filename in FILES:
        combine_throughput(filename)

