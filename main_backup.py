from mininet.cli import CLI
from datetime import datetime
import uuid

from mininet.log import setLogLevel

from topology.network_topology import create_topology
from telemetry.collect_metrics import collect_metrics

from scripts.inject_faults import (
    inject_inter_switch_link_failure,
    restore_inter_switch_link,
    log_experiment,
)


def main():

    net = create_topology()

    fault_type = "interswitch-link-failure"
    target = "Switch1-Switch2"

    experiment_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:6]
    )

    fault_injected = False
    status = "failed"

    start_time = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    try:

        # Configure OVS switches.
        for switch in ["Switch1", "Switch2"]:
            net.get(switch).cmd(
                f"ovs-vsctl set-fail-mode {switch} standalone"
            )

        # Inject high latency.
        inject_inter_switch_link_failure(net)
        fault_injected = True

        # Collect telemetry while the fault is active.
        _, status = collect_metrics(
            net,
            duration=180,
            mode="experiment",
            fault_type=fault_type,
            experiment_id=experiment_id,
        )

    except KeyboardInterrupt:
        status = "interrupted"
        print("\nExperiment interrupted.")

    except Exception as error:
        status = "failed"
        print(f"\nExperiment failed: {error}")

    finally:

        try:
            if fault_injected:
                restore_inter_switch_link(net)

        except Exception as error:
            status = "failed"
            print(f"\nFailed to packet loss: {error}")

        finally:

            end_time = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )

            try:
                log_experiment(
                    experiment_id=experiment_id,
                    fault_type=fault_type,
                    target=target,
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    description=(
                        "bandwidth reduced from 50Mbps to 5mbps"
                        "on both inter-switch interfaces"
                    ),
                )

            finally:
                CLI(net)
                net.stop()
                print("\nMininet network stopped.")


if __name__ == "__main__":
    setLogLevel("info")
    main()

