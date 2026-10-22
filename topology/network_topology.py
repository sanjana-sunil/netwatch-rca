
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
def create_topology():
    net = Mininet(controller=None, switch = OVSSwitch)
    info("***adding switches***\n")
    s1 = net.addSwitch("Switch1")
    s2 = net.addSwitch("Switch2")
    info("***adding hosts***\n")
    h1 = net.addHost("Host1", ip = "10.0.0.1/24")
    h2 = net.addHost("Host2", ip = "10.0.0.2/24")
    h3 = net.addHost("Host3", ip = "10.0.0.3/24")
    h4 = net.addHost("Host4", ip = "10.0.0.4/24")
    info("***creating links***\n")
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(s1, s2)
    net.addLink(h3, s2)
    net.addLink(h4, s2)
    info("***starting network***\n")
    net.start()
    info("***testing connectivity***\n")
    net.pingAll()
    info("***Entering Mininet CLI***\n")
    CLI(net)
    info("***stopping the network***\n")
    net.stop()
if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
