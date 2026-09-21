import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from beanfeature_application.service import ApplicationService, ConflictError, NotFoundError
from beanfeature_infrastructure.bootstrap import Container, create_container

from .schemas import (
    CreateExperimentRequest,
    DatasetResponse,
    ErrorResponse,
    ExperimentResponse,
    HealthResponse,
    ProjectResponse,
    RunResponse,
    SystemInfoResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_service(container: Annotated[Container, Depends(get_container)]) -> ApplicationService:
    return container.service


Service = Annotated[ApplicationService, Depends(get_service)]
ContainerDep = Annotated[Container, Depends(get_container)]


def error_response(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message}},
    )


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.container = create_container(database_url)
        logger.info("api.start version=0.1.0")
        yield
        application.state.container.metadata.engine.dispose()
        logger.info("api.stop")

    application = FastAPI(title="BeanFeature Lab API", version="0.1.0", lifespan=lifespan)
    origins = os.getenv(
        "BEANFEATURE_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(NotFoundError)
    async def not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return error_response("not_found", str(exc), 404)

    @application.exception_handler(ConflictError)
    async def conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        return error_response("conflict", str(exc), 409)

    @application.exception_handler(ValueError)
    async def invalid(_request: Request, exc: ValueError) -> JSONResponse:
        return error_response("invalid_configuration", str(exc), 422)

    @application.exception_handler(RequestValidationError)
    async def validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response("validation_error", "Request validation failed", 422)

    @application.exception_handler(SQLAlchemyError)
    async def persistence(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("api.persistence_error type=%s", type(exc).__name__)
        return error_response("persistence_error", "Storage is unavailable", 503)

    @application.get(
        "/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}}
    )
    def health(container: ContainerDep):
        if container.metadata.database_state() != "connected":
            return error_response("persistence_error", "Storage is unavailable", 503)
        return HealthResponse(status="ok")

    @application.get("/api/v1/system/info", response_model=SystemInfoResponse)
    def system_info(service: Service):
        return service.system_info()

    @application.get("/api/v1/projects", response_model=list[ProjectResponse])
    def projects() -> list[ProjectResponse]:
        return []

    @application.get("/api/v1/datasets", response_model=list[DatasetResponse])
    def datasets() -> list[DatasetResponse]:
        return []

    @application.get("/api/v1/experiments", response_model=list[ExperimentResponse])
    def experiments(service: Service) -> list[ExperimentResponse]:
        return [ExperimentResponse.from_domain(item) for item in service.list_experiments()]

    @application.post(
        "/api/v1/experiments",
        response_model=ExperimentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_experiment(body: CreateExperimentRequest, service: Service) -> ExperimentResponse:
        created = service.create_experiment(body.name, body.configuration.to_domain())
        return ExperimentResponse.from_domain(created)

    @application.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentResponse)
    def get_experiment(experiment_id: int, service: Service) -> ExperimentResponse:
        return ExperimentResponse.from_domain(service.get_experiment(experiment_id))

    @application.get("/api/v1/runs", response_model=list[RunResponse])
    def runs(service: Service) -> list[RunResponse]:
        return [RunResponse.from_domain(item) for item in service.list_runs()]

    @application.post(
        "/api/v1/experiments/{experiment_id}/runs",
        response_model=RunResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_run(experiment_id: int, service: Service) -> RunResponse:
        return RunResponse.from_domain(service.create_run(experiment_id))

    @application.get("/api/v1/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: int, service: Service) -> RunResponse:
        return RunResponse.from_domain(service.get_run(run_id))

    @application.post("/api/v1/runs/{run_id}/cancel", response_model=RunResponse)
    def cancel_run(run_id: int, service: Service) -> RunResponse:
        return RunResponse.from_domain(service.cancel_run(run_id))

    return application


app = create_app()
