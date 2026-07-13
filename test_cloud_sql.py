import asyncio
import os

import asyncpg


async def main():
    connection = await asyncpg.connect(
        user="adk_user",
        password=os.environ["ADK_DB_PASSWORD"],
        database="adk_sessions",
        host="127.0.0.1",
        port=5432,
    )

    print("CONNECTED TO CLOUD SQL")

    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())