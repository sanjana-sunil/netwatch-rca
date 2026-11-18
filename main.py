
import subprocess
import time
from pathlib import Path

from topology.network_topology import create_topology
from telemetry.collect_metrics import collect_metrics


DURATION = 180

UDP_BITRATE = "5M"

TRAFFIC_PAIRS = [
    ("Host1", "Host2", 5202),
    ("Host3", "Host4", 5203),
    ("Host1", "Host3", 5204),
]


def start_background_traffic(net):

    servers = []
    clients = []

    hosts = {
        host.name: host
        for host in net.hosts
    }

    try:
        # Start iperf3 servers on destination hosts.
        for source_name, destination_name, port in TRAFFIC_PAIRS:

            destination = hosts[destination_name]

            server = destination.popen(
                ["iperf3", "-s", "-p", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            servers.append(server)

        # Allow servers to initialize.
        time.sleep(2)

        # Start all traffic flows concurrently.
        for source_name, destination_name, port in TRAFFIC_PAIRS:

            source = hosts[source_name]
            destination = hosts[destination_name]

            client = source.popen(
                [
                    "iperf3",
                    "-c", destination.IP(),
                    "-p", str(port),
                    "-u",
                    "-b", UDP_BITRATE,
                    "-t", str(DURATION + 30),
                    "-i", "1",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            clients.append(client)

        print("\nBackground traffic started successfully.")

        return servers, clients

    except Exception:
        stop_background_traffic(servers, clients)
        raise


def stop_background_traffic(servers, clients):

    print("\nStopping background traffic...")

    for process in clients + servers:

        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    print("Background traffic stopped.")


def main():

    net = None
    servers = []
    clients = []

    try:

        print("\n===================================")
        print("       NETWATCH-RCA LOADED BASELINE")
        print("===================================\n")

        # Create and start Mininet topology.
        net = create_topology()

        # Configure switches.
        for switch in net.switches:
            switch.cmd(
                f"ovs-vsctl set-fail-mode {switch.name} standalone"
            )

        print("\nTopology started successfully.")

        # Start concurrent background traffic.
        servers, clients = start_background_traffic(net)

        print("\nCollecting loaded baseline metrics...")
        print(f"Duration: {DURATION} seconds")
        print("Output: data/loaded_baseline.csv\n")

        # Collect telemetry while traffic is running.
        experiment_id, status = collect_metrics(
            net,
            duration=DURATION,
            mode="udp_baseline",
            fault_type=""
        )

        print("\n===================================")
        print("       COLLECTION SUMMARY")
        print("===================================")
        print(f"Experiment ID: {experiment_id}")
        print(f"Status: {status}")
        print("Output: data/loaded_baseline.csv")
        print("===================================\n")

    except KeyboardInterrupt:
        print("\nLoaded baseline collection interrupted.")

    except Exception as error:
        print(f"\nError during collection: {error}")
        raise

    finally:

        # Stop traffic before shutting down Mininet.
        stop_background_traffic(servers, clients)

        if net is not None:
            print("\nStopping Mininet topology...")
            net.stop()
            print("Mininet stopped successfully.")


if __name__ == "__main__":
    main()

