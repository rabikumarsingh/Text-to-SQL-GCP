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

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from text_to_sql_agent.agent import root_agent
from text_to_sql_agent.services.cache_service import cache_service
from text_to_sql_agent.services.tracing_service import configure_tracing


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
        "Redis caching, and OpenTelemetry tracing."
    ),
    version="1.2.0",
)


tracer = configure_tracing()


FastAPIInstrumentor.instrument_app(app)


RequestsInstrumentor().instrument()


# ==========================================================
# DATABASE CONFIGURATION
# ==========================================================

DB_USER = "adk_user"

DB_NAME = "adk_sessions"


DB_PASSWORD = os.getenv(
    "ADK_DB_PASSWORD"
)


INSTANCE_CONNECTION_NAME = (
    "test-to-sql-502205:"
    "us-central1:"
    "text-to-sql-postgres"
)


if not DB_PASSWORD:

    raise RuntimeError(
        "ADK_DB_PASSWORD environment variable is missing."
    )


encoded_password = quote_plus(
    DB_PASSWORD
)


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

    session_id = (
        request.session_id
        or str(uuid.uuid4())
    )

    with tracer.start_as_current_span(
        "text_to_sql.query"
    ) as query_span:

        query_span.set_attribute(
            "text_to_sql.question.length",
            len(request.question),
        )

        query_span.set_attribute(
            "text_to_sql.session.provided",
            request.session_id is not None,
        )

        try:

            # ==============================================
            # REDIS CACHE LOOKUP
            # ==============================================

            with tracer.start_as_current_span(
                "redis.cache_lookup"
            ) as cache_span:

                cached_response = await cache_service.get(
                    user_id=request.user_id,
                    session_id=session_id,
                    question=request.question,
                )

                cache_hit = (
                    cached_response is not None
                )

                cache_span.set_attribute(
                    "cache.hit",
                    cache_hit,
                )

            if cached_response is not None:

                query_span.set_attribute(
                    "text_to_sql.cache_status",
                    "HIT",
                )

                return QueryResponse(
                    session_id=session_id,
                    answer=cached_response["answer"],
                    cache_status="HIT",
                )


            # ==============================================
            # CLOUD SQL SESSION LOOKUP
            # ==============================================

            with tracer.start_as_current_span(
                "cloudsql.session_lookup"
            ) as session_lookup_span:

                session = await session_service.get_session(
                    app_name=APP_NAME,
                    user_id=request.user_id,
                    session_id=session_id,
                )

                session_lookup_span.set_attribute(
                    "session.exists",
                    session is not None,
                )


            # ==============================================
            # CLOUD SQL SESSION CREATE
            # ==============================================

            if session is None:

                with tracer.start_as_current_span(
                    "cloudsql.session_create"
                ):

                    await session_service.create_session(
                        app_name=APP_NAME,
                        user_id=request.user_id,
                        session_id=session_id,
                    )


            # ==============================================
            # CREATE ADK MESSAGE
            # ==============================================

            user_message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=request.question
                    )
                ],
            )


            # ==============================================
            # EXECUTE ADK AGENT
            # ==============================================

            final_answer = None

            event_count = 0


            with tracer.start_as_current_span(
                "adk.agent_execution"
            ) as agent_span:

                async for event in runner.run_async(
                    user_id=request.user_id,
                    session_id=session_id,
                    new_message=user_message,
                ):

                    event_count += 1

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


                agent_span.set_attribute(
                    "adk.event_count",
                    event_count,
                )

                agent_span.set_attribute(
                    "adk.final_response.present",
                    final_answer is not None,
                )


            # ==============================================
            # VALIDATE AGENT RESPONSE
            # ==============================================

            if not final_answer:

                raise RuntimeError(
                    "Agent returned no final response."
                )


            # ==============================================
            # REDIS CACHE WRITE
            # ==============================================

            with tracer.start_as_current_span(
                "redis.cache_write"
            ):

                await cache_service.set(
                    user_id=request.user_id,
                    session_id=session_id,
                    question=request.question,
                    value={
                        "answer": final_answer,
                    },
                )


            # ==============================================
            # FINAL TRACE ATTRIBUTES
            # ==============================================

            query_span.set_attribute(
                "text_to_sql.cache_status",
                "MISS",
            )

            query_span.set_attribute(
                "text_to_sql.answer.length",
                len(final_answer),
            )


            # ==============================================
            # RETURN RESPONSE
            # ==============================================

            return QueryResponse(
                session_id=session_id,
                answer=final_answer,
                cache_status="MISS",
            )


        except Exception as exc:

            query_span.record_exception(
                exc
            )

            query_span.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    str(exc),
                )
            )

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