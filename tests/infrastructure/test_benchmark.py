import pytest

from beanfeature_infrastructure.benchmark import benchmark_deployment_model


def test_benchmark_rejects_unreliable_sampling_configuration() -> None:
    with pytest.raises(ValueError, match="repeats"):
        benchmark_deployment_model(repeats=1)
    with pytest.raises(ValueError, match="Sampling interval"):
        benchmark_deployment_model(sampling_interval_seconds=0.001)
