from ..services.semantic_layer_service import semantic_layer_service


def get_business_context() -> dict:
    """Return the configured business domain."""
    return semantic_layer_service.get_domain()


def get_data_availability() -> dict:
    """Return the available date range for business data."""
    return semantic_layer_service.get_data_availability()


def get_available_metrics() -> dict:
    """Return all approved business metrics."""
    return semantic_layer_service.get_metrics()


def get_metric_definition(metric_name: str) -> dict:
    """Return the approved definition of a business metric."""

    metric = semantic_layer_service.get_metric(metric_name)

    if metric is None:
        return {
            "found": False,
            "metric_name": metric_name,
        }

    return {
        "found": True,
        "metric_name": metric_name,
        "definition": metric,
    }


def get_available_dimensions() -> dict:
    """Return all approved business dimensions."""
    return semantic_layer_service.get_dimensions()


def get_dimension_definition(dimension_name: str) -> dict:
    """Return the approved definition of a business dimension."""

    dimension = semantic_layer_service.get_dimension(dimension_name)

    if dimension is None:
        return {
            "found": False,
            "dimension_name": dimension_name,
        }

    return {
        "found": True,
        "dimension_name": dimension_name,
        "definition": dimension,
    }


def get_relationships() -> dict:
    """Return all approved table relationships."""
    return semantic_layer_service.get_relationships()

def get_table_definition(table_name: str) -> dict:
    """
    Return the physical BigQuery table definition
    for an approved semantic table.

    Args:
        table_name: Semantic table name.
    """

    tables = semantic_layer_service.get_tables()

    table = tables.get(table_name)

    if table is None:
        return {
            "found": False,
            "table_name": table_name,
        }

    return {
        "found": True,
        "table_name": table_name,
        "definition": table,
    }