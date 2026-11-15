import csv
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_LOG = PROJECT_ROOT / "logs" / "experiment_log.csv"
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
    start_time,
    end_time,
    status,
    description,
):
    """Append one experiment record to experiment_log.csv."""

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    duration_seconds = round((end - start).total_seconds(), 2)

    with open(EXPERIMENT_LOG, "a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            experiment_id,
            fault_type,
            target,
            start_time,
            end_time,
            duration_seconds,
            status,
            description,
        ])

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
