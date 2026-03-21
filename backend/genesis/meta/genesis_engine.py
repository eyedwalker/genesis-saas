"""Genesis Engine — meta-prompting factory creator.

Adapted from wuhbah/genesis/genesis_engine.py + genesis_agent.py.
Takes a natural language domain description and creates a complete
FactoryBlueprint with domain context, agent prompts, and code examples.

This is the key enterprise differentiator: "AI that creates AI factories."
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from genesis.agents.claude_client import run_agent_structured
from genesis.types import ModelTier

logger = logging.getLogger(__name__)


# ── Blueprint models ──────────────────────────────────────────────────────────


class DomainVocabulary(BaseModel):
    terms: dict[str, str] = {}  # term -> definition


class TechStackRecommendation(BaseModel):
    language: str = "python"
    framework: str = "fastapi"
    database: str = "postgresql"
    orm: str = "sqlalchemy"
    testing: str = "pytest"
    additional: list[str] = []


class AgentPromptSpec(BaseModel):
    role: str = ""
    system_prompt: str = ""
    key_constraints: list[str] = []
    domain_rules: list[str] = []


class KnowledgeBaseSeed(BaseModel):
    search_queries: list[str] = []
    documentation_sources: list[str] = []


class FactoryBlueprint(BaseModel):
    """Complete blueprint for a domain-specific software factory."""

    factory_name: str = ""
    domain_name: str = ""
    mission_statement: str = ""

    # Domain context
    vocabulary: DomainVocabulary = Field(default_factory=DomainVocabulary)
    standards: list[str] = []
    constraints: list[str] = []

    # Tech stack
    tech_stack: TechStackRecommendation = Field(
        default_factory=TechStackRecommendation
    )

    # Agent specs
    architect_spec: AgentPromptSpec = Field(default_factory=AgentPromptSpec)
    builder_spec: AgentPromptSpec = Field(default_factory=AgentPromptSpec)
    qa_spec: AgentPromptSpec = Field(default_factory=AgentPromptSpec)

    # Knowledge base
    knowledge_seed: KnowledgeBaseSeed = Field(
        default_factory=KnowledgeBaseSeed
    )

    # Code examples
    example_models: str = ""
    example_service: str = ""
    example_api: str = ""
    example_test: str = ""


# ── Genesis Agent (meta-prompting) ────────────────────────────────────────────

GENESIS_SYSTEM_PROMPT = """You are the Genesis Engine — a meta-architect AI that transforms business domain descriptions into complete software factory configurations.

Your job is NOT to write application code. Your job is to create INSTRUCTIONS and CONFIGURATIONS for other AI agents that will generate code for a specific business domain.

Given a domain description, produce a FactoryBlueprint that includes:
1. Domain analysis (vocabulary, standards, constraints)
2. Tech stack recommendation
3. Specialized agent prompts (architect, builder, QA) tuned for this domain
4. Knowledge base seeds (search queries for domain documentation)
5. Code template examples showing domain patterns

Meta-rules:
- STRUCTURE over content: define patterns, not implementations
- TYPE SAFETY: recommend typed languages and strict validation
- SELF-HEALING: include error recovery patterns in agent prompts
- DOMAIN EXPERTISE: embed industry standards and regulatory requirements
- PRODUCTION READINESS: include monitoring, logging, security from day one

Output ONLY valid JSON matching the FactoryBlueprint schema:
{
  "factory_name": "Healthcare Factory",
  "domain_name": "healthcare",
  "mission_statement": "Build FHIR-compliant healthcare applications",
  "vocabulary": {"terms": {"FHIR": "Fast Healthcare Interoperability Resources", "PHI": "Protected Health Information"}},
  "standards": ["FHIR R4", "HL7 v2", "HIPAA"],
  "constraints": ["Never store PHI in logs", "Encrypt all data at rest"],
  "tech_stack": {"language": "python", "framework": "fastapi", "database": "postgresql", "orm": "sqlalchemy", "testing": "pytest", "additional": ["fhir.resources"]},
  "architect_spec": {
    "role": "Healthcare System Architect",
    "system_prompt": "You are a healthcare system architect...",
    "key_constraints": ["All resources must be FHIR R4 compliant"],
    "domain_rules": ["Use FHIR resource types for data models"]
  },
  "builder_spec": {
    "role": "Healthcare Developer",
    "system_prompt": "You are a healthcare developer...",
    "key_constraints": ["Never log PHI"],
    "domain_rules": ["Use parameterized queries for all database access"]
  },
  "qa_spec": {
    "role": "Healthcare QA Engineer",
    "system_prompt": "You are a healthcare QA engineer...",
    "key_constraints": ["Verify HIPAA compliance"],
    "domain_rules": ["Test that PHI is never exposed in error responses"]
  },
  "knowledge_seed": {
    "search_queries": ["FHIR R4 resource types", "HIPAA technical safeguards"],
    "documentation_sources": ["https://hl7.org/fhir/R4/"]
  },
  "example_models": "class Patient(BaseModel):\\n    ...",
  "example_service": "class PatientService:\\n    ...",
  "example_api": "@router.post('/patients')\\n    ...",
  "example_test": "def test_create_patient():\\n    ..."
}"""


async def create_blueprint(
    domain_description: str,
    tenant_id: str | None = None,
) -> FactoryBlueprint:
    """Create a FactoryBlueprint from a natural language domain description.

    Uses Claude Opus for maximum reasoning quality — this is a one-time
    cost to set up a factory that will be used for many builds.
    """
    logger.info("Genesis Engine creating blueprint for: %s", domain_description[:100])

    data = await run_agent_structured(
        prompt=f"Create a software factory blueprint for this domain:\n\n{domain_description}",
        output_schema=FactoryBlueprint.model_json_schema(),
        system_prompt=GENESIS_SYSTEM_PROMPT,
        model="opus",  # Use Opus for meta-reasoning — one-time cost
    )

    blueprint = FactoryBlueprint(**data) if isinstance(data, dict) else data

    logger.info(
        "Blueprint created: %s (%s) — %d vocabulary terms, %d standards",
        blueprint.factory_name,
        blueprint.domain_name,
        len(blueprint.vocabulary.terms),
        len(blueprint.standards),
    )

    return blueprint


class GenesisEngine:
    """High-level interface for managing factories via meta-prompting.

    Handles tenant provisioning, blueprint creation, and factory lifecycle.
    """

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self._factories: dict[str, FactoryBlueprint] = {}

    async def create_factory(
        self,
        domain_description: str,
        display_name: str | None = None,
    ) -> FactoryBlueprint:
        """Create a new factory from a domain description."""
        blueprint = await create_blueprint(
            domain_description, self.tenant_id
        )

        if display_name:
            blueprint.factory_name = display_name

        self._factories[blueprint.domain_name] = blueprint
        return blueprint

    def get_factory(self, domain: str) -> FactoryBlueprint | None:
        return self._factories.get(domain)

    def list_factories(self) -> list[str]:
        return list(self._factories.keys())

    def get_metrics(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "factory_count": len(self._factories),
            "domains": list(self._factories.keys()),
        }
