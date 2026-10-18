# GitHub and RepoScope Concepts in Easy English

## Part 1. GitHub terms

**1. Repository ("repo").** A project folder that lives on GitHub, with all its files and their full history. Real-life example: a shared cupboard for one school project where everybody can see every version of every page. Example: `python/cpython` is the repository of the Python language.

**2. Repository owner.** The user or organization the repository belongs to. In `python/cpython`, `python` is the owner. Like the name on the cupboard.

**3. Public and private repositories.** Public: anyone can see it (RepoScope only uses these). Private: only people the owner invites. Like a notice board in a hallway (public) versus a locked drawer (private).

**4. Fork.** Your own copy of someone else's repository, made on GitHub. You can change your copy freely without touching the original. Real-life: you photocopy a classmate's notes and write on your copy. The *fork count* tells how many people made such copies, a sign that a project is useful. A fork is different from a clone: a fork is a copy that stays on GitHub; a clone (see 13) is a copy downloaded to your computer.

**5. Star.** A "like" or bookmark. People star repositories they find useful. More stars usually means more popular. Example: `pandas-dev/pandas` has over 50,000 stars.

**6. Watch.** Subscribing to a repository so GitHub notifies you about its activity. Like following a YouTube channel with the bell turned on. (RepoScope does not collect watchers.)

**7. Issue.** A message on a repository reporting a bug or suggesting an idea. Like a complaint or suggestion slip in a box.

**8. Open issue.** An issue nobody has resolved yet. The *open issue count* shows how much unfinished business a project has. (GitHub's number also counts open pull requests.)

**9. Pull request.** A request: "I changed some files in my fork, please add my changes to your project." The owner reviews it and accepts or rejects it. Like handing a corrected page to the teacher to be put into the class booklet.

**10. Commit.** A saved snapshot of the project with a short message, for example "fix login bug". Like pressing Save and writing a note about what changed. The history is a list of commits.

**11. Branch.** A separate line of work inside one repository. You try a new feature on a branch so the main version stays safe. Like writing a draft on a copy of a page before replacing the real page.

**12. Default branch.** The branch you see first and that is treated as the official version, usually `main` (older ones use `master`).

**13. Clone.** Downloading a repository from GitHub to your own computer using Git (`git clone URL`). Like downloading a shared document so you can work offline. Difference from a fork: forking happens on GitHub and creates a new repository under your account; cloning only copies to your machine and creates no new GitHub repository.

**14. License.** The legal permission the owner gives to others: may they copy, change or sell the code? Examples: MIT License (very free), Apache 2.0, GPL. A repository with no license is "all rights reserved" by default. In RepoScope, no license shows as a dash.

**15. README.** The front-page file (`README.md`) explaining what the project is and how to use it. Like the cover page of a book.

**16. Archived repository.** The owner marked it read-only: no new issues, pull requests or pushes. It is kept as a record. Like a museum piece: visible, not changed any more.

**17. API.** Application Programming Interface: a way for programs to talk to a service. Real-life: a restaurant waiter. You (the program) tell the waiter what you want in an agreed format; the kitchen (GitHub) prepares it and the waiter brings it back.

**18. API endpoint.** One specific address of the API for one kind of request. Example used by RepoScope: `https://api.github.com/search/repositories` (search repositories). Like one item on the waiter's menu.

**19. API request and response.** The request is what we send (address, parameters, headers such as the token). The response is what GitHub sends back: a status code, headers (including rate-limit info) and a body of data in JSON.

**20. JSON.** A text format for data, made of `{ "name": value }` pairs and `[ lists ]`. Example: `{"full_name": "python/cpython", "stargazers_count": 60000}`. Python reads it into dictionaries and lists.

**21. Pagination.** Big answers are split into pages. RepoScope asks for page 1 (100 repositories), then page 2, and so on. Like a search engine's "next page". GitHub search stops after 1,000 results per query.

**22. Rate limit.** A cap on how many requests you may make per time window so the service is not overloaded. Unauthenticated search: 10 per minute; with a token: 30 per minute. Other (non-search) requests: 60 per hour without a token, 5,000 with one. When you run out, GitHub answers with an error and a reset time. Like a library allowing you to borrow only so many books per hour.

**23. Authentication token.** A long secret password-like string that tells GitHub who you are, giving a higher rate limit. Treat it like a password: never share it, never put it in code or screenshots.

**24. HTTP status codes.** The number at the start of every response. 200 = success. 401 = you are not authenticated (bad token). 403 = forbidden, or rate limit used up. 404 = not found. 422 = the request was understood but invalid (for example a bad search query). 429 = too many requests. 500+ = GitHub's server problem. RepoScope reacts differently to each.

**25. Git versus GitHub.** Git is a program on your computer that tracks versions of files. GitHub is a website that hosts Git repositories and adds sharing, issues, pull requests and stars. Git is the notebook with history; GitHub is the cloud bookshelf where notebooks are shared.

## Part 2. Every attribute in RepoScope

"Direct" means copied from the API field named in brackets. "Derived" means RepoScope computed or cleaned it.

| # | Attribute | Meaning | Why useful | Example | Source |
|---|---|---|---|---|---|
| 1 | ID | Permanent unique number of the repository | Identifies a repo even if it is renamed; prevents duplicates | 858127 | Direct (`id`) |
| 2 | Name | Short name without owner | Sorting, searching | pandas | Direct (`name`) |
| 3 | Full name | `owner/name` | Unique readable label | pandas-dev/pandas | Direct (`full_name`) |
| 4 | Owner | Username or organization | Group by creator | pandas-dev | Direct (`owner.login`) |
| 5 | Description | One-line summary written by the owner | Text searching, understanding purpose | "Flexible and powerful data analysis..." | Direct (`description`), extra spaces/newlines removed; missing stays empty |
| 6 | Language | Main programming language GitHub detects | Compare ecosystems | Python | Direct (`language`); can be missing |
| 7 | Stars | Number of stars | Popularity | 50033 | Direct (`stargazers_count`) |
| 8 | Forks | Number of forks | Reuse/adoption | 1200 | Direct (`forks_count`) |
| 9 | Open issues | Open issues and pull requests | Workload and activity | 35 | Direct (`open_issues_count`) |
| 10 | Created | Date the repository was created | Age | 2010-08-24 | Direct (`created_at`), shown as a date |
| 11 | Last updated | Last time the repository record changed | Is it alive? | 2024-06-01 | Direct (`updated_at`) |
| 12 | License | Name of the license | Legal reuse | MIT License | Direct (`license.name`); missing when none |
| 13 | Default branch | The main branch | Where the official code is | main | Direct (`default_branch`) |
| 14 | URL | Web address of the repository page | "Open on GitHub" | https://github.com/pandas-dev/pandas | Direct (`html_url`) |
| 15 | Archived | Read-only repository? | Filter out dead projects | No | Direct (`archived`), stored as 0/1 |
| 16 | Visibility | public or private | Always public in this project | public | Direct (`visibility`); derived from `private` if absent |
| 17 | Collected at | When RepoScope saved this record | Knowing how fresh the numbers are | 2026-10-12 18:30 | Derived (our own clock) |

Missing values (no description, language or license) are stored as empty (NULL), shown as a dash, never crash the app, and are always sorted last.

## Part 3. Other concepts

**Web scraping** means a program reads a normal web page (HTML) and cuts out the data it wants. It is fragile: when the page design changes, it breaks. It can also break a site's rules.

**Why this project uses an API.** The API gives the same data in a clean JSON form, officially allowed, with documented limits and error codes. It is still "collecting data from GitHub" as the assignment requires, but it is safer and more reliable than scraping HTML.

**PyQt6.** A Python library for building desktop windows (buttons, tables, tabs) using the Qt toolkit. It handles drawing and mouse clicks; we connect our Python functions to its signals.

**GUI.** Graphical User Interface: windows and buttons instead of typing commands.

**SQLite.** A small database stored in one file (`data/reposcope.db`) with no server to install. Python includes it (`sqlite3`). It keeps records safe when you close the program.

**Background worker (thread).** A second line of work running at the same time as the window. Downloading from the internet can take seconds; if the window did the downloading itself it would freeze ("Not responding"). So a worker thread downloads while the main thread keeps the window alive and receives progress messages.

**Why progress bars need a reliable total.** Percent = done divided by total. If the total is unknown, we cannot say "40%". For a search, GitHub tells us `total_count`, so we can compute the percent. For the automatic plan the total is your target (15,000). When the total is unknown the bar would only show activity, not percent.

**Why repository IDs prevent duplicates.** Names can change and two queries can return the same repository. The numeric ID never changes. The database uses the ID as its primary key, so saving a repository twice updates the one row instead of creating a second.
