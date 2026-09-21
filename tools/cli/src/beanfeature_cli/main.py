import json
from typing import Annotated

import typer

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.service import NotFoundError
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_research.contracts import ModelId, SelectorId

app = typer.Typer(help="BeanFeature Lab foundation CLI. Scientific execution is not implemented.")
system_app = typer.Typer()
experiment_app = typer.Typer()
run_app = typer.Typer()
app.add_typer(system_app, name="system")
app.add_typer(experiment_app, name="experiments")
app.add_typer(run_app, name="runs")


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
    typer.echo(f"{run.display_id} QUEUED — execution is not implemented in Stage 4A.")
