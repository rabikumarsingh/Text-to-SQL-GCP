import time

from google.cloud import bigquery
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


PROJECT_ID = "test-to-sql-502205"
TABLE_ID = "bigquery-public-data.chicago_taxi_trips.taxi_trips"

MAX_BYTES_BILLED = 10 * 1024**3  # 10 GiB
MAX_ROWS_RETURNED = 100

client = bigquery.Client(project=PROJECT_ID)

tracer = trace.get_tracer(__name__)


def get_table_schema() -> dict:
    """Return the schema of the configured BigQuery table."""

    with tracer.start_as_current_span(
        "bigquery.get_table_schema"
    ) as span:

        span.set_attribute(
            "bigquery.project_id",
            PROJECT_ID,
        )

        span.set_attribute(
            "bigquery.table_id",
            TABLE_ID,
        )

        try:
            table = client.get_table(TABLE_ID)

            columns = [
                {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                }
                for field in table.schema
            ]

            span.set_attribute(
                "bigquery.schema.column_count",
                len(columns),
            )

            span.set_status(Status(StatusCode.OK))

            return {
                "table": TABLE_ID,
                "columns": columns,
            }

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    str(exc),
                )
            )
            raise


def dry_run_query(sql: str) -> dict:
    """Validate SQL and estimate bytes processed without executing it."""

    with tracer.start_as_current_span(
        "bigquery.dry_run"
    ) as span:

        span.set_attribute(
            "bigquery.project_id",
            PROJECT_ID,
        )

        span.set_attribute(
            "bigquery.operation",
            "dry_run",
        )

        try:
            job_config = bigquery.QueryJobConfig(
                dry_run=True,
                use_query_cache=False,
            )

            query_job = client.query(
                sql,
                job_config=job_config,
            )

            estimated_bytes = (
                query_job.total_bytes_processed or 0
            )

            span.set_attribute(
                "bigquery.estimated_bytes_processed",
                estimated_bytes,
            )

            span.set_attribute(
                "bigquery.validation.valid",
                True,
            )

            span.set_status(Status(StatusCode.OK))

            return {
                "valid": True,
                "estimated_bytes_processed": estimated_bytes,
                "error": None,
            }

        except Exception as exc:
            span.set_attribute(
                "bigquery.validation.valid",
                False,
            )

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    str(exc),
                )
            )

            return {
                "valid": False,
                "estimated_bytes_processed": None,
                "error": str(exc),
            }


def execute_safe_query(sql: str) -> dict:
    """
    Execute a BigQuery query with cost and result-size controls.
    """

    with tracer.start_as_current_span(
        "bigquery.execute_safe_query"
    ) as parent_span:

        parent_span.set_attribute(
            "bigquery.project_id",
            PROJECT_ID,
        )

        parent_span.set_attribute(
            "bigquery.max_bytes_billed",
            MAX_BYTES_BILLED,
        )

        parent_span.set_attribute(
            "bigquery.max_rows_returned",
            MAX_ROWS_RETURNED,
        )

        try:
            # ----------------------------------------------
            # Mandatory second dry run
            # ----------------------------------------------

            dry_run_result = dry_run_query(sql)

            if not dry_run_result["valid"]:

                parent_span.set_attribute(
                    "bigquery.execution.allowed",
                    False,
                )

                parent_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        "BigQuery dry run failed",
                    )
                )

                return {
                    "success": False,
                    "error": dry_run_result["error"],
                }

            estimated_bytes = (
                dry_run_result[
                    "estimated_bytes_processed"
                ]
            )

            parent_span.set_attribute(
                "bigquery.estimated_bytes_processed",
                estimated_bytes,
            )

            # ----------------------------------------------
            # Cost guard
            # ----------------------------------------------

            if estimated_bytes > MAX_BYTES_BILLED:

                parent_span.set_attribute(
                    "bigquery.execution.allowed",
                    False,
                )

                parent_span.set_attribute(
                    "bigquery.cost_guard.triggered",
                    True,
                )

                parent_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        "Query exceeded maximum allowed bytes",
                    )
                )

                return {
                    "success": False,
                    "error": "Query exceeds maximum allowed bytes.",
                    "estimated_bytes_processed": estimated_bytes,
                }

            parent_span.set_attribute(
                "bigquery.execution.allowed",
                True,
            )

            parent_span.set_attribute(
                "bigquery.cost_guard.triggered",
                False,
            )

            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=MAX_BYTES_BILLED,
                use_query_cache=True,
            )

            # ----------------------------------------------
            # Submit query
            # ----------------------------------------------

            with tracer.start_as_current_span(
                "bigquery.execute"
            ) as execute_span:

                start_time = time.perf_counter()

                query_job = client.query(
                    sql,
                    job_config=job_config,
                )

                execute_span.set_attribute(
                    "bigquery.job_id",
                    query_job.job_id,
                )

                # ------------------------------------------
                # Wait for results
                # ------------------------------------------

                with tracer.start_as_current_span(
                    "bigquery.fetch_results"
                ) as fetch_span:

                    rows = query_job.result(
                        max_results=MAX_ROWS_RETURNED
                    )

                    results = [
                        dict(row.items())
                        for row in rows
                    ]

                    fetch_span.set_attribute(
                        "bigquery.row_count",
                        len(results),
                    )

                    fetch_span.set_status(
                        Status(StatusCode.OK)
                    )

                execution_time = (
                    time.perf_counter()
                    - start_time
                )

                actual_bytes = (
                    query_job.total_bytes_processed or 0
                )

                cache_hit = bool(query_job.cache_hit)

                execute_span.set_attribute(
                    "bigquery.actual_bytes_processed",
                    actual_bytes,
                )

                execute_span.set_attribute(
                    "bigquery.cache_hit",
                    cache_hit,
                )

                execute_span.set_attribute(
                    "bigquery.execution_time_seconds",
                    execution_time,
                )

                execute_span.set_status(
                    Status(StatusCode.OK)
                )

            # ----------------------------------------------
            # Parent span metrics
            # ----------------------------------------------

            parent_span.set_attribute(
                "bigquery.row_count",
                len(results),
            )

            parent_span.set_attribute(
                "bigquery.actual_bytes_processed",
                actual_bytes,
            )

            parent_span.set_attribute(
                "bigquery.cache_hit",
                cache_hit,
            )

            parent_span.set_attribute(
                "bigquery.execution_time_seconds",
                execution_time,
            )

            parent_span.set_attribute(
                "bigquery.execution.success",
                True,
            )

            parent_span.set_status(
                Status(StatusCode.OK)
            )

            return {
                "success": True,
                "rows": results,
                "row_count": len(results),
                "estimated_bytes_processed": estimated_bytes,
                "actual_bytes_processed": actual_bytes,
                "cache_hit": cache_hit,
                "execution_time_seconds": round(
                    execution_time,
                    3,
                ),
            }

        except Exception as exc:

            parent_span.set_attribute(
                "bigquery.execution.success",
                False,
            )

            parent_span.record_exception(exc)

            parent_span.set_status(
                Status(
                    StatusCode.ERROR,
                    str(exc),
                )
            )

            return {
                "success": False,
                "error": str(exc),
            }