# RepoScope Code Walkthrough (for beginners)

## 1. The big picture

```
GitHub API -> fetch pages -> validate/normalize -> save in SQLite -> load list -> search/filter -> sort -> measure -> show
 github_client   scraper        models.py           database.py     data_store    filtering.py    sorting_   benchmark   ui/
                                                                                  searching_      algorithms
```

1. `github_client.py` sends an HTTPS request such as `/search/repositories?q=language:"Python" stars:>=20000&per_page=100&page=1` and returns JSON converted to a Python dictionary.
2. `scraper.py` (class `Collector`) loops over pages and queries, and after each page calls `models.normalize_repository` for every item. That function turns the nested GitHub object into a flat dictionary with our 17 keys and turns missing values into `None`.
3. `database.py` saves the flat dictionaries in SQLite. The repository ID is the primary key, so repeats are updates, not new rows. It also saves "query number and page" so collection can resume.
4. When collection ends, `DataStore.reload()` reads all rows into one Python list of dictionaries (`store.records`). This list is the single source of truth the tabs read from. Tabs never modify it; they build new lists from it.
5. `filtering.py` and `searching_algorithms.py` produce smaller lists. `sorting_algorithms.py` produces sorted copies and counts its own work. `benchmark.py` runs all algorithms fairly and verifies them. The `ui/` files display everything.

Everything is a plain `dict`, so when a repository is moved by a sort, all of its attributes move with it.

## 2. The comparison rules (`models.comparable_value`)

All three features (sort, search, filter) call this one function so they always agree:

- text: stripped, lowercase (`"Python "` becomes `"python"`); empty becomes missing.
- numbers: `int`; non-numbers become missing.
- dates: whole day number (`date.toordinal()`); times inside a day are ignored.
- archived: 0 or 1.
- missing: `None`. In sorting, missing always goes last, in ascending and descending order. In filters, a missing value never matches `equals`, `contains`, `greater_than` etc.; only `is missing` matches it.

## 3. Source files

- `config.py`: constants only (API address, 100 per page, 1000 results limit, the 20 languages and 7 star ranges of the automatic plan, default target 15,000).
- `models.py`: `Column` list (key, label, kind), `normalize_repository`, `comparable_value`.
- `database.py`: class `Database`. `save_repositories` uses `INSERT ... ON CONFLICT(id) DO UPDATE`, i.e. "insert, but if the ID exists, update". It returns `(new, duplicates)` by comparing the row count before and after. `get_progress/save_progress/reset_progress` store resume info. `get_statistics` runs SQL (`COUNT`, `SUM`, `GROUP BY`) for the dashboard.
- `github_client.py`: `parse_source_url` validates what the user typed; `GitHubClient._request` sends the request, remembers the rate-limit headers, retries network errors and 5xx errors up to 3 times, and converts HTTP errors into our own exceptions (`AuthError`, `NotFoundError`, `RateLimitError`, `ApiError`, `NetworkError`).
- `scraper.py`: `Collector`, explained in section 7.
- `sorting_algorithms.py`, `benchmark.py`, `searching_algorithms.py`, `filtering.py`, `exporter.py`: explained below.
- `ui/`: `main_window.py` creates the tabs and connects them; `workers.py` holds the two background threads; `repository_table.py` is the paged table; `filter_panel.py`, `explorer_tab.py`, `search_tab.py`, `sorting_tab.py`, `collection_tab.py`, `dashboard_tab.py`, `export_tab.py` are the tabs; `theme.py` is the colour/style sheet.

## 4. Sorting

### 4.1 How the code is organised

- A **sort spec** is a list of levels such as `[("language", False), ("stars", True), ("name", False)]` (the boolean means descending).
- For each record we build an **entry** `(keys, record)`, where `keys` has one `(is_missing, value)` pair per level. Building keys happens before the timer starts.
- `SortSpec.compare(a, b)` returns -1, 0 or 1. It looks at level 1; only if the keys tie does it look at level 2, and so on. That is how **multi-level sorting** works for every algorithm: one comparison of two records uses all levels. It is the "equivalent correct method" to doing several stable passes. (Counting sort is the exception: it does it by stable passes from the last level to the first.)
- Each algorithm has the signature `algorithm(items, spec, metrics)` and returns the sorted list. `metrics` holds `comparisons`, `swaps`, `movements`.
- `sort_records` copies the input into entries, starts `time.perf_counter()`, calls the algorithm, stops the timer, and returns a `SortResult` (time, comparisons, swaps, movements, complexity, stability, record count, sorted records). Python's `sorted()` and `list.sort()` are not used anywhere in the project's sorting. (The tests use `sorted` only as an independent answer key.)

### 4.2 What is counted

- **Comparison**: one call of `compare` between two records. Counted by `metrics.comparisons += 1` right before the call, inside the algorithm. Never estimated.
- **Swap**: two items in the same list exchange places (`a[i], a[j] = a[j], a[i]`). Counted once. A swap of an item with itself is skipped and not counted.
- **Movement**: one item written into a list position outside a swap: an insertion-sort shift, the final placement, a merge-sort output write, a counting-sort placement. Merge sort and counting sort report 0 swaps and only movements. Bubble, selection, quick and heap sort report swaps and 0 movements.

### 4.3 Worked example used below

Three repositories, sort by stars ascending: `A=30, B=10, C=20`. Expected result: `B, C, A`.
Measured by the real code: Bubble 3 comparisons/2 swaps; Selection 3/2 swaps; Insertion 3 comparisons/0 swaps/4 movements; Merge 3 comparisons/0 swaps/5 movements; Quick 5 comparisons/2 swaps; Counting 0 comparisons/3 movements; Heap 3 comparisons/2 swaps; Shell 3 comparisons/4 movements.

### 4.4 The algorithms

**Bubble sort.** Idea: walk through the list, swapping neighbours that are in the wrong order; the biggest item "bubbles" to the end each pass.
Walk-through of `[30, 10, 20]`: compare 10 and 30, swap -> `[10, 30, 20]`; compare 20 and 30, swap -> `[10, 20, 30]`; next pass compare 20 and 10, no swap, so stop. 3 comparisons, 2 swaps.
```python
for end in range(len(items) - 1, 0, -1):      # the unsorted part is items[0..end]
    swapped = False
    for j in range(end):
        metrics.comparisons += 1
        if compare(items[j + 1], items[j]) < 0:   # strictly "<": equal items never swap
            items[j], items[j + 1] = items[j + 1], items[j]
            metrics.swaps += 1
            swapped = True
    if not swapped:                                # nothing moved: already sorted, stop early
        break
```
Time best O(n) (already sorted, thanks to the early stop), average and worst O(n²). Extra space O(1). Stable: yes, because equal items are never swapped.

**Selection sort.** Idea: find the item that belongs first, swap it into place, repeat for the rest.
Walk-through: smallest of `[30,10,20]` is 10, swap with position 0 -> `[10,30,20]`; smallest of the rest is 20, swap -> `[10,20,30]`.
Code: the inner loop updates `first_in_order` whenever `compare(items[j], items[first_in_order]) < 0` (one comparison counted each time); after the loop, `if first_in_order != start:` swap and count one swap.
Time O(n²) always (it always scans). Space O(1). It makes at most n-1 swaps (few swaps). **Not stable**: the long-distance swap can jump an item over an equal one. Example: `X=500, Y=500, Z=100` ascending becomes `Z, Y, X`: X and Y reversed.

**Insertion sort.** Idea: keep the left part sorted; take the next item and slide it left into its place, like sorting playing cards in your hand.
Walk-through: `[30,10,20]`: take 10, shift 30 right, place 10 -> `[10,30,20]` (2 movements); take 20, shift 30 right, stop at 10, place 20 (2 movements).
```python
current = items[i]; j = i - 1
while j >= 0:
    metrics.comparisons += 1
    if compare(current, items[j]) < 0:     # strictly smaller: shift the bigger item right
        items[j + 1] = items[j]; metrics.movements += 1; j -= 1
    else:
        break
if j + 1 != i:                              # write the held item only if it actually moved
    items[j + 1] = current; metrics.movements += 1
```
Time best O(n) (already sorted), average and worst O(n²). Space O(1). Stable: yes (equal items are not shifted past). Uses shifts, so 0 swaps and movements counted.

**Merge sort.** Idea: split in half, sort each half, merge the two sorted halves by repeatedly taking the smaller front item.
Walk-through: `[30,10,20]` -> `[30]` and `[10,20]`; `[10,20]` -> merge `[10]`,`[20]` = `[10,20]`; merge `[30]` with `[10,20]`: 10 < 30 take 10, 20 < 30 take 20, then the leftover 30.
```python
if compare(right[j], left[i]) < 0:   # take right only if strictly smaller
    merged.append(right[j]); j += 1
else:                                # tie: take left, the earlier item -> stable
    merged.append(left[i]); i += 1
metrics.movements += 1               # every item appended to the output is a movement
```
Time O(n log n) in best, average and worst. Space O(n) for the temporary lists. Stable: yes. Swaps: 0.

**Quick sort.** Idea: pick a pivot; put smaller items before it, equal items next to it, larger items after it; repeat on the smaller and larger groups.
Our version is a "three-way partition" (smaller / equal / larger) which stays fast when many repositories have the same stars or language. It recurses into the smaller part and loops over the larger part so the call stack stays about log n deep. The pivot is the middle item, so already sorted data is not a worst case.
Time best/average O(n log n), worst O(n²). Space O(log n). **Not stable** (partitioning swaps items across distance). Counts: one comparison per item per partition, and a swap each time two items exchange places.

**Counting sort.** Idea: if keys are whole numbers in a limited range, count how many items have each key, turn the counts into starting positions, and place each item directly. No comparisons.
Example keys `[3, 1, 2, 1]`: counts for 1,2,3 = `[2,1,1]`; start positions `[0,2,3]`; placing items left to right gives `1,1,2,3`, with the two 1s in their original order.
Code: `bucket_of(entry)` maps a key to a bucket (reversed with `high - value` for descending; missing values go to an extra last bucket); the loop `output[counts[bucket]] = entry; counts[bucket] += 1` places items and counts one movement each.
Time O(n + k) where k is the key range; space O(n + k); stable. **Only allowed for whole numbers and dates** (stars, forks, open issues, created, updated, id, archived). For text columns it is disabled with a tooltip, and the benchmark lists it as "Not available: ...". It is also refused when the range is above 1,000,000. For several levels it runs one stable pass per level from the last to the first.

**Heap sort (extra).** Idea: arrange the items as a max-heap (every parent is "after or equal" to its children). The largest is at the top; swap it to the end, shrink the heap, repair, repeat. `_sift_down` repairs a heap by comparing a parent with its two children (2 comparisons per level) and swapping downwards.
Time O(n log n) always; space O(1); not stable.

**Shell sort (extra).** Idea: insertion sort that first compares items far apart (gap 40, then 13, 4, 1), so items travel long distances quickly, and the last gap-1 pass has little to fix. The gaps follow `gap = 3*gap + 1` (Knuth).
Time about O(n^1.5) for this gap sequence (best near O(n log n)); space O(1); not stable. Uses shifts, so 0 swaps and movements counted.

**Radix sort (extra).** Idea: sort whole numbers one digit at a time, starting with the ones digit, then tens, then hundreds. For each digit, drop every record into one of ten buckets (0 to 9), then collect the buckets in order. Because each round keeps the earlier order of equal digits, after the last digit the numbers are fully sorted.
Example keys `[170, 45, 75, 90]`: ones digit -> buckets 0: 170, 90; 5: 45, 75 -> `[170, 90, 45, 75]`. Tens digit -> 4: 45; 7: 170, 75; 9: 90 -> `[45, 170, 75, 90]`. Hundreds digit -> 0: 45, 75, 90; 1: 170 -> `[45, 75, 90, 170]`.
```python
buckets = [[] for _ in range(10)]                    # one bucket for each digit 0 to 9
for number, entry in pairs:                          # visited in order, so equal digits keep their order
    buckets[(number // place) % 10].append((number, entry))
    metrics.movements += 1                           # placing a record in a bucket is one movement
pairs = [pair for bucket in buckets for pair in bucket]
place *= 10                                          # 1 -> 10 -> 100 ...
```
Before the digit rounds each key is turned into a number that is 0 or bigger (`value - smallest`, or `biggest - value` for descending). Missing values are set aside and placed last. For several levels it runs one full radix sort per level, last level first.
Time O(d·n), where d is the number of digits of the biggest key (stars up to 6 digits, so 6 rounds); space O(n + 10); stable. 0 comparisons and 0 swaps. Only for numbers and dates (disabled for text). Measured here: 36 ms for 15,076 repositories by stars, with 90,456 movements (6 rounds x 15,076).

**Bucket sort (extra).** Idea: spread the numbers into buckets by size, sort each small bucket, then join the buckets in order. Like sorting exam papers into piles (0 to 9, 10 to 19, ...), sorting each pile by hand, and stacking the piles.
Example keys `[170, 45, 75, 90]` with 4 buckets over the range 45 to 170: bucket 0 gets 45 and 75, bucket 1 gets 90, bucket 2 is empty, bucket 3 gets 170. Only bucket 0 needs sorting (75 is compared with 45, 1 comparison). Joining gives `[45, 75, 90, 170]`. RepoScope reports exactly this: 1 comparison, 0 swaps, 4 movements.
```python
bucket_count = len(pairs)                                  # as many buckets as records
for number, entry in pairs:
    buckets[number * bucket_count // (largest + 1)].append((number, entry))   # small -> first buckets, big -> last
    metrics.movements += 1                                 # placing a record in a bucket is one movement
for bucket in buckets:
    _sort_one_bucket(bucket, metrics)                      # insertion sort inside the bucket
    sorted_pairs.extend(bucket)                            # then join the buckets in order
```
The formula `number * bucket_count // (largest + 1)` always gives a bucket from 0 to `bucket_count - 1`, and a bigger number never gets a smaller bucket, so the joined result is in order. Inside a bucket it uses insertion sort with a strict "<", so equal keys keep their order and the whole sort is stable. A comparison here compares two keys of the current level; each shift and placement inside a bucket is a movement too. Descending order and missing values (always last) are handled the same way as in radix sort, and several levels are done one after another, last level first.
Time: best and average O(n + k) when the numbers are spread out evenly (k = number of buckets); worst O(n²) if almost all records fall into one bucket, because then it is just insertion sort. Space O(n + k). Stable. Only numbers and dates (disabled for text). Measured here on 15,076 repositories: 35 ms by stars, 25 ms by created date, 20 ms by ID, against Merge Sort 97 ms, 46 ms and 42 ms. Forks, whose values are very uneven, took 79 ms.

**Bogo sort (extra, joke algorithm).** Idea: shuffle the list randomly, check whether it is sorted, and repeat until it is. Like throwing a deck of cards in the air until it lands in order.
```python
while not _is_in_order(items, compare, metrics):     # each check compares neighbours (comparisons counted)
    metrics.check_stop()                             # lets the Cancel button work
    for i in range(len(items) - 1, 0, -1):           # shuffle: swap each item with a random earlier one
        j = generator.randint(0, i)
        if j != i:
            items[i], items[j] = items[j], items[i]
            metrics.swaps += 1
```
Time: best O(n) (already sorted), average O(n·n!), worst has no upper limit (it is random). For 8 records n! = 40,320 shuffles on average; for 15,076 records the number has tens of thousands of digits, so it would never finish. **RepoScope therefore only allows Bogo Sort for 8 records or fewer** and explains why otherwise (use "Use only a random sample"). Not stable (random). The seed is fixed (42), so a run can be repeated. Measured here: 8 records took 13.5 ms and about 20,000 swaps.

### 4.5 Stability with an example

Two repositories with equal stars: `X (500 stars)`, `Y (500)`, plus `Z (100)`, in that input order. A stable sort keeps X before Y: ascending -> `Z, X, Y`. Bubble, insertion, merge and counting sort do that (RepoScope's tests check it against an answer key for both directions). Selection sort gives `Z, Y, X`. Stability matters for multi-level sorting by passes ("sort by name, then stable-sort by language") and when you want ties to stay in the earlier order.

### 4.6 Why benchmark results differ

- Different amounts of work: O(n²) algorithms do millions of comparisons; O(n log n) ones tens of thousands.
- Different kinds of work: swapping, shifting and comparing cost different amounts in Python.
- Data shape: insertion/bubble sort are fast on nearly sorted input; quick sort struggles on adversarial input.
- Noise: other programs, CPU caches, Python's memory management. So a run can differ by a few percent. A good big-O does not guarantee winning on small inputs.
- Radix, bogo and the others: Counting Sort 28 ms and Radix Sort 36 ms (no comparisons at all) versus Merge Sort 86 ms on the same 15,076 repositories sorted by stars; this run was timed separately from the numbers below.
- Real measurement from this project (15,076 collected repositories, stars descending): Counting Sort 37 ms, Merge Sort 104 ms, Quick Sort 123 ms, Heap Sort 212 ms, Shell Sort 233 ms. On a 2,000-record sample sorted by three levels: Bubble 881 ms, Selection 667 ms, Insertion 421 ms, Merge 11 ms. (Your computer will give other numbers.)

### 4.7 Benchmark method (`benchmark.py`)

1. `prepare_input` chooses the input: all records, optionally a random sample or a shuffled copy with a fixed seed (42), so repeats are comparable.
2. For each algorithm `sort_records` builds new entries from the same original list, so no algorithm ever sees another's output.
3. `verify_result` checks, without sorting: same number of records; the same Python objects (nothing lost or duplicated); every neighbouring pair in order; for stable algorithms equal keys keep their original order. Then the sorted key sequence must equal the first algorithm's.
4. Only if all results are verified does the GUI name the fastest. Otherwise it shows "Comparison is not valid".
5. Safeguard: above 3,000 records, if a quadratic algorithm is selected, a dialog offers Run anyway / Skip the slow ones / Cancel. The sample option lets you benchmark fewer records.

## 5. Searching (`searching_algorithms.py`)

- **Linear search**: look at every record in order. One record check = one comparison. Works for every operator and on unsorted data. Example: find `stars == 5` in `[7, 5, 9]`: 2 checks.
- **Binary search**: for data sorted ascending, look at the middle; if the wanted value is bigger, discard the left half, otherwise the right half. For `[1, 3, 5, 7, 9]` finding 7: middle 5 < 7 -> keep `[7, 9]`; middle 7 found. About log₂ n steps (27 comparisons for 15,076 records instead of 15,076).
  **Why sorted data is required:** discarding half is only correct if everything on one side is smaller. On unsorted data it would silently miss matches.
  **How RepoScope prevents wrong answers:** `binary_search` first calls `is_sorted_ascending(records, column)` using the same comparison rules as sorting (missing last). If it fails it raises `NotSortedError`; the GUI then asks "Sort a copy with Merge Sort first?". Data sorted by another column, or descending, is rejected too. It supports equals, starts with, greater/less than, before/after date, using lower-bound and upper-bound searches. It refuses `contains`/`ends with`, because those matches are not in one contiguous block of a sorted list.
- **Hash index** (extra): builds a dictionary from value to records in one pass, then answers exact-match questions with one lookup. It reports the index build time separately.
- **Substring search** (`contains`) uses a linear scan over records with Python's built-in `in` on the text; it is not binary search.
- **Search versus filter:** a filter (Explorer) shows only matching rows and combines many conditions; a search (Search tab) runs one chosen algorithm and reports comparisons and time. Both use the same `evaluate_operator`, so they give the same answer, which the tests check.

## 6. Filters and multi-level sorting in the GUI

- `Condition` has column, operator, value, NOT flag and AND/OR join. `filter_records` splits the list into OR-groups of AND-conditions; a record is kept if any group is fully true. So `A AND B OR C` means `(A AND B) OR C` (AND before OR). NOT flips one condition's result.
- The Explorer header click sorts by one column (click again to reverse). Shift+click adds levels. The Sorting Laboratory has an editor for up to 4 levels with a direction for each.
- **Scope.** `store.records` (all) is never reordered. "Full dataset": the lab sorts a copy of everything; applying it shows all records sorted in the Explorer and clears the filters. "Filtered results": the lab sorts only a copy of the Explorer's filtered list; applying it shows those records sorted and keeps the filters; all other records stay stored. The scope name is shown in the lab label and in every benchmark row.

## 7. Collection, resume, pause and stop (`scraper.py`)

`Collector.run(source, target, restart)`:
1. Opens its own `Database` connection (SQLite connections must stay in one thread).
2. Reads saved progress `(query_index, next_page)`; if unfinished it resumes there.
3. For each query and page it calls `_call_api`, which waits if rate-limited (a countdown in the status line), then calls the client.
4. It normalizes items, saves them with `save_repositories`, saves the new position with `save_progress`, and reports progress.
5. It moves to the next query when a page is short or the 1,000 results limit is reached; it finishes when the target is reached.

Pause/resume/stop use two `threading.Event` objects. `_checkpoint()` is called before every request: while paused it waits (checks every 0.2 s); if stop was requested it returns False and `run` returns "stopped". A paused thread can still be stopped. A request already in flight finishes first (up to a few seconds). Stopping never deletes saved records. Errors: invalid URL (message box before starting), 401/403/404 (log line, stop, data kept), network failure (3 retries then stop, data kept), 422 (that query is skipped), unusable items (skipped with a warning).

**Progress percentage.** Automatic mode: unique records in database / target. URL search mode: items fetched / `min(total_count, 1000, target)`, where `total_count` comes from GitHub's first response. One repository: 1 of 1.

## 8. The GUI and threads

- **Signals and slots.** A button's `clicked` signal is connected to a Python method, e.g. `self.start_button.clicked.connect(self.start)`.
- **Background workers.** `ScraperThread` (a `QThread`) runs the `Collector`. The collector calls plain callbacks; the thread turns them into Qt signals (`status`, `progress`, `log`, `done`). Qt delivers signals across threads safely to the GUI thread, which updates the progress bar and labels. The GUI never touches the worker's database connection; it uses its own.
- **Why not download in the button handler?** The GUI thread draws the window and handles clicks. A 20-second network call would freeze it. A thread keeps it responsive.
- `SortThread` runs `run_benchmark` on a copied list and has a cancel flag the algorithms check once per outer loop, so "Cancel" and closing the window work even during slow sorts.
- **Table data.** `RepositoryTable` keeps the whole result list but gives the `QTableView` only one page (50 to 500 rows) through `RepositoryTableModel`. 15,000 rows are never put in the view at once. The model's `data()` method formats each cell on demand (thousands separators, dates, dash for missing).
- **Shutdown.** `closeEvent` stops the timers, stops the collector (waits up to 30 s), cancels any sort, and closes the database.

## 9. Storage, duplicates, export

- Records are saved page by page in a transaction. A crash loses at most the page in flight.
- Duplicates: `id INTEGER PRIMARY KEY` plus the upsert. The counter "duplicates skipped" is `len(records) - new_rows`.
- Resume after a restart: the `progress` table (source key, query number, next page, finished flag) is in the same SQLite file.
- CSV export uses `csv.DictWriter` (quotes, commas and newlines in descriptions are handled). JSON export uses `json.dump(..., ensure_ascii=False, indent=2)`. Both write all 17 attributes in the same order. No token is ever involved.
