import time as time_module
from datetime import datetime
from typing import Any, List, Union

from .enums import StatusEnum


class QueryBuilder:
    """Fluent query builder for Motadata ServiceOps API qualification filters."""

    def __init__(self):
        self.quals: List[dict] = []

    def where_property(
        self,
        key: str,
        operator: str,
        values: Union[List[Any], Any],
    ) -> "QueryBuilder":
        """Filter based on a property field like 'request.statusId'.

        Args:
            key: The property key (e.g. 'request.statusId')
            operator: Comparison operator (e.g. 'in', 'not_in', 'equal')
            values: List of values or a single value
        """
        if not isinstance(values, list):
            values = [values]

        # Unpack IntEnum / enums to integer values if applicable
        normalized_values = [int(v) if isinstance(v, (int, StatusEnum)) else v for v in values]

        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "PropertyOperandRest", "key": key},
                "operator": operator,
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "ListLongValueRest", "value": normalized_values},
                },
            }
        )
        return self

    def where_variable(
        self,
        key: str,
        operator: str,
        values: Union[List[Any], Any],
    ) -> "QueryBuilder":
        """Filter based on a variable operand like 'categoryId'.

        Args:
            key: The variable key (e.g. 'categoryId')
            operator: Comparison operator (e.g. 'in', 'not_in', 'equal')
            values: List of values or a single value
        """
        if not isinstance(values, list):
            values = [values]

        normalized_values = [int(v) if isinstance(v, (int, StatusEnum)) else v for v in values]

        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "VariableOperandRest", "value": key},
                "operator": operator,
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "ListLongValueRest", "value": normalized_values},
                },
            }
        )
        return self

    def where_string_property(
        self,
        key: str,
        operator: str,
        value: str,
    ) -> "QueryBuilder":
        """Filter based on a string property field (e.g. '.name', contains)."""
        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "PropertyOperandRest", "key": key},
                "operator": operator,
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "StringValueRest", "value": value},
                },
            }
        )
        return self

    def where_enum_property(
        self,
        key: str,
        operator: str,
        value: str,
    ) -> "QueryBuilder":
        """Filter based on an enum property field (e.g. '.conversation.conversationState')."""
        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "PropertyOperandRest", "key": key},
                "operator": operator,
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "EnumValueRest", "value": value},
                },
            }
        )
        return self

    def where_not_closed(self) -> "QueryBuilder":
        """Filter for tickets that are not closed."""
        return self.where_property("request.statusId", "not_in", [StatusEnum.CLOSED])

    def where_not_categorized(self) -> "QueryBuilder":
        """Filter for tickets that are not categorized (categoryId is null or 0)."""
        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "VariableOperandRest", "value": "categoryId"},
                "operator": "in",
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "ListLongValueRest", "value": [0]},
                },
            }
        )
        return self

    def where_created_after(self, target_time: Union[datetime, float, int]) -> "QueryBuilder":
        """Filter for tickets created after a specific datetime or timestamp using within_last.

        Args:
            target_time: A datetime instance or unix timestamp (seconds).
        """
        current_time = time_module.time()
        if isinstance(target_time, datetime):
            given_timestamp = target_time.timestamp()
        else:
            given_timestamp = float(target_time)

        milliseconds_ago = max(0, int((current_time - given_timestamp) * 1000))

        self.quals.append(
            {
                "type": "RelationalQualificationRest",
                "leftOperand": {"type": "PropertyOperandRest", "key": "request.createdTime"},
                "operator": "within_last",
                "rightOperand": {
                    "type": "ValueOperandRest",
                    "value": {"type": "LongValueRest", "value": milliseconds_ago},
                },
            }
        )
        return self

    def add_raw_qualification(self, qualification: dict) -> "QueryBuilder":
        """Add an arbitrary raw qualification dictionary."""
        self.quals.append(qualification)
        return self

    def clear(self) -> "QueryBuilder":
        """Clear all qualifications from this builder."""
        self.quals = []
        return self

    def build(self) -> dict:
        """Build the query dictionary payload for the API."""
        return {"qualDetails": {"type": "FlatQualificationRest", "quals": self.quals}}

    def to_dict(self) -> dict:
        """Alias for build()."""
        return self.build()
