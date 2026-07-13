from .tools.semantic_tools import (
    get_business_context,
    get_data_availability,
    get_available_metrics,
    get_metric_definition,
    get_available_dimensions,
    get_dimension_definition,
    get_relationships,
)

print(get_business_context())
print(get_data_availability())
print(get_available_metrics())
print(get_metric_definition("total_revenue"))
print(get_available_dimensions())
print(get_dimension_definition("company_category"))
print(get_relationships())