"""Base classes and utilities for isolated failure injection in test environments.

All failure injection must be strictly contained within test execution
contexts and must never leak into persistent state or production configurations.
"""
from __future__ import annotations

import abc
from typing import Any, Callable, Dict, Generator, List, Optional


class BaseFaultInjector(abc.ABC):
    """Abstract base class for all failure injectors.

    Provides context manager semantics and ensures that any injected
    fault is automatically and safely reverted when exiting the context.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self.is_active = False

    @abc.abstractmethod
    def activate(self) -> None:
        """Inject the failure mode."""
        pass

    @abc.abstractmethod
    def deactivate(self) -> None:
        """Cleanly revert the failure mode and restore original state."""
        pass

    def __enter__(self) -> "BaseFaultInjector":
        if self.is_active:
            raise RuntimeError(f"Fault injector {self.name!r} is already active.")
        try:
            self.activate()
        except BaseException as activation_error:
            try:
                self.deactivate()
            except BaseException as cleanup_error:
                raise activation_error from cleanup_error
            raise
        self.is_active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.deactivate()
        finally:
            self.is_active = False
