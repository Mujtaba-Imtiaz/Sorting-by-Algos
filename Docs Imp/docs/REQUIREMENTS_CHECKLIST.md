# Requirements Checklist

"Verified" below means I ran it (tests or a live run) in my development environment. "Manual" means it needs a human to look at it (the GUI was exercised offscreen by automated tests, but a person has not yet looked at it on a real screen, and Windows was not available to me).

| # | Requirement | Where | Test / evidence | Status |
|---|---|---|---|---|
| 1 | Python 3, PyQt6, GitHub REST API, stdlib, CSV/JSON, local persistent DB | `requirements.txt`, `github_client.py`, `database.py`, `exporter.py` | all tests | Verified |
| 2 | At least 15,000 unique records, no fabrication | `scraper.py`, `config.py` (bulk plan) | Live run: 15,076 unique IDs saved in two resumed slices (about 7 minutes in total, no token) | Verified (live) |
| 3 | At least 12 attributes (17 stored) | `models.py` | `test_database.NormalizeTests` | Verified |
| 4 | Null-safe description/language/license | `models.normalize_repository`, `comparable_value` | `test_missing_fields_become_none`, sorting/filter missing tests; live data had 187 missing descriptions and 1,114 missing licenses | Verified |
| 5 | Unique by repository ID, total count shown | `database.save_repositories`, Dashboard | `test_duplicates_are_not_counted_twice`, `test_overlapping_queries_do_not_create_duplicates` | Verified |
| 6 | Official API, URL input with validation and help | `github_client.parse_source_url`, `SUPPORTED_FORMATS_HELP` | `test_supported_urls`, `test_invalid_urls`, GUI test for invalid URL | Verified |
| 7 | Start, Pause, Resume, Stop, status, count, progress %, readable errors/rate limits | `scraper.Collector`, `ui/collection_tab.py`, `ui/workers.py` | `test_pause_really_pauses_and_resume_continues`, `test_stop_while_paused...`, `test_rate_limit_is_waited_out...`, GUI button-state test | Verified (logic); GUI look is Manual |
| 8 | Responsive GUI via background workers | `ui/workers.py` | GUI tests drive threads; sort and collection run off the GUI thread | Verified (logic) |
| 9 | Incremental saving and resume (also after restart) | `database.save_progress`, `Collector` | `test_resume_continues_from_saved_page...`, `test_records_and_progress_survive_a_restart`, live resume "query 61, page 5" | Verified |
| 10 | Pagination, duplicates, network failure, invalid URL, rate limit, auth errors, missing fields, unexpected responses | `github_client.py`, `scraper.py` | `test_error_ends_the_run...`, `test_query_rejected_with_422...`, `test_single_repository_and_not_found`; 401 and network paths are coded but only simulated through exceptions, not triggered live | Verified (simulated) |
| 11 | Optional token, masked, never saved/logged/exported | `collection_tab.py`, `github_client.py` | `test_no_token_or_secret_columns_exist`, `test_export_has_no_secret_fields`; token only in an `Authorization` header | Verified |
| 12 | Explain rate limits and 15,000 strategy | README sections 4 to 5, tutorial, walkthrough | Documentation | Done |
| 13 | Dashboard (counts, languages, stars, archived, status, chart) | `ui/dashboard_tab.py` | GUI test checks card values; chart is Manual | Verified / Manual |
| 14 | Explorer: paged table, header sorting, multi-column filters, multi-level sort, open in browser, detail view | `ui/explorer_tab.py`, `repository_table.py`, `filter_panel.py` | `test_explorer_filter_and_header_sorting`; opening the browser is Manual | Verified / Manual |
| 15 | Sorting Lab: algorithm, column, direction, scope, metrics, complexity, stability, Benchmark All, table | `ui/sorting_tab.py` | `test_sorting_lab_single_run_scope_and_apply`, `test_benchmark_all_with_two_level_sort` | Verified |
| 16 | Export selected/filtered CSV/JSON with explanation | `ui/export_tab.py`, `exporter.py` | `test_export.*`, `test_export_tab_counts_and_writes` | Verified |
| 17 | Bubble, selection, insertion, merge, quick, counting | `sorting_algorithms.py` | `test_sorting.*` (all columns, both directions) | Verified |
| 18 | At least two extra algorithms (heap, shell, plus radix, bucket and bogo) | `sorting_algorithms.py` | same | Verified |
| 19 | No `sorted()`/`list.sort()` inside the sorting | `sorting_algorithms.py` | search the file; `sorted` appears only in tests | Verified |
| 20 | Counting, radix and bucket sort disabled for text, bogo sort limited to 8 records, each with an explanation | `unsupported_reason`, `sorting_tab.update_algorithm_choices` | `test_counting_sort_rejects_text_columns`, `test_radix_sort_refuses_text`, `BucketSortTests`, `test_bogo_sort_refuses_more_than_the_limit`, `test_text_column_disables_counting_sort` | Verified |
| 21 | Real records sorted; attributes preserved | entries `(keys, record)` | `test_no_records_lost_or_duplicated_and_attributes_preserved` | Verified |
| 22 | Metrics: time, comparisons, swaps, movements, complexity, stability, count; counted inside algorithms; timer around algorithm only | `SortMetrics`, `sort_records` | `test_metrics_are_non_negative...`, `test_counts_are_exact_for_a_tiny_example` | Verified |
| 23 | Merge/counting report 0 swaps, movements separately | same | `test_metrics_...` | Verified |
| 24 | Stability stated from real behaviour | `ALGORITHMS` | `test_stable_algorithms_keep_original_order...`, `test_unstable_label_is_honest` | Verified |
| 25 | Benchmark: equal copies, same key semantics, verification, fastest, no hard-coded numbers, sample/confirmation for O(n²), record counts shown | `benchmark.py`, `sorting_tab.confirm_slow` | `BenchmarkTests`, GUI benchmark test; live full-size benchmark on 15,076 records | Verified |
| 26 | Linear, binary (sorted required), extra search, all operators, per column | `searching_algorithms.py`, `ui/search_tab.py` | `test_binary_search_agrees_with_linear_search_for_every_operator`, `...refuses_unsorted_data`, hash test | Verified |
| 27 | Advanced filters AND/OR/NOT, string operators, add/remove/clear | `filtering.py`, `filter_panel.py` | `test_filtering.*` | Verified |
| 28 | Multi-level sorting with add/remove levels and directions | `SortSpec`, `LevelsEditor` | `test_multi_level_sorting_matches_reference_for_every_algorithm`, GUI two-level benchmark | Verified |
| 29 | Full vs filtered scope without corrupting data | `sorting_tab`, `explorer_tab.show_sorted_result` | `test_sorting_lab_single_run_scope_and_apply` (stored count stays 1,200) | Verified |
| 30 | Empty dataset, invalid inputs, repeated clicks, safe shutdown | empty-state labels, disabled buttons, `closeEvent` | empty-dataset search/sort tests; `test_collection_buttons_and_url_validation`; closing during a live run is Manual | Partly verified |
| 31 | Complete project, README, Windows guide, PyCharm guide, token guide, tests guide, troubleshooting, viva, tutorial | `README.md`, `docs/` | Documentation | Done |

## Test results (last run)

`python -m unittest discover -s tests` : **Ran 96 tests, OK** (run three times in a row, in Linux, Python 3.12, PyQt6 offscreen).

## Honest limitations

- I could not run on Windows or look at the window on a real display. Do the manual GUI walk-through once (README section 11) before the viva.
- The 15,000 target was reached against the live API from my environment on 2026-10-12. Your run depends on GitHub's current data, rate limits and network. Without a token it can be slower (GitHub documents 10 search requests per minute); with a token it is faster. If you end with fewer than 15,000, the Dashboard shows the true number; run Start again (it resumes) or lower the star range in `config.py`.
- Collected repositories are the top results by stars for each language and star range, so the dataset is biased toward popular repositories.
- GitHub search results can change between runs, so counts may differ slightly.
- The unauthenticated single-repository endpoint has only 60 requests per hour; this was exhausted in my shared environment, so the "one repository" URL path was verified with a simulated client, and the live-API check used the search path.
- Dates are compared by day, not by time of day.
- Explorer header sorting uses Merge Sort; it takes about 0.3 seconds for 15,000 records.
