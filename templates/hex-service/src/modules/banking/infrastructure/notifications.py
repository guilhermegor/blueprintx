from __future__ import annotations

from ..domain.ports import NotificationPort


class EmailNotificationAdapter(NotificationPort):
    def send_balance_alert(self, to_email: str, current_balance: float, threshold: float) -> None:
        print(f"Email -> {to_email}: balance ${current_balance:.2f} is below ${threshold:.2f}")
