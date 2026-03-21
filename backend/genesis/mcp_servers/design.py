"""Design MCP Server — real design tools for building beautiful apps.

Gives Claude's design assistants actual tools:
- Generate color palettes from a brand color (shade scales, semantic colors)
- Create design token configs (Tailwind, CSS custom properties)
- Suggest component libraries for a tech stack
- Generate typography scales
- Audit visual consistency
"""

from __future__ import annotations

import colorsys
import json
import re
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Color Palette Generator ───────────────────────────────────────────────────

def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100

def _hsl_to_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

def _generate_shade_scale(hex_color: str) -> dict[str, str]:
    """Generate a 50-950 shade scale from a base color (like Tailwind)."""
    h, s, l = _hex_to_hsl(hex_color)
    shades = {
        "50":  _hsl_to_hex(h, max(s * 0.3, 10), 97),
        "100": _hsl_to_hex(h, max(s * 0.4, 15), 93),
        "200": _hsl_to_hex(h, max(s * 0.5, 20), 86),
        "300": _hsl_to_hex(h, max(s * 0.7, 30), 74),
        "400": _hsl_to_hex(h, max(s * 0.85, 45), 60),
        "500": _hsl_to_hex(h, s, l),  # Base color
        "600": _hsl_to_hex(h, s * 1.05, l * 0.85),
        "700": _hsl_to_hex(h, s * 1.1, l * 0.7),
        "800": _hsl_to_hex(h, s * 1.1, l * 0.55),
        "900": _hsl_to_hex(h, s * 1.05, l * 0.4),
        "950": _hsl_to_hex(h, s * 1.0, l * 0.25),
    }
    return shades


@tool(
    "generate_color_palette",
    "Generate a complete color palette from a brand color. Creates shade scales (50-950), semantic colors, and dark mode variants.",
    {"brand_color": str, "style": str},
)
async def generate_color_palette(args: dict[str, Any]) -> dict[str, Any]:
    brand = args["brand_color"].strip()
    style = args.get("style", "modern")  # modern, warm, cool, vibrant, muted

    if not brand.startswith("#"):
        brand = f"#{brand}"

    h, s, l = _hex_to_hsl(brand)

    # Generate primary shade scale
    primary = _generate_shade_scale(brand)

    # Generate complementary color (opposite on wheel)
    complement_h = (h + 180) % 360
    secondary_hex = _hsl_to_hex(complement_h, s * 0.7, l)
    secondary = _generate_shade_scale(secondary_hex)

    # Generate accent (triadic)
    accent_h = (h + 120) % 360
    accent_hex = _hsl_to_hex(accent_h, s * 0.8, l)

    # Neutral grays (slight tint of brand hue)
    neutral = {
        "50":  _hsl_to_hex(h, 5, 98),
        "100": _hsl_to_hex(h, 5, 96),
        "200": _hsl_to_hex(h, 5, 90),
        "300": _hsl_to_hex(h, 5, 82),
        "400": _hsl_to_hex(h, 5, 64),
        "500": _hsl_to_hex(h, 5, 46),
        "600": _hsl_to_hex(h, 6, 32),
        "700": _hsl_to_hex(h, 6, 25),
        "800": _hsl_to_hex(h, 7, 15),
        "900": _hsl_to_hex(h, 8, 9),
        "950": _hsl_to_hex(h, 10, 4),
    }

    # Semantic colors
    semantic = {
        "success": {"light": "#16a34a", "dark": "#4ade80"},
        "warning": {"light": "#eab308", "dark": "#facc15"},
        "error":   {"light": "#dc2626", "dark": "#f87171"},
        "info":    {"light": primary["600"], "dark": primary["400"]},
    }

    # Dark mode background layers
    dark_mode = {
        "background":   neutral["950"],
        "surface":      neutral["900"],
        "elevated":     neutral["800"],
        "border":       neutral["700"],
        "text_primary": neutral["50"],
        "text_secondary": neutral["400"],
    }

    return {
        "content": [{"type": "text", "text": json.dumps({
            "brand_color": brand,
            "palette": {
                "primary": primary,
                "secondary": secondary,
                "accent": accent_hex,
                "neutral": neutral,
            },
            "semantic": semantic,
            "dark_mode": dark_mode,
            "css_variables": _palette_to_css(primary, secondary, neutral, semantic),
            "tailwind_config": _palette_to_tailwind(primary, secondary, neutral),
        }, indent=2)}]
    }


def _palette_to_css(primary, secondary, neutral, semantic):
    lines = [":root {"]
    for shade, color in primary.items():
        lines.append(f"  --color-primary-{shade}: {color};")
    for shade, color in secondary.items():
        lines.append(f"  --color-secondary-{shade}: {color};")
    for shade, color in neutral.items():
        lines.append(f"  --color-neutral-{shade}: {color};")
    for name, colors in semantic.items():
        lines.append(f"  --color-{name}: {colors['light']};")
    lines.append("}")
    return "\n".join(lines)


def _palette_to_tailwind(primary, secondary, neutral):
    return {
        "theme": {
            "extend": {
                "colors": {
                    "primary": primary,
                    "secondary": secondary,
                    "neutral": neutral,
                }
            }
        }
    }


# ── Design Token Generator ────────────────────────────────────────────────────

@tool(
    "generate_design_tokens",
    "Generate a complete design token configuration — spacing, typography, border radius, shadows, breakpoints. Outputs Tailwind config and CSS custom properties.",
    {"style": str, "density": str},
)
async def generate_design_tokens(args: dict[str, Any]) -> dict[str, Any]:
    style = args.get("style", "modern")  # modern, compact, spacious, playful
    density = args.get("density", "default")  # compact, default, comfortable

    spacing_multiplier = {"compact": 0.75, "default": 1.0, "comfortable": 1.25}[density]

    base_spacing = int(4 * spacing_multiplier)
    spacing = {
        "0": "0",
        "px": "1px",
        "0.5": f"{base_spacing * 0.5}px",
        "1": f"{base_spacing}px",
        "1.5": f"{base_spacing * 1.5}px",
        "2": f"{base_spacing * 2}px",
        "3": f"{base_spacing * 3}px",
        "4": f"{base_spacing * 4}px",
        "5": f"{base_spacing * 5}px",
        "6": f"{base_spacing * 6}px",
        "8": f"{base_spacing * 8}px",
        "10": f"{base_spacing * 10}px",
        "12": f"{base_spacing * 12}px",
        "16": f"{base_spacing * 16}px",
    }

    border_radius = {
        "modern": {"none": "0", "sm": "4px", "DEFAULT": "8px", "md": "12px", "lg": "16px", "xl": "24px", "full": "9999px"},
        "compact": {"none": "0", "sm": "2px", "DEFAULT": "4px", "md": "6px", "lg": "8px", "xl": "12px", "full": "9999px"},
        "spacious": {"none": "0", "sm": "6px", "DEFAULT": "12px", "md": "16px", "lg": "24px", "xl": "32px", "full": "9999px"},
        "playful": {"none": "0", "sm": "8px", "DEFAULT": "16px", "md": "20px", "lg": "28px", "xl": "36px", "full": "9999px"},
    }.get(style, {})

    typography = {
        "display": {"size": "3rem", "weight": "700", "lineHeight": "1.1", "letterSpacing": "-0.02em"},
        "h1": {"size": "2.25rem", "weight": "700", "lineHeight": "1.2", "letterSpacing": "-0.02em"},
        "h2": {"size": "1.875rem", "weight": "600", "lineHeight": "1.3", "letterSpacing": "-0.01em"},
        "h3": {"size": "1.5rem", "weight": "600", "lineHeight": "1.4", "letterSpacing": "0"},
        "h4": {"size": "1.25rem", "weight": "600", "lineHeight": "1.4", "letterSpacing": "0"},
        "body": {"size": "1rem", "weight": "400", "lineHeight": "1.6", "letterSpacing": "0"},
        "small": {"size": "0.875rem", "weight": "400", "lineHeight": "1.5", "letterSpacing": "0"},
        "caption": {"size": "0.75rem", "weight": "500", "lineHeight": "1.4", "letterSpacing": "0.02em"},
    }

    shadows = {
        "xs":  "0 1px 2px rgba(0, 0, 0, 0.05)",
        "sm":  "0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)",
        "md":  "0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)",
        "lg":  "0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05)",
        "xl":  "0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04)",
        "2xl": "0 25px 50px rgba(0, 0, 0, 0.25)",
    }

    font_stacks = {
        "modern": "Inter, system-ui, -apple-system, sans-serif",
        "compact": "'DM Sans', system-ui, sans-serif",
        "spacious": "'Plus Jakarta Sans', system-ui, sans-serif",
        "playful": "'Nunito', system-ui, sans-serif",
    }

    return {
        "content": [{"type": "text", "text": json.dumps({
            "tokens": {
                "spacing": spacing,
                "borderRadius": border_radius,
                "typography": typography,
                "shadows": shadows,
                "fontFamily": font_stacks.get(style, font_stacks["modern"]),
            },
            "style": style,
            "density": density,
            "tailwind_extend": {
                "spacing": spacing,
                "borderRadius": border_radius,
                "boxShadow": shadows,
                "fontFamily": {"sans": [font_stacks.get(style, font_stacks["modern"])]},
            },
        }, indent=2)}]
    }


# ── Component Library Recommender ─────────────────────────────────────────────

@tool(
    "recommend_components",
    "Recommend the best component library and design system for a given tech stack, project type, and requirements.",
    {"tech_stack": str, "project_type": str, "requirements": str},
)
async def recommend_components(args: dict[str, Any]) -> dict[str, Any]:
    stack = args["tech_stack"].lower()
    project = args.get("project_type", "saas")
    reqs = args.get("requirements", "").lower()

    recommendations = []

    if "react" in stack or "next" in stack:
        recommendations = [
            {"name": "Shadcn/ui + Radix + Tailwind", "fit": "excellent",
             "why": "Headless, accessible, copy-paste ownership, Tailwind-native. Best for custom design.",
             "install": "npx shadcn-ui@latest init", "size": "~0KB (copy-paste, no runtime dep)"},
            {"name": "MUI (Material UI)", "fit": "excellent" if "enterprise" in reqs else "good",
             "why": "Comprehensive, Material Design 3, excellent docs. Best for enterprise apps.",
             "install": "npm install @mui/material @emotion/react @emotion/styled", "size": "~300KB"},
            {"name": "Ant Design", "fit": "excellent" if "enterprise" in reqs or "dashboard" in project else "good",
             "why": "Enterprise-grade, 60+ components, built-in form/table/date handling.",
             "install": "npm install antd", "size": "~400KB"},
            {"name": "Mantine", "fit": "good",
             "why": "100+ components, hooks library, excellent DX. Good MUI alternative.",
             "install": "npm install @mantine/core @mantine/hooks", "size": "~200KB"},
        ]
    elif "angular" in stack:
        recommendations = [
            {"name": "Angular Material + CDK", "fit": "excellent",
             "why": "Official Google, Material Design 3, CDK for custom components.",
             "install": "ng add @angular/material", "size": "~150KB"},
            {"name": "PrimeNG", "fit": "excellent" if "enterprise" in reqs else "good",
             "why": "80+ components, themes, enterprise-ready. Best rich component set for Angular.",
             "install": "npm install primeng primeicons", "size": "~300KB"},
            {"name": "Taiga UI", "fit": "good",
             "why": "Modern, polymorphic, great DX. Angular-first design.",
             "install": "npm install @taiga-ui/core", "size": "~200KB"},
            {"name": "NG-ZORRO (Ant Design for Angular)", "fit": "good",
             "why": "Ant Design components ported to Angular. Great for enterprise.",
             "install": "ng add ng-zorro-antd", "size": "~350KB"},
        ]
    elif "vue" in stack:
        recommendations = [
            {"name": "Vuetify", "fit": "excellent",
             "why": "Material Design, comprehensive, excellent docs.",
             "install": "npm install vuetify", "size": "~300KB"},
            {"name": "Quasar", "fit": "excellent" if "mobile" in reqs else "good",
             "why": "Cross-platform (web + mobile + desktop), Material Design.",
             "install": "npm install quasar @quasar/extras", "size": "~200KB"},
            {"name": "PrimeVue", "fit": "good",
             "why": "80+ components, multiple themes. Vue port of PrimeNG.",
             "install": "npm install primevue", "size": "~250KB"},
        ]
    elif "python" in stack or "fastapi" in stack or "django" in stack:
        recommendations = [
            {"name": "HTMX + Tailwind + Alpine.js", "fit": "excellent",
             "why": "Server-rendered, minimal JS, works with Jinja2/Django templates.",
             "install": "pip install django-htmx (or include via CDN)", "size": "~14KB total"},
            {"name": "Streamlit", "fit": "good" if "dashboard" in project else "limited",
             "why": "Instant data apps from Python. No frontend code needed.",
             "install": "pip install streamlit", "size": "N/A (full framework)"},
        ]

    return {
        "content": [{"type": "text", "text": json.dumps({
            "tech_stack": stack,
            "project_type": project,
            "recommendations": recommendations,
            "general_advice": [
                "Pick ONE component library — don't mix (e.g., no MUI buttons + Ant Design tables)",
                "Headless libraries (Radix, Headless UI) give you design control",
                "Full libraries (MUI, Ant) ship faster but are harder to customize",
                "Always add a design token layer on top (CSS variables or Tailwind config)",
            ],
        }, indent=2)}]
    }


# ── Visual Consistency Auditor ────────────────────────────────────────────────

@tool(
    "audit_visual_consistency",
    "Audit CSS/Tailwind code for visual consistency issues — mixed border radiuses, inconsistent spacing, mismatched colors, font size chaos.",
    {"code": str, "filename": str},
)
async def audit_visual_consistency(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")
    findings = []

    # Check for mixed border radiuses
    radius_values = set(re.findall(r'border-radius:\s*([\d.]+(?:px|rem|%))', code))
    rounded_classes = set(re.findall(r'rounded-(\w+)', code))
    if len(radius_values) > 3:
        findings.append({
            "issue": f"Too many border-radius values ({len(radius_values)}): {', '.join(sorted(radius_values))}",
            "severity": "medium",
            "fix": "Standardize to 2-3 values (e.g., 4px, 8px, 9999px) via design tokens",
        })

    # Check for hardcoded colors instead of tokens
    hex_colors = set(re.findall(r'#[0-9a-fA-F]{3,8}', code))
    if len(hex_colors) > 10:
        findings.append({
            "issue": f"{len(hex_colors)} hardcoded hex colors — should use design tokens",
            "severity": "high",
            "fix": "Define colors as CSS variables (--color-primary) or Tailwind config",
        })

    # Check for inconsistent spacing
    px_values = re.findall(r'(?:padding|margin|gap):\s*(\d+)px', code)
    if px_values:
        non_grid = [int(v) for v in px_values if int(v) % 4 != 0]
        if non_grid:
            findings.append({
                "issue": f"Non-grid spacing values: {sorted(set(non_grid))}px — use 4px grid",
                "severity": "medium",
                "fix": "Round to nearest 4px: " + ", ".join(f"{v}→{round(v/4)*4}" for v in sorted(set(non_grid))[:5]),
            })

    # Check for mixed font sizes
    font_sizes = set(re.findall(r'font-size:\s*([\d.]+(?:px|rem|em))', code))
    text_classes = set(re.findall(r'text-(xs|sm|base|lg|xl|2xl|3xl|4xl)', code))
    if font_sizes and text_classes:
        findings.append({
            "issue": "Mixing hardcoded font-size with Tailwind text classes",
            "severity": "medium",
            "fix": "Use only Tailwind text classes OR only CSS font-size, not both",
        })

    # Check for missing dark mode support
    if "dark:" not in code and "@media (prefers-color-scheme: dark)" not in code:
        if len(code) > 500:  # Only flag for substantial files
            findings.append({
                "issue": "No dark mode support detected",
                "severity": "low",
                "fix": "Add dark: variants in Tailwind or @media (prefers-color-scheme: dark) in CSS",
            })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "file": filename,
            "findings": findings,
            "metrics": {
                "unique_colors": len(hex_colors),
                "unique_radiuses": len(radius_values | rounded_classes),
                "unique_font_sizes": len(font_sizes | text_classes),
            },
            "consistency_score": max(0, 100 - sum(20 if f["severity"] == "high" else 10 for f in findings)),
        }, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

design_server = create_sdk_mcp_server(
    name="genesis-design",
    version="1.0.0",
    tools=[generate_color_palette, generate_design_tokens, recommend_components, audit_visual_consistency],
)
