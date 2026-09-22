import json
from typing import Annotated

import typer

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.service import NotFoundError
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_research.contracts import ModelId, SelectorId

app = typer.Typer(help="BeanFeature Lab reproducible local research CLI.")
system_app = typer.Typer()
experiment_app = typer.Typer()
run_app = typer.Typer()
dataset_app = typer.Typer()
core_app = typer.Typer()
classifier_app = typer.Typer()
app.add_typer(system_app, name="system")
app.add_typer(experiment_app, name="experiments")
app.add_typer(run_app, name="runs")
app.add_typer(dataset_app, name="dataset")
app.add_typer(core_app, name="core")
app.add_typer(classifier_app, name="classifier")


@classifier_app.command("train")
def train_classifier() -> None:
    """Refit RUN-000003 baseline on validated data for deployment, not evaluation."""
    metadata = create_container().service.train_deployment_classifier()
    typer.echo(json.dumps(metadata, ensure_ascii=False, indent=2))


@dataset_app.command("fetch")
def fetch_dataset(
    accept_official_schema: bool = typer.Option(
        False, help="Acknowledge DERMASON/AspectRation/roundness spellings in official ARFF"
    ),
) -> None:
    manifest = create_container().service.fetch_dataset(
        accept_official_schema=accept_official_schema
    )
    typer.echo(json.dumps(manifest, ensure_ascii=False, indent=2))


@dataset_app.command("validate")
def validate_dataset(accept_official_schema: bool = typer.Option(False)) -> None:
    manifest = create_container().service.validate_dataset(
        accept_official_schema=accept_official_schema
    )
    typer.echo(json.dumps(manifest, ensure_ascii=False, indent=2))


@dataset_app.command("list")
def list_datasets() -> None:
    typer.echo(json.dumps(create_container().service.list_datasets(), ensure_ascii=False, indent=2))


@system_app.command("info")
def system_info() -> None:
    container = create_container()
    typer.echo(json.dumps(container.service.system_info(), ensure_ascii=False, indent=2))


@experiment_app.command("list")
def list_experiments() -> None:
    container = create_container()
    for item in container.service.list_experiments():
        typer.echo(f"{item.id}\t{item.name}\t{item.configuration.model.value}")


@experiment_app.command("create")
def create_experiment(
    name: str,
    model: Annotated[ModelId, typer.Option()],
    selector: Annotated[SelectorId, typer.Option()],
    k_original_features: Annotated[int | None, typer.Option()] = None,
    n_components: Annotated[int | None, typer.Option()] = None,
    smoke: Annotated[
        bool, typer.Option(help="2×1 outer / 2 inner integration check; not final science")
    ] = False,
) -> None:
    container = create_container()
    kind = "pca_components" if selector is SelectorId.PCA else "original_features"
    try:
        item = container.service.create_experiment(
            name,
            ExperimentConfig(
                model=model,
                selector=selector,
                budget_kind=kind,
                k_original_features=k_original_features,
                n_components=n_components,
                required_raw_feature_count=16 if kind == "pca_components" else None,
                evaluation_mode="smoke" if smoke else "protocol",
            ),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Created experiment {item.id}. No scientific result has been calculated.")


@run_app.command("list")
def list_runs() -> None:
    container = create_container()
    for item in container.service.list_runs():
        typer.echo(f"{item.display_id}\t{item.status.value}\texperiment={item.experiment_id}")


@run_app.command("create")
def create_run(experiment_id: int) -> None:
    container = create_container()
    try:
        run = container.service.create_run(experiment_id)
    except NotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"{run.display_id} QUEUED — process with 'beanfeature runs process-next' or worker.")


@run_app.command("show")
def show_run(run_id: int) -> None:
    run = create_container().service.get_run(run_id)
    typer.echo(
        json.dumps(
            {
                "display_id": run.display_id,
                "status": run.status.value,
                "error": run.error,
                "summary": run.summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@run_app.command("process-next")
def process_next() -> None:
    run = create_container().service.process_next_run()
    if run is None:
        typer.echo("No QUEUED runs")
    else:
        typer.echo(
            f"{run.display_id} {run.status.value}" + (f" — {run.error}" if run.error else "")
        )


@run_app.command("result")
def run_result(run_id: int) -> None:
    result = create_container().service.get_run_result(run_id)
    if result is None:
        typer.echo("NOT_CALCULATED")
    else:
        typer.echo(json.dumps(result["summary"], ensure_ascii=False, indent=2))


@run_app.command("series")
def budget_series() -> None:
    typer.echo(
        json.dumps(create_container().service.feature_budget_series(), ensure_ascii=False, indent=2)
    )


@run_app.command("compare")
def compare_runs(compact_run_id: int, baseline_run_id: int) -> None:
    comparison = create_container().service.compare_runs(
        compact_run_id, baseline_run_id, persist=True
    )
    typer.echo(json.dumps(comparison, ensure_ascii=False, indent=2))


@core_app.command("enqueue-mi")
def enqueue_core_mi(
    confirm_compute: bool = typer.Option(False, help="Queue 86 full-protocol conditions"),
) -> None:
    if not confirm_compute:
        typer.echo(
            "Would queue 5×16 MI conditions plus six 16-feature baselines (86 runs). "
            "Pass --confirm-compute."
        )
        raise typer.Exit(2)
    service = create_container().service
    if not service.list_datasets():
        typer.echo("Validate official UCI 602 dataset first", err=True)
        raise typer.Exit(2)
    models = (
        ModelId.LOGISTIC_REGRESSION,
        ModelId.SVM_RBF,
        ModelId.RANDOM_FOREST,
        ModelId.XGBOOST,
        ModelId.LIGHTGBM,
    )
    for model in (*models, ModelId.MLP):
        experiment = service.create_experiment(
            f"C0 baseline {model.value}",
            ExperimentConfig(
                model=model,
                selector=SelectorId.NONE,
                budget_kind="original_features",
                k_original_features=16,
            ),
        )
        service.create_run(experiment.id)
    for model in models:
        for k in range(1, 17):
            experiment = service.create_experiment(
                f"C1 MI {model.value} k={k}",
                ExperimentConfig(
                    model=model,
                    selector=SelectorId.MUTUAL_INFORMATION,
                    budget_kind="original_features",
                    k_original_features=k,
                ),
            )
            service.create_run(experiment.id)
    typer.echo(
        "Queued 86 protocol runs. Execute with 'beanfeature-worker' or repeated "
        "'beanfeature runs process-next'."
    )
