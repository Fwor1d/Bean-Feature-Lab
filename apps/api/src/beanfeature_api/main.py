import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from beanfeature_application.service import ApplicationService, ConflictError, NotFoundError
from beanfeature_infrastructure.bootstrap import Container, create_container
from beanfeature_research.contracts import ModelId

from .schemas import (
    ClassifierExampleResponse,
    CoreSufficiencyResponse,
    CreateExperimentRequest,
    DatasetQualityResponse,
    DatasetResponse,
    DeploymentModelResponse,
    ErrorResponse,
    ExperimentResponse,
    FeatureBudgetPointResponse,
    FoldResultResponse,
    HealthResponse,
    PredictRequest,
    PredictResponse,
    ProjectResponse,
    RunResponse,
    RunSummaryResponse,
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
    demo_read_only = os.getenv("BEANFEATURE_DEMO_READ_ONLY") == "1"

    @application.middleware("http")
    async def public_demo_guard(request: Request, call_next):
        inference = request.method == "POST" and request.url.path == "/api/v1/classifier/predict"
        if inference:
            content_length = request.headers.get("content-length")
            if content_length and not content_length.isdigit():
                return error_response("invalid_request", "Invalid Content-Length header", 400)
            if content_length and int(content_length) > 32_768:
                return error_response("payload_too_large", "Classifier request exceeds 32 KiB", 413)
        if demo_read_only and request.method not in {"GET", "HEAD", "OPTIONS"} and not inference:
            return error_response("demo_read_only", "Public presentation is read-only", 403)
        return await call_next(request)

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
    def datasets(service: Service) -> list[DatasetResponse]:
        return [DatasetResponse.model_validate(item) for item in service.list_datasets()]

    @application.get("/api/v1/datasets/{dataset_id}/manifest")
    def dataset_manifest(dataset_id: int, service: Service):
        return service.get_dataset_manifest(dataset_id)

    @application.get("/api/v1/datasets/{dataset_id}/quality", response_model=DatasetQualityResponse)
    def dataset_quality(dataset_id: int, service: Service) -> DatasetQualityResponse:
        return DatasetQualityResponse.model_validate(service.dataset_quality(dataset_id))

    @application.get("/api/v1/classifier/model", response_model=DeploymentModelResponse)
    def classifier_model(service: Service):
        model = service.classifier_info()
        if model is None:
            return error_response("not_found", "Deployment model is not registered", 404)
        return model

    @application.get("/api/v1/classifier/example", response_model=ClassifierExampleResponse)
    def classifier_example(service: Service) -> ClassifierExampleResponse:
        return ClassifierExampleResponse.model_validate(service.classifier_example())

    @application.post("/api/v1/classifier/predict", response_model=PredictResponse)
    def classifier_predict(body: PredictRequest, service: Service):
        return service.predict_classifier(body.features)

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

    @application.get("/api/v1/runs/{run_id}/summary", response_model=RunSummaryResponse)
    def run_summary(run_id: int, service: Service) -> RunSummaryResponse:
        run = service.get_run(run_id)
        return RunSummaryResponse(
            run_id=run.display_id,
            status=run.status,
            result_state="CALCULATED"
            if run.status.value == "COMPLETED" and run.summary
            else "NOT_CALCULATED",
            summary=run.summary if run.status.value == "COMPLETED" else None,
        )

    @application.get("/api/v1/runs/{run_id}/detail")
    def run_detail(run_id: int, service: Service):
        result = service.get_run_detail(run_id)
        if result is None:
            return error_response("not_calculated", "Scientific result is not available", 409)
        return result

    @application.get("/api/v1/runs/{run_id}/verify")
    def verify_run(run_id: int, service: Service):
        return service.verify_run(run_id)

    @application.get("/api/v1/runs/{run_id}/export/{export_kind}")
    def export_run(
        run_id: int,
        export_kind: Literal["result.json", "config.json", "folds.csv", "selected-features.csv"],
        service: Service,
    ) -> Response:
        filename, media_type, content = service.export_run(run_id, export_kind)
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @application.get("/api/v1/runs/{run_id}/folds", response_model=list[FoldResultResponse])
    def run_folds(run_id: int, service: Service):
        result = service.get_run_result(run_id)
        if result is None:
            return error_response("not_calculated", "Scientific result is not available", 409)
        return [FoldResultResponse.model_validate(fold) for fold in result["folds"]]

    @application.get("/api/v1/runs/{run_id}/stability")
    def run_stability(run_id: int, service: Service):
        result = service.get_run_result(run_id)
        if result is None:
            return error_response("not_calculated", "Scientific result is not available", 409)
        return {
            "run_id": result["run_id"],
            "feature_stability": result["summary"].get("feature_stability"),
        }

    @application.get("/api/v1/runs/{run_id}/paired-comparison/{baseline_run_id}")
    def run_paired_comparison(run_id: int, baseline_run_id: int, service: Service):
        return service.compare_runs(run_id, baseline_run_id)

    @application.get(
        "/api/v1/feature-budget/series", response_model=list[FeatureBudgetPointResponse]
    )
    def feature_budget_series(service: Service) -> list[FeatureBudgetPointResponse]:
        return [
            FeatureBudgetPointResponse.model_validate(item)
            for item in service.feature_budget_series()
        ]

    @application.get("/api/v1/core/sufficiency", response_model=list[CoreSufficiencyResponse])
    def core_sufficiency(service: Service) -> list[CoreSufficiencyResponse]:
        return [
            CoreSufficiencyResponse.model_validate(service.core_sufficiency(model))
            for model in ModelId
            if model is not ModelId.MLP
        ]

    @application.get("/api/v1/core/sufficiency/{model}", response_model=CoreSufficiencyResponse)
    def model_sufficiency(model: ModelId, service: Service) -> CoreSufficiencyResponse:
        return CoreSufficiencyResponse.model_validate(service.core_sufficiency(model))

    @application.post("/api/v1/runs/{run_id}/cancel", response_model=RunResponse)
    def cancel_run(run_id: int, service: Service) -> RunResponse:
        return RunResponse.from_domain(service.cancel_run(run_id))

    return application


app = create_app()
