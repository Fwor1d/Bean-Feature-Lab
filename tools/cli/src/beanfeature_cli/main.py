import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.service import NotFoundError
from beanfeature_infrastructure.benchmark import benchmark_deployment_model
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.files import ArtifactStore
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


def _run_primary_key(value: str) -> int:
    if value.isdigit():
        return int(value)
    match = re.fullmatch(r"RUN-(\d{6})", value)
    if not match:
        raise typer.BadParameter("Run must be an integer ID or RUN-000001 display ID")
    return int(match.group(1))


@classifier_app.command("train")
def train_classifier() -> None:
    """Refit RUN-000003 baseline on validated data for deployment, not evaluation."""
    metadata = create_container().service.train_deployment_classifier()
    typer.echo(json.dumps(metadata, ensure_ascii=False, indent=2))


@classifier_app.command("predict-example")
def predict_classifier_example() -> None:
    """Predict one real UCI row; this is a demo, not a scientific evaluation."""
    service = create_container().service
    example = service.classifier_example()
    prediction = service.predict_classifier(example["features"])
    typer.echo(
        json.dumps(
            {
                **prediction,
                "actual_class": example["actual_class"],
                "correct": prediction["predicted_class"] == example["actual_class"],
                "demo_note": "One UCI row; not an evaluation metric.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@classifier_app.command("benchmark")
def benchmark_classifier(
    repeats: Annotated[int, typer.Option(min=5, max=1_000)] = 30,
) -> None:
    """Measure deployment latency, size, and process-tree RSS outside scientific CV."""
    result = benchmark_deployment_model(repeats=repeats)
    measured_at = datetime.now(UTC)
    payload = {**result, "measured_at_utc": measured_at.isoformat()}
    relative = f"benchmarks/{result['model_id']}-{measured_at:%Y%m%dT%H%M%SZ}.json"
    store = ArtifactStore(Path("artifacts/models"))
    digest = store.write_json(relative, payload)
    store.write_json(
        "benchmarks/latest.json",
        {"artifact_relative_path": relative, "artifact_sha256": digest},
    )
    typer.echo(
        json.dumps(
            {**payload, "artifact_relative_path": relative, "artifact_sha256": digest},
            ensure_ascii=False,
            indent=2,
        )
    )


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


@dataset_app.command("quality")
def dataset_quality(dataset_id: Annotated[int, typer.Option()] = 1) -> None:
    """Report source quality diagnostics without modifying the validated dataset."""
    quality = create_container().service.dataset_quality(dataset_id)
    typer.echo(json.dumps(quality, ensure_ascii=False, indent=2))


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


@run_app.command("verify")
def verify_run(run: str) -> None:
    verification = create_container().service.verify_run(_run_primary_key(run))
    typer.echo(json.dumps(verification, ensure_ascii=False, indent=2))
    if not verification["verified"]:
        raise typer.Exit(1)


@run_app.command("reproduce")
def reproduce_run(run: str) -> None:
    source_id = _run_primary_key(run)
    created = create_container().service.reproduce_run(source_id)
    typer.echo(
        f"{created.display_id} QUEUED as a new reproduction of RUN-{source_id:06d}. "
        "The source run was not modified."
    )


@run_app.command("export")
def export_run(
    run: str,
    kind: Annotated[
        str,
        typer.Option(help="result.json, config.json, folds.csv, or selected-features.csv"),
    ] = "result.json",
    output: Annotated[Path | None, typer.Option()] = None,
) -> None:
    filename, _media_type, content = create_container().service.export_run(
        _run_primary_key(run), kind
    )
    destination = output or Path(filename)
    destination.write_bytes(content)
    typer.echo(str(destination.resolve()))


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
    confirm_compute: bool = typer.Option(
        False, help="Idempotently queue only missing Core MI/baseline conditions"
    ),
) -> None:
    service = create_container().service
    plan = service.enqueue_core_matrix(create=confirm_compute)
    typer.echo(json.dumps(plan, ensure_ascii=False, indent=2))
    if not confirm_compute and plan["missing"]:
        typer.echo(
            "Dry run only. Pass --confirm-compute to enqueue the missing conditions.",
            err=True,
        )


@core_app.command("sufficiency")
def core_sufficiency(
    model: Annotated[ModelId | None, typer.Option()] = None,
    persist: Annotated[
        bool, typer.Option(help="Write a hash-addressed derived analysis artifact")
    ] = False,
) -> None:
    service = create_container().service
    models = (
        [model]
        if model
        else [
            ModelId.LOGISTIC_REGRESSION,
            ModelId.SVM_RBF,
            ModelId.RANDOM_FOREST,
            ModelId.XGBOOST,
            ModelId.LIGHTGBM,
        ]
    )
    typer.echo(
        json.dumps(
            [service.core_sufficiency(selected, persist=persist) for selected in models],
            ensure_ascii=False,
            indent=2,
        )
    )


@core_app.command("enqueue-comparators")
def enqueue_core_comparators(
    confirm_compute: bool = typer.Option(
        False, help="Idempotently queue missing Core comparator conditions"
    ),
    branch: Annotated[
        list[str] | None,
        typer.Option(
            help=(
                "Limit to repeatable branch names: anova, rfe, tree_importance, l1_sparse_path, pca"
            )
        ),
    ] = None,
) -> None:
    service = create_container().service
    plan = service.enqueue_core_comparators(
        create=confirm_compute,
        branches=set(branch) if branch else None,
    )
    typer.echo(json.dumps(plan, ensure_ascii=False, indent=2))
    if not confirm_compute and plan["missing"]:
        typer.echo(
            "Dry run only. Pass --confirm-compute to enqueue the missing conditions.",
            err=True,
        )
