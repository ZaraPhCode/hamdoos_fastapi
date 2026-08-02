"""OperationResult: mirrors the .NET OperationResult from 0_Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class OperationResult(Generic[T]):
    is_succeeded: bool = False
    message: str = ""
    data: T | None = None
    redirect_url: str | None = None

    @classmethod
    def success(cls, message: str = "Operation completed successfully", data: Any = None) -> OperationResult:
        return cls(is_succeeded=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str = "Operation failed", data: Any = None) -> OperationResult:
        return cls(is_succeeded=False, message=message, data=data)