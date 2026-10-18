# Viva Preparation

## A. 43 likely questions with easy answers

**Project and data**

1. **What is the objective of RepoScope?** To collect a large set of real GitHub repositories, store them, and let the user search, filter, sort and benchmark them, so that sorting and searching algorithms are applied and compared on real data.
2. **Why are GitHub repositories good entities?** They are real, public, plentiful, and have many typed attributes (text, numbers, dates, booleans) and natural missing values, which is ideal for testing different sort keys.
3. **Where do the records come from and how many are there?** From the official GitHub REST API (`/search/repositories`). In my test run the application collected 15,076 unique repositories. The count shown on the Dashboard is always the real number of unique IDs in my database.
4. **Which attributes do you store?** 17: ID, name, full name, owner, description, language, stars, forks, open issues, created, last updated, license, default branch, URL, archived, visibility, and collected-at.
5. **Which attributes can be missing?** Description, language and license (and rarely others). They are stored as NULL, shown as a dash, and sorted last.
6. **How do you avoid duplicates?** The repository ID is the primary key and saving uses an upsert, so a repeat updates the same row. The count is of unique IDs.
7. **Why an API and not scraping HTML?** The API is official, stable and returns clean JSON with documented limits and errors; HTML scraping breaks when the page changes and may violate site rules. It still collects data from GitHub.
8. **How can one run reach 15,000 if GitHub search gives only 1,000 results?** The automatic plan runs about 140 different queries (20 languages x 7 star ranges). Each returns up to 1,000 different repositories; duplicates are removed by ID.
9. **What are the limitations?** Search results are the top results by stars per query (not a random sample of GitHub); one URL gives at most 1,000 results; rate limits apply; numbers like stars are as of collection time.

**API concepts**

10. **What is pagination?** Splitting a big result into pages. I request 100 per page and increase `page` until the results end or page 10.
11. **What is a rate limit and how do you handle it?** A cap on requests per time. I read the `X-RateLimit-*` headers; if the limit is used up or GitHub answers 403/429 with Retry-After, the collector shows a countdown and retries automatically; Stop still works during the wait.
12. **What does a token do and is it safe?** It raises the limit (30 search requests per minute instead of 10). It lives only in memory or in an environment variable, is never saved, logged or exported.
13. **What HTTP codes do you handle?** 200 success; 401 bad token; 403/429 rate limit or forbidden; 404 not found; 422 invalid query (skipped); 5xx server error (retried).
14. **What is JSON?** A text format of key-value pairs and lists that Python converts to dictionaries and lists.

**Storage and threads**

15. **Why SQLite?** It is built into Python, needs no server, stores everything in one file, and survives restarts.
16. **How does resume work after closing the app?** After each page the `progress` table stores the query number and next page. Start with the same source continues from there. I tested it: a stopped run resumed at "query 61, page 5" and finished.
17. **How do Pause, Resume and Stop work?** Two thread events. Before each request the worker checks them: paused means it waits; stop means it ends cleanly. Saved data is never deleted.
18. **What is a background worker and why use one?** A second thread. Network calls take time; if they ran in the GUI thread the window would freeze. The worker reports progress through Qt signals.
19. **Why does each thread open its own database connection?** SQLite connections must be used by one thread; separate connections avoid unsafe sharing.
20. **Why is the table fast with 15,000 rows?** It is paged: only 100 (or 50 to 500) rows are given to the view at a time.

**Sorting**

21. **Which sorting algorithms did you implement?** Bubble, selection, insertion, merge, quick, counting (from class), and heap, shell, radix, bucket and bogo (extra). None uses `sorted()` or `list.sort()`.
22. **Explain the complexity of each.** Bubble O(n) best/O(n²); selection O(n²); insertion O(n) best/O(n²); merge O(n log n); quick O(n log n) average, O(n²) worst; counting O(n + k); heap O(n log n); shell about O(n^1.5). Space: O(1) for bubble, selection, insertion, heap, shell; O(n) merge; O(log n) quick; O(n + k) counting.
23. **What is stability and which are stable?** Equal keys keep their original order. Stable: bubble, insertion, merge, counting. Not stable: selection, quick, heap, shell. Selection example: X(500), Y(500), Z(100) becomes Z, Y, X.
24. **Define comparison, swap and movement.** Comparison: one comparison of two records' keys. Swap: two items exchange places. Movement: an item written to a position outside a swap (a shift or a merge output write). They are counted inside the algorithms.
25. **Why does merge sort show zero swaps?** It never exchanges two items in place; it writes items into a new list, so those are movements. I did not call writes swaps.
26. **How do you measure time fairly?** `time.perf_counter()` around only the algorithm call. Key preparation, database, GUI and verification are outside the timer.
27. **How does the benchmark guarantee fairness?** Each algorithm gets its own copy of the same original input and the same direction and key rules. Results are then verified (sorted, nothing lost, stable algorithms keep tie order, same key sequence as the others).
28. **Why can the fastest algorithm vary?** Big-O ignores constants; data shape matters; Python overhead; timing noise. For small or nearly sorted data insertion sort can beat the O(n log n) ones. Counting sort was fastest on stars but cannot sort text.
29. **Why is counting sort disabled for text?** It needs whole-number keys in a limited range to use as array positions. Strings cannot be counted into buckets. The app disables it and explains why; it never silently substitutes another algorithm.
30. **How do you sort several columns?** One comparator checks level 1, and only on a tie level 2, then level 3. Each level has its own direction. It works for all algorithms. Counting sort uses one stable pass per level from last to first.
31. **How do you treat missing values and dates?** Missing is always last (in both directions). Dates are compared as day numbers; text is compared case-insensitively.
32. **What happens to the data when sorting a filtered scope?** Only a copy of the filtered list is sorted. The stored list and database are never reordered or deleted. Full scope sorts a copy of all records.

**Searching and filtering**

33. **Linear versus binary search?** Linear checks each item (O(n)) and works on any data. Binary halves the range (O(log n)) but needs data sorted by the same key. On 15,076 records it used 27 comparisons versus 15,076.
34. **How do you make sure binary search is never used wrongly?** The function checks `is_sorted_ascending` with the same rules as sorting and raises `NotSortedError` otherwise; the GUI offers to sort a copy first. It also refuses `contains`.
35. **Why can't binary search do "contains"?** Matches for a substring are scattered through a sorted list, not in one contiguous block. I use a linear scan with substring matching for that.
36. **What extra search did you add?** A hash index (dictionary) for exact matches: one lookup after a one-time O(n) build.
37. **How do composite filters work?** Conditions have AND/OR and a NOT checkbox. AND binds tighter than OR. Missing values never match a comparison, but NOT can invert it.
38. **Difference between a column filter and a substring search?** A filter keeps matching rows in the Explorer using operators; a search in the Search tab runs a chosen algorithm and reports its comparisons and time. Both use the same operator function.

**Quality**

39. **How did you test it?** 96 automated tests (unittest): sorting (all algorithms, both directions, empty/single/duplicates/missing, stability, metrics, multi-level), benchmark verification, searching (all methods agree), filters, database persistence, collector (pagination, resume, pause, stop, rate limit, errors with a fake GitHub), export, and a GUI smoke test. Result of the last run: all 96 passed. I also ran a real collection of 15,076 records.
40. **How does radix sort work and when can it be used?** It sorts whole numbers digit by digit from the ones digit upward, using ten buckets (0 to 9) for each digit; each round keeps the earlier order, so the final result is sorted. It makes no comparisons, takes O(d·n) time (d = number of digits) and is stable. It only works for numbers and dates, so it is disabled for text. On 15,076 stars it took 36 ms.
41. **What is bogo sort and why is it limited?** It shuffles randomly until the list is sorted. It needs about n! shuffles on average, so it is only a joke or teaching example. RepoScope allows at most 8 records, because for thousands of records it would never finish. It is not stable.
42. **How does bucket sort work, and when is it slow?** It spreads whole numbers into buckets by size, sorts each small bucket with insertion sort, and joins the buckets in order. It is O(n + k) when numbers are spread evenly, but O(n²) if most records land in one bucket. It is stable and works only for numbers and dates. On 15,076 stars it took 35 ms.
43. **What would you improve?** Add a token-based faster mode by default, more collection strategies (date ranges), charts, and a cancel for long exports; run the GUI test on Windows too.

## B. Demonstration sequence (3 to 5 minutes)

| Time | Click | Say |
|---|---|---|
| 0:00 | Dashboard | "These are real GitHub repositories collected via the API; the total is unique IDs." |
| 0:30 | Data Collection | Show URL box, help text, automatic mode. Press Start, then Pause, Resume. "The worker is a background thread; pause really waits; every page is saved; Stop or closing keeps the data and Start continues from the saved page." Point to the rate-limit line. |
| 1:10 | Explorer | Click Stars twice; Shift+click Language. Add filter Language = Python AND Stars > 1000, add NOT Archived. Double-click a row, press Open on GitHub. |
| 1:50 | Search | Column Stars, greater than 5000, Binary: accept the sort prompt. Then Linear: compare the comparison counts and explain why sorting was needed. |
| 2:30 | Sorting Laboratory | Language ascending then Stars descending, Merge Sort, Run sort: metrics and preview. Tick sample 3,000, press Benchmark all: fastest row, stable column, merge sort swaps 0 and movements, Verified Yes. Switch Scope to filtered and Apply to Explorer. |
| 4:00 | Export | Export filtered results as CSV. |
| 4:20 | Terminal | `python -m unittest discover -s tests` shows all tests passing. |
