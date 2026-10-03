"""Calculation policy interface. Each published version must never change meaning."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.assessment import AssessmentBreakdown
from app.domain.profile import Profile


class CalculationPolicy(ABC):
    version: str

    @abstractmethod
    def calculate(self, profile: Profile) -> AssessmentBreakdown:
        """Pure function of the profile: no I/O, no clock, no randomness."""
