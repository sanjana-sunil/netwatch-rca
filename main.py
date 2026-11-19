import argparse
import time
import uuid
from datetime import datetime

from topology.network_topology import create_topology
from telemetry.collect_metrics import collect_metrics
from scripts.generate_traffic import (
    start_background_traffic,
    stop_background_traffic,
)
from scripts.inject_faults import (
    inject_inter_switch_link_failure,
    restore_inter_switch_link,
    inject_high_latency,
    restore_high_latency,
    inject_packet_loss,
    restore_packet_loss,
    inject_bandwidth_limitation,
    restore_bandwidth_limitation,
    log_experiment,
)

TRAFFIC_CONDITIONS = ("idle", "tcp", "udp")

FAULTS = {
    "inter_switch_link_failure": (
        inject_inter_switch_link_failure,
        restore_inter_switch_link,
        "Switch1-Switch2",
        "Disable the inter-switch link",
    ),
    "high_latency": (
        inject_high_latency,
        restore_high_latency,
        "Switch1-eth3 and Switch2-eth1",
        "100 ms delay with 10 ms jitter",
    ),
    "packet_loss": (
        inject_packet_loss,
        restore_packet_loss,
        "Switch1-eth3 and Switch2-eth1",
        "10 percent packet loss",
    ),
    "bandwidth_limitation": (
        inject_bandwidth_limitation,
        restore_bandwidth_limitation,
        "Switch1-eth3 and Switch2-eth1",
        "Reduce inter-switch bandwidth from 50 Mbps to 5 Mbps",
    ),
}

BASELINE_MODES = {
    "idle": "baseline",
    "tcp": "loaded_baseline",
    "udp": "udp_baseline",
}


def make_experiment_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def configure_switches(net):
    for switch in net.switches:
        switch.cmd(
            f"ovs-vsctl set-fail-mode {switch.name} standalone"
        )


def run_baselines(net, duration, conditions=None):
    conditions = conditions or TRAFFIC_CONDITIONS

    for condition in conditions:
        servers, clients = start_background_traffic(net, condition, duration)
        try:
            print(f"\nCollecting {condition.upper()} healthy baseline...")
            experiment_id, status = collect_metrics(
                net,
                duration=duration,
                mode=BASELINE_MODES[condition],
                fault_type="",
                traffic_condition=condition,
            )
            print(
                f"Baseline complete: condition={condition}, "
                f"id={experiment_id}, status={status}"
            )
        finally:
            stop_background_traffic(servers, clients)
            time.sleep(2)


def run_one_fault_experiment(net, fault_type, condition, duration):
    inject, restore, target, description = FAULTS[fault_type]
    servers, clients = start_background_traffic(net, condition, duration)

    experiment_id = make_experiment_id()
    start_time = datetime.now().isoformat(timespec="seconds")
    status = "failed"
    injected = False
    error_message = ""

    try:
        print(
            f"\n=== Fault: {fault_type} | "
            f"Traffic: {condition.upper()} ==="
        )

        inject(net)
        injected = True

        returned_id, collection_status = collect_metrics(
            net,
            duration=duration,
            mode="experiment",
            fault_type=fault_type,
            experiment_id=experiment_id,
            traffic_condition=condition,
        )
        experiment_id = returned_id
        status = collection_status
        if collection_status == "interrupted":
            raise KeyboardInterrupt

    except KeyboardInterrupt:
        status = "interrupted"
        raise

    except Exception as error:
        error_message = str(error)
        status = "failed"
        print(f"Experiment failed: {error}")

    finally:
        if injected:
            try:
                restore(net)
            except Exception as restore_error:
                status = "restore_failed"
                error_message = (
                    f"{error_message}; restoration error: {restore_error}"
                    if error_message else str(restore_error)
                )
                print(f"WARNING: fault restoration failed: {restore_error}")

        stop_background_traffic(servers, clients)
        end_time = datetime.now().isoformat(timespec="seconds")

        log_experiment(
            experiment_id=experiment_id,
            fault_type=fault_type,
            target=target,
            traffic_condition=condition,
            start_time=start_time,
            end_time=end_time,
            status=status,
            description=(
                f"{description}; traffic_condition={condition}"
                + (f"; error={error_message}" if error_message else "")
            ),
        )

    time.sleep(2)


def run_fault_matrix(net, duration, selected_faults=None, selected_conditions=None):
    fault_types = selected_faults or list(FAULTS)
    conditions = selected_conditions or list(TRAFFIC_CONDITIONS)
    total = len(fault_types) * len(conditions)
    completed = 0

    for fault_type in fault_types:
        for condition in conditions:
            run_one_fault_experiment(
                net,
                fault_type,
                condition,
                duration,
            )
            completed += 1
            print(f"\nProgress: {completed}/{total} experiments finished.")


def main():
    parser = argparse.ArgumentParser(
        description="NetWatch-RCA baseline and fault experiment runner"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Collect healthy idle, TCP and UDP baselines instead of faults",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds for each collection (default: 60)",
    )
    parser.add_argument(
        "--fault",
        choices=tuple(FAULTS),
        action="append",
        help="Run only this fault type; may be supplied more than once",
    )
    parser.add_argument(
        "--condition",
        choices=TRAFFIC_CONDITIONS,
        action="append",
        help="Run only this traffic condition; may be supplied more than once",
    )
    args = parser.parse_args()

    if args.duration <= 0:
        parser.error("--duration must be greater than zero")

    net = None
    try:
        print("\n===================================")
        print("          NETWATCH-RCA")
        print("===================================\n")

        net = create_topology()
        configure_switches(net)
        print("Topology started successfully.")

        if args.baseline:
            run_baselines(net, args.duration, args.condition)
        else:
            run_fault_matrix(net, args.duration, args.fault, args.condition)

        print("\nAll requested runs have finished.")

    finally:
        if net is not None:
            print("\nStopping Mininet topology...")
            net.stop()
            print("Mininet stopped.")


if __name__ == "__main__":
    main()

