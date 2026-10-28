# Live Sort Visualizer

A **terminal** sorting-algorithm playground built with Python's [`rich`](https://github.com/Textualize/rich) library — watch Bubble, Selection, and Insertion sort happen **card by card**, step by step, with live comparison/swap counters — plus two C companions: a timed performance analyzer and a greedy fractional-knapsack lab exercise.

```
  ┌───────────────────────────────────────────────────────┐
  │  ╭─────╮ ╭─────╮ ╭─────╮ ╭─────╮                     │
  │  │  42 │ │  7 │ │ 19 │ │  3 │   ← unicode "cards"    │
  │  ╰─────╯ ╰─────╯ ╰─────╯ ╰─────╯                     │
  │   i  j  min           ← colored role markers          │
  │  step 4/23  ████░░░░  17%  ·  comparisons 7  swaps 2 │
  └───────────────────────────────────────────────────────┘
   rich TUI (Python)          +          C analyzers (gcc)
```

---

## The Setup — three programs, one theme

| # | Program | Language | What it answers |
|---|---------|----------|-----------------|
| 1 | `live_sort_visualizer.py` | Python + `rich` | *What does the algorithm actually do, step by step?* |
| 2 | `sorting_performance_analyzer.c` | C | *How do Selection vs Insertion compare in time and operations, across many trials?* |
| 3 | `PBLE_AOA.c` | C | *A greedy Algorithms-lab exercise (fractional knapsack) that shares the menu-driven, sort-using spirit* |

The three are **independent console programs** — no shared files, no CSV pipeline — they just live in one repo under the Analysis-of-Algorithms umbrella.

---

## The Story — how three people built it

The work split by **artifact**: one person owned the visual tool end-to-end, one owned the measurement harness, one owned the course lab exercise. Same terminal, three mental models: *see it*, *measure it*, *apply it*.

### Person 1 — Visualization Engineer (the Python TUI)

**Ideation.** Bar charts in a terminal are cliché and lie about what's happening — they show size, not *state*. Their idea: every array element is a **rounded Unicode card** (`╭─────╮ │ 42 │ ╰─────╯`), and every algorithm step **yields a Frame** — an immutable snapshot with the array, colored role markers (`i`, `j`, `min`, `key`), a human note ("swapped 42 → 7"), and running counters. The sorter is a **generator**, so the same `frames()` stream powers both *step mode* (press Enter) and *auto mode* (1.4 s cadence). Insertion sort lifts a card out, leaving a dashed empty slot (`None` in the array) — the display shows the hole, not just the shifted values.

**What they implemented** (`live_sort_visualizer.py`, ~1,300 lines):

| Piece | Job |
|-------|-----|
| `Frame` dataclass | One immutable step: `array`, `marks`, `roles`, `note`, `kind`, `comparisons`, `actions`, `ordered` |
| `SortStrategy` (ABC) | Abstract `frames()`; concrete `run()`, `_start()`, `_done()` |
| `BubbleSort.frames()` | Early-exit on a no-swap pass; tracks a `settled` set of ordered indices |
| `SelectionSort.frames()` | Roles `i` / `j` / `min`; counts swaps |
| `InsertionSort.frames()` | Role `key`; `None` hole for the lifted card; counts shifts |
| `Card` / `CardRow` | Unicode box drawing, `CARD_STYLES` per state (default/i/j/min/key/ordered), index rail + track line |
| `LiveSorter` | Collects frames, `_render()` (clear + header + cards + note), `_advance()` (step vs auto), `_final()` (✓ SORTED / ✕ MISMATCH) |
| `Menu` | Options: manual input, random generate, show, visualize (cap `LIVE_LIMIT = 30` cards), compare all, exit |
| `DataManager` | Untouched master copy, `MAX_SIZE = 500`, arrangements random/sorted/reverse |
| `option_compare()` | Rich table: Method · Steps · Comparisons · Swaps/Shifts · Correct, with column winners highlighted |
| `run_to_completion()` | Headless sort powering the compare table (`SortSummary`) |

### Person 2 — Performance Analyst (the C benchmark)

**Ideation.** Counters are nice, but the AOA course wants **milliseconds**. Their idea: a tight C harness that runs Selection and Insertion on the *same untouched master copy* for **1–100 timing trials**, averages `clock()` deltas, and refuses to print numbers it can't verify — every trial is checked with `isSorted` and cross-checked with `arraysEqual` before results are believed. Three dataset shapes (sorted, reverse, random) expose each algorithm's best and worst case.

**What they implemented** (`sorting_performance_analyzer.c`, ~370 lines):

| Piece | Job |
|-------|-----|
| `SortStats` | `{ comparisons, operations, elapsedMs }` filled by every run |
| `selectionSort(int a[], int size, SortStats*)` | In-place sort; increments stats inside the hot loop |
| `insertionSort(int a[], int size, SortStats*)` | Same contract, shift-counted |
| `copyArray` / `isSorted` / `arraysEqual` | The trust layer — no result ships unverified |
| `enterData` / `generateData` | Manual entry or `rand() % 100000` (seeded `time(NULL)`), sorted/reverse/random arrangements |
| `runSelection` / `runInsertion` | Single runs with stats + timing (timing wraps the sort loop only) |
| `compareBoth` | N trials from the master copy, averages, ASCII table, plain-English interpretation ("Selection Sort performs n(n−1)/2 comparisons for every arrangement…") |
| `showMenu` | Menu loop, choices 1–7, `MAX_SIZE 10000` |

### Person 3 — Algorithms Lab Engineer (the greedy exercise)

**Ideation.** The AOA problem-based lab exercise: **Smart Delivery Planning** — a delivery vehicle with limited capacity, packages each with value and weight, and the goal of maximizing total value (fractional knapsack: it's fine to load *part* of a package). The key idea is the classic greedy ratio: sort packages by **value/weight descending**, then load them whole until the next one doesn't fit, then take the fraction of it.

**What they implemented** (`PBLE_AOA.c`, ~190 lines):

| Piece | Job |
|-------|-----|
| `struct Package` | `{ id, value, weight, ratio, fraction }`, array of `MAX 100` |
| `enterPackages` / `displayPackages` | Menu-driven scanf/printf I/O |
| `calculateRatios` | `ratio = value / weight` per package |
| `sortPackages` | **Bubble sort** on `ratio` descending — the greedy precondition (incidentally the same algorithm Person 1 visualizes) |
| `findMaximumValue` | Greedy fill: whole packages while capacity allows, then the fractional last one |
| `displaySelectedPackages` | What got loaded, whole vs fraction, and the grand total value |
| `main` | Menu loop, choices 1–7 (enter → ratio → sort → max value → selected) |

---

## Files in this repository

| File | What it is |
|------|------------|
| `live_sort_visualizer.py` | The main event: rich TUI, 3 strategies, step/auto playback, compare table |
| `sorting_performance_analyzer.c` | Timing benchmark: Selection vs Insertion, N trials, verified results |
| `PBLE_AOA.c` | Greedy fractional knapsack lab ("Smart Delivery Planning") |
| `requirements.txt` | One line: `rich` |

## How to run

**Python visualizer**
```bash
pip install -r requirements.txt
python3 live_sort_visualizer.py
```
Exit any prompt with a negative number (e.g. `-1`) or menu option 6. Live runs cap at 30 cards; use *Compare all methods* for larger lists.

**C performance analyzer**
```bash
gcc sorting_performance_analyzer.c -o analyzer
./analyzer
```
Enter or generate data first (menu 1–2), then run a sort (3–4) or the multi-trial comparison (5).

**C knapsack exercise**
```bash
gcc PBLE_AOA.c -o pble
./pble
```
Menu: enter packages → capacity → ratios → sort → max value → selected packages.

## The three algorithms on cards

| Algorithm | What the cards do | Counted as |
|-----------|-------------------|------------|
| **Bubble** | Adjacent cards swap when out of order; settled cards turn cyan and the run early-exits on a clean pass | swaps |
| **Selection** | `min` marker sweeps for the smallest remaining card, then one swap into place | swaps |
| **Insertion** | The `key` card lifts out (dashed hole), larger cards shift right one slot until it drops in | shifts |
