"""Pydantic models — ported from wabah/src/lib/genesis/types.ts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class PipelineStage(str, Enum):
    REQUIREMENTS = "requirements"
    REQUIREMENTS_REVIEW = "requirements_review"
    DESIGN = "design"
    DESIGN_REVIEW = "design_review"
    INTERVIEWING = "interviewing"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    BUILDING = "building"
    REVIEWING = "reviewing"
    CODE_REVIEW = "code_review"
    QA_REVIEW = "qa_review"
    DELIVERABLE_REVIEW = "deliverable_review"
    APPROVED = "approved"
    EXPORTED = "exported"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class ApprovalType(str, Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    PLAN = "plan"
    CODE = "code"
    QA = "qa"
    DELIVERABLE = "deliverable"


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ProjectRole(str, Enum):
    OWNER = "owner"
    BA = "ba"
    DESIGNER = "designer"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    QA = "qa"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class GenesisAction(str, Enum):
    CREATE_FACTORY = "create_factory"
    EDIT_FACTORY = "edit_factory"
    DELETE_FACTORY = "delete_factory"
    CREATE_BUILD = "create_build"
    ADVANCE_BUILD = "advance_build"
    APPROVE_REQUIREMENTS = "approve_requirements"
    APPROVE_DESIGN = "approve_design"
    APPROVE_PLAN = "approve_plan"
    APPROVE_CODE = "approve_code"
    APPROVE_QA = "approve_qa"
    APPROVE_DELIVERABLE = "approve_deliverable"
    EXPORT = "export"
    DEPLOY = "deploy"
    MANAGE_ASSISTANTS = "manage_assistants"
    MANAGE_MEMBERS = "manage_members"
    COMMENT = "comment"
    VIEW = "view"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AssistantDomain(str, Enum):
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    COMPLIANCE = "compliance"
    INFRASTRUCTURE = "infrastructure"
    FRONTEND = "frontend"
    BUSINESS = "business"
    PROJECT = "project"
    BA = "ba"


class ModelTier(str, Enum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


class ComplianceFramework(str, Enum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"


class WorkItemType(str, Enum):
    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    BUG = "bug"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"


class WorkItemStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class WorkItemPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocType(str, Enum):
    PRD = "prd"
    ADR = "adr"
    OPENAPI = "openapi"
    DATA_MODEL = "data_model"
    RUNBOOK = "runbook"
    README = "readme"
    USER_STORIES = "user_stories"


class DocFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    MERMAID = "mermaid"


class ConnectorType(str, Enum):
    JSON = "json"
    GITHUB_ISSUES = "github_issues"
    JIRA = "jira"
    LINEAR = "linear"


class DeploymentTier(str, Enum):
    SHARED = "shared"
    DEDICATED = "dedicated"
    SELF_HOSTED = "self_hosted"
    AMPLIFY = "amplify"
    SST = "sst"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    BUILDING_IMAGE = "building_image"
    PUSHING_IMAGE = "pushing_image"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DESTROYED = "destroyed"


class FactoryStatus(str, Enum):
    SETUP = "setup"
    ACTIVE = "active"
    ARCHIVED = "archived"


# ── Assistant Config ───────────────────────────────────────────────────────────


class Pattern(BaseModel):
    name: str
    description: str
    criteria: str


class AssistantConfig(BaseModel):
    id: str
    name: str
    domain: AssistantDomain
    description: str
    system_prompt: str = Field(alias="systemPrompt", default="")
    weight: float = 1.0
    is_active: bool = Field(alias="isActive", default=True)
    patterns: list[Pattern] = []

    model_config = {"populate_by_name": True}


# ── Review ─────────────────────────────────────────────────────────────────────


class Finding(BaseModel):
    title: str
    severity: Severity
    assistant_id: str = Field(alias="assistantId", default="")
    pattern: str = ""
    description: str = ""
    location: str | None = None
    recommendation: str = ""
    code_example: str | None = Field(alias="codeExample", default=None)

    model_config = {"populate_by_name": True}


class ReviewSynthesis(BaseModel):
    vibe_score: int = Field(alias="vibeScore", default=0)
    grade: str = ""
    summary: str = ""
    by_severity: dict[str, int] = Field(alias="bySeverity", default_factory=dict)
    by_assistant: dict[str, int] = Field(alias="byAssistant", default_factory=dict)
    top_issues: list[str] = Field(alias="topIssues", default_factory=list)
    recommendations: list[str] = []

    model_config = {"populate_by_name": True}


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"
    assistant_ids: list[str] = Field(alias="assistantIds", default_factory=list)
    tenant_id: str = Field(alias="tenantId", default="")
    context: str = ""
    model_config_override: dict[str, str] | None = Field(
        alias="modelConfig", default=None
    )

    model_config = {"populate_by_name": True}


class ReviewResponse(BaseModel):
    findings: list[Finding] = []
    synthesis: ReviewSynthesis = Field(default_factory=ReviewSynthesis)
    assistants_used: list[str] = Field(alias="assistantsUsed", default_factory=list)
    token_usage: dict[str, int] = Field(alias="tokenUsage", default_factory=dict)

    model_config = {"populate_by_name": True}


# ── Interview ──────────────────────────────────────────────────────────────────


class InterviewQuestion(BaseModel):
    question: str
    category: str = ""
    answer: str | None = None


class InterviewResult(BaseModel):
    questions: list[InterviewQuestion] = []
    summary: str = ""
    suggested_domain: str = Field(alias="suggestedDomain", default="")
    suggested_tech_stack: str = Field(alias="suggestedTechStack", default="")
    suggested_assistants: list[str] = Field(
        alias="suggestedAssistants", default_factory=list
    )

    model_config = {"populate_by_name": True}


# ── Requirements ───────────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    id: str
    given: str
    when_: str = Field(alias="when")
    then: str

    model_config = {"populate_by_name": True}


class UserStory(BaseModel):
    id: str
    epic: str = ""
    title: str = ""
    persona: str = ""
    capability: str = ""
    benefit: str = ""
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        alias="acceptanceCriteria", default_factory=list
    )
    priority: str = ""

    model_config = {"populate_by_name": True}


class RequirementsResult(BaseModel):
    summary: str = ""
    epics: list[str] = []
    stories: list[UserStory] = []
    non_functional: list[str] = Field(alias="nonFunctional", default_factory=list)
    assumptions: list[str] = []
    out_of_scope: list[str] = Field(alias="outOfScope", default_factory=list)

    model_config = {"populate_by_name": True}


# ── Design ─────────────────────────────────────────────────────────────────────


class PageSpec(BaseModel):
    name: str
    route: str = ""
    description: str = ""
    layout: str = ""
    components: list[str] = []
    user_story_ids: list[str] = Field(alias="userStoryIds", default_factory=list)

    model_config = {"populate_by_name": True}


class ComponentSpec(BaseModel):
    id: str
    name: str
    description: str = ""
    props: list[str] = []
    states: list[str] = []
    interactions: list[str] = []


class StyleTokens(BaseModel):
    colors: dict[str, str] = {}
    spacing: dict[str, str] = {}
    typography: dict[str, str] = {}
    border_radius: dict[str, str] = Field(alias="borderRadius", default_factory=dict)

    model_config = {"populate_by_name": True}


class WireframeDesc(BaseModel):
    page_name: str = Field(alias="pageName", default="")
    description: str = ""
    ascii_wireframe: str | None = Field(alias="asciiWireframe", default=None)

    model_config = {"populate_by_name": True}


class DesignResult(BaseModel):
    pages: list[PageSpec] = []
    components: list[ComponentSpec] = []
    style_tokens: StyleTokens = Field(
        alias="styleTokens", default_factory=StyleTokens
    )
    navigation_flow: str = Field(alias="navigationFlow", default="")
    wireframe_descriptions: list[WireframeDesc] = Field(
        alias="wireframeDescriptions", default_factory=list
    )

    model_config = {"populate_by_name": True}


# ── Plan ───────────────────────────────────────────────────────────────────────


class PlanStep(BaseModel):
    file_path: str = Field(alias="filePath", default="")
    description: str = ""
    dependencies: list[str] = []

    model_config = {"populate_by_name": True}


class ImplementationPlan(BaseModel):
    feature_name: str = Field(alias="featureName", default="")
    description: str = ""
    business_rules: list[str] = Field(alias="businessRules", default_factory=list)
    steps: list[PlanStep] = []
    api_endpoints: list[str] = Field(alias="apiEndpoints", default_factory=list)
    database_changes: list[str] = Field(alias="databaseChanges", default_factory=list)
    estimated_complexity: str = Field(alias="estimatedComplexity", default="medium")
    suggested_assistants: list[str] = Field(
        alias="suggestedAssistants", default_factory=list
    )

    model_config = {"populate_by_name": True}


# ── Build ──────────────────────────────────────────────────────────────────────


class BuildResult(BaseModel):
    code: str = ""
    file_map: dict[str, str] = Field(alias="fileMap", default_factory=dict)
    files_created: list[str] = Field(alias="filesCreated", default_factory=list)
    explanation: str = ""

    model_config = {"populate_by_name": True}


# ── Testing & DevOps ──────────────────────────────────────────────────────────


class TestSuiteResult(BaseModel):
    test_files: dict[str, str] = Field(alias="testFiles", default_factory=dict)
    config_files: dict[str, str] = Field(alias="configFiles", default_factory=dict)
    test_framework: str = Field(alias="testFramework", default="pytest")
    test_count: int = Field(alias="testCount", default=0)
    coverage_targets: dict[str, int] = Field(
        alias="coverageTargets", default_factory=dict
    )

    model_config = {"populate_by_name": True}


class DevOpsResult(BaseModel):
    files: dict[str, str] = {}
    platform: str = "docker"
    commands: dict[str, str] = {}
    environment_vars: list[str] = Field(
        alias="environmentVars", default_factory=list
    )
    ports: list[int] = []

    model_config = {"populate_by_name": True}


# ── Model Configuration ──────────────────────────────────────────────────────


class ModelConfig(BaseModel):
    interviewer: ModelTier = ModelTier.HAIKU
    requirements: ModelTier = ModelTier.SONNET
    design: ModelTier = ModelTier.SONNET
    planning: ModelTier = ModelTier.SONNET
    building: ModelTier = ModelTier.SONNET
    reviewing: ModelTier = ModelTier.SONNET
    testing: ModelTier = ModelTier.SONNET
    devops: ModelTier = ModelTier.HAIKU
    docs: ModelTier = ModelTier.HAIKU


# ── Compliance & Standards ────────────────────────────────────────────────────


class ComplianceProfile(BaseModel):
    frameworks: list[ComplianceFramework] = []
    data_classification: str = Field(alias="dataClassification", default="internal")
    requires_encryption_at_rest: bool = Field(
        alias="requiresEncryptionAtRest", default=False
    )
    requires_audit_logging: bool = Field(
        alias="requiresAuditLogging", default=False
    )

    model_config = {"populate_by_name": True}


class CodingStandards(BaseModel):
    preset: str = "startup"
    lint_rules: list[str] = Field(alias="lintRules", default_factory=list)
    naming_convention: str = Field(alias="namingConvention", default="snake_case")
    max_file_length: int = Field(alias="maxFileLength", default=500)
    require_docstrings: bool = Field(alias="requireDocstrings", default=False)
    test_coverage: int = Field(alias="testCoverage", default=80)

    model_config = {"populate_by_name": True}


class FactoryContext(BaseModel):
    domain: str = ""
    tech_stack: str = Field(alias="techStack", default="")
    name: str = ""
    model_config_override: ModelConfig | None = Field(
        alias="modelConfig", default=None
    )
    compliance_profile: ComplianceProfile | None = Field(
        alias="complianceProfile", default=None
    )
    coding_standards: CodingStandards | None = Field(
        alias="codingStandards", default=None
    )
    assistant_overrides: dict[str, Any] | None = Field(
        alias="assistantOverrides", default=None
    )

    model_config = {"populate_by_name": True}


# ── Permissions mapping ──────────────────────────────────────────────────────


ROLE_PERMISSIONS: dict[ProjectRole, set[GenesisAction]] = {
    ProjectRole.OWNER: set(GenesisAction),
    ProjectRole.BA: {
        GenesisAction.CREATE_BUILD,
        GenesisAction.ADVANCE_BUILD,
        GenesisAction.APPROVE_REQUIREMENTS,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.DESIGNER: {
        GenesisAction.ADVANCE_BUILD,
        GenesisAction.APPROVE_DESIGN,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.ARCHITECT: {
        GenesisAction.CREATE_BUILD,
        GenesisAction.ADVANCE_BUILD,
        GenesisAction.APPROVE_PLAN,
        GenesisAction.APPROVE_CODE,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.ENGINEER: {
        GenesisAction.CREATE_BUILD,
        GenesisAction.ADVANCE_BUILD,
        GenesisAction.APPROVE_CODE,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.QA: {
        GenesisAction.ADVANCE_BUILD,
        GenesisAction.APPROVE_QA,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.REVIEWER: {
        GenesisAction.APPROVE_CODE,
        GenesisAction.APPROVE_DELIVERABLE,
        GenesisAction.COMMENT,
        GenesisAction.VIEW,
    },
    ProjectRole.VIEWER: {GenesisAction.VIEW},
}
