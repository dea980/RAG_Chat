"""Abstract base classes and data structures for modular RAG pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class ModuleError(Exception):
    """Exception raised when a pipeline module fails."""
    


@dataclass
class ModuleContext:
    """Shared state that flows through pipeline modules."""
    question: str
    session_id: str
    user_id: str
    history_handler: Optional[Callable[[str], Any]] = None
    history: Optional[Any] = None
    context_text: str = ""
    images: List[str] = field(default_factory=list)
    reasoning: Optional[str] = None
    response: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class PipelineModule(ABC):
    """Base interface for all pipeline modules."""

    name: str = "base"

    @abstractmethod
    def run(self, context: ModuleContext) -> ModuleContext:
        """Execute module logic and return the updated context."""
        

