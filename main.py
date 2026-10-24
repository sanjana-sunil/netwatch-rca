from mininet.cli import CLI
from mininet.log import setLogLevel
from topology.network_topology import create_topology
from telemetry.collect_ping import collect_metrics

def main():
    net = create_topology()
    try:
        for switch in ["Switch1", "Switch2"]:
            net.get(switch).cmd(
                    f"ovs-vsctl set-fail-mode {switch} standalone"
            )
        collect_metrics(net, duration = 30)
        CLI(net)
    except KeyboardInterrupt:
        print("Telemetry collection has stopped\n")
    finally:
        net.stop()
        print("Mininet network stopped")

if __name__ == "__main__":
    setLogLevel("info")
    main()
