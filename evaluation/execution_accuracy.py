import json
import math
import re
import time
import uuid
from pathlib import Path

import requests
from google.cloud import bigquery


SERVICE_URL = "https://text-to-sql-agent-oyrokfuoiq-uc.a.run.app"
QUERY_URL = f"{SERVICE_URL}/query"

PROJECT_ID = "test-to-sql-502205"

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"

bq_client = bigquery.Client(project=PROJECT_ID)


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_generated_sql(answer):
    match = re.search(
        r"```sql\s*(.*?)```",
        answer,
        re.DOTALL | re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1).strip()


def call_agent(question, eval_id, max_attempts=5):
    payload = {
        "question": question,
        "user_id": "execution_accuracy_user",
        "session_id": f"execution-{eval_id}-{uuid.uuid4()}",
    }

    retryable_status_codes = {
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(1, max_attempts + 1):
        print(
            f"{eval_id}: calling deployed agent "
            f"(attempt {attempt}/{max_attempts})"
        )

        response = requests.post(
            QUERY_URL,
            json=payload,
            timeout=180,
        )

        if response.ok:
            return response.json()

        print(
            f"{eval_id}: HTTP {response.status_code}"
        )

        if (
            response.status_code not in retryable_status_codes
            or attempt == max_attempts
        ):
            response.raise_for_status()

        wait_seconds = 10 * attempt

        print(
            f"{eval_id}: retrying in "
            f"{wait_seconds} seconds..."
        )

        time.sleep(wait_seconds)

    raise RuntimeError(
        f"{eval_id}: exhausted retries"
    )


def execute_query(sql):
    query_job = bq_client.query(sql)

    rows = query_job.result()

    return [
        tuple(row.values())
        for row in rows
    ]


def values_equal(left, right):
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(
            left,
            right,
            rel_tol=1e-6,
            abs_tol=1e-6,
        )

    return left == right


def rows_equal(generated_rows, reference_rows):
    if len(generated_rows) != len(reference_rows):
        return False

    for generated_row, reference_row in zip(
        generated_rows,
        reference_rows,
    ):
        if len(generated_row) != len(reference_row):
            return False

        for generated_value, reference_value in zip(
            generated_row,
            reference_row,
        ):
            if not values_equal(
                generated_value,
                reference_value,
            ):
                return False

    return True


def evaluate_case(test_case):
    eval_id = test_case["id"]

    print(
        f"\nRunning {eval_id}: "
        f"{test_case['question']}"
    )

    agent_response = call_agent(
        question=test_case["question"],
        eval_id=eval_id,
    )

    generated_sql = extract_generated_sql(
        agent_response["answer"]
    )

    if generated_sql is None:
        return {
            "id": eval_id,
            "sql_generated": False,
            "generated_sql_executed": False,
            "reference_sql_executed": False,
            "execution_accuracy": False,
            "error": "Generated SQL not found.",
        }

    reference_sql = test_case["reference_sql"]

    try:
        generated_rows = execute_query(generated_sql)

    except Exception as exc:
        return {
            "id": eval_id,
            "sql_generated": True,
            "generated_sql_executed": False,
            "reference_sql_executed": False,
            "execution_accuracy": False,
            "error": f"Generated SQL failed: {exc}",
        }

    try:
        reference_rows = execute_query(reference_sql)

    except Exception as exc:
        return {
            "id": eval_id,
            "sql_generated": True,
            "generated_sql_executed": True,
            "reference_sql_executed": False,
            "execution_accuracy": False,
            "error": f"Reference SQL failed: {exc}",
        }

    execution_accuracy = rows_equal(
        generated_rows,
        reference_rows,
    )

    return {
        "id": eval_id,
        "sql_generated": True,
        "generated_sql_executed": True,
        "reference_sql_executed": True,
        "execution_accuracy": execution_accuracy,
        "generated_rows": generated_rows,
        "reference_rows": reference_rows,
    }


def main():
    dataset = load_dataset()

    results = []

    for test_case in dataset:
        try:
            result = evaluate_case(test_case)

        except Exception as exc:
            result = {
                "id": test_case["id"],
                "sql_generated": False,
                "generated_sql_executed": False,
                "reference_sql_executed": False,
                "execution_accuracy": False,
                "error": str(exc),
            }

        results.append(result)

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

    total_cases = len(results)

    correct_cases = sum(
        result["execution_accuracy"]
        for result in results
    )

    execution_accuracy_rate = (
        correct_cases / total_cases
        if total_cases
        else 0
    )

    summary = {
        "total_cases": total_cases,
        "correct_cases": correct_cases,
        "incorrect_cases": total_cases - correct_cases,
        "execution_accuracy": round(
            execution_accuracy_rate,
            4,
        ),
    }

    print("\nEXECUTION ACCURACY SUMMARY")

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()