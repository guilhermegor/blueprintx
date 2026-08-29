"""E-mail orchestration seam — backend-agnostic dispatch policy, sending, and body HTML-ization.

Sibling package to ``utils/ms_office/`` (blueprintx#118/#121): where ``ms_office/`` holds
*vendor* behaviour (what Outlook specifically does), this package holds capabilities every
e-mail backend needs — Outlook, SMTP, or any future one. Nothing here imports a concrete
backend; :mod:`utils.email.sender` is injected the sender callable instead.
"""
