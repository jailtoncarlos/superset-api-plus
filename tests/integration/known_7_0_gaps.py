"""Integration tests that fail on Superset 7.0 until a migration task fixes them (feature #53).

Each entry names the test (``<module>::<test>``) and the issue that fixes it. On a 7.0 server the test is marked
``xfail(strict=True)``: it still runs, and the day it passes the strict xfail fails, so the entry is removed with the
task that fixed it. On a server before 7.0 nothing is marked. Found by running the whole suite on a 7.0.0rc3 stack.
"""

KNOWN_7_0_GAPS = {
    "test_assets.py::test_charts_exported_in_batches_and_imported_one_object_at_a_time":
        "#69 (T-16): 7.0 exports add tags.yaml",
    "test_dashboards.py::test_dashboard_created_read_updated_and_deleted":
        "#69 (T-16): 7.0 json_metadata adds expand_all_slices and map_label_colors, drops filter_scopes",
    "test_dashboards.py::test_saving_a_chart_read_with_a_null_query_context_datasource_repairs_the_dashboard_datasets":
        "#136 (T-21): 7.0 no longer refuses a null query_context datasource",
    "test_dashboards.py::test_dashboard_layout_and_native_filters_are_stored_as_built":
        "#72 (T-19): 7.0 stores native filters differently",
    "test_dashboards.py::test_time_filter_without_dataset_and_chart_scoped_filter_are_stored":
        "#72 (T-19): chartsInScope of a chart scoped filter on 7.0",
    "test_dashboards.py::test_browser_check_reports_what_the_dashboard_shows":
        "#137 (T-22): the browser check reads the 6.1 dashboard DOM",
    "test_data.py::test_refresh_duplicate_and_get_or_create":
        "#138 (T-23): get_or_create of a physical table on the 7.0.0rc3 SQLite stack",
    "test_errors.py::test_error_list_body_is_mapped_by_status":
        "#139 (T-24): a 7.0 403 comes without the SIP-40 error list",
}
