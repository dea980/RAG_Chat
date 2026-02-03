"""Pipeline runner that executes modular RAG pipelines."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Union

from .base import ModuleContext, PipelineModule, ModuleError
from .modules import GenerationModule, ReasoningModule, RetrieveModule


ModuleConfig = Union[PipelineModule, Dict[str, object]]


DEFAULT_REGISTRY = {
    "retrieve": RetrieveModule,
    "reasoning": ReasoningModule,
    "generation": GenerationModule,
}


class PipelineRunner:
    """Execute a sequence of pipeline modules."""

    def __init__(self, steps: Sequence[ModuleConfig], registry: Dict[str, type] | None = None):
        self.steps = steps
        self.registry = registry or DEFAULT_REGISTRY

    def _build_module(self, config: ModuleConfig) -> PipelineModule:
        if isinstance(config, PipelineModule):
            return config

        if not isinstance(config, dict):  # pragma: no cover - defensive guard
            raise ModuleError(f"Invalid module configuration: {config}")

        module_type = config.get("type")
        if module_type not in self.registry:
            raise ModuleError(f"Unknown module type: {module_type}")

        params = config.get("config", {}) or {}
        module_cls = self.registry[module_type]
        return module_cls(**params)

    def run(self, context: ModuleContext) -> ModuleContext:
        for config in self.steps:
            module = self._build_module(config)
            context = module.run(context)
        return context

