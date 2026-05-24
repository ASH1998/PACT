from __future__ import annotations
"""Provenance Service — label data sources and propagate taint through agent steps."""

# Default tool output / side-effect labels
TOOL_LABELS: dict[str, dict] = {
    "email.read": {
        "output_label": "untrusted.email",
        "side_effect": None,
    },
    "web.read": {
        "output_label": "untrusted.web",
        "side_effect": None,
    },
    "file.read": {
        "output_label": "internal.data",
        "side_effect": None,
    },
    "file.read_secret": {
        "output_label": "secret",
        "side_effect": None,
    },
    "email.send": {
        "output_label": None,
        "side_effect": "external_write",
    },
    "respond_to_user": {
        "output_label": "agent.generated",
        "side_effect": None,
    },
    "shell.execute_mock": {
        "output_label": None,
        "side_effect": "external_write",
    },
}


# Module-level shared state — survives across ProvenanceService instances
# (ProvenanceService() is instantiated per-request in tools.py and scenarios.py,
# so instance-level state would be lost between requests.)
_run_labels: dict[str, list[dict]] = {}


class ProvenanceService:
    """Tracks data provenance and propagates taint labels through agent steps."""

    def get_tool_labels(self, tool: str) -> dict:
        """Get default provenance labels for a tool."""
        return TOOL_LABELS.get(tool, {"output_label": "agent.generated", "side_effect": None})

    def start_run(self, run_id: str) -> None:
        """Initialize provenance tracking for a run."""
        _run_labels[run_id] = [{"label": "trusted.user", "source_step": -1, "source_tool": "user", "source_resource": ""}]

    def ensure_run(self, run_id: str) -> None:
        """Initialize provenance tracking for a run if not already started."""
        if run_id not in _run_labels:
            _run_labels[run_id] = [{"label": "trusted.user", "source_step": -1, "source_tool": "user", "source_resource": ""}]

    def record_step(self, run_id: str, tool: str, step_id: int = 0, resource: str = "") -> dict | None:
        """Record a tool step and return its output label as a structured dict."""
        labels = self.get_tool_labels(tool)
        output_label = labels.get("output_label")

        if output_label and run_id in _run_labels:
            entry = {"label": output_label, "source_step": step_id, "source_tool": tool, "source_resource": resource}
            existing_labels = [e["label"] for e in _run_labels[run_id]]
            if output_label not in existing_labels:
                _run_labels[run_id].append(entry)

        return {"label": output_label, "source_step": step_id, "source_tool": tool} if output_label else None

    def build_provenance(self, run_id: str, tool: str) -> dict:
        """Build the provenance context for an action envelope."""
        labels = self.get_tool_labels(tool)
        accumulated = _run_labels.get(run_id, [{"label": "trusted.user", "source_step": -1, "source_tool": "user", "source_resource": ""}])

        # influenced_by: all labels accumulated so far
        influenced_by = [entry["label"] for entry in accumulated]

        # source attribution: structured provenance with step-level detail
        influenced_by_sources = [
            {"label": entry["label"], "source_step": entry["source_step"], "source_tool": entry["source_tool"], "source_resource": entry.get("source_resource", "")}
            for entry in accumulated
        ]

        # uses_data: data labels relevant to this step
        uses_data = []
        if labels["output_label"]:
            uses_data.append(labels["output_label"])

        return {
            "influenced_by": influenced_by,
            "influenced_by_sources": influenced_by_sources,
            "uses_data": uses_data,
            "side_effect": labels["side_effect"],
        }

    def get_accumulated_labels(self, run_id: str) -> list[str]:
        """Get all accumulated provenance labels for a run."""
        return [entry["label"] for entry in _run_labels.get(run_id, [])]

    def has_untrusted_influence(self, run_id: str) -> bool:
        """Check if any untrusted data has influenced this run."""
        labels = _run_labels.get(run_id, [])
        return any(entry["label"].startswith("untrusted.") for entry in labels)

    def has_secret_data(self, run_id: str) -> bool:
        """Check if secret data has been accessed in this run."""
        return any(entry["label"] == "secret" for entry in _run_labels.get(run_id, []))
