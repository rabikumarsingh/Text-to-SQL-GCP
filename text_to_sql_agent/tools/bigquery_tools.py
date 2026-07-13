from google.cloud import bigquery
import time


PROJECT_ID = "test-to-sql-502205"
TABLE_ID = "bigquery-public-data.chicago_taxi_trips.taxi_trips"

MAX_BYTES_BILLED = 10 * 1024**3  # 10 GiB
MAX_ROWS_RETURNED = 100

client = bigquery.Client(project=PROJECT_ID)


def get_table_schema() -> dict:
    """Return the schema of the configured BigQuery table."""

    table = client.get_table(TABLE_ID)

    columns = [
        {
            "name": field.name,
            "type": field.field_type,
            "mode": field.mode,
        }
        for field in table.schema
    ]

    return {
        "table": TABLE_ID,
        "columns": columns,
    }


def dry_run_query(sql: str) -> dict:
    """Validate SQL and estimate bytes processed without executing it."""

    try:
        job_config = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
        )

        query_job = client.query(sql, job_config=job_config)

        return {
            "valid": True,
            "estimated_bytes_processed": query_job.total_bytes_processed,
            "error": None,
        }

    except Exception as e:
        return {
            "valid": False,
            "estimated_bytes_processed": None,
            "error": str(e),
        }


def execute_safe_query(sql: str) -> dict:
    """
    Execute a BigQuery query with cost and result-size controls.
    """

    try:
        # Mandatory second dry run.
        dry_run_result = dry_run_query(sql)

        if not dry_run_result["valid"]:
            return {
                "success": False,
                "error": dry_run_result["error"],
            }

        estimated_bytes = dry_run_result["estimated_bytes_processed"]

        if estimated_bytes > MAX_BYTES_BILLED:
            return {
                "success": False,
                "error": "Query exceeds maximum allowed bytes.",
                "estimated_bytes_processed": estimated_bytes,
            }

        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES_BILLED,
            use_query_cache=True,
        )

        start_time = time.perf_counter()

        query_job = client.query(
            sql,
            job_config=job_config,
        )

        rows = query_job.result(
            max_results=MAX_ROWS_RETURNED
        )

        execution_time = time.perf_counter() - start_time

        results = [dict(row.items()) for row in rows]

        return {
            "success": True,
            "rows": results,
            "row_count": len(results),
            "estimated_bytes_processed": estimated_bytes,
            "actual_bytes_processed": query_job.total_bytes_processed,
            "cache_hit": query_job.cache_hit,
            "execution_time_seconds": round(execution_time, 3),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }