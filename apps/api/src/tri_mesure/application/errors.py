"""Application errors, independent of any transport (HTTP, CLI, worker)."""


class AppError(Exception):
    status = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


class Invalid(AppError):
    status = 422
