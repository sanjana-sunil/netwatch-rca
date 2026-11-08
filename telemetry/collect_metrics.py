import csv
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from telemetry.collect_ping import collect_ping

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HOST_NAMES = ["Host1", "Host2", "Host3", "Host4"]
SWITCH_NAMES = ["Switch1", "Switch2"]

INTERVAL = 2

FIELDS = [
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
]
INTERFACE_COUNTERS = {
    "rx_packets": ("rx_packets", "packets"),
    "tx_packets": ("tx_packets", "packets"),
    "rx_bytes": ("rx_bytes", "bytes"),
    "tx_bytes": ("tx_bytes", "bytes"),
    "rx_errors": ("rx_errors", "count"),
    "tx_errors": ("tx_errors", "count"),
    "rx_drops": ("rx_dropped", "count"),
    "tx_drops": ("tx_dropped", "count"),
}
def make_row(entity_type, entity_name, metric_name, value, unit, source="", destination="", interface="", experiment_id="", mode="baseline",    fault_type="",):
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "experiment_id": experiment_id,
        "mode": mode,
        "entity_type": entity_type,
        "entity_name": entity_name,
        "source_host": source,
        "destination_host": destination,
        "interface": interface,
        "metric_name": metric_name,
        "metric_value": value,
        "unit": unit,
        "fault_type": fault_type,
    }
def collect_path_metrics(net, experiment_id, mode, fault_type):
    rows = []
    hosts = {host.name: host for host in net.hosts}

    for source_name in HOST_NAMES:
        for destination_name in HOST_NAMES:
            if source_name == destination_name:
                continue

            measurement = collect_ping(
                hosts[source_name],
                hosts[destination_name],
                count=5,
            )
            values = [
                ("rtt_avg_ms", measurement["rtt_ms"], "ms"),
                (
                    "packet_loss_pct",
                    measurement["packet_loss_percent"],
                    "%",
                ),
                ("jitter_ms", measurement["jitter_ms"], "ms"),
                (
                    "path_reachability",
                    measurement["path_reachable"],
                    "boolean",
                ),
            ]
            for name, value, unit in values:
                rows.append(
                    make_row(
                        entity_type="path",
                        entity_name=f"{source_name}->{destination_name}",
                        metric_name=name,
                        value=value,
                        unit=unit,
                        source=source_name,
                        destination=destination_name,
                        experiment_id=experiment_id,
                        mode=mode,
                        fault_type=fault_type,
                    )
                )

    return rows

def collect_host_interface_metrics(net, experiment_id, mode, fault_type):
    rows = []

    for host in net.hosts:
        # Mininet interface names are used directly, avoiding
        # assumptions about interface numbering.
        for intf in host.intfList():
            if intf.name == "lo":
                continue

            interface = intf.name

            for metric_name, (counter_name, unit) in INTERFACE_COUNTERS.items():
                command = (
                    f"cat /sys/class/net/{interface}/statistics/"
                    f"{counter_name}"
                )
                output = host.cmd(command).strip()

                try:
                    value = int(output)
                except ValueError:
                    value = None

                rows.append(
                    make_row(
                        entity_type="interface",
                        entity_name=interface,
                        metric_name=metric_name,
                        value=value,
                        unit=unit,
                        interface=interface,
                        experiment_id=experiment_id,
                        mode=mode,
                        fault_type=fault_type,
                    )
                )

            output = host.cmd(
                f"ip -o link show dev {interface}"
            )

            # Check the interface flags rather than searching the
            # entire command output for the word "UP".
            match = re.search(r"<([^>]*)>", output)
            is_up = (
                int("UP" in match.group(1).split())
                if match
                else None
            )

            rows.append(
                make_row(
                    entity_type="interface",
                    entity_name=interface,
                    metric_name="link_status",
                    value=is_up,
                    unit="boolean",
                    interface=interface,
                    experiment_id=experiment_id,
                    mode=mode,
                    fault_type=fault_type,
                )
            )

    return rows


def collect_switch_port_metrics(net, experiment_id, mode, fault_type):
    rows = []

    for switch_name in SWITCH_NAMES:
        switch = net.get(switch_name)

        output = switch.cmd(
            f"ovs-vsctl list-ports {switch_name}"
        )

        for port in output.splitlines():
            port = port.strip()

            if not port:
                continue

            # 1. Collect switch interface counters
            for metric_name, (counter_name, unit) in INTERFACE_COUNTERS.items():

                command = (
                    f"cat /sys/class/net/{port}/statistics/"
                    f"{counter_name}"
                )

                output = switch.cmd(command).strip()

                try:
                    value = int(output)
                except ValueError:
                    value = None

            

            # 2. Collect administrative interface status
            status_output = switch.cmd(
                f"ip -o link show dev {port}"
            )

            match = re.search(r"<([^>]*)>", status_output)

            admin_status = (
                int("UP" in match.group(1).split())
                if match
                else None
            )

            rows.append(
                make_row(
                    entity_type="switch_port",
                    entity_name=f"{switch_name}:{port}",
                    metric_name="admin_status",
                    value=admin_status,
                    unit="boolean",
                    interface=port,
                    experiment_id=experiment_id,
                    mode=mode,
                    fault_type=fault_type,
                )
            )

            # 3. Collect operational interface status
            oper_output = switch.cmd(
                f"cat /sys/class/net/{port}/operstate"
            ).strip()

            oper_status = oper_output if oper_output else None

            rows.append(
                make_row(
                    entity_type="switch_port",
                    entity_name=f"{switch_name}:{port}",
                    metric_name="oper_status",
                    value=oper_status,
                    unit="state",
                    interface=port,
                    experiment_id=experiment_id,
                    mode=mode,
                    fault_type=fault_type,
                )
            )

    return rows


def read_cpu_counters(host):
    output = host.cmd("cat /proc/stat")
    first_line = output.splitlines()[0].split()

    values = [int(value) for value in first_line[1:]]
    total = sum(values)
    # Linux CPU counters: user, nice, system, idle, iowait, etc.
    idle = values[3] + (values[4] if len(values) > 4 else 0)

    return total, idle

def collect_system_metrics(
    net,
    previous_cpu,
    experiment_id,
    mode,
    fault_type,
):
    rows = []

    # Mininet hosts share the VM's kernel. Label these VM-level
    # readings explicitly rather than treating them as per-host data.
    host = net.hosts[0]

    total, idle = read_cpu_counters(host)

    if previous_cpu is not None:
        old_total, old_idle = previous_cpu
        total_delta = total - old_total
        idle_delta = idle - old_idle

        if total_delta > 0:
            cpu_usage = 100.0 * (
                total_delta - idle_delta
            ) / total_delta

            rows.append(
                make_row(
                    entity_type="vm",
                    entity_name="Ubuntu-VM",
                    metric_name="cpu_usage_pct",
                    value=round(cpu_usage, 3),
                    unit="%",
                    experiment_id=experiment_id,
                    mode=mode,
                    fault_type=fault_type,
                )
            )

    mem_output = host.cmd("cat /proc/meminfo")

    mem_total = re.search(r"^MemTotal:\s+(\d+)", mem_output, re.M)
    mem_available = re.search(
        r"^MemAvailable:\s+(\d+)",
        mem_output,
        re.M,
    )

    if mem_total and mem_available:
        total_kb = int(mem_total.group(1))
        available_kb = int(mem_available.group(1))

        if total_kb > 0:
            memory_usage = (
                100.0 * (total_kb - available_kb) / total_kb
            )

            rows.append(
                make_row(
                    entity_type="vm",
                    entity_name="Ubuntu-VM",
                    metric_name="memory_usage_pct",
                    value=round(memory_usage, 3),
                    unit="%",
                    experiment_id=experiment_id,
                    mode=mode,
                    fault_type=fault_type,
                )
            )

    return rows, (total, idle)

def append_measurements(csv_file, rows):
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    file_exists = csv_file.exists() and csv_file.stat().st_size > 0

    if file_exists:
        with open(csv_file, "r", newline="") as file:
            existing_fields = next(csv.reader(file), [])

        if existing_fields != FIELDS:
            raise ValueError(
                f"{csv_file} has an old or incompatible CSV header. "
                "Back up the file before starting a new-schema collection."
            )

    with open(csv_file, "a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if not file_exists:
            writer.writeheader()

        writer.writerows(rows)


def collect_metrics(
    net,
    duration=30,
    mode="baseline",
    fault_type="",
):
    if mode not in ("baseline", "experiment"):
        raise ValueError(
            "mode must be 'baseline' or 'experiment'"
        )

    csv_file = (
        PROJECT_ROOT / "data" / "baseline.csv"
        if mode == "baseline"
        else PROJECT_ROOT / "data" / "experiments.csv"
    )

    experiment_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:6]
    )

    print(f"Starting {mode} telemetry collection.")
    print(f"Output: {csv_file}")
    print(f"Experiment ID: {experiment_id}")

    previous_cpu = None
    deadline = time.monotonic() + duration

    try:
        while time.monotonic() < deadline:
            cycle_start = time.monotonic()

            rows = collect_path_metrics(
                net, experiment_id, mode, fault_type
            )

            rows.extend(
                collect_host_interface_metrics(
                    net, experiment_id, mode, fault_type
                )
            )

            rows.extend(
                collect_switch_port_metrics(
                    net, experiment_id, mode, fault_type
                )
            )

            system_rows, previous_cpu = collect_system_metrics(
                net,
                previous_cpu,
                experiment_id,
                mode,
                fault_type,
            )
            rows.extend(system_rows)

            append_measurements(csv_file, rows)

            print(
                f"Saved {len(rows)} metric rows; "
                f"elapsed={time.monotonic() - cycle_start:.1f}s",
                flush=True,
            )

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(INTERVAL, remaining))

    except KeyboardInterrupt:
        print("\nTelemetry collection interrupted.")

    print("Telemetry collection finished.")
