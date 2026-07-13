from sqlglot import exp, parse
from sqlglot.errors import ParseError

from .semantic_layer_service import semantic_layer_service


FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Merge,
    exp.Command,
)


class SemanticSQLValidator:

    def __init__(self):
        self.semantic_layer = semantic_layer_service

    def validate(
        self,
        sql: str,
        metric_name: str | None = None,
    ) -> dict:

        errors = []

        # 1. Parse SQL
        try:
            statements = parse(
                sql,
                read="bigquery",
            )

        except ParseError as exc:
            return {
                "valid": False,
                "errors": [
                    f"SQL parse error: {str(exc)}"
                ],
            }

        # 2. Exactly one statement
        if len(statements) != 1:
            return {
                "valid": False,
                "errors": [
                    "Exactly one SQL statement is allowed."
                ],
            }

        statement = statements[0]

        # 3. Query only
        if not isinstance(statement, exp.Query):
            errors.append(
                "Only SELECT queries are allowed."
            )

        # 4. Block DDL / DML
        for forbidden_type in FORBIDDEN_NODE_TYPES:

            if statement.find(forbidden_type):

                errors.append(
                    f"Forbidden SQL operation detected: "
                    f"{forbidden_type.__name__}"
                )

        # 5. Load approved metadata
        approved_tables = (
            self._get_approved_tables()
        )

        approved_columns = (
            self._get_approved_columns()
        )

        # 6. Validate physical tables
        referenced_tables = set()

        for table in statement.find_all(exp.Table):

            physical_name = (
                self._normalize_table_name(table)
            )

            referenced_tables.add(
                physical_name
            )

            if physical_name not in approved_tables:

                errors.append(
                    f"Unapproved table referenced: "
                    f"{physical_name}"
                )

        # 7. Build alias -> semantic table map
        alias_to_semantic_table = (
            self._build_alias_to_semantic_table_map(
                statement
            )
        )

        # 8. Validate JOINs
        join_errors = self._validate_joins(
            statement=statement,
            alias_to_semantic_table=(
                alias_to_semantic_table
            ),
        )

        errors.extend(join_errors)

        # 9. Validate approved metric formula
        if metric_name is not None:

            metric_errors = (
                self._validate_metric_expression(
                    statement=statement,
                    metric_name=metric_name,
                    alias_to_semantic_table=(
                        alias_to_semantic_table
                    ),
                )
            )

            errors.extend(metric_errors)

        # 10. Collect SELECT aliases
        select_aliases = set()

        for alias in statement.find_all(exp.Alias):

            alias_name = alias.alias

            if alias_name:

                select_aliases.add(
                    alias_name
                )

        # 11. Validate columns
        referenced_columns = set()

        for column in statement.find_all(exp.Column):

            column_name = column.name

            referenced_columns.add(
                column_name
            )

            if column_name in select_aliases:
                continue

            if column_name not in approved_columns:

                errors.append(
                    f"Unapproved column referenced: "
                    f"{column_name}"
                )

        # 12. Return validation result
        return {
            "valid": len(errors) == 0,

            "errors": sorted(
                set(errors)
            ),

            "metric_name": metric_name,

            "referenced_tables": sorted(
                referenced_tables
            ),

            "referenced_columns": sorted(
                referenced_columns
            ),

            "select_aliases": sorted(
                select_aliases
            ),

            "alias_to_semantic_table":
                alias_to_semantic_table,
        }

    # ======================================================
    # APPROVED TABLES
    # ======================================================

    def _get_approved_tables(
        self,
    ) -> set[str]:

        tables = self.semantic_layer.get_tables()

        return {
            definition["full_table_name"]
            for definition in tables.values()
        }

    # ======================================================
    # APPROVED COLUMNS
    # ======================================================

    def _get_approved_columns(
        self,
    ) -> set[str]:

        tables = self.semantic_layer.get_tables()

        approved_columns = set()

        for definition in tables.values():

            approved_columns.update(
                definition["columns"].keys()
            )

        return approved_columns

    # ======================================================
    # ALIAS -> SEMANTIC TABLE MAP
    # ======================================================

    def _build_alias_to_semantic_table_map(
        self,
        statement: exp.Expression,
    ) -> dict[str, str]:

        semantic_tables = (
            self.semantic_layer.get_tables()
        )

        physical_to_semantic = {

            definition["full_table_name"]:
                semantic_name

            for semantic_name, definition
            in semantic_tables.items()
        }

        alias_map = {}

        for table in statement.find_all(exp.Table):

            physical_name = (
                self._normalize_table_name(table)
            )

            semantic_name = (
                physical_to_semantic.get(
                    physical_name
                )
            )

            if semantic_name is None:
                continue

            sql_alias = table.alias_or_name

            alias_map[
                sql_alias
            ] = semantic_name

            alias_map[
                table.name
            ] = semantic_name

        return alias_map

    # ======================================================
    # JOIN VALIDATION
    # ======================================================

    def _validate_joins(
        self,
        statement: exp.Expression,
        alias_to_semantic_table: dict[str, str],
    ) -> list[str]:

        errors = []

        relationships = (
            self.semantic_layer.get_relationships()
        )

        approved_relationships = []

        for relationship in relationships.values():

            condition = relationship[
                "join_condition"
            ]

            approved_relationships.append(
                {
                    "left_table":
                        relationship["left_table"],

                    "right_table":
                        relationship["right_table"],

                    "join_type":
                        relationship[
                            "join_type"
                        ].upper(),

                    "left_column":
                        condition["left_column"],

                    "right_column":
                        condition["right_column"],
                }
            )

        for join in statement.find_all(exp.Join):

            joined_table = join.this

            if not isinstance(
                joined_table,
                exp.Table,
            ):

                errors.append(
                    "Only direct table JOINs "
                    "are currently allowed."
                )

                continue

            join_type = self._get_join_type(join)

            on_expression = join.args.get("on")

            if on_expression is None:

                errors.append(
                    "JOIN must contain an ON condition."
                )

                continue

            equalities = list(
                on_expression.find_all(exp.EQ)
            )

            if len(equalities) != 1:

                errors.append(
                    "JOIN must contain exactly one "
                    "approved equality condition."
                )

                continue

            equality = equalities[0]

            left_expression = equality.left
            right_expression = equality.right

            if not (
                isinstance(
                    left_expression,
                    exp.Column,
                )
                and isinstance(
                    right_expression,
                    exp.Column,
                )
            ):

                errors.append(
                    "JOIN condition must compare "
                    "two columns."
                )

                continue

            sql_left_alias = (
                left_expression.table
            )

            sql_right_alias = (
                right_expression.table
            )

            sql_left_column = (
                left_expression.name
            )

            sql_right_column = (
                right_expression.name
            )

            semantic_left_table = (
                alias_to_semantic_table.get(
                    sql_left_alias
                )
            )

            semantic_right_table = (
                alias_to_semantic_table.get(
                    sql_right_alias
                )
            )

            matched = False

            for approved in approved_relationships:

                forward_match = (
                    semantic_left_table
                    == approved["left_table"]

                    and semantic_right_table
                    == approved["right_table"]

                    and sql_left_column
                    == approved["left_column"]

                    and sql_right_column
                    == approved["right_column"]

                    and join_type
                    == approved["join_type"]
                )

                reverse_match = (
                    semantic_left_table
                    == approved["right_table"]

                    and semantic_right_table
                    == approved["left_table"]

                    and sql_left_column
                    == approved["right_column"]

                    and sql_right_column
                    == approved["left_column"]

                    and join_type
                    == approved["join_type"]
                )

                if forward_match or reverse_match:

                    matched = True

                    break

            if not matched:

                errors.append(
                    "JOIN does not match an approved "
                    "semantic relationship."
                )

        return errors

    # ======================================================
    # JOIN TYPE NORMALIZATION
    # ======================================================

    @staticmethod
    def _get_join_type(
        join: exp.Join,
    ) -> str:

        side = (
            join.args.get("side") or ""
        ).upper()

        kind = (
            join.args.get("kind") or ""
        ).upper()

        if side:
            return f"{side} JOIN"

        if kind == "CROSS":
            return "CROSS JOIN"

        return "INNER JOIN"

    # ======================================================
    # APPROVED METRIC NORMALIZATION
    # ======================================================

    def _get_normalized_metric_expression(
        self,
        metric_name: str,
    ) -> str | None:

        metric = self.semantic_layer.get_metric(
            metric_name
        )

        if metric is None:
            return None

        sql_expression = metric.get(
            "sql_expression"
        )

        if not sql_expression:
            return None

        try:

            parsed_expression = parse(
                sql_expression,
                read="bigquery",
            )

        except ParseError:

            return None

        if len(parsed_expression) != 1:
            return None

        return parsed_expression[0].sql(
            dialect="bigquery",
            normalize=True,
        )

    # ======================================================
    # METRIC EXPRESSION VALIDATION
    # ======================================================

    def _validate_metric_expression(
        self,
        statement: exp.Expression,
        metric_name: str,
        alias_to_semantic_table: dict[str, str],
    ) -> list[str]:

        approved_metric_expression = (
            self._get_normalized_metric_expression(
                metric_name
            )
        )

        if approved_metric_expression is None:

            return [
                f"Metric is not defined or cannot be parsed: "
                f"{metric_name}"
            ]

        generated_expressions = []

        for select in statement.find_all(exp.Select):

            for projection in select.expressions:

                expression = projection

                if isinstance(expression, exp.Alias):

                    expression = expression.this

                normalized_expression = (
                    expression.copy()
                )

                for column in (
                    normalized_expression.find_all(
                        exp.Column
                    )
                ):

                    sql_table_alias = column.table

                    semantic_table_name = (
                        alias_to_semantic_table.get(
                            sql_table_alias
                        )
                    )

                    if semantic_table_name:

                        column.set(
                            "table",
                            exp.Identifier(
                                this=semantic_table_name
                            ),
                        )

                normalized_generated_expression = (
                    normalized_expression.sql(
                        dialect="bigquery",
                        normalize=True,
                    )
                )

                generated_expressions.append(
                    normalized_generated_expression
                )

        if (
            approved_metric_expression
            not in generated_expressions
        ):

            return [
                f"Generated SQL does not contain the "
                f"approved metric expression for "
                f"'{metric_name}'."
            ]

        return []

    # ======================================================
    # TABLE NAME NORMALIZATION
    # ======================================================

    @staticmethod
    def _normalize_table_name(
        table: exp.Table,
    ) -> str:

        parts = [
            table.catalog,
            table.db,
            table.name,
        ]

        return ".".join(
            part
            for part in parts
            if part
        )


semantic_sql_validator = SemanticSQLValidator()