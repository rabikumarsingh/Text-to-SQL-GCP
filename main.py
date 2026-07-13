import os
import uuid
from urllib.parse import quote_plus

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from text_to_sql_agent.agent import root_agent
from text_to_sql_agent.services.cache_service import cache_service


load_dotenv()


# ==========================================================
# APPLICATION CONFIGURATION
# ==========================================================

APP_NAME = "text_to_sql_api"


app = FastAPI(
    title="Enterprise Text-to-SQL Agent API",
    description=(
        "Semantic-layer-driven Text-to-SQL Agent "
        "built with Google ADK, BigQuery, Cloud SQL, "
        "and Redis caching."
    ),
    version="1.1.0",
)


# ==========================================================
# DATABASE CONFIGURATION
# ==========================================================

DB_USER = "adk_user"
DB_NAME = "adk_sessions"

DB_PASSWORD = os.getenv("ADK_DB_PASSWORD")

INSTANCE_CONNECTION_NAME = (
    "test-to-sql-502205:"
    "us-central1:"
    "text-to-sql-postgres"
)


if not DB_PASSWORD:
    raise RuntimeError(
        "ADK_DB_PASSWORD environment variable is missing."
    )


encoded_password = quote_plus(DB_PASSWORD)


DB_URL = (
    f"postgresql+asyncpg://"
    f"{DB_USER}:{encoded_password}"
    f"@/{DB_NAME}"
    f"?host=/cloudsql/{INSTANCE_CONNECTION_NAME}"
)


# ==========================================================
# ADK SERVICES
# ==========================================================

session_service = DatabaseSessionService(
    db_url=DB_URL,
)


runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


# ==========================================================
# REQUEST / RESPONSE MODELS
# ==========================================================

class QueryRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
    )

    user_id: str = Field(
        default="api_user",
        min_length=1,
        max_length=100,
    )

    session_id: str | None = None


class QueryResponse(BaseModel):

    session_id: str

    answer: str

    cache_status: str = "MISS"


# ==========================================================
# HEALTH ENDPOINT
# ==========================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "text-to-sql-agent",
    }


# ==========================================================
# REDIS HEALTH ENDPOINT
# ==========================================================

@app.get("/redis-health")
async def redis_health():

    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=int(
            os.getenv(
                "REDIS_PORT",
                "6379",
            )
        ),
        decode_responses=True,
    )

    try:

        result = await redis_client.ping()

        return {
            "status": "healthy",
            "redis_ping": result,
        }

    finally:

        await redis_client.aclose()


# ==========================================================
# QUERY ENDPOINT
# ==========================================================

@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_agent(
    request: QueryRequest,
):

    # ------------------------------------------------------
    # Generate or reuse session ID
    # ------------------------------------------------------

    session_id = (
        request.session_id
        or str(uuid.uuid4())
    )

    try:

        # --------------------------------------------------
        # Redis Cache Lookup
        # Cache key = user_id + session_id + question
        # --------------------------------------------------

        cached_response = await cache_service.get(
            user_id=request.user_id,
            session_id=session_id,
            question=request.question,
        )

        if cached_response is not None:

            return QueryResponse(
                session_id=session_id,
                answer=cached_response["answer"],
                cache_status="HIT",
            )

        # --------------------------------------------------
        # Load Existing ADK Session From Cloud SQL
        # --------------------------------------------------

        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=request.user_id,
            session_id=session_id,
        )

        # --------------------------------------------------
        # Create Session If Missing
        # --------------------------------------------------

        if session is None:

            await session_service.create_session(
                app_name=APP_NAME,
                user_id=request.user_id,
                session_id=session_id,
            )

        # --------------------------------------------------
        # Convert Question To ADK Message
        # --------------------------------------------------

        user_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=request.question
                )
            ],
        )

        # --------------------------------------------------
        # Execute ADK Agent
        # --------------------------------------------------

        final_answer = None

        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=session_id,
            new_message=user_message,
        ):

            if not event.is_final_response():
                continue

            if (
                event.content is None
                or event.content.parts is None
            ):
                continue

            text_parts = [
                part.text
                for part in event.content.parts
                if getattr(
                    part,
                    "text",
                    None,
                )
            ]

            if text_parts:

                final_answer = "".join(
                    text_parts
                )

        # --------------------------------------------------
        # Validate Agent Response
        # --------------------------------------------------

        if not final_answer:

            raise RuntimeError(
                "Agent returned no final response."
            )

        # --------------------------------------------------
        # Store Response In Redis
        # Cache key = user_id + session_id + question
        # --------------------------------------------------

        await cache_service.set(
            user_id=request.user_id,
            session_id=session_id,
            question=request.question,
            value={
                "answer": final_answer,
            },
        )

        # --------------------------------------------------
        # Return Response
        # --------------------------------------------------

        return QueryResponse(
            session_id=session_id,
            answer=final_answer,
            cache_status="MISS",
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

# ==========================================================
# LOCAL ENTRYPOINT
# ==========================================================

if __name__ == "__main__":

    import uvicorn


    uvicorn.run(

        "main:app",

        host="0.0.0.0",

        port=int(
            os.getenv(
                "PORT",
                "8080",
            )
        ),

        reload=True,

    )