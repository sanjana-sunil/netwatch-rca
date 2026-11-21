
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "scripts")

import evaluate_threshold_methods as evaluator


def diagnose_method(method, training, testing):
    thresholds = evaluator.build_thresholds(training, method)

    print("\n" + "=" * 75)
    print(f"METHOD: {method}")
    print("=" * 75)

    for (condition, experiment_id), rows in sorted(testing.items()):
        violations = []
        status_violations = []

        for row in rows:
            metric = row.get("metric_name", "").strip()
            raw_value = row.get("metric_value", "").strip()

            if not raw_value:
                continue

            if metric in evaluator.STATUS_METRICS:
                if evaluator.is_down(raw_value):
                    status_violations.append(
                        (metric, row.get("entity_name", ""),
                         raw_value)
                    )
                continue

            if metric not in evaluator.METRIC_DIRECTIONS:
                continue

            try:
                value = float(raw_value)
            except ValueError:
                continue

            if not evaluator.math.isfinite(value):
                continue

            key = (
                condition,
                row.get("entity_type", ""),
                row.get("entity_name", ""),
                metric,
                row.get("unit", ""),
            )

            threshold = thresholds.get(key)

            if threshold is not None and value > threshold:
                violations.append(
                    (metric, row.get("entity_name", ""),
                     value, threshold)
                )

        metric_counts = Counter(
            item[0] for item in violations
        )

        print(f"\nCondition: {condition}")
        print(f"Session: {experiment_id}")
        print(f"Numeric violations: {len(violations)}")
        print(f"Violations by metric: {dict(metric_counts)}")
        print(f"Status violations: {len(status_violations)}")

        for metric, entity, value, threshold in violations[:10]:
            print(
                f"  NUMERIC: {metric:18} "
                f"{entity:18} "
                f"value={value:.4f}, threshold={threshold:.4f}"
            )

        for metric, entity, value in status_violations[:10]:
            print(
                f"  STATUS:  {metric:18} "
                f"{entity:18} value={value}"
            )

        if not violations and not status_violations:
            print("  No anomaly trigger found.")


def main():
    healthy = evaluator.load_healthy_data()
    training, testing = evaluator.split_healthy_sessions(healthy)

    print(f"Training sessions: {len(training)}")
    print(f"Testing sessions: {len(testing)}")

    for method in evaluator.METHODS:
        diagnose_method(method, training, testing)


if __name__ == "__main__":
    main()

