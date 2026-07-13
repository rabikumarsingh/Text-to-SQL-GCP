import json
import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests
import vertexai

from vertexai.evaluation import (
    EvalTask,
    PointwiseMetric,
    PointwiseMetricPromptTemplate,
)


PROJECT_ID = "test-to-sql-502205"
LOCATION = "us-central1"

SERVICE_URL = os.environ["SERVICE_URL"].rstrip("/")
QUERY_URL = f"{SERVICE_URL}/query"

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"


vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
)


business_correctness = PointwiseMetric(
    metric="business_correctness",
    metric_prompt_template=PointwiseMetricPromptTemplate(
        criteria={
            "business_correctness": (
                "Determine whether the response correctly answers "
                "the user's business question."
            ),
            "sql_consistency": (
                "Determine whether the business answer is consistent "
                "with the SQL and metadata shown in the response."
            ),
        },
        rating_rubric={
            "5": "Fully correct and internally consistent.",
            "4": "Correct with only minor issues.",
            "3": "Partially correct or missing useful information.",
            "2": "Mostly incorrect with substantial issues.",
            "1": "Incorrect, contradictory, or unusable.",
        },
        input_variables=[
            "prompt",
            "response",
        ],
    ),
)


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def call_agent(question, eval_id, max_attempts=5):
    payload = {
        "question": question,
        "user_id": "vertex_evaluation_user",
        "session_id": f"vertex-{eval_id}-{uuid.uuid4()}",
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

        start_time = time.perf_counter()

        response = requests.post(
            QUERY_URL,
            json=payload,
            timeout=180,
        )

        latency_seconds = time.perf_counter() - start_time

        if response.ok:
            data = response.json()

            return (
                data["answer"],
                data["cache_status"],
                latency_seconds,
            )

        print(
            f"{eval_id}: HTTP {response.status_code}"
        )

        print(response.text)

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


def main():
    dataset = load_dataset()

    evaluation_rows = []

    for test_case in dataset:
        eval_id = test_case["id"]
        question = test_case["question"]

        print(f"\nRunning {eval_id}: {question}")

        try:
            answer, cache_status, latency = call_agent(
                question=question,
                eval_id=eval_id,
            )

            evaluation_rows.append(
                {
                    "eval_id": eval_id,
                    "prompt": question,
                    "response": answer,
                    "cache_status": cache_status,
                    "agent_latency_seconds": round(
                        latency,
                        3,
                    ),
                }
            )

        except Exception as exc:
            print(
                f"{eval_id}: agent execution failed: {exc}"
            )

    if not evaluation_rows:
        raise RuntimeError(
            "No successful agent responses to evaluate."
        )

    eval_dataframe = pd.DataFrame(evaluation_rows)

    print("\nAGENT RESPONSES COLLECTED")
    print(
        eval_dataframe[
            [
                "eval_id",
                "cache_status",
                "agent_latency_seconds",
            ]
        ]
    )

    eval_task = EvalTask(
        dataset=eval_dataframe,
        metrics=[
            business_correctness,
        ],
        experiment="text-to-sql-real-agent-evaluation",
    )

    result = eval_task.evaluate()

    print("\nSUMMARY METRICS")
    print(result.summary_metrics)

    print("\nMETRICS TABLE")

    columns = [
        "eval_id",
        "cache_status",
        "agent_latency_seconds",
        "business_correctness/score",
    ]

    print(result.metrics_table[columns])


if __name__ == "__main__":
    main()