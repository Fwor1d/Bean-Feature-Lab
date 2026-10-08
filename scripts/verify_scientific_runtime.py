"""Read-only restored-evidence check; no acquisition, training, recovery or DB writes."""

import argparse
import json
from collections import Counter
from pathlib import Path

from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_research.engine import validated_frozen_outer_splits


def verify(root: Path) -> dict:
    root = root.resolve()
    database = root / "storage/sqlite/beanfeature.sqlite"
    if not database.is_file() or (root / ".restore-in-progress").exists():
        raise ValueError("Runtime is missing or restoration is incomplete")
    url = "sqlite:///" + database.as_uri() + "?mode=ro&uri=true"
    container = create_container(url, runtime_root=root)
    try:
        service = container.service
        dataset, dataset_manifest = service.dataset_store.load()
        runs = service.list_runs()
        verified, full_protocol = 0, 0
        sources = {}
        for run in runs:
            if run.status.value != "COMPLETED":
                continue
            result = service.verify_run(run.id)
            if not result["verified"]:
                raise ValueError(f"{run.display_id}: {result['errors']}")
            verified += 1
            config = service.get_experiment(run.experiment_id).configuration
            if config.evaluation_mode != "protocol":
                continue
            key = (config.dataset_version, config.seed, run.dataset_hash)
            if key not in sources:
                sources[key] = service.resolve_frozen_outer_manifest(config, dataset)
            payload = service.get_run_result(run.id)
            manifest = {
                "dataset_hash": payload["dataset_manifest"]["arff_sha256"],
                "dataset_version": payload["dataset_manifest"]["dataset_version"],
                "rows": payload["dataset_manifest"]["rows"],
                "seed": payload["configuration"]["seed"],
                "cv_protocol_version": payload["summary"]["cv_protocol_version"],
                "outer_split_set_sha256": payload["summary"]["outer_split_set_sha256"],
                "splits": payload.get("splits"),
            }
            validated_frozen_outer_splits(
                manifest,
                dataset.target,
                seed=config.seed,
                dataset_hash=dataset.arff_sha256,
                dataset_version=config.dataset_version,
            )
            if manifest["outer_split_set_sha256"] != sources[key]["outer_split_set_sha256"]:
                raise ValueError(f"{run.display_id}: outer manifest differs from frozen source")
            full_protocol += 1
        model = service.classifier_info()
        return {
            "verified": True,
            "run_counts": dict(Counter(run.status.value for run in runs)),
            "completed_verified": verified,
            "full_protocol_verified": full_protocol,
            "dataset_version": dataset_manifest["dataset_version"],
            "dataset_sha256": dataset.arff_sha256,
            "rows": len(dataset.target),
            "features": dataset.feature_names,
            "frozen_sources": [
                {key: manifest[key] for key in ("source_run_id", "outer_split_set_sha256")}
                for manifest in sources.values()
            ],
            "deployment_model": model["model_id"] if model else None,
        }
    finally:
        container.metadata.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, indent=2))
