import os

import pandas as pd
import vertexai

from vertexai.evaluation import (
    EvalTask,
    PointwiseMetric,
    PointwiseMetricPromptTemplate,
)


PROJECT_ID = "test-to-sql-502205"
LOCATION = "us-central1"

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


eval_dataset = pd.DataFrame(
    [
        {
            "prompt": (
                "Which company category generated the highest "
                "total revenue in 2023?"
            ),
            "response": (
                "The company category that generated the highest "
                "total revenue in 2023 was PREMIUM, with total "
                "revenue of 66,320,228.28."
            ),
        },
        {
            "prompt": (
                "What was the average taxi fare in 2021?"
            ),
            "response": (
                "The average taxi fare in 2021 was approximately 20.97."
            ),
        },
    ]
)


eval_task = EvalTask(
    dataset=eval_dataset,
    metrics=[
        business_correctness,
    ],
    experiment="text-to-sql-managed-evaluation",
)


result = eval_task.evaluate()


print("\nSUMMARY METRICS")
print(result.summary_metrics)


print("\nMETRICS TABLE")
print(result.metrics_table)