"""エージェント共通の型（ADK のエージェント構成に対応）。

autonomy はコード上の約束事:
- autonomous      … 家族の承認なしに進めてよい
- propose_only    … 提示までで、確定は家族が行う
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Autonomy = Literal["autonomous", "propose_only"]


@dataclass
class AgentResult:
    agent: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    proposal: bool = False  # True なら家族の確定待ち


class Agent(ABC):
    name: str = "agent"
    role: str = ""
    autonomy: Autonomy = "autonomous"

    @abstractmethod
    async def run(self, **kwargs: Any) -> AgentResult: ...

    def describe(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role, "autonomy": self.autonomy}
