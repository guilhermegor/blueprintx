"""Vendor-scoped Microsoft Office helpers — one module per app (blueprintx#118).

``outlook_gateway.py`` (Outlook desktop automation) and ``excel_sheet_names.py`` (Excel
worksheet-name rules) group here because both are *vendor behaviour*: what a specific Office
app does, not a capability the vendor merely implements. Backend-agnostic e-mail capabilities
(dispatch policy, body HTML-ization) live in the sibling ``utils/email/`` package instead — a
port must not carry logic one adapter happens to implement.
"""
