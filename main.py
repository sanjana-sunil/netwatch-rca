
from topology.network_topology import create_topology
from telemetry.collect_metrics import collect_metrics


def main():

    net = None

    try:
        print("\n===================================")
        print("       NETWATCH-RCA BASELINE")
        print("===================================\n")

        # Create and start the Mininet topology.
        net = create_topology()

        # Configure switches to operate in standalone mode.
        for switch in net.switches:
            switch.cmd(
                f"ovs-vsctl set-fail-mode {switch.name} standalone"
            )

        print("\nTopology started successfully.")
        print("Collecting healthy baseline metrics...")
        print("Duration: 180 seconds")
        print("Output: data/baseline.csv\n")

        # Collect baseline telemetry.
        experiment_id, status = collect_metrics(
            net,
            duration=180,
            mode="baseline",
            fault_type=""
        )

        print("\n===================================")
        print("       COLLECTION SUMMARY")
        print("===================================")
        print(f"Experiment ID: {experiment_id}")
        print(f"Status: {status}")
        print("Output: data/baseline.csv")
        print("===================================\n")

    except KeyboardInterrupt:
        print("\nBaseline collection interrupted by user.")

    except Exception as error:
        print(f"\nError during baseline collection: {error}")
        raise

    finally:
        if net is not None:
            print("\nStopping Mininet topology...")
            net.stop()
            print("Mininet stopped successfully.")


if __name__ == "__main__":
    main()

