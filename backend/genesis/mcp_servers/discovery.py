"""Discovery MCP Server — research and analysis tools for the interview phase.

Gives Claude's discovery assistants real tools to help users think:
- Analyze competitor websites and extract feature sets
- Research market size and trends
- Generate persona cards from user descriptions
- Create journey maps from workflow descriptions
- Validate business model assumptions
"""

from __future__ import annotations

import json
import re
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Competitor Analyzer ───────────────────────────────────────────────────────

@tool(
    "analyze_competitor",
    "Analyze a competitor product or website. Extracts features, pricing model, target audience, strengths/weaknesses, and differentiation opportunities.",
    {"url_or_description": str, "our_domain": str},
)
async def analyze_competitor(args: dict[str, Any]) -> dict[str, Any]:
    target = args["url_or_description"]
    domain = args.get("our_domain", "")

    # Build analysis framework
    analysis = {
        "competitor": target,
        "analysis_framework": {
            "features_to_identify": [
                "Core features (what's on the homepage hero)",
                "Pricing tiers and model (freemium, per-seat, usage-based)",
                "Target audience (who are they selling to)",
                "Integrations listed",
                "Social proof (customer logos, testimonials, case studies)",
                "Unique selling proposition (what they claim is different)",
            ],
            "competitive_dimensions": [
                "Price positioning (budget vs premium)",
                "Feature completeness (MVP vs full-featured)",
                "Ease of use (self-serve vs enterprise sales)",
                "Target market (SMB vs mid-market vs enterprise)",
                "Technical approach (cloud vs on-prem, API-first vs GUI)",
            ],
            "differentiation_opportunities": [
                "Underserved segments they ignore",
                "Features they lack that users complain about",
                "Better pricing model possibilities",
                "Technical advantages you could build",
                "Integration gaps",
            ],
        },
        "instructions": f"Analyze {target} using the framework above. "
        f"Compare against our {domain} product. "
        "Focus on actionable differentiation opportunities.",
    }

    return {
        "content": [{"type": "text", "text": json.dumps(analysis, indent=2)}]
    }


# ── Persona Generator ─────────────────────────────────────────────────────────

@tool(
    "generate_persona",
    "Generate a detailed user persona card from a description. Includes demographics, goals, frustrations, tech proficiency, and jobs-to-be-done.",
    {"description": str, "domain": str},
)
async def generate_persona(args: dict[str, Any]) -> dict[str, Any]:
    description = args["description"]
    domain = args.get("domain", "")

    persona_template = {
        "template": "User Persona Card",
        "sections": {
            "demographics": {
                "fields": ["Name (fictional)", "Role/Title", "Age range", "Company size", "Industry"],
                "purpose": "Make the persona concrete and relatable",
            },
            "goals": {
                "fields": ["Primary goal", "Secondary goals", "Success metrics"],
                "purpose": "What does this person need to accomplish?",
            },
            "frustrations": {
                "fields": ["Current pain points", "Workarounds they use", "What they've tried before"],
                "purpose": "Why are they looking for a new solution?",
            },
            "jobs_to_be_done": {
                "fields": [
                    "Functional job: What task are they trying to complete?",
                    "Emotional job: How do they want to feel?",
                    "Social job: How do they want to be perceived?",
                ],
                "purpose": "Understand the full job, not just the functional need",
            },
            "context": {
                "fields": [
                    "When does this need arise? (trigger moment)",
                    "Where are they when it happens? (environment)",
                    "Who else is involved? (stakeholders)",
                    "How often? (frequency)",
                ],
                "purpose": "Understand the situation, not just the person",
            },
            "tech_proficiency": {
                "fields": ["Technical skill level (1-5)", "Tools they currently use", "Comfort with new software"],
                "purpose": "Design the right level of complexity",
            },
            "buying_criteria": {
                "fields": ["Must-haves", "Nice-to-haves", "Deal-breakers", "Budget authority"],
                "purpose": "Understand what drives the purchase decision",
            },
        },
        "input_description": description,
        "domain": domain,
        "instructions": "Generate a complete persona card using this template. Fill in realistic details based on the description and domain. Make it specific enough to guide design decisions.",
    }

    return {
        "content": [{"type": "text", "text": json.dumps(persona_template, indent=2)}]
    }


# ── Journey Map Builder ───────────────────────────────────────────────────────

@tool(
    "build_journey_map",
    "Create a user journey map from a workflow description. Maps stages, actions, emotions, pain points, and opportunities at each step.",
    {"workflow": str, "persona": str},
)
async def build_journey_map(args: dict[str, Any]) -> dict[str, Any]:
    workflow = args["workflow"]
    persona = args.get("persona", "User")

    journey_template = {
        "template": "User Journey Map",
        "persona": persona,
        "stage_template": {
            "per_stage": {
                "stage_name": "Name of this phase",
                "user_action": "What the user does",
                "touchpoints": "What systems/people they interact with",
                "emotion": "How they feel (frustrated/neutral/satisfied/delighted)",
                "pain_points": "What's difficult or annoying",
                "opportunities": "Where we can improve the experience",
                "metrics": "How we'd measure success at this stage",
            },
        },
        "standard_stages": [
            "Awareness — How they discover they have this problem",
            "Research — How they look for solutions",
            "Decision — How they choose a solution",
            "Onboarding — First experience with the product",
            "Regular Use — Day-to-day usage",
            "Advanced Use — Power user behaviors",
            "Advocacy — How they recommend to others (or don't)",
        ],
        "workflow_description": workflow,
        "instructions": f"Map the journey for {persona} through: {workflow}. "
        "Use the stage template to analyze each step. "
        "Focus on pain points and opportunities — these drive product decisions.",
    }

    return {
        "content": [{"type": "text", "text": json.dumps(journey_template, indent=2)}]
    }


# ── Hypothesis Validator ──────────────────────────────────────────────────────

@tool(
    "validate_hypothesis",
    "Structure and validate a business hypothesis. Identifies riskiest assumptions, suggests experiments, and defines success criteria.",
    {"hypothesis": str, "target_market": str},
)
async def validate_hypothesis(args: dict[str, Any]) -> dict[str, Any]:
    hypothesis = args["hypothesis"]
    market = args.get("target_market", "")

    validation = {
        "hypothesis": hypothesis,
        "target_market": market,
        "framework": {
            "hypothesis_format": "We believe that [capability] will result in [outcome] for [persona]",
            "validation_checklist": [
                "Is the problem validated (evidence, not assumption)?",
                "Is the persona specific (not 'users')?",
                "Is the outcome measurable?",
                "Is there a timeline for validation?",
                "Are kill criteria defined (when to stop)?",
            ],
            "risk_assessment": {
                "value_risk": "Will customers choose to use/pay for this?",
                "usability_risk": "Can customers figure out how to use it?",
                "feasibility_risk": "Can we build this with available resources?",
                "viability_risk": "Does this work for the business?",
            },
            "experiment_options": [
                {"type": "Fake Door", "effort": "Low", "description": "Landing page with signup to measure demand"},
                {"type": "Concierge", "effort": "Medium", "description": "Do it manually for first customers"},
                {"type": "Wizard of Oz", "effort": "Medium", "description": "Fake the automation behind the scenes"},
                {"type": "Prototype", "effort": "Medium-High", "description": "Build a minimal interactive version"},
                {"type": "MVP", "effort": "High", "description": "Ship the minimum viable product"},
            ],
            "success_metrics": {
                "leading": "Early signals (signups, demo requests, time-on-page)",
                "lagging": "Business outcomes (revenue, retention, NPS)",
                "actionable": "Metrics that drive decisions, not vanity metrics",
            },
        },
        "instructions": "Analyze this hypothesis. Identify the riskiest assumption, suggest the cheapest experiment to test it, and define clear pass/fail criteria.",
    }

    return {
        "content": [{"type": "text", "text": json.dumps(validation, indent=2)}]
    }


# ── Scope Shaper ──────────────────────────────────────────────────────────────

@tool(
    "shape_scope",
    "Help define and hammer scope for a project. Separates must-haves from nice-to-haves, identifies rabbit holes, and defines no-gos.",
    {"features": str, "appetite": str},
)
async def shape_scope(args: dict[str, Any]) -> dict[str, Any]:
    features = args["features"]
    appetite = args.get("appetite", "6 weeks")

    scope = {
        "input_features": features,
        "appetite": appetite,
        "framework": {
            "scope_categories": {
                "must_have": "Without these, the product doesn't solve the core problem",
                "should_have": "Important but could ship without them in v1",
                "could_have": "Nice-to-have, include only if time permits",
                "wont_have": "Explicitly out of scope for this iteration",
            },
            "rabbit_hole_checklist": [
                "Does any feature require technology we haven't used before?",
                "Does any feature require integration with a third-party API?",
                "Does any feature have unclear requirements that could expand?",
                "Does any feature require complex UI that could take forever to polish?",
                "Does any feature require data migration or schema changes?",
            ],
            "scope_hammering_questions": [
                "What's the simplest version that solves the core problem?",
                "What can we hardcode that we're tempted to make configurable?",
                "What edge cases can we handle with an error message instead of a feature?",
                "What admin features can be database queries instead of UI?",
                "What can be a V2 feature?",
            ],
            "appetite_options": {
                "1_week": "Quick fix or small enhancement",
                "2_weeks": "Small batch — well-understood problem",
                "6_weeks": "Big batch — complex but bounded problem",
                "beyond": "Consider breaking into multiple bets",
            },
        },
        "instructions": f"Analyze these features for a {appetite} appetite. "
        "Categorize each feature, identify rabbit holes, and hammer scope to fit the appetite. "
        "Be aggressive about cutting — it's better to ship less that works than more that doesn't.",
    }

    return {
        "content": [{"type": "text", "text": json.dumps(scope, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

discovery_server = create_sdk_mcp_server(
    name="genesis-discovery",
    version="1.0.0",
    tools=[analyze_competitor, generate_persona, build_journey_map, validate_hypothesis, shape_scope],
)
