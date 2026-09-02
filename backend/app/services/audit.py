"""監査ログ（設計書 7章）。

Firestore の audit コレクションと、Cloud Logging が拾える構造化ログ(stdout JSON)の両方に出す。
外部 API 呼び出しは必ず policy（非学習ポリシー）を添えて記録する。
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app import repo
from app.config import get_settings
from app.models import AuditAction, AuditLog

_logger = logging.getLogger("omoide.audit")
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


async def record(
    family_id: str,
    action: AuditAction,
    *,
    actor: str = "system",
    target: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        family_id=family_id,
        actor=actor,
        action=action,
        target=target,
        detail=detail or {},
        policy=get_settings().no_training_policy,
    )
    await repo.append_audit(log)
    _logger.info(
        json.dumps(
            {
                "severity": "INFO",
                "message": f"audit:{action.value}",
                "familyId": family_id,
                "actor": actor,
                "action": action.value,
                "target": target,
                "detail": log.detail,
                "policy": log.policy,
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return log


async def record_external_call(
    family_id: str, provider: str, operation: str, *, mode: str, target: str | None = None
) -> AuditLog:
    """外部 API へ家族データを渡した事実と、学習オプトアウト設定の証跡。"""
    return await record(
        family_id,
        AuditAction.external_call,
        actor=provider,
        target=target,
        detail={"provider": provider, "operation": operation, "mode": mode, "opt_out_training": True},
    )
