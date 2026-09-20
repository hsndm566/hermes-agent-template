import asyncio
from pathlib import Path
import asyncpg
from .config import settings

async def main():
    conn = await asyncpg.connect(settings.database_url)
    try:
        for path in sorted(Path('/app/migrations').glob('*.sql')):
            await conn.execute(path.read_text())
            print(f"applied {path.name}")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
