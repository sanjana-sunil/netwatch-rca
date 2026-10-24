import re
import time
from pathlib import Path
from datetime import datetime
from mininet.net import Mininet
import csv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_FILE = PROJECT_ROOT / "data" / "experiments.csv"
TARGETS = ["Host1", "Host2", "Host3", "Host4"]
INTERVAL = 2
FIELDS = ["timestamp", "source", "target", "rtt_ms", "packet_loss_percent"]

def collect_ping(source, target):
    timestamp = datetime.now().isoformat(timespec="seconds")
    output = source.cmd(
            f"ping -n -c 1 -W 1 {target.IP()}"
        )
    match = re.search(r"time[=<]([\d.]+)\s*ms", output)
    rtt = float(match.group(1)) if match else None
    packet_loss = 0 if match else 100
    return{
            "timestamp": timestamp,
            "source": source.name,
            "target": target.name,
            "rtt_ms": rtt,
            "packet_loss_percent": packet_loss
        }
def save_measurement(measurement):
    CSV_FILE.parent.mkdir(parents = True, exist_ok = True)
    file_exists = CSV_FILE.exists() and CSV_FILE.stat().st_size > 0
    with open(CSV_FILE, "a", newline = "") as file:
        writer = csv.DictWriter(file, fieldnames = FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(measurement)

def collect_metrics(net, duration = 30):
    hosts = {host.name: host for host in net.hosts}
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
            for source_name in TARGETS:
                for target_name in TARGETS:
                    if time.monotonic() >= deadline:
                        return
                    if source_name == target_name:
                        continue
                    measurement = collect_ping(
                            hosts[source_name],
                            hosts[target_name]
                        )
                    save_measurement(measurement)
                    print(measurement, flush = True)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(INTERVAL, remaining))
    print("\nTelemetry collection has stopped.")
