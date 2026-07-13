import json
import os
import re
import time
import uuid
from pathlib import Path

import requests


SERVICE_URL = os.environ["SERVICE_URL"].rstrip("/")
QUERY_URL = f"{SERVICE_URL}/query"

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_generated_sql(answer):
    match = re.search(
        r"```sql\s*(.*?)```",
        answer,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_field(answer, field_name):
    pattern = rf"{re.escape(field_name)}:\s*(.+)"

    match = re.search(
        pattern,
        answer,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def call_agent(question, eval_id, max_attempts=5):
    payload = {
        "question": question,
        "user_id": "evaluation_user",
        "session_id": f"{eval_id}-{uuid.uuid4()}",
    }

    retryable_status_codes = {
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(1, max_attempts + 1):
        start_time = time.perf_counter()

        response = requests.post(
            QUERY_URL,
            json=payload,
            timeout=180,
        )

        latency_seconds = (
            time.perf_counter() - start_time
        )

        if response.ok:
            return response.json(), latency_seconds

        print(
            f"{eval_id}: HTTP {response.status_code} "
            f"(attempt {attempt}/{max_attempts})"
        )

        if (
            response.status_code not in retryable_status_codes
            or attempt == max_attempts
        ):
            response.raise_for_status()

        time.sleep(10 * attempt)

    raise RuntimeError(
        f"{eval_id}: exhausted retries"
    )


def normalize_list(values):
    return {
        value.strip().lower()
        for value in values
    }


def evaluate_case(test_case):
    eval_id = test_case["id"]

    print(f"\nRunning {eval_id}: {test_case['question']}")

    response, latency_seconds = call_agent(
        question=test_case["question"],
        eval_id=eval_id,
    )

    answer = response["answer"]

    generated_sql = extract_generated_sql(answer)

    actual_metric = extract_field(
        answer,
        "Metric Used",
    )

    actual_dimensions = extract_field(
        answer,
        "Dimensions Used",
    )
    print(
        f"Expected dimensions: "
        f"{test_case['expected_dimensions']}"
        )

    print(
        f"Actual dimensions: "
        f"{actual_dimensions}"
    )

    actual_tables = extract_field(
        answer,
        "Tables Used",
    )

    expected_metric = test_case["expected_metric"]

    metric_match = (
        actual_metric is not None
        and actual_metric.strip().lower()
        == expected_metric.strip().lower()
    )

    expected_dimensions = normalize_list(
        test_case["expected_dimensions"]
    )

    returned_dimensions = normalize_list(
        actual_dimensions.split(",")
        if actual_dimensions
        else []
    )

    dimension_match = (
        expected_dimensions == returned_dimensions
    )

    expected_tables = normalize_list(
        test_case["expected_tables"]
    )

    returned_tables = normalize_list(
        actual_tables.split(",")
        if actual_tables
        else []
    )

    table_match = (
        expected_tables == returned_tables
    )

    sql_generated = generated_sql is not None

    passed = all(
        [
            metric_match,
            dimension_match,
            table_match,
            sql_generated,
        ]
    )

    result = {
        "id": eval_id,
        "question": test_case["question"],
        "metric_match": metric_match,
        "dimension_match": dimension_match,
        "table_match": table_match,
        "sql_generated": sql_generated,
        "latency_seconds": round(
            latency_seconds,
            3,
        ),
        "cache_status": response["cache_status"],
        "passed": passed,
    }

    print(json.dumps(result, indent=2))

    return result


def main():
    dataset = load_dataset()

    results = []

    for test_case in dataset:
        try:
            result = evaluate_case(test_case)

        except Exception as exc:
            result = {
                "id": test_case["id"],
                "question": test_case["question"],
                "metric_match": False,
                "dimension_match": False,
                "table_match": False,
                "sql_generated": False,
                "latency_seconds": None,
                "cache_status": None,
                "passed": False,
                "error": str(exc),
            }

            print(json.dumps(result, indent=2))

        results.append(result)

    passed_count = sum(
        result["passed"]
        for result in results
    )

    total_count = len(results)

    pass_rate = (
        passed_count / total_count
        if total_count
        else 0
    )

    summary = {
        "total_cases": total_count,
        "passed_cases": passed_count,
        "failed_cases": total_count - passed_count,
        "pass_rate": round(pass_rate, 4),
    }

    print("\nEvaluation Summary")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()