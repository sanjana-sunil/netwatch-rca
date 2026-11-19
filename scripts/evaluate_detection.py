
import csv
from collections import defaultdict


LOG_FILE = "logs/experiments_log.csv"
EXPERIMENT_FILE = "data/experiments.csv"
ANOMALY_FILE = "data/anomalies.csv"


EXPECTED_METRICS = {
    "high_latency": {"rtt_avg_ms", "jitter_ms"},
    "packet_loss": {"packet_loss_pct", "path_reachability"},
    "inter_switch_link_failure": {
        "path_reachability",
        "packet_loss_pct",
        "admin_status",
        "oper_status",
    },
    "bandwidth_limitation": {"throughput_mbps"},
}


def normalize_fault(fault):
    fault = fault.strip().lower()
    fault = fault.replace("-", "_").replace(" ", "_")

    aliases = {
        "interswitch_link_failure": "inter_switch_link_failure"
    }

    return aliases.get(fault, fault)


# Load completed experiment IDs
    
# Load completed experiments with their fault type and traffic condition
completed = {}

with open(LOG_FILE, newline="") as file:
    for row in csv.DictReader(file):
        if row["status"].strip().lower() == "completed":
            experiment_id = row["experiment_id"]
            fault_type = normalize_fault(row["fault_type"])
            traffic_condition = row["traffic_condition"].strip().lower()

            completed[experiment_id] = (fault_type, traffic_condition)


# Find experiment IDs that actually have measurements
measured = set()

with open(EXPERIMENT_FILE, newline="") as file:
    for row in csv.DictReader(file):
        measured.add(row["experiment_id"])


# Keep only supported, completed experiments with measurements
valid_experiments = {}

for experiment_id, (fault_type, traffic_condition) in completed.items():

    if experiment_id not in measured:
        continue

    if fault_type not in EXPECTED_METRICS:
        continue

    if fault_type in (
        "high_latency",
        "inter_switch_link_failure",
        "packet_loss",
    ):
        if traffic_condition not in ("idle", "tcp"):
            continue

    elif fault_type == "bandwidth_limitation":
        if traffic_condition != "tcp":
            continue

    valid_experiments[experiment_id] = fault_type



# Find relevant anomalies for each experiment
detected = defaultdict(set)

with open(ANOMALY_FILE, newline="") as file:
    for row in csv.DictReader(file):
        if row["anomaly"].strip().lower() == "yes":
            detected[row["experiment_id"]].add(row["metric_name"])


# Calculate detection coverage
results = defaultdict(
    lambda: {"total": 0, "detected": 0}
)

for experiment_id, fault_type in valid_experiments.items():

    results[fault_type]["total"] += 1

    relevant_metrics = EXPECTED_METRICS[fault_type]

    if detected[experiment_id] & relevant_metrics:
        results[fault_type]["detected"] += 1


# Display results
print("\n===== THRESHOLD DETECTION COVERAGE =====")

print(f"Completed experiments in log: {len(completed)}")
print(f"Experiments with measurements: {len(measured)}")
print(f"Valid experiments evaluated: {len(valid_experiments)}")

for fault_type, counts in sorted(results.items()):

    total = counts["total"]
    found = counts["detected"]
    missed = total - found

    percentage = found / total * 100 if total else 0

    print(f"\nFault: {fault_type}")
    print(f"Experiments evaluated: {total}")
    print(f"Detected: {found}")
    print(f"Missed: {missed}")
    print(f"Detection coverage: {percentage:.2f}%")

