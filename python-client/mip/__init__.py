"""Notebook-facing MIP Python client."""

from __future__ import annotations

from .analysis import AnalysisSet
from .client import Client
from .display import to_frame
from .exceptions import MipAlgorithmNotAvailable
from .exceptions import MipBackendError
from .exceptions import MipConfigurationError
from .exceptions import MipError
from .exceptions import UnsupportedOperationError
from .pipeline import Pipeline

__all__ = [
    "AnalysisSet",
    "Client",
    "MipAlgorithmNotAvailable",
    "MipBackendError",
    "MipConfigurationError",
    "MipError",
    "Pipeline",
    "UnsupportedOperationError",
    "to_frame",
]
