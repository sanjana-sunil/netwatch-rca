
import json
import subprocess
import time

from topology.network_topology import create_topology
from mininet.log import setLogLevel


def test_iperf(net, source_name, destination_name, port):

    hosts = {host.name: host for host in net.hosts}

    source = hosts[source_name]
    destination = hosts[destination_name]

    print(f"\nTesting {source_name} -> {destination_name}")

    server = None
    client = None

    try:
        # Start iperf3 server.
        server = destination.popen(
            ["iperf3", "-s", "-1", "-p", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        time.sleep(1)

        # Verify that server did not exit immediately.
        if server.poll() is not None:
            out, err = server.communicate()
            print("SERVER FAILED")
            print("Server stdout:", out)
            print("Server stderr:", err)
            return

        # Run client.
        client = source.popen(
            [
                "iperf3",
                "-c", destination.IP(),
                "-p", str(port),
                "-t", "10",
                "-J"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output, error = client.communicate(timeout=20)

        print("Client return code:", client.returncode)

        if client.returncode != 0:
            print("CLIENT ERROR:", error)
            return

        result = json.loads(output)

        if result.get("error"):
            print("IPERF ERROR:", result["error"])
            return

        received = result["end"]["sum_received"]["bits_per_second"]
        sent = result["end"]["sum_sent"]["bits_per_second"]

        print(f"Sender throughput:   {sent / 1_000_000:.3f} Mbps")
        print(f"Receiver throughput: {received / 1_000_000:.3f} Mbps")

    except Exception as error:
        print("TEST FAILED:", error)

    finally:
        if client is not None and client.poll() is None:
            client.kill()
            client.wait()

        if server is not None and server.poll() is None:
            server.kill()
            server.wait()


def main():

    setLogLevel("warning")

    net = create_topology()

    try:
        # Match the switch configuration used in your main project.
        for switch in ("Switch1", "Switch2"):
            net.get(switch).cmd(
                f"ovs-vsctl set-fail-mode {switch} standalone"
            )

        print("\nChecking iperf3 installation:")

        for host in net.hosts:
            print(host.name, host.cmd("which iperf3").strip())

        test_iperf(net, "Host1", "Host2", 5210)
        test_iperf(net, "Host3", "Host4", 5211)
        test_iperf(net, "Host1", "Host3", 5212)

    finally:
        net.stop()


if __name__ == "__main__":
    main()

