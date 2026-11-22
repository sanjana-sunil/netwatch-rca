
import pandas as pd
import numpy as np

from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix

from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.inference import VariableElimination
from pgmpy.parameter_estimator import DiscreteMLE

# Configuration
DATASET = "data/bn_dataset.csv"

FEATURES = [
    "high_rtt",
    "high_jitter",
    "high_packet_loss",
    "path_unreachable",
    "inter_switch_link_down",
]

TARGET = "fault_type"


def main():

    # Load dataset
    df = pd.read_csv(DATASET)

    columns = FEATURES + [TARGET]
    df = df[columns].copy()

    # Treat symptom values as categorical states
    for feature in FEATURES:
        df[feature] = df[feature].astype(str).str.strip().str.lower()

    df[TARGET] = df[TARGET].astype(str).str.strip()

    print("Dataset loaded:", len(df), "sessions")

    # Five-fold stratified cross-validation
    skf = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42
    )

    labels = sorted(df[TARGET].unique())

    actual = []
    predicted = []
    abstentions = []

    print("\nStarting 5-fold cross-validation...")

    for fold, (train_idx, test_idx) in enumerate(
        skf.split(df[FEATURES], df[TARGET]), start=1
    ):

        train_data = df.iloc[train_idx].copy()
        test_data = df.iloc[test_idx].copy()

        # Define and train the Bayesian Network
        edges = [(TARGET, feature) for feature in FEATURES]
        model = DiscreteBayesianNetwork(edges)

        model.fit(
            train_data,
            estimator=DiscreteMLE()
        )

        inference = VariableElimination(model)

        fold_diagnosed = 0
        fold_abstentions = 0

        for _, row in test_data.iterrows():

            evidence = {
                feature: row[feature]
                for feature in FEATURES
                if row[feature] != "unknown"
            }

            if not evidence:
                abstentions.append(row[TARGET])
                fold_abstentions += 1
                continue

            result = inference.query(
                variables=[TARGET],
                evidence=evidence,
                show_progress=False
            )

            states = result.state_names[TARGET]
            prediction = states[np.argmax(result.values)]

            actual.append(row[TARGET])
            predicted.append(prediction)
            fold_diagnosed += 1

        print(
            f"Fold {fold}: "
            f"test={len(test_data)}, "
            f"diagnosed={fold_diagnosed}, "
            f"abstentions={fold_abstentions}"
        )

    # Combined evaluation across all five folds
    total = len(df)
    diagnosed = len(predicted)
    coverage = diagnosed / total if total else 0

    print("\n========== 5-FOLD CROSS-VALIDATION RESULTS ==========")
    print("Total sessions:", total)
    print("Diagnosed sessions:", diagnosed)
    print("Insufficient-evidence sessions:", len(abstentions))
    print(f"Diagnosis coverage: {coverage:.2%}")

    if diagnosed:
        print("\nConfusion Matrix:")
        print(confusion_matrix(actual, predicted, labels=labels))

        print("\nClassification Report:")
        print(
            classification_report(
                actual,
                predicted,
                labels=labels,
                zero_division=0
            )
        )

    if abstentions:
        print("\nAbstentions by actual fault type:")
        print(pd.Series(abstentions).value_counts().to_string())

if __name__ == "__main__":
    main()
