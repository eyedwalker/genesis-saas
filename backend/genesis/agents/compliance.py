"""Compliance framework prompts — SOC2, HIPAA, GDPR, PCI_DSS."""

from __future__ import annotations

from genesis.types import ComplianceFramework, ComplianceProfile

COMPLIANCE_PROMPTS: dict[ComplianceFramework, dict[str, str]] = {
    ComplianceFramework.SOC2: {
        "architecture": "\n\nSOC2 compliance: Implement audit logging for all data access. Use role-based access control. Encrypt data at rest and in transit.",
        "building": "\n\nSOC2 compliance: Include audit trails for create/update/delete. Log user actions with timestamps. Implement session timeout. Use parameterized queries.",
        "reviewing": "\n\nSOC2 review focus: Check for audit logging gaps, access control bypasses, unencrypted data storage, missing input validation.",
    },
    ComplianceFramework.HIPAA: {
        "architecture": "\n\nHIPAA compliance: Never store PHI in logs or error messages. Implement access controls per role. Encrypt all PHI at rest and in transit. Design for audit trail of all PHI access.",
        "building": "\n\nHIPAA compliance: NEVER log PHI (patient names, SSN, medical records). Use parameterized queries. Implement minimum necessary access. Include audit logging for all PHI access. Use encryption for storage.",
        "reviewing": "\n\nHIPAA review focus: Check for PHI in logs/errors, unencrypted PHI storage, overly broad data access, missing audit trails, insufficient access controls.",
    },
    ComplianceFramework.GDPR: {
        "architecture": "\n\nGDPR compliance: Implement data subject rights (access, erasure, portability). Design for consent management. Minimize data collection. Support data processing records.",
        "building": "\n\nGDPR compliance: Implement right to erasure endpoints. Record consent for data processing. Minimize personal data collection. Support data export in standard formats.",
        "reviewing": "\n\nGDPR review focus: Check for missing consent flows, data retention issues, lack of erasure capability, excessive data collection, missing privacy notices.",
    },
    ComplianceFramework.PCI_DSS: {
        "architecture": "\n\nPCI DSS compliance: Never store CVV/CVC. Tokenize card data. Use established payment processors. Implement network segmentation.",
        "building": "\n\nPCI DSS compliance: NEVER store CVV/CVC. Use payment processor tokens. Mask card numbers (show last 4 only). Implement strong authentication for payment flows.",
        "reviewing": "\n\nPCI DSS review focus: Check for raw card data storage, CVV logging, unencrypted payment data, missing tokenization, weak authentication in payment flows.",
    },
}


def get_compliance_prompt(
    stage: str,
    profile: ComplianceProfile | None,
) -> str:
    """Get compliance instructions for a pipeline stage."""
    if not profile or not profile.frameworks:
        return ""
    parts = []
    for framework in profile.frameworks:
        prompts = COMPLIANCE_PROMPTS.get(framework, {})
        if stage in prompts:
            parts.append(prompts[stage])
    return "".join(parts)
