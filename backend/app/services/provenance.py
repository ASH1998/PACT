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


class ProvenanceService:
    """Tracks data provenance and propagates taint labels through agent steps."""

    def __init__(self):
        # Per-run accumulated influence labels
        self._run_labels: dict[str, list[str]] = {}

    def get_tool_labels(self, tool: str) -> dict:
        """Get default provenance labels for a tool."""
        return TOOL_LABELS.get(tool, {"output_label": "agent.generated", "side_effect": None})

    def start_run(self, run_id: str) -> None:
        """Initialize provenance tracking for a run."""
        self._run_labels[run_id] = ["trusted.user"]

    def record_step(self, run_id: str, tool: str) -> str | None:
        """Record a tool step and return its output label."""
        labels = self.get_tool_labels(tool)
        output_label = labels.get("output_label")

        if output_label and run_id in self._run_labels:
            if output_label not in self._run_labels[run_id]:
                self._run_labels[run_id].append(output_label)

        return output_label

    def build_provenance(self, run_id: str, tool: str) -> dict:
        """Build the provenance context for an action envelope."""
        labels = self.get_tool_labels(tool)
        accumulated = self._run_labels.get(run_id, ["trusted.user"])

        # influenced_by: all labels accumulated so far
        influenced_by = list(accumulated)

        # uses_data: data labels relevant to this step
        uses_data = []
        if labels["output_label"]:
            uses_data.append(labels["output_label"])

        return {
            "influenced_by": influenced_by,
            "uses_data": uses_data,
            "side_effect": labels["side_effect"],
        }

    def get_accumulated_labels(self, run_id: str) -> list[str]:
        """Get all accumulated provenance labels for a run."""
        return list(self._run_labels.get(run_id, []))

    def has_untrusted_influence(self, run_id: str) -> bool:
        """Check if any untrusted data has influenced this run."""
        labels = self._run_labels.get(run_id, [])
        return any(label.startswith("untrusted.") for label in labels)

    def has_secret_data(self, run_id: str) -> bool:
        """Check if secret data has been accessed in this run."""
        return "secret" in self._run_labels.get(run_id, [])
