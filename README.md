# netwatch-rca
An intelligent network fault diagnosis system that uses real-time telemetry, anomaly detection, and probabilistic reasoning to identify network faults and rank their likely root causes.

# Features
1. Network Telemetry Collection: Monitor network performance metrics such as latency, packet loss, throughput, and interface statistics.
2. Automated Anomaly Detection: Identify abnormal network behavior using threshold-based rules and machine learning.
3. Fault Classification: Categorize network faults based on observed telemetry patterns.
4. Probabilistic Root Cause Analysis: Use a Bayesian Network to estimate the most likely causes of detected network anomalies.
5. Fault Injection and Validation: Simulate network failures and congestion in Mininet to evaluate diagnostic accuracy.
6. Visualized Diagnostics: Display network metrics, detected anomalies, and ranked root causes through a dashboard.

# Tech Stack
1. Ubuntu Linux — Project execution environment.
2. Mininet + Open vSwitch — Simulate network topologies and traffic.
3. Python — Implement telemetry processing, anomaly detection, and diagnosis logic.
4. iproute2 + ping + tcpdump — Collect network metrics and inspect traffic and packet loss.
5. scikit-learn — Build and evaluate an anomaly detection or fault classification model.
6. pgmpy — Implement Bayesian Networks for probabilistic root-cause analysis.
7. Flask + HTML/CSS/JavaScript — Build a lightweight dashboard to visualize telemetry, detected faults, and likely root causes.
8. Pandas + Matplotlib — Process telemetry data and plot performance trends.

