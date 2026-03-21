"""Model resolver — maps pipeline stages to Anthropic model IDs."""

from __future__ import annotations

from genesis.types import ModelConfig, ModelTier

MODEL_IDS: dict[ModelTier, str] = {
    ModelTier.HAIKU: "claude-haiku-4-5-20251001",
    ModelTier.SONNET: "claude-sonnet-4-6-20250610",
    ModelTier.OPUS: "claude-opus-4-6-20250610",
}

DEFAULT_MODEL_CONFIG = ModelConfig()

MODEL_PRESETS: dict[str, ModelConfig] = {
    "budget": ModelConfig(
        interviewer=ModelTier.HAIKU, requirements=ModelTier.HAIKU,
        design=ModelTier.HAIKU, planning=ModelTier.HAIKU,
        building=ModelTier.HAIKU, reviewing=ModelTier.HAIKU,
        testing=ModelTier.HAIKU, devops=ModelTier.HAIKU, docs=ModelTier.HAIKU,
    ),
    "standard": ModelConfig(),
    "premium": ModelConfig(
        planning=ModelTier.OPUS, building=ModelTier.OPUS,
        reviewing=ModelTier.OPUS,
    ),
}


def resolve_model(
    stage: str,
    config: ModelConfig | None = None,
) -> str:
    """Resolve a pipeline stage to the correct Anthropic model ID."""
    cfg = config or DEFAULT_MODEL_CONFIG
    tier = getattr(cfg, stage, ModelTier.SONNET)
    return MODEL_IDS.get(tier, MODEL_IDS[ModelTier.SONNET])


# SDK tier names for Claude Agent SDK (uses "sonnet", "opus", "haiku")
SDK_TIER_NAMES: dict[ModelTier, str] = {
    ModelTier.HAIKU: "haiku",
    ModelTier.SONNET: "sonnet",
    ModelTier.OPUS: "opus",
}


def resolve_model_tier(
    stage: str,
    config: ModelConfig | None = None,
) -> str:
    """Resolve a pipeline stage to a Claude Agent SDK model tier name."""
    cfg = config or DEFAULT_MODEL_CONFIG
    tier = getattr(cfg, stage, ModelTier.SONNET)
    return SDK_TIER_NAMES.get(tier, "sonnet")
