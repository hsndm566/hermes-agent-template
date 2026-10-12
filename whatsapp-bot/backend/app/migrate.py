import asyncio
from pathlib import Path
import asyncpg
from .config import settings

async def main():
    conn = await asyncpg.connect(settings.database_url)
    try:
        directory = Path('/app/migrations')
        if not directory.is_dir():
            directory = Path(__file__).resolve().parents[2] / 'migrations'
        for path in sorted(directory.glob('*.sql')):
            await conn.execute(path.read_text())
            print(f"applied {path.name}")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
