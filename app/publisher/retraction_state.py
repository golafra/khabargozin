"""Retraction FSM states."""

from enum import Enum


class RetractionState(str, Enum):
    DETECTED = "detected"
    CLASSIFY_AI = "classify_ai"
    UPDATE = "update"
    CORRECTION = "correction"
    RETRACTION = "retraction"
    IGNORE = "ignore"
