import csv
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_LOG = PROJECT_ROOT / "logs" / "experiments_log.csv"
LEGACY_EXPERIMENT_LOG = PROJECT_ROOT / "logs" / "experiment_log.csv"
NORMAL_BANDWIDTH = "50mbit"
LIMITED_BANDWIDTH = "5mbit"
# Inter-switch interfaces
INTER_SWITCH_INTERFACES = [
    "Switch1-eth3",
    "Switch2-eth1",
]

LATENCY = "100ms"
JITTER = "10ms"
PACKET_LOSS = "10%"

def inject_inter_switch_link_failure(net):
    """
    Disable the link connecting Switch1 and Switch2.
    """
    print("\nInjecting fault: Inter-switch link failure")

    net.configLinkStatus("Switch1", "Switch2", "down")

    print("Inter-switch link is DOWN.")


def restore_inter_switch_link(net):
    """
    Restore the link connecting Switch1 and Switch2.
    """
    print("\nRestoring inter-switch link")

    net.configLinkStatus("Switch1", "Switch2", "up")

    print("Inter-switch link is UP.")


def inject_high_latency(net):
    """
    Add 100 ms delay and 10 ms jitter to both ends
    of the inter-switch link.

    Preserve the existing HTB bandwidth configuration.
    """

    print("\nInjecting fault: High latency")

    applied_interfaces = []

    try:
        for interface in INTER_SWITCH_INTERFACES:

            command = [
                "tc", "qdisc", "add",
                "dev", interface,
                "parent", "5:1",
                "handle", "10:",
                "netem",
                "delay", LATENCY, JITTER,
            ]

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )

            applied_interfaces.append(interface)

            print(f"Added delay to {interface}")

    except subprocess.CalledProcessError as error:

        # Roll back any interface already configured.
        for interface in applied_interfaces:
            subprocess.run(
                [
                    "tc", "qdisc", "del",
                    "dev", interface,
                    "parent", "5:1",
                ],
                capture_output=True,
                text=True,
            )

        raise RuntimeError(
            f"Could not inject high latency: {error.stderr}"
        ) from error

    print("High latency fault successfully injected.")


def restore_high_latency(net):
    """
    Remove netem qdiscs while preserving HTB bandwidth shaping.
    """

    print("\nRestoring normal latency")

    for interface in INTER_SWITCH_INTERFACES:

        subprocess.run(
            [
                "tc", "qdisc", "del",
                "dev", interface,
                "parent", "5:1",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        print(f"Removed added delay from {interface}")

    print("High latency fault successfully restored.")

def inject_packet_loss(net):
    print("\nInjecting fault: Packet loss")

    applied_interfaces = []

    try:
        for interface in INTER_SWITCH_INTERFACES:
            command = [
                "tc", "qdisc", "add",
                "dev", interface,
                "parent", "5:1",
                "handle", "20:",
                "netem", "loss", PACKET_LOSS
            ]

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )

            applied_interfaces.append(interface)
            print(f"Added 10% packet loss to {interface}")

    except subprocess.CalledProcessError as error:
        # Remove any qdisc already applied.
        for interface in applied_interfaces:
            subprocess.run(
                [
                    "tc", "qdisc", "del",
                    "dev", interface,
                    "parent", "5:1"
                ],
                capture_output=True,
                text=True
            )

        raise RuntimeError(
            f"Could not inject packet loss: {error.stderr}"
        ) from error

    print("Packet-loss fault successfully injected.")

def restore_packet_loss(net):
    print("\nRestoring normal packet transmission")

    for interface in INTER_SWITCH_INTERFACES:
        subprocess.run(
            [
                "tc", "qdisc", "del",
                "dev", interface,
                "parent", "5:1"
            ],
            check=True,
            capture_output=True,
            text=True
        )

        print(f"Removed packet loss from {interface}")

    print("Packet-loss fault successfully restored.")

def log_experiment(
    experiment_id,
    fault_type,
    target,
    traffic_condition,
    start_time,
    end_time,
    status,
    description,
):
    """Append an experiment record, including its traffic condition."""

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not EXPERIMENT_LOG.exists() and LEGACY_EXPERIMENT_LOG.exists():
        LEGACY_EXPERIMENT_LOG.replace(EXPERIMENT_LOG)

    file_exists = EXPERIMENT_LOG.exists() and EXPERIMENT_LOG.stat().st_size > 0

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)
    duration_seconds = round((end - start).total_seconds(), 2)

    fields = [
        "experiment_id",
        "fault_type",
        "target",
        "traffic_condition",
        "start_time",
        "end_time",
        "duration_seconds",
        "status",
        "description",
    ]

    if file_exists:
        with EXPERIMENT_LOG.open("r", newline="") as file:
            existing_reader = csv.reader(file)
            existing_header = next(existing_reader, [])
            existing_rows = list(existing_reader)

        old_fields = [
            "experiment_id", "fault_type", "target", "start_time",
            "end_time", "duration_seconds", "status", "description",
        ]
        if existing_header == old_fields:
            legacy_rows = existing_rows
        elif existing_header == fields:
            legacy_rows = None
        else:
            # The previous logger used csv.writer without writing a header.
            legacy_rows = [existing_header] + existing_rows

        if legacy_rows is not None:
            migrated_rows = []
            for old_row in legacy_rows:
                if len(old_row) == len(old_fields):
                    old = dict(zip(old_fields, old_row))
                    migrated_rows.append({
                        "experiment_id": old["experiment_id"],
                        "fault_type": old["fault_type"],
                        "target": old["target"],
                        "traffic_condition": "idle",
                        "start_time": old["start_time"],
                        "end_time": old["end_time"],
                        "duration_seconds": old["duration_seconds"],
                        "status": old["status"],
                        "description": old["description"],
                    })
            temp_file = EXPERIMENT_LOG.with_suffix(".csv.tmp")
            with temp_file.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(migrated_rows)
            temp_file.replace(EXPERIMENT_LOG)
        elif existing_header != fields:
            raise ValueError(
                f"{EXPERIMENT_LOG} has an unexpected header. Back it up "
                "before writing new experiment records."
            )

    with EXPERIMENT_LOG.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "experiment_id": experiment_id,
            "fault_type": fault_type,
            "target": target,
            "traffic_condition": traffic_condition,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "status": status,
            "description": description,
        })

    print(f"Experiment details saved to {EXPERIMENT_LOG}")

def inject_bandwidth_limitation(net):
    print("\nInjecting fault: Bandwidth limitation")

    modified_interfaces = []

    try:
        for interface in INTER_SWITCH_INTERFACES:
            command = [
                "tc", "class", "change",
                "dev", interface,
                "classid", "5:1",
                "htb",
                "rate", LIMITED_BANDWIDTH,
                "ceil", LIMITED_BANDWIDTH
            ]

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )

            modified_interfaces.append(interface)
            print(
                f"Bandwidth reduced to 5 Mbps on {interface}"
            )

    except subprocess.CalledProcessError as error:
        # Restore any interface already modified.
        for interface in modified_interfaces:
            subprocess.run(
                [
                    "tc", "class", "change",
                    "dev", interface,
                    "classid", "5:1",
                    "htb",
                    "rate", NORMAL_BANDWIDTH,
                    "ceil", NORMAL_BANDWIDTH
                ],
                capture_output=True,
                text=True
            )

        raise RuntimeError(
            f"Could not inject bandwidth limitation: {error.stderr}"
        ) from error

    print("Bandwidth limitation successfully injected.")

def restore_bandwidth_limitation(net):
    print("\nRestoring normal bandwidth")

    for interface in INTER_SWITCH_INTERFACES:
        command = [
            "tc", "class", "change",
            "dev", interface,
            "classid", "5:1",
            "htb",
            "rate", NORMAL_BANDWIDTH,
            "ceil", NORMAL_BANDWIDTH
        ]

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        print(f"Restored 50 Mbps on {interface}")

    print("Normal bandwidth successfully restored.")

