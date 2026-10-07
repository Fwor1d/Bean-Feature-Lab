from beanfeature_infrastructure.resources import ProcessTreeResourceMonitor


def test_process_tree_resource_monitor_records_explicit_scope() -> None:
    result = ProcessTreeResourceMonitor(sampling_interval_seconds=0.005).start().finish()
    assert result["status"] == "CALCULATED"
    assert result["peak_process_tree_rss_bytes"] >= result["baseline_process_tree_rss_bytes"]
    assert result["incremental_peak_rss_bytes"] >= 0
    assert result["rss_samples"] >= 1
    expected_scope = "fresh run process: dataset-load, nested-search, refit, and evaluation"
    assert result["scope"] == expected_scope
