from dataclasses import dataclass
from typing import Literal

PIIClass = Literal[
    "identity",
    "contact",
    "address",
    "tax",
    "free_text",
    "operational_identifier",
]

Boundary = Literal[
    "private_raw",
    "downstream_safe",
    "public",
]


@dataclass(frozen=True)
class PIIField:
    column_name: str
    pii_class: PIIClass


@dataclass(frozen=True)
class BoundaryValidationResult:
    boundary: Boundary
    requested_columns: tuple[str, ...]
    blocked_columns: tuple[str, ...]

    @property
    def is_allowed(self) -> bool:
        return not self.blocked_columns


ORDERS_PII_FIELDS: tuple[PIIField, ...] = (
    PIIField("buyer_message", "free_text"),
    PIIField("buyer_username", "identity"),
    PIIField("recipient", "identity"),
    PIIField("phone_number", "contact"),
    PIIField("zipcode", "address"),
    PIIField("country", "address"),
    PIIField("province", "address"),
    PIIField("district", "address"),
    PIIField("districts", "address"),
    PIIField("detail_address", "address"),
    PIIField("additional_address_information", "address"),
    PIIField("seller_note", "free_text"),
    PIIField("tax_info_buyer_tax_id", "tax"),
    PIIField("tax_info_full_name_of_buyer", "tax"),
    PIIField("tax_info_email", "tax"),
    PIIField("tax_info_phone_number", "tax"),
    PIIField("tax_info_registered_address", "tax"),
    PIIField("tracking_id", "operational_identifier"),
    PIIField("package_id", "operational_identifier"),
    PIIField("checked_marked_by", "operational_identifier"),
)


PII_FIELDS_BY_SOURCE: dict[str, tuple[PIIField, ...]] = {
    "orders": ORDERS_PII_FIELDS,
}


def list_pii_columns(
    source_name: str,
) -> tuple[str, ...]:
    fields = PII_FIELDS_BY_SOURCE.get(source_name, ())

    return tuple(
        field.column_name
        for field in fields
    )


def validate_projection_boundary(
    *,
    source_name: str,
    requested_columns: tuple[str, ...],
    boundary: Boundary,
) -> BoundaryValidationResult:
    """
    Validate whether selected canonical raw columns may cross a boundary.

    Private raw projections preserve source fidelity and are allowed.
    Downstream-safe and public projections reject classified PII columns.
    This function inspects column names only and never reads row values.
    """

    if boundary == "private_raw":
        return BoundaryValidationResult(
            boundary=boundary,
            requested_columns=requested_columns,
            blocked_columns=(),
        )

    pii_columns = set(list_pii_columns(source_name))

    blocked_columns = tuple(
        column_name
        for column_name in requested_columns
        if column_name in pii_columns
    )

    return BoundaryValidationResult(
        boundary=boundary,
        requested_columns=requested_columns,
        blocked_columns=blocked_columns,
    )


def require_safe_projection(
    *,
    source_name: str,
    requested_columns: tuple[str, ...],
    boundary: Boundary,
) -> None:
    result = validate_projection_boundary(
        source_name=source_name,
        requested_columns=requested_columns,
        boundary=boundary,
    )

    if result.is_allowed:
        return

    blocked = ", ".join(result.blocked_columns)

    raise ValueError(
        f"PII boundary violation for source '{source_name}' "
        f"at boundary '{boundary}': {blocked}"
    )
