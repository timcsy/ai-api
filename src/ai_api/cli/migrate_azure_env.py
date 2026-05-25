"""Phase 5 T056 / US4: migrate AZURE_OPENAI_API_KEY env into DB as ProviderCredential.

Idempotent: re-running with same env values prints "already migrated" and exits 0.

Usage (inside running pod):
    python -m ai_api.cli.migrate_azure_env

After this completes, the gateway will prefer the DB credential and stop reading
the env (the env fallback in proxy/router.py is kept as a safety net during the
transitional release N+1; Release N+2 removes that fallback entirely).
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from ai_api.config import get_settings
from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.models import ProviderCredential, ProviderCredentialStatus
from ai_api.observability.logging import setup_logging
from ai_api.services.provider_credentials import (
    DuplicateLabelError,
    ProviderCredentialService,
    _fingerprint,
)

LABEL = "migrated-from-env"


async def _run() -> int:
    settings = get_settings()
    if not settings.azure_openai_api_key:
        print("nothing to migrate: AZURE_OPENAI_API_KEY is not set")
        return 0

    sm = get_sessionmaker()
    async with sm() as session:
        existing_label = await session.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider == "azure",
                ProviderCredential.label == LABEL,
            )
        )
        if existing_label.scalar_one_or_none() is not None:
            print(f"already migrated (provider=azure, label={LABEL})")
            return 0
        target_fp = _fingerprint(settings.azure_openai_api_key)
        active_same_fp = await session.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider == "azure",
                ProviderCredential.fingerprint == target_fp,
                ProviderCredential.status == ProviderCredentialStatus.active,
            )
        )
        if active_same_fp.scalar_one_or_none() is not None:
            print(f"already migrated (provider=azure, matching fingerprint={target_fp})")
            return 0

        extra = {"api_version": settings.azure_openai_api_version}
        try:
            cred = await ProviderCredentialService(session).create(
                provider="azure",
                label=LABEL,
                api_key=settings.azure_openai_api_key,
                base_url=settings.azure_openai_api_base or None,
                extra_config=extra,
                created_by="env-migration",
            )
        except DuplicateLabelError:
            print(f"already migrated (provider=azure, label={LABEL})")
            return 0
        await session.commit()
        print(
            f"migrated 1 credential (id={cred.id}, provider=azure, "
            f"label={LABEL}, fingerprint={cred.fingerprint})"
        )
    return 0


async def main() -> int:
    setup_logging()
    try:
        return await _run()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
