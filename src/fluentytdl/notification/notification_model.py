from dataclasses import dataclass, field
from typing import Any


@dataclass
class Notification:
    type: str  # "quality_warning" | "download_error" | "risk_control" | "info"
    title: str
    message: str
    severity: str = "info"  # "info" | "warning" | "critical"
    timestamp: float = 0.0
    id: int = 0
    is_read: bool = False
    related_task_id: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
