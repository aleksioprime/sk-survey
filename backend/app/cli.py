"""Служебные команды: python -m app.cli bootstrap | nocobase-fetch <каталог> | nocobase-load <каталог> [владелец]."""

import asyncio
import json
import sys
from pathlib import Path

from sk_common.cli import bootstrap
from sk_common.uow import UnitOfWork

from app.core.config import settings


async def nocobase_fetch(target: str) -> None:
    from app.legacy.nocobase import fetch

    if not settings.nocobase_url or not settings.nocobase_api_key:
        sys.exit('Задайте NOCOBASE_URL и NOCOBASE_API_KEY')
    counts = await fetch(settings.nocobase_url, settings.nocobase_api_key, Path(target))
    print(json.dumps(counts, ensure_ascii=False, indent=1))


async def nocobase_load(source: str, owner_email: str | None) -> None:
    from app.legacy.nocobase import load

    async with UnitOfWork() as uow:
        report = await load(uow.session, Path(source), owner_email)
    print(json.dumps(report['counts'], ensure_ascii=False, indent=1))
    print(f'Пропущено: { {k: len(v) for k, v in report["skipped"].items()} }. Подробно: {source}/report.json')


def main() -> None:
    command, *args = sys.argv[1:] or ['']
    if command == 'bootstrap':
        asyncio.run(bootstrap())
    elif command == 'nocobase-fetch' and args:
        asyncio.run(nocobase_fetch(args[0]))
    elif command == 'nocobase-load' and args:
        asyncio.run(nocobase_load(args[0], args[1] if len(args) > 1 else None))
    else:
        print('Команды: bootstrap | nocobase-fetch <каталог> | nocobase-load <каталог> [email владельца]')
        sys.exit(1)


if __name__ == '__main__':
    main()
