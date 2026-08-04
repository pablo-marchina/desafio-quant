"""Initial evaluation rubrics used to critique project outputs."""

RUBRICS: dict[str, str] = {
    "output_adherence": "The output follows the required schema and requested structure.",
    "specificity": "The output is concrete and avoids generic AI language.",
    "traceability": "Claims are tied to evidence, sources, and explicit confidence.",
    "executability": "The next action is operationally clear for the NVIDIA team.",
    "modularity": "The solution keeps responsibilities separated and components reusable.",
    "validation": "The work includes tests, checks, or a clear justification for their absence.",
    "risk_awareness": "The output identifies uncertainty, assumptions, and remaining risks.",
}
