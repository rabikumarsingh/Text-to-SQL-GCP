# Enterprise Agentic Text-to-SQL Platform on Google Cloud

An enterprise-grade, semantic-layer-driven Text-to-SQL agent built using Google ADK, Gemini, BigQuery, Cloud SQL PostgreSQL, Memorystore Redis, FastAPI, Docker, Cloud Run, and GitHub Actions CI/CD.

The platform converts natural-language business questions into semantically validated SQL, executes approved queries against BigQuery, maintains persistent multi-turn conversations, caches repeated queries, and is deployed as a scalable API on Google Cloud.

---

## Business Use Case

Business users frequently need insights from enterprise data but may not know SQL or understand the underlying database schema.

Traditional Text-to-SQL systems introduce several production risks:

- Hallucinated tables and columns
- Incorrect joins
- Incorrect business metric definitions
- Expensive BigQuery queries
- Unauthorized SQL execution
- Loss of conversational context
- Repeated execution of identical analytical queries

This project addresses these problems by introducing a semantic governance layer and an agentic SQL generation workflow.

A user can ask:

> Which company category generated the highest total revenue in 2023?

The agent:

1. Understands the business question.
2. Inspects available business context.
3. Checks data availability.
4. Identifies approved metrics.
5. Identifies approved dimensions.
6. Retrieves semantic metric definitions.
7. Retrieves semantic dimension definitions.
8. Retrieves approved table definitions.
9. Retrieves approved relationships.
10. Generates SQL.
11. Validates SQL against the semantic layer.
12. Performs a BigQuery dry run.
13. Executes the approved query.
14. Returns the business answer and SQL execution metadata.

---

## Purpose

The purpose of this project is to demonstrate how an Agentic AI application can be moved from a prototype into a production-oriented cloud architecture.

The platform provides:

- Natural Language to SQL generation
- Semantic-layer-driven SQL governance
- Agentic tool orchestration
- SQL validation before execution
- BigQuery dry-run cost estimation
- Safe BigQuery query execution
- Persistent multi-turn conversations
- Redis query-result caching
- User and session-aware cache isolation
- Containerized API deployment
- Serverless application hosting
- Secure secret management
- Automated CI/CD deployment

---

## High-Level Architecture

```text
                        USER / CLIENT APPLICATION
                                  |
                                  v
                          FastAPI REST API
                                  |
                                  v
                        Google ADK Runner
                                  |
                                  v
                    Agentic Text-to-SQL Agent
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
          v                       v                       v
   Semantic Layer          ADK Session Store         Redis Cache
          |                       |                       |
          v                       v                       v
 Semantic Metadata       Cloud SQL PostgreSQL    Memorystore Redis
          |
          v
 Semantic SQL Validator
          |
          v
 BigQuery Dry Run
          |
          v
 Safe Query Execution
          |
          v
       BigQuery
```

---

## Google Cloud Deployment Architecture

```text
GitHub Repository
        |
        | git push
        v
GitHub Actions
        |
        | Workload Identity Federation
        v
Google Cloud IAM
        |
        v
Docker Image Build
        |
        v
Artifact Registry
        |
        v
Cloud Run Deployment
        |
        +----------------------+
        |                      |
        v                      v
Cloud SQL PostgreSQL     VPC Connector
                               |
                               v
                        Memorystore Redis
                               |
                               v
                            BigQuery
```

---

## Agent Workflow

```text
User Question
      |
      v
Get Business Context
      |
      v
Check Data Availability
      |
      v
Discover Approved Metrics
      |
      v
Discover Approved Dimensions
      |
      v
Get Metric Definition
      |
      v
Get Dimension Definition
      |
      v
Get Table Definitions
      |
      v
Get Approved Relationships
      |
      v
Generate SQL
      |
      v
Semantic SQL Validation
      |
      v
BigQuery Dry Run
      |
      v
Safe Query Execution
      |
      v
Business Answer
```

---

## Semantic Layer

The semantic layer acts as the governance boundary between the LLM and BigQuery.

It defines approved:

- Business metrics
- Dimensions
- Tables
- Columns
- Relationships
- Join conditions
- SQL expressions
- Data availability

Example metric:

```yaml
total_revenue:
  description: Total revenue generated by taxi trips
  sql_expression: SUM(taxi_trips.trip_total)
  source_tables:
    - taxi_trips
```

Example relationship:

```yaml
taxi_trips_to_company_master:

  relationship_type: many_to_one

  left_table: taxi_trips

  right_table: company_master

  join_type: INNER JOIN

  join_condition:

    left_column: company

    right_column: company_name
```

The generated SQL must satisfy semantic validation rules before execution.

---

## Long-Term Conversation Persistence

Google ADK sessions are persisted using Cloud SQL PostgreSQL.

```text
Cloud Run
    |
    v
DatabaseSessionService
    |
    v
Cloud SQL PostgreSQL
    |
    +-- sessions
    +-- events
    +-- app_states
    +-- user_states
    +-- schema_version
```

This allows conversation history to survive:

- Cloud Run container restarts
- New Cloud Run revisions
- Application redeployments
- Scaling to multiple instances

A conversation is identified using:

```text
app_name + user_id + session_id
```

---

## Redis Query Caching

Google Cloud Memorystore Redis is used for query-result caching.

Cache key:

```text
user_id + session_id + normalized_question
```

The key is hashed using SHA-256.

```text
User Question
      |
      v
Redis Lookup
   /      \
 HIT      MISS
  |         |
  v         v
Return     ADK Agent
Cached        |
Answer        v
            BigQuery
               |
               v
          Store Result
           In Redis
```

Current cache TTL:

```text
3600 seconds
```

Benefits:

- Reduced BigQuery execution cost
- Reduced response latency
- Reduced LLM calls
- Session-aware cache isolation

---

## Technology Stack

### Agentic AI

- Google Agent Development Kit (ADK)
- Gemini 2.5 Flash
- Tool-based agent orchestration

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

### Data Platform

- Google BigQuery
- BigQuery Public Datasets
- Semantic metadata layer

### Persistent Memory

- Cloud SQL for PostgreSQL
- Google ADK DatabaseSessionService
- asyncpg
- SQLAlchemy async engine

### Caching

- Google Cloud Memorystore for Redis
- redis-py asyncio client
- SHA-256 cache keys
- TTL-based cache expiration

### Google Cloud Infrastructure

- Google Cloud Run
- Google Artifact Registry
- Google Cloud SQL
- Google Cloud Memorystore
- Serverless VPC Access
- Google Secret Manager
- Google IAM

### Containerization

- Docker

### CI/CD

- GitHub Actions
- Google Cloud Workload Identity Federation
- Docker
- Artifact Registry
- Cloud Run

---

## API Endpoints

### Health Check

```text
GET /health
```

Example response:

```json
{
  "status": "healthy",
  "service": "text-to-sql-agent"
}
```

### Redis Health Check

```text
GET /redis-health
```

Example response:

```json
{
  "status": "healthy",
  "redis_ping": true
}
```

### Text-to-SQL Query

```text
POST /query
```

Example request:

```json
{
  "question": "Which company category generated the highest total revenue in 2023?",
  "user_id": "business_user_01",
  "session_id": "business-session-001"
}
```

Example response:

```json
{
  "session_id": "business-session-001",
  "answer": "The PREMIUM company category generated the highest total revenue.",
  "cache_status": "MISS"
}
```

Repeated request:

```json
{
  "session_id": "business-session-001",
  "answer": "The PREMIUM company category generated the highest total revenue.",
  "cache_status": "HIT"
}
```

---

## Docker Deployment

Build:

```bash
docker build -t text-to-sql-agent .
```

Tag:

```bash
docker tag text-to-sql-agent \
us-central1-docker.pkg.dev/PROJECT_ID/REPOSITORY/text-to-sql-agent:latest
```

Push:

```bash
docker push \
us-central1-docker.pkg.dev/PROJECT_ID/REPOSITORY/text-to-sql-agent:latest
```

Deploy:

```bash
gcloud run services update text-to-sql-agent \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/REPOSITORY/text-to-sql-agent:latest \
  --region=us-central1 \
  --project=PROJECT_ID
```

---

## CI/CD Pipeline

The production deployment pipeline uses GitHub Actions.

```text
Developer
    |
    | git push
    v
GitHub Repository
    |
    v
GitHub Actions Workflow
    |
    v
Run Tests
    |
    v
Authenticate To Google Cloud
    |
    | Workload Identity Federation
    v
Build Docker Image
    |
    v
Push Image
    |
    v
Artifact Registry
    |
    v
Deploy New Revision
    |
    v
Cloud Run
    |
    v
Health Check
```

### CI/CD Security

The pipeline uses Workload Identity Federation.

No long-lived Google Cloud service-account JSON keys are stored in GitHub.

GitHub Actions receives short-lived Google Cloud credentials during workflow execution.

### Deployment Trigger

The deployment workflow runs when code is pushed to:

```text
main
```

### Deployment Strategy

Docker images are tagged using the Git commit SHA:

```text
text-to-sql-agent:<GITHUB_SHA>
```

This provides:

- Immutable deployments
- Deployment traceability
- Easy rollback to previous revisions

---

## Current Production Features

- Agentic Text-to-SQL workflow
- Gemini-powered SQL generation
- Semantic SQL governance
- Approved metrics and dimensions
- Approved table relationships
- SQL validation
- BigQuery dry runs
- BigQuery execution metadata
- Persistent ADK conversations
- Cloud SQL session storage
- Redis query-result caching
- Session-aware cache isolation
- FastAPI REST API
- Docker containerization
- Artifact Registry image storage
- Cloud Run deployment
- Secret Manager integration
- Serverless VPC connectivity
- GitHub Actions CI/CD architecture

---

## Future Improvements

- Automated unit and integration tests
- SQL query audit logging
- Cache invalidation strategy
- Semantic cache
- Redis distributed locking
- Rate limiting
- API authentication
- Role-based access control
- Langfuse or OpenTelemetry observability
- Cloud Monitoring dashboards
- BigQuery cost budgets
- Terraform infrastructure provisioning
- Canary deployment strategy
- Automated rollback

---

## Author

Rabi Kumar Singh

Senior Data Scientist | AI Engineer | Agentic AI | Generative AI | Machine Learning

GitHub: Jurk06

LinkedIn: rabi-kumar-singh