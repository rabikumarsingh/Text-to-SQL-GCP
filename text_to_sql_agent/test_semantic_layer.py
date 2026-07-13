from .tools.semantic_tools import (
    get_business_context,
    get_data_availability,
    get_available_metrics,
    get_metric_definition,
    get_available_dimensions,
    get_dimension_definition,
    get_relationships,
)


print("\nBUSINESS CONTEXT")
print(get_business_context())

print("\nDATA AVAILABILITY")
print(get_data_availability())

print("\nMETRICS")
print(get_available_metrics())

print("\nMETRIC DEFINITION")
print(get_metric_definition("total_revenue"))

print("\nDIMENSIONS")
print(get_available_dimensions())

print("\nDIMENSION DEFINITION")
print(get_dimension_definition("company_category"))

print("\nRELATIONSHIPS")
print(get_relationships())