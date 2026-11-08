import re
from datetime import datetime


def collect_ping(source, target, count=5):
    timestamp = datetime.now().isoformat(timespec="seconds")

    output = source.cmd(
        f"ping -n -c {count} -W 1 {target.IP()}"
    )

    # Extract RTT samples from successful replies.
    rtt_samples = [
        float(value)
        for value in re.findall(r"time[=<]([\d.]+)\s*ms", output)
    ]

    # Extract packet loss reported by ping.
    loss_match = re.search(
        r"([\d.]+)% packet loss",
        output
    )

    packet_loss = (
        float(loss_match.group(1))
        if loss_match
        else 100.0
    )

    # Average RTT from successful replies.
    avg_rtt = (
        sum(rtt_samples) / len(rtt_samples)
        if rtt_samples
        else None
    )

    # Mean absolute difference between successive RTT samples.
    jitter = (
        sum(
            abs(rtt_samples[i] - rtt_samples[i - 1])
            for i in range(1, len(rtt_samples))
        ) / (len(rtt_samples) - 1)
        if len(rtt_samples) > 1
        else None
    )

    return {
        "timestamp": timestamp,
        "source": source.name,
        "target": target.name,
        "rtt_ms": round(avg_rtt, 4) if avg_rtt is not None else None,
        "packet_loss_percent": packet_loss,
        "jitter_ms": round(jitter, 4) if jitter is not None else None,
        "path_reachable": int(len(rtt_samples) > 0),
        }
