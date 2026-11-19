import subprocess
import time

TRAFFIC_PAIRS = [
    ("Host1", "Host2", 5202),
    ("Host3", "Host4", 5203),
    ("Host1", "Host3", 5204),
]

UDP_BITRATE = "5M"


def start_background_traffic(net, traffic_condition, duration):
    """Start parallel TCP or UDP iperf3 flows; idle starts no processes."""

    if traffic_condition not in ("idle", "tcp", "udp"):
        raise ValueError("traffic_condition must be idle, tcp or udp")

    if traffic_condition == "idle":
        print("Idle condition selected: no background traffic started.")
        return [], []

    servers = []
    clients = []
    hosts = {host.name: host for host in net.hosts}

    try:
        for _, destination_name, port in TRAFFIC_PAIRS:
            server = hosts[destination_name].popen(
                ["iperf3", "-s", "-p", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            servers.append(server)

        time.sleep(2)

        for source_name, destination_name, port in TRAFFIC_PAIRS:
            command = [
                "iperf3",
                "-c", hosts[destination_name].IP(),
                "-p", str(port),
                "-t", str(duration + 30),
                "-i", "1",
            ]

            if traffic_condition == "udp":
                command.extend(["-u", "-b", UDP_BITRATE])

            client = hosts[source_name].popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            clients.append(client)

        time.sleep(2)
        print(f"{traffic_condition.upper()} background traffic started.")
        return servers, clients

    except Exception:
        stop_background_traffic(servers, clients)
        raise


def stop_background_traffic(servers, clients):
    for process in clients + servers:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print("Background traffic stopped.")

