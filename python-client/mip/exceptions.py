"""Public exception types for the MIP client."""

from __future__ import annotations


class MipError(Exception):
    """Base class for MIP client errors."""


class MipConfigurationError(MipError):
    """Raised when required client configuration is missing."""


class MipBackendError(MipError):
    """Raised when platform-backend returns an error or invalid response."""


class MipAlgorithmNotAvailable(MipError):
    """Raised when a requested algorithm is not available."""


class UnsupportedOperationError(MipError):
    """Raised when a result cannot support the requested local operation."""
