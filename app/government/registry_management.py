"""Administrator-only Registry Management interface for Hakiki Hire."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st

from api_client import HakikiHireAPIClient, HakikiHireAPIError


CATEGORY_LABELS = {
    "company": "Companies",
    "agency": "Recruitment agencies",
    "blacklist": "Blacklist",
}

STATUS_OPTIONS = [
    "active",
    "dormant",
    "expired",
    "revoked",
]


def _display(value: Any, fallback: str = "Not provided") -> str:
    if value is None:
        return fallback

    text = str(value).strip()

    return text or fallback


def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip()

    return text or None


def _record_label(record: Dict[str, Any]) -> str:
    identifier = (
        record.get("external_id")
        or record.get("registration_number")
        or record.get("licence_number")
        or record.get("id")
    )

    return "{} | {}".format(
        _display(record.get("name")),
        _display(identifier),
    )


def _refresh_registry() -> None:
    st.session_state.registry_refresh_nonce = (
        int(
            st.session_state.get(
                "registry_refresh_nonce",
                0,
            )
        )
        + 1
    )


def _render_company_fields(
    prefix: str,
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = record or {}

    external_id = st.text_input(
        "Company ID",
        value=str(record.get("external_id") or ""),
        key="{}_company_external_id".format(prefix),
    )

    registration_number = st.text_input(
        "Registration number",
        value=str(
            record.get("registration_number")
            or ""
        ),
        key="{}_company_registration".format(prefix),
    )

    county = st.text_input(
        "County",
        value=str(record.get("county") or ""),
        key="{}_company_county".format(prefix),
    )

    status_value = str(
        record.get("status") or "active"
    ).lower()

    status_index = (
        STATUS_OPTIONS.index(status_value)
        if status_value in STATUS_OPTIONS
        else 0
    )

    registry_status = st.selectbox(
        "Registry status",
        STATUS_OPTIONS,
        index=status_index,
        format_func=str.title,
        key="{}_company_status".format(prefix),
    )

    return {
        "external_id": _clean_optional(external_id),
        "registration_number": _clean_optional(
            registration_number
        ),
        "county": _clean_optional(county),
        "status": registry_status,
    }


def _render_agency_fields(
    prefix: str,
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = record or {}

    external_id = st.text_input(
        "Agency ID",
        value=str(record.get("external_id") or ""),
        key="{}_agency_external_id".format(prefix),
    )

    licence_number = st.text_input(
        "Licence number",
        value=str(record.get("licence_number") or ""),
        key="{}_agency_licence".format(prefix),
    )

    licence_status_options = [
        "active",
        "expired",
        "revoked",
        "suspended",
    ]

    current_licence_status = str(
        record.get("licence_status") or "active"
    ).lower()

    licence_status_index = (
        licence_status_options.index(
            current_licence_status
        )
        if current_licence_status
        in licence_status_options
        else 0
    )

    licence_status = st.selectbox(
        "Licence status",
        licence_status_options,
        index=licence_status_index,
        format_func=str.title,
        key="{}_agency_licence_status".format(prefix),
    )

    authorised_destinations = st.text_input(
        "Authorised destinations",
        value=str(
            record.get("authorised_destinations")
            or ""
        ),
        help=(
            "Separate multiple destinations with semicolons, "
            "for example: Qatar;UAE;Saudi Arabia"
        ),
        key="{}_agency_destinations".format(prefix),
    )

    county = st.text_input(
        "County",
        value=str(record.get("county") or ""),
        key="{}_agency_county".format(prefix),
    )

    current_status = str(
        record.get("status") or "active"
    ).lower()

    status_index = (
        STATUS_OPTIONS.index(current_status)
        if current_status in STATUS_OPTIONS
        else 0
    )

    registry_status = st.selectbox(
        "Registry status",
        STATUS_OPTIONS,
        index=status_index,
        format_func=str.title,
        key="{}_agency_status".format(prefix),
    )

    return {
        "external_id": _clean_optional(external_id),
        "licence_number": _clean_optional(
            licence_number
        ),
        "licence_status": licence_status,
        "authorised_destinations": _clean_optional(
            authorised_destinations
        ),
        "county": _clean_optional(county),
        "status": registry_status,
    }


def _render_blacklist_fields(
    prefix: str,
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = record or {}

    kinds = [
        "name",
        "email",
        "phone",
        "domain",
    ]

    current_kind = str(
        record.get("blacklist_kind") or "name"
    ).lower()

    kind_index = (
        kinds.index(current_kind)
        if current_kind in kinds
        else 0
    )

    kind = st.selectbox(
        "Blacklist kind",
        kinds,
        index=kind_index,
        format_func=str.title,
        key="{}_blacklist_kind".format(prefix),
    )

    reason = st.text_area(
        "Reason",
        value=str(
            record.get("blacklist_reason")
            or ""
        ),
        height=110,
        key="{}_blacklist_reason".format(prefix),
    )

    return {
        "blacklist_kind": kind,
        "blacklist_reason": _clean_optional(reason),
        "status": "listed",
    }


def _render_category_fields(
    category: str,
    prefix: str,
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if category == "company":
        return _render_company_fields(
            prefix,
            record,
        )

    if category == "agency":
        return _render_agency_fields(
            prefix,
            record,
        )

    return _render_blacklist_fields(
        prefix,
        record,
    )


def _render_create_form(
    client: HakikiHireAPIClient,
    category: str,
) -> None:
    with st.expander(
        "Add new {}".format(
            CATEGORY_LABELS[category].rstrip("s").lower()
        ),
        expanded=False,
    ):
        with st.form(
            "registry_create_{}".format(category),
            clear_on_submit=True,
        ):
            name_label = (
                "Blacklist value"
                if category == "blacklist"
                else "Registered name"
            )

            name = st.text_input(name_label)

            fields = _render_category_fields(
                category,
                "create_{}".format(category),
            )

            record_is_mock = st.checkbox(
                "Simulated or mock reference data",
                value=True,
                help=(
                    "Keep this selected for demonstration "
                    "and synthetic registry records."
                ),
            )

            submitted = st.form_submit_button(
                "Add registry record",
                type="primary",
                width="stretch",
            )

        if submitted:
            payload = {
                "category": category,
                "name": name.strip(),
                "record_is_mock": record_is_mock,
                **fields,
            }

            try:
                created = client.create_registry_record(
                    payload
                )

                st.session_state.registry_success_message = (
                    "{} was added to Registry Management."
                ).format(
                    _display(created.get("name"))
                )

                _refresh_registry()
                st.rerun()

            except (
                ValueError,
                HakikiHireAPIError,
            ) as error:
                st.error(
                    getattr(
                        error,
                        "message",
                        str(error),
                    )
                )


def _render_audit_history(
    client: HakikiHireAPIClient,
    record: Dict[str, Any],
) -> None:
    try:
        entries = client.get_registry_audit_history(
            int(record["id"])
        )
    except (
        ValueError,
        HakikiHireAPIError,
    ) as error:
        st.error(
            getattr(
                error,
                "message",
                str(error),
            )
        )
        return

    if not entries:
        st.info(
            "No Registry Management activity "
            "has been recorded for this entry."
        )
        return

    for entry in entries:
        action = str(
            entry.get("action") or "changed"
        ).replace("_", " ").title()

        st.markdown(
            "**{}** by **{}**".format(
                action,
                _display(
                    entry.get("actor"),
                    "Unknown administrator",
                ),
            )
        )

        st.caption(
            _display(
                entry.get("created_at"),
                "Time not recorded",
            )
        )

        details_text = str(
            entry.get("details_json") or ""
        ).strip()

        if details_text:
            try:
                st.json(json.loads(details_text))
            except json.JSONDecodeError:
                st.code(details_text)

        st.divider()


def _render_edit_controls(
    client: HakikiHireAPIClient,
    category: str,
    records: List[Dict[str, Any]],
) -> None:
    if not records:
        return

    options = {
        int(record["id"]): record
        for record in records
    }

    selected_id = st.selectbox(
        "Select a record to manage",
        options=list(options),
        format_func=lambda value: _record_label(
            options[value]
        ),
        key="registry_selected_{}".format(category),
    )

    record = options[int(selected_id)]

    with st.expander(
        "Edit selected record",
        expanded=False,
    ):
        with st.form(
            "registry_edit_{}_{}".format(
                category,
                selected_id,
            )
        ):
            name_label = (
                "Blacklist value"
                if category == "blacklist"
                else "Registered name"
            )

            name = st.text_input(
                name_label,
                value=str(record.get("name") or ""),
            )

            fields = _render_category_fields(
                category,
                "edit_{}_{}".format(
                    category,
                    selected_id,
                ),
                record,
            )

            record_is_mock = st.checkbox(
                "Simulated or mock reference data",
                value=bool(
                    record.get("record_is_mock")
                ),
            )

            submitted = st.form_submit_button(
                "Save changes",
                type="primary",
                width="stretch",
            )

        if submitted:
            payload = {
                "name": name.strip(),
                "record_is_mock": record_is_mock,
                **fields,
            }

            try:
                updated = client.update_registry_record(
                    int(selected_id),
                    payload,
                )

                st.session_state.registry_success_message = (
                    "{} was updated."
                ).format(
                    _display(updated.get("name"))
                )

                _refresh_registry()
                st.rerun()

            except (
                ValueError,
                HakikiHireAPIError,
            ) as error:
                st.error(
                    getattr(
                        error,
                        "message",
                        str(error),
                    )
                )

    with st.expander(
        "Status and audit history",
        expanded=False,
    ):
        is_active = bool(record.get("is_active"))

        st.write(
            "Current management status: **{}**".format(
                "Active"
                if is_active
                else "Inactive"
            )
        )

        action_name = (
            "Deactivate record"
            if is_active
            else "Reactivate record"
        )

        if st.button(
            action_name,
            key="registry_status_{}_{}".format(
                category,
                selected_id,
            ),
            width="stretch",
        ):
            try:
                updated = (
                    client.update_registry_record_status(
                        int(selected_id),
                        not is_active,
                    )
                )

                st.session_state.registry_success_message = (
                    "{} is now {}."
                ).format(
                    _display(updated.get("name")),
                    (
                        "active"
                        if updated.get("is_active")
                        else "inactive"
                    ),
                )

                _refresh_registry()
                st.rerun()

            except (
                ValueError,
                HakikiHireAPIError,
            ) as error:
                st.error(
                    getattr(
                        error,
                        "message",
                        str(error),
                    )
                )

        st.subheader("Audit history")
        _render_audit_history(
            client,
            record,
        )


def _render_registry_table(
    category: str,
    records: List[Dict[str, Any]],
) -> None:
    if not records:
        st.info(
            "No {} match the current Registry Management "
            "filters.".format(
                CATEGORY_LABELS[category].lower()
            )
        )
        return

    rows = []

    for record in records:
        row = {
            "ID": record.get("id"),
            "Name": record.get("name"),
            "Registry status": str(
                record.get("status") or ""
            ).title(),
            "Management status": (
                "Active"
                if record.get("is_active")
                else "Inactive"
            ),
            "Updated by": record.get("updated_by"),
        }

        if category == "company":
            row.update(
                {
                    "Company ID": record.get(
                        "external_id"
                    ),
                    "Registration": record.get(
                        "registration_number"
                    ),
                    "County": record.get("county"),
                }
            )

        elif category == "agency":
            row.update(
                {
                    "Agency ID": record.get(
                        "external_id"
                    ),
                    "Licence": record.get(
                        "licence_number"
                    ),
                    "Licence status": str(
                        record.get("licence_status")
                        or ""
                    ).title(),
                    "Destinations": record.get(
                        "authorised_destinations"
                    ),
                    "County": record.get("county"),
                }
            )

        else:
            row.update(
                {
                    "Kind": str(
                        record.get("blacklist_kind")
                        or ""
                    ).title(),
                    "Reason": record.get(
                        "blacklist_reason"
                    ),
                }
            )

        rows.append(row)

    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        height=min(
            520,
            38 * len(rows) + 40,
        ),
    )


def _render_category(
    client: HakikiHireAPIClient,
    category: str,
) -> None:
    search_column, inactive_column = st.columns(
        [3, 1]
    )

    with search_column:
        search = st.text_input(
            "Search {}".format(
                CATEGORY_LABELS[category].lower()
            ),
            placeholder=(
                "Search by name, identifier, "
                "registration, or licence"
            ),
            key="registry_search_{}".format(category),
        )

    with inactive_column:
        st.write("")
        include_inactive = st.checkbox(
            "Include inactive",
            value=False,
            key="registry_inactive_{}".format(category),
        )

    try:
        records = client.get_registry_records(
            category=category,
            search=search,
            include_inactive=include_inactive,
        )
    except (
        ValueError,
        HakikiHireAPIError,
    ) as error:
        st.error(
            getattr(
                error,
                "message",
                str(error),
            )
        )
        return

    st.caption(
        "{} record{} in this view".format(
            len(records),
            "" if len(records) == 1 else "s",
        )
    )

    _render_registry_table(
        category,
        records,
    )

    _render_create_form(
        client,
        category,
    )

    _render_edit_controls(
        client,
        category,
        records,
    )


def render_registry_management(
    client: HakikiHireAPIClient,
) -> None:
    """Render the persistent administrator Registry Management page."""

    reviewer = st.session_state.get(
        "reviewer_profile"
    ) or {}

    if reviewer.get("role") != "admin":
        st.error(
            "Administrator access is required."
        )
        return

    heading_column, return_column = st.columns(
        [5, 1]
    )

    with heading_column:
        st.header("Registry Management")
        st.caption(
            "Manage persistent company, recruitment agency, "
            "and blacklist reference records."
        )

    with return_column:
        if st.button(
            "Return",
            key="close_registry",
            width="stretch",
        ):
            st.session_state.registry_view = False
            st.session_state.pending_navigation = "Overview"
            st.rerun()

    st.warning(
        "The current registry contains simulated reference data. "
        "It is not an official government verification service."
    )

    success_message = st.session_state.pop(
        "registry_success_message",
        None,
    )

    if success_message:
        st.success(success_message)

    company_tab, agency_tab, blacklist_tab = st.tabs(
        [
            "Companies",
            "Recruitment agencies",
            "Blacklist",
        ]
    )

    with company_tab:
        _render_category(
            client,
            "company",
        )

    with agency_tab:
        _render_category(
            client,
            "agency",
        )

    with blacklist_tab:
        _render_category(
            client,
            "blacklist",
        )
