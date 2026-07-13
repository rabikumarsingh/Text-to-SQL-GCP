import os
import sys
import uuid

import requests
import time

SERVICE_URL = os.environ["SERVICE_URL"].rstrip("/")

QUERY_URL = f"{SERVICE_URL}/query"

session_id = f"ci-integration-{uuid.uuid4()}"

payload = {
    "question": (
        "What was the average taxi fare in 2020?"
    ),
    "user_id": "github_actions_integration_user",
    "session_id": session_id,
}


def call_query(max_attempts=5):
    retryable_status_codes = {
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(1, max_attempts + 1):
        print(
            f"Calling /query "
            f"(attempt {attempt}/{max_attempts})..."
        )

        response = requests.post(
            QUERY_URL,
            json=payload,
            timeout=180,
        )

        if response.ok:
            data = response.json()

            assert data["session_id"] == session_id
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0
            assert data["cache_status"] in {"MISS", "HIT"}

            return data

        print(
            f"Request failed: HTTP {response.status_code}"
        )
        print(response.text)

        if (
            response.status_code not in retryable_status_codes
            or attempt == max_attempts
        ):
            response.raise_for_status()

        wait_seconds = 10 * attempt

        print(
            f"Transient failure. Retrying in "
            f"{wait_seconds} seconds..."
        )

        time.sleep(wait_seconds)

    raise RuntimeError("Integration test exhausted retries.")

print("Running first query...")

first_response = call_query()

if first_response["cache_status"] != "MISS":
    print(
        "ERROR: First request should be MISS, got:",
        first_response["cache_status"],
    )
    sys.exit(1)

print("First request: MISS")


print("Running second query...")

second_response = call_query()

if second_response["cache_status"] != "HIT":
    print(
        "ERROR: Second request should be HIT, got:",
        second_response["cache_status"],
    )
    sys.exit(1)

if first_response["answer"] != second_response["answer"]:
    print("ERROR: Cached answer differs from original answer.")
    sys.exit(1)

print("Second request: HIT")

print("Integration test PASSED.")