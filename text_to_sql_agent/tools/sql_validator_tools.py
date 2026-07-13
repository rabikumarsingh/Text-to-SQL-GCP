from ..services.semantic_sql_validator import (
    semantic_sql_validator,
)


def validate_semantic_sql(
    sql: str,
    metric_name: str,
) -> dict:
    """
    Validate generated SQL against the semantic layer.

    Args:
        sql: Generated BigQuery GoogleSQL.
        metric_name: Approved semantic metric name.

    Returns:
        Semantic SQL validation result.
    """

    return semantic_sql_validator.validate(
        sql=sql,
        metric_name=metric_name,
    )