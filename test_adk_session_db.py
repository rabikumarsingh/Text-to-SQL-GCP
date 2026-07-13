import asyncio
import os
import uuid
from urllib.parse import quote_plus

from google.adk.sessions import DatabaseSessionService


APP_NAME = "text_to_sql_api"
USER_ID = "persistent_test_user"
SESSION_ID = str(uuid.uuid4())

password = quote_plus(os.environ["ADK_DB_PASSWORD"])

DB_URL = (
    f"postgresql+asyncpg://"
    f"adk_user:{password}"
    f"@127.0.0.1:5432/adk_sessions"
)

session_service = DatabaseSessionService(
    db_url=DB_URL,
)


async def main():
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    print("SESSION CREATED")
    print("USER ID:", session.user_id)
    print("SESSION ID:", session.id)

    loaded_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    print("SESSION LOADED FROM DATABASE")
    print("LOADED SESSION ID:", loaded_session.id)


if __name__ == "__main__":
    asyncio.run(main())