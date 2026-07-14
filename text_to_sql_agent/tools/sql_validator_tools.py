from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ..services.semantic_sql_validator import (
    semantic_sql_validator,
)


tracer = trace.get_tracer(__name__)


def validate_semantic_sql(
    sql: str,
    metric_name: str,
) -> dict:
    """
    Validate generated SQL against the semantic layer.
    """

    with tracer.start_as_current_span(
        "semantic_validation.validate"
    ) as span:

        # Do not store raw SQL in traces.

        span.set_attribute(
            "semantic_validation.metric_name",
            metric_name,
        )

        try:

            result = semantic_sql_validator.validate(
                sql=sql,
                metric_name=metric_name,
            )

            is_valid = bool(
                result.get("valid", False)
            )

            errors = result.get("errors") or []

            span.set_attribute(
                "semantic_validation.valid",
                is_valid,
            )

            span.set_attribute(
                "semantic_validation.error_count",
                len(errors),
            )

            if is_valid:

                span.set_status(
                    Status(StatusCode.OK)
                )

            else:

                # Invalid generated SQL is an expected
                # validation outcome, not a system exception.

                span.set_status(
                    Status(StatusCode.UNSET)
                )

            return result

        except Exception as exc:

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    str(exc),
                )
            )

            raise