"""Domain exceptions.

Services raise these instead of ``HTTPException``; the HTTP layer maps them to
status codes (see ARCHITECTURE §2).
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all domain errors."""


class ValidationError(AppError):
    """Input cannot be processed by the domain layer."""


class NotFoundError(AppError):
    """Requested entity does not exist."""


class ScanNotFoundError(NotFoundError):
    """Requested scan run does not exist."""


class RepositoryNotFoundError(NotFoundError):
    """Requested repository does not exist."""
