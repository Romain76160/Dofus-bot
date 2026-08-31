from __future__ import annotations

from app.config import settings


class InputDisabledError(RuntimeError):
    pass


class InputController:
    """
    Boundary for graphical actions.

    The concrete Windows mouse/keyboard adapter will be added only after
    observation/calibration is reliable.
    """

    def ensure_enabled(self) -> None:
        if not settings.allow_input:
            raise InputDisabledError(
                "Graphical input is disabled. Set ALLOW_INPUT=true explicitly."
            )

    def click(self, x: int, y: int) -> None:
        self.ensure_enabled()
        raise NotImplementedError("No concrete input adapter configured yet.")

    def press(self, key: str) -> None:
        self.ensure_enabled()
        raise NotImplementedError("No concrete input adapter configured yet.")
