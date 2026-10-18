# RepoScope: GitHub Repository Analyzer

CS200 Data Structures and Algorithms, Project 1.
RepoScope collects real public repositories from the official GitHub REST API, stores them in a local SQLite database, and lets you explore, filter, search, sort and benchmark them with sorting algorithms written from scratch.

Documentation in `docs/`:
- `TUTORIAL_GITHUB.md`: GitHub terms, every attribute, and background concepts in easy English.
- `CODE_WALKTHROUGH.md`: the whole project explained file by file, with the algorithms.
- `VIVA.md`: 40 viva questions with answers and a 3 to 5 minute demo script.
- `REQUIREMENTS_CHECKLIST.md`: every requirement mapped to a file and a test, plus honest limitations.

## 1. What you need

- Windows 10 or 11 (also works on macOS and Linux).
- Python 3.10 or newer (3.12 was used for testing). Install from python.org and tick **Add Python to PATH**.
- Internet access for collecting data.

## 2. Install and run (Windows, Command Prompt or PowerShell)

```
cd path\to\RepoScope
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

PowerShell may block `activate`. If so run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
The only dependency is PyQt6. Everything else is the Python standard library (sqlite3, urllib, threading, csv, json).

## 3. PyCharm setup (beginner guide)

1. **File > Open** and choose the `RepoScope` folder.
2. PyCharm offers to create a virtual environment: accept it. Otherwise: **File > Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter > Virtualenv**.
3. Open `requirements.txt`. PyCharm shows "Install requirements". Click it. (Or open the Terminal tab and run `pip install -r requirements.txt`.)
4. Right-click `main.py` and choose **Run 'main'**.
5. To run tests: right-click the `tests` folder and choose **Run 'Python tests in tests'**.
6. Important: the working directory must be the `RepoScope` folder (it is by default).

## 4. Optional GitHub token

Without a token GitHub allows 10 search requests per minute. With a token it allows 30. Collecting 15,000 repositories needs about 150 to 250 search requests, so a token roughly cuts the time to a third. The project works without one, only slower.

1. Sign in to GitHub, open **Settings > Developer settings > Personal access tokens > Tokens (classic)** (or fine-grained tokens).
2. Click **Generate new token**. Give it a name. **Do not tick any scopes**: public data needs none.
3. Copy the token once (GitHub never shows it again).
4. Give it to RepoScope in one of two ways:
   - Paste it in the masked token box on the Data Collection tab (kept in memory only), or
   - Set an environment variable before starting: `setx GITHUB_TOKEN "ghp_yourtoken"` then open a new terminal. In PowerShell for one session: `$env:GITHUB_TOKEN="ghp_yourtoken"`.

The token is never written to the database, the log, exports or source code. Never commit it to Git. `.gitignore` already excludes the database.

## 5. Collecting the first records and then the full dataset

Open the **Data Collection** tab.

**First records (about 30 seconds):**
1. Choose "Collect from a GitHub URL", paste `https://github.com/search?q=language%3APython+stars%3A%3E50000&type=repositories`, set the target to 100, click **Start**.
2. Watch the progress bar and the log. Records appear in the Explorer when collection ends (or click **Reload data**).

**Full dataset (15,000 or more):**
1. Choose "Build a large dataset automatically", target `15000`, click **Start**.
2. It runs about 140 prepared searches (20 languages x 7 star ranges). Each search can return at most 1,000 repositories, which is why many searches are needed.
3. You may Pause, Resume or Stop at any time. Every page is saved at once. You may also close the app. Next time choose the same source and click **Start**: it continues from the saved query and page (the label shows it).
4. GitHub documents 10 search requests per minute without a token (30 with one), so budget up to about 30 minutes without a token. In my own test run (no token) it took about 7 minutes. When the limit is reached the app shows a countdown and continues by itself.
5. The Dashboard shows the live unique count. The count only goes up when a new repository ID appears; repeats are skipped.

**Backup option:** `reposcope_collected_15076.db` (delivered next to this project) is a snapshot of 15,076 real repositories that I collected with this very application on 2026-10-12. To use it, close RepoScope and copy it to `data/reposcope.db`. Your professor should see you run the collection yourself; keep the snapshot as a fallback only.

If fewer than 15,000 unique repositories exist in your database, the Dashboard says so. The app never invents records.

## 5b. Where the search queries are written

The automatic mode uses a list of searches built from two lists in `config.py`:

```python
BULK_LANGUAGES = ["Python", "JavaScript", "TypeScript", ...]            # 20 languages
BULK_STAR_RANGES = [">=20000", "10000..19999", "5000..9999", ...]       # 7 star ranges
```

`build_bulk_plan()` in `github_client.py` combines every star range with every language:

```python
queries.append(f'language:"{language}" stars:{star_range}')   # for example language:"Python" stars:>=20000
```

That gives 7 x 20 = 140 searches. To collect different repositories, edit the two lists in `config.py` (for example add a language or a star range) and restart the app.

## 6. Using the tabs

- **Theme**: the button at the top right switches between dark and light mode. RepoScope starts in the same mode as your system and remembers your last choice.
- **Dashboard**: totals, languages, stars, archived count, collection status, language chart.
- **Data Collection**: URL or automatic mode, Start/Pause/Resume/Stop, progress, rate limit, log.
- **Repository Explorer**: paged table. Click a header to sort; Shift+click adds more sort levels. Add filter conditions (AND, OR, NOT). Double-click a row (or use Details) to see everything; "Open on GitHub" opens the repository page.
- **Search**: linear, binary and hash-index search with comparison counts.
- **Sorting Laboratory**: choose scope, columns (up to 4 levels), algorithm, run it, or **Benchmark all algorithms**. "Show sorted result in Explorer" displays the result.
- **Export**: entire dataset, Explorer results, or selected rows, as CSV or JSON.

Supported URLs are listed on the Data Collection tab: one repository, a user/organization, a topic, a search URL, or an `api.github.com` search/repo URL. A search/user/topic URL yields at most 1,000 repositories (a GitHub limit).

## 7. Running the automated tests

```
python -m unittest discover -s tests -v
```
or `pytest` if you installed it (`pytest.ini` is included). The GUI test runs the real window without showing it (`QT_QPA_PLATFORM=offscreen` is set automatically). Tests never touch the network or your real database.

## 8. Exporting data

Open **Export**, choose what to export and CSV or JSON, click **Export**, choose a file name. All 17 attributes are written. Missing values are empty cells in CSV and `null` in JSON. CSV is saved as UTF-8 with a BOM so Excel on Windows shows international text correctly.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `No module named PyQt6` | Activate the virtual environment, then `pip install -r requirements.txt`. |
| `python` not recognised | Reinstall Python with "Add Python to PATH", or use `py` instead of `python`. |
| "Rate limit reached. Waiting..." | Normal. The app waits and continues. Add a token to go faster. |
| "GitHub rejected the token (401)" | Token is wrong or expired. Clear the box (or the environment variable) or make a new token. |
| "Network problem after 3 attempts" | Check internet/proxy/firewall. Click Start again: it resumes. |
| 0 records after Start | Read the red log lines. Check the URL format against the help text. |
| Explorer is empty after collecting | Click **Reload data**. |
| Benchmark of Bubble/Selection/Insertion is slow | They are O(n^2). Tick "Use only a random sample" (for example 3,000 records). |
| Counting, Radix or Bucket Sort greyed out | They only sort whole numbers and dates, not text columns. |
| "Bogo Sort needs a tiny input" | Bogo Sort shuffles until sorted (about n! tries), so it is limited to 8 records. Tick "Use only a random sample" and set it to 8 or less. |
| Want a fresh start | Close the app and delete `data/reposcope.db` (and `-wal`, `-shm`). |

## 10. Project layout

```
main.py                     start the application
config.py                   constants (API address, paging, bulk plan, paths)
models.py                   the 17 columns, API normalisation, comparison rules
database.py                 SQLite storage, duplicate-safe saving, saved progress
github_client.py            URL validation, bulk plan, HTTP requests, errors, rate limits
scraper.py                  Collector: pagination, pause/resume/stop, resume logic
sorting_algorithms.py       11 sorting algorithms, metrics, multi-level comparator
benchmark.py                fair benchmark, verification, sampling
searching_algorithms.py     linear, binary, hash search
filtering.py                AND/OR/NOT filters and operators
exporter.py                 CSV and JSON export
ui/                         PyQt6 interface (tabs, table, workers, theme)
tests/                      automated tests
docs/                       tutorials, walkthrough, viva, requirements checklist
```

## 11. Demonstration script for the viva (about 4 minutes)

1. **(30 s) Dashboard.** "RepoScope collects real GitHub repositories through the official API. The card shows unique repositories counted by repository ID."
2. **(40 s) Data Collection.** Point to the two modes, the URL box and its help. Click Start, then Pause (say: the worker really waits), Resume, and mention progress is saved after every page so Stop/restart continues. Show the rate-limit line.
3. **(40 s) Explorer.** Click the Stars header (sorted, Merge Sort), Shift+click Language for two levels. Add a filter: Language equals Python AND Stars greater than 1000; add a NOT archived condition. Open Details, click Open on GitHub.
4. **(40 s) Search.** Column Stars, "greater than", binary search: the app asks to sort first because binary search needs sorted data. Compare the comparison count with linear search.
5. **(80 s) Sorting Laboratory.** Sort by Language ascending then Stars descending; scope Full dataset; Run sort and show metrics. Press **Benchmark all algorithms** with a 3,000 sample. Point to fastest row, stable column, swaps zero for merge sort versus movements, and the verified column. Switch scope to Filtered results and show Apply.
6. **(20 s) Export** CSV and open it.
7. **(20 s) Tests.** Run `python -m unittest discover -s tests` and show it passing.
