
import pandas as pd
import numpy as np

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.inference import VariableElimination
from pgmpy.parameter_estimator import DiscreteMLE


# Configuration
DATASET = "data/bn_dataset.csv"
OUTPUT_FILE = "data/rca_results.csv"

FEATURES = [
    "high_rtt",
    "high_jitter",
    "high_packet_loss",
    "path_unreachable",
    "inter_switch_link_down",
]

TARGET = "fault_type"


def explain_root_cause(row):

    symptoms = {
        feature: str(row[feature]).strip().lower()
        for feature in FEATURES
    }

    evidence = []

    # Rule 1: Inter-switch link failure
    if symptoms["inter_switch_link_down"] == "yes":
        evidence.append(
            "Inter-switch port is reported down"
        )

    # Rule 2: Path connectivity failure
    if symptoms["path_unreachable"] == "yes":
        evidence.append(
            "Network path is unreachable"
        )

    # Rule 3: Packet loss
    if symptoms["high_packet_loss"] == "yes":
        evidence.append(
            "Packet loss exceeds the healthy baseline threshold"
        )

    # Rule 4: High latency
    if symptoms["high_rtt"] == "yes":
        evidence.append(
            "Average RTT exceeds the healthy baseline threshold"
        )

    # Rule 5: High jitter
    if symptoms["high_jitter"] == "yes":
        evidence.append(
            "Jitter exceeds the healthy baseline threshold"
        )

    # Determine rule-based root cause
    
    # Determine rule-based root cause
    if symptoms["inter_switch_link_down"] == "yes":
        root_cause = "inter_switch_link_failure"

    elif symptoms["high_packet_loss"] == "yes":
        root_cause = "packet_loss"

    elif symptoms["path_unreachable"] == "yes":
        root_cause = "connectivity_failure"

    elif (
        symptoms["high_rtt"] == "yes"
        or symptoms["high_jitter"] == "yes"
    ):
        root_cause = "high_latency"

    elif all(value == "no" for value in symptoms.values()):
        root_cause = "normal"

    else:
        root_cause = "insufficient_evidence"

    if not evidence:
        evidence.append("No abnormal symptoms confirmed")

    return root_cause, "; ".join(evidence)


def main():

    # Load dataset
    df = pd.read_csv(DATASET)

    for feature in FEATURES:
        df[feature] = (
            df[feature]
            .astype(str)
            .str.strip()
            .str.lower()
        )

    df[TARGET] = df[TARGET].astype(str).str.strip()

    print("Dataset loaded:", len(df), "sessions")

    # Train BN using the complete dataset for diagnosis
    edges = [(TARGET, feature) for feature in FEATURES]

    model = DiscreteBayesianNetwork(edges)
    model.fit(df[FEATURES + [TARGET]], estimator=DiscreteMLE())

    inference = VariableElimination(model)

    results = []

    print("\nRunning Bayesian Network and rule-based RCA...")

    for _, row in df.iterrows():

        evidence = {
            feature: row[feature]
            for feature in FEATURES
            if row[feature] != "unknown"
        }

        if evidence:

            prediction_result = inference.query(
                variables=[TARGET],
                evidence=evidence,
                show_progress=False
            )

            states = prediction_result.state_names[TARGET]
            probabilities = prediction_result.values

            best_index = np.argmax(probabilities)

            predicted_fault = states[best_index]
            confidence = float(probabilities[best_index])

        else:
            predicted_fault = "insufficient_evidence"
            confidence = 0.0

        root_cause, explanation = explain_root_cause(row)

        results.append({
            "experiment_id": row.get("experiment_id", ""),
            "actual_fault": row[TARGET],
            "predicted_fault": predicted_fault,
            "bn_confidence": round(confidence, 4),
            "rule_based_root_cause": root_cause,
            "supporting_evidence": explanation,
        })

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print("\n========== RCA RESULTS ==========")
    print("Sessions processed:", len(results_df))
    print("Results saved to:", OUTPUT_FILE)

    print("\nRoot cause distribution:")
    print(
        results_df["rule_based_root_cause"]
        .value_counts()
        .to_string()
    )

    print("\nSample diagnoses:")
    print(
        results_df[
            [
                "actual_fault",
                "predicted_fault",
                "bn_confidence",
                "rule_based_root_cause",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

