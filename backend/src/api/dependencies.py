"""Shared FastAPI dependencies.

Authentication resolves the trusted ``user_id`` from a validated Cognito JWT (see
security steering) and never trusts a client-supplied identity. The validator is
built per configured user pool; when Cognito is not configured, protected routes
fail closed.

An explicit, opt-in local development bypass is available only when
``AUTH_ALLOW_LOCAL_DEV_USER`` is set AND ``APP_ENV`` is ``local``. It is ignored
in every other environment so nothing can accidentally run unauthenticated.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import Settings, get_settings
from src.core.errors import ServiceUnavailableError, UnauthorizedError
from src.core.security.cognito import AuthenticatedUser, CognitoJwtValidator

if TYPE_CHECKING:
    from src.repositories.reading_results import ReadingResultRepository
    from src.services.book_discovery import BookDiscoveryService
    from src.services.discussions import DiscussionService
    from src.services.jobs import JobService
    from src.services.progress import ProgressService
    from src.services.uploads import UploadService

# auto_error=False so we can raise our own consistent error envelope.
_bearer_scheme = HTTPBearer(auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _get_validator(
    issuer: str, client_id: str, jwks_url: str
) -> CognitoJwtValidator:
    """Cache one validator (and its JWKS client) per pool configuration."""
    from jwt import PyJWKClient

    return CognitoJwtValidator(
        issuer=issuer,
        client_id=client_id,
        signing_key_client=PyJWKClient(jwks_url),
    )


def get_validator(settings: SettingsDep) -> CognitoJwtValidator:
    """Provide the JWT validator; fails closed if Cognito is unconfigured."""
    if (
        not settings.cognito_issuer
        or not settings.cognito_client_id
        or not settings.cognito_jwks_url
    ):
        raise UnauthorizedError("Authentication is not configured")
    return _get_validator(
        settings.cognito_issuer,
        settings.cognito_client_id,
        settings.cognito_jwks_url,
    )


ValidatorDep = Annotated[CognitoJwtValidator, Depends(get_validator)]


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    settings: SettingsDep,
) -> AuthenticatedUser:
    """Resolve the authenticated user from the bearer token.

    Order of resolution:
    1. Local dev bypass (only if enabled AND app_env == local).
    2. Otherwise, require a bearer token and validate it against Cognito.
    """
    if settings.auth_allow_local_dev_user and settings.is_local:
        return AuthenticatedUser(user_id=settings.local_dev_user_id)

    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("A bearer token is required")

    validator = get_validator(settings)
    return validator.validate(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def get_book_discovery_service(
    settings: SettingsDep,
) -> AsyncIterator[BookDiscoveryService]:
    """Build the book discovery service with a request-scoped HTTP client.

    Providers share one httpx client that is closed when the request completes.
    The cache is DynamoDB when a table is configured, otherwise a no-op (local
    default), so discovery works without AWS.
    """
    import httpx

    from src.integrations.book_providers.google_books import GoogleBooksProvider
    from src.integrations.book_providers.open_library import OpenLibraryProvider
    from src.repositories.book_cache import (
        BookCacheRepository,
        DynamoDBBookCache,
        NullBookCache,
    )
    from src.services.book_discovery import BookDiscoveryService

    cache: BookCacheRepository
    if settings.book_cache_table_name:
        cache = DynamoDBBookCache.from_settings(
            settings, settings.book_cache_table_name
        )
    else:
        cache = NullBookCache()

    timeout = httpx.Timeout(settings.book_provider_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield BookDiscoveryService(
            primary=GoogleBooksProvider(
                client, api_key=settings.google_books_api_key
            ),
            fallback=OpenLibraryProvider(client),
            cache=cache,
        )


BookServiceDep = Annotated[
    "BookDiscoveryService", Depends(get_book_discovery_service)
]


def _build_job_service(settings: Settings) -> JobService:
    """Construct the JobService with DynamoDB repo + SQS queue (or no-op)."""
    import boto3

    from src.integrations.sqs import NullQueue, QueuePort, SqsQueue
    from src.repositories.jobs import DynamoDBJobRepository
    from src.services.jobs import JobService

    if not settings.jobs_table_name:
        raise ServiceUnavailableError("Job storage is not configured")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    repo = DynamoDBJobRepository(dynamodb.Table(settings.jobs_table_name))

    queue: QueuePort
    if settings.jobs_queue_url:
        queue = SqsQueue.from_settings(settings, settings.jobs_queue_url)
    else:
        queue = NullQueue()

    return JobService(repository=repo, queue=queue)


def get_job_service(settings: SettingsDep) -> JobService:
    return _build_job_service(settings)


JobServiceDep = Annotated["JobService", Depends(get_job_service)]


def get_upload_service(settings: SettingsDep) -> UploadService:
    """Construct the UploadService; requires a configured uploads bucket."""
    from src.integrations.s3_storage import S3Storage
    from src.services.uploads import UploadService

    if not settings.uploads_bucket_name:
        raise ServiceUnavailableError("Uploads are not configured")

    storage = S3Storage.from_settings(settings, settings.uploads_bucket_name)
    return UploadService(
        storage=storage,
        jobs=_build_job_service(settings),
        verify_object_exists=settings.verify_uploaded_object,
    )


UploadServiceDep = Annotated["UploadService", Depends(get_upload_service)]


def get_progress_service(settings: SettingsDep) -> ProgressService:
    """Construct the ProgressService; requires a configured progress table."""
    import boto3

    from src.repositories.progress import DynamoDBProgressRepository
    from src.services.progress import ProgressService

    if not settings.progress_table_name:
        raise ServiceUnavailableError("Progress storage is not configured")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    repo = DynamoDBProgressRepository(
        dynamodb.Table(settings.progress_table_name)
    )
    return ProgressService(repository=repo)


ProgressServiceDep = Annotated["ProgressService", Depends(get_progress_service)]


def get_reading_result_repository(
    settings: SettingsDep,
) -> ReadingResultRepository:
    """Reader for stored adaptive-reading results; requires the results bucket."""
    from src.repositories.reading_results import S3ReadingResultRepository

    if not settings.reading_results_bucket_name:
        raise ServiceUnavailableError("Reading results are not configured")
    return S3ReadingResultRepository.from_settings(
        settings, settings.reading_results_bucket_name
    )


ReadingResultRepoDep = Annotated[
    "ReadingResultRepository", Depends(get_reading_result_repository)
]


def get_discussion_service(settings: SettingsDep) -> DiscussionService:
    """Build the DiscussionService (conversation repo + discussion agent).

    The discussion agent is invoked directly for interactive turns. Its
    GraphRAG-retrieval and text-generation capabilities require the Knowledge
    Base and Bedrock to be configured.
    """
    import boto3

    from src.agents.discussion.agent import DiscussionAgent
    from src.mcp_server.tools.generation import TextGenerationTool
    from src.mcp_server.tools.graphrag import GraphRAGRetrievalTool
    from src.repositories.conversations import DynamoDBConversationRepository
    from src.services.discussions import DiscussionService

    if not settings.conversations_table_name:
        raise ServiceUnavailableError("Discussions are not configured")
    if not settings.knowledge_base_id:
        raise ServiceUnavailableError("GraphRAG is not configured")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    repo = DynamoDBConversationRepository(
        dynamodb.Table(settings.conversations_table_name)
    )

    agent_runtime = boto3.client(
        "bedrock-agent-runtime", region_name=settings.aws_region
    )
    bedrock_runtime = boto3.client(
        "bedrock-runtime", region_name=settings.aws_region
    )
    retriever = GraphRAGRetrievalTool(agent_runtime, settings.knowledge_base_id)
    generator = TextGenerationTool(bedrock_runtime, settings.generation_model_id)

    agent = DiscussionAgent(retriever=retriever, generator=generator)
    return DiscussionService(repository=repo, agent=agent)


DiscussionServiceDep = Annotated[
    "DiscussionService", Depends(get_discussion_service)
]

__all__ = [
    "AuthenticatedUser",
    "BookServiceDep",
    "CurrentUser",
    "DiscussionServiceDep",
    "JobServiceDep",
    "ProgressServiceDep",
    "ReadingResultRepoDep",
    "SettingsDep",
    "UploadServiceDep",
    "get_book_discovery_service",
    "get_current_user",
    "get_discussion_service",
    "get_job_service",
    "get_progress_service",
    "get_reading_result_repository",
    "get_upload_service",
    "get_validator",
]
