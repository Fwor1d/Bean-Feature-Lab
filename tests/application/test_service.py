import pytest

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.service import ApplicationService
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.database import Base
from beanfeature_research.contracts import ModelId, SelectorId


def test_pca_cannot_be_original_budget(tmp_path) -> None:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    service: ApplicationService = container.service
    with pytest.raises(ValueError, match="PCA is not"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.PCA,
                "original_features",
                k_original_features=4,
            ),
        )
    with pytest.raises(ValueError, match="PCA requires"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.MUTUAL_INFORMATION,
                "pca_components",
                n_components=4,
            ),
        )
    with pytest.raises(ValueError, match="all 16"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.PCA,
                "pca_components",
                n_components=4,
                required_raw_feature_count=4,
            ),
        )
