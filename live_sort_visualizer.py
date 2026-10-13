#!/usr/bin/env python3
"""
Live Sort Visualizer
====================

A menu-driven console program that lets you *watch* a sorting algorithm work
one iteration at a time.  Every number is drawn as a playing-card box and the
loop variables of the algorithm (``i``, ``j``, and friends) are shown as
colours on the cards, so you can see exactly where each counter sits.

Run it with::

    python3 live_sort_visualizer.py

Requirements: ``rich`` (see requirements.txt).

Exit at any prompt by typing a negative number (for example ``-1``).

Design notes
------------
* :class:`Frame`      -- one snapshot of the array plus the loop variables that
  point into it; strategies yield a stream of these, one per iteration.
* :class:`Role`       -- a loop variable (``i``, ``j``, ``min``, ``key``) and the
  colour it is drawn in.
* :class:`Card` / :class:`CardRow` -- draw numbers as coloured boxes.
* :class:`SortStrategy` -- abstract base; ``frames()`` is a *generator* that
  never mutates its input.
* :class:`LiveSorter` -- replays those frames on screen.
* :class:`DataManager`-- owns the untouched master list; sorting always uses
  a copy.
* :class:`Menu`       -- the interactive loop.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Mapping, Sequence

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Global look / tuning
# ---------------------------------------------------------------------------

INK = "#e6edf3"            # primary text
DIM = "#8b949e"            # secondary text
FAINT = "#30363d"          # hairlines / empty states
ACCENT = "#58a6ff"         # app blue ("inner loop j")
AMBER = "#e3b341"          # "outer loop i"
GOOD = "#7ee787"           # "key / hole"
FINE = "#39c5cf"           # ordered / final region
VIOLET = "#bc8cff"         # "minimum"
DANGER = "#ff7b72"         # exit / errors
PANEL_EDGE = "#21262d"     # neutral panel border

#: One loop variable, the human label shown in the legend, and its colour.
@dataclass(frozen=True)
class Role:
    key: str
    label: str
    colour: str


ROLE_I = Role("i", "outer loop i", AMBER)
ROLE_J = Role("j", "inner loop j", ACCENT)
ROLE_MIN = Role("min", "minimum", VIOLET)
ROLE_KEY = Role("key", "key / hole", GOOD)

#: Card appearance per visual state: border, track, fill and value colour.
CARD_STYLES: dict[str, dict[str, str]] = {
    "default": {"edge": "#6e7681", "track": FAINT, "fill": "#161b22", "text": "#c9d1d9"},
    "i":       {"edge": AMBER,  "track": AMBER,  "fill": "#2b2210", "text": "#ffd866"},
    "j":       {"edge": ACCENT, "track": ACCENT, "fill": "#0d2136", "text": "#a5d0ff"},
    "min":     {"edge": VIOLET, "track": VIOLET, "fill": "#1d1533", "text": "#d8b9ff"},
    "key":     {"edge": GOOD,   "track": GOOD,   "fill": "#12291a", "text": "#aff5b4"},
    "ordered": {"edge": FINE,   "track": FINE,   "fill": "#0f262c", "text": "#a5f3fc"},
}

#: Glyph + colour for the one-line note under the row.
STEP_ICONS: dict[str, tuple[str, str]] = {
    "compare": ("≠", ACCENT),
    "swap":    ("⇄", GOOD),
    "shift":   ("→", GOOD),
    "insert":  ("↳", GOOD),
    "pick":    ("⇧", GOOD),
    "mark":    ("•", VIOLET),
    "start":   ("▸", DIM),
    "done":    ("✓", FINE),
}

MIN_CARD_WIDTH = 5      # inner width of a card that holds two digits
PANEL_PAD = 4           # panel borders (2) + inner padding (2)
LIVE_LIMIT = 30         # cards allowed in the live pointer view
AUTOPLAY_DELAY = 1.4    # seconds between iterations in auto-play mode


# ---------------------------------------------------------------------------
# Visual frames produced by the strategies
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """One snapshot of the array plus the loop variables that point into it.

    ``array`` may contain ``None`` -- that draws an empty (lifted-out) slot used
    by insertion sort.  ``marks`` maps an index to the card state it should be
    drawn in (one of :data:`CARD_STYLES`).  ``roles`` maps a loop-variable key
    to the index it currently sits on, for the legend.
    """

    array: list[int | None]
    marks: dict[int, str] = field(default_factory=dict)
    roles: dict[str, int] = field(default_factory=dict)
    note: str = ""
    kind: str = "start"
    comparisons: int = 0
    actions: int = 0
    ordered: frozenset[int] = frozenset()


@dataclass
class SortSummary:
    """Result of running a strategy to completion (used by "compare")."""

    name: str
    steps: int
    comparisons: int
    actions: int
    final: list[int]
    ok: bool


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

class Card:
    """A single number drawn as a filled chip with a coloured edge.

    ::

        ╭─────╮
        │  42 │
        ╰─────╯

    ``value`` may be ``None``, which draws an empty (dashed) slot -- used when a
    card has been lifted out of the row by insertion sort.
    """

    STYLES = CARD_STYLES
    MIN_WIDTH = MIN_CARD_WIDTH

    def __init__(self, value: int | None, width: int | None = None) -> None:
        self.value = value
        self.width = width if width is not None else self.natural_width()

    def natural_width(self) -> int:
        if self.value is None:
            return self.MIN_WIDTH
        return max(self.MIN_WIDTH, len(str(self.value)) + 2)

    @property
    def label(self) -> str:
        return "" if self.value is None else str(self.value)

    @classmethod
    def theme(cls, state: str) -> dict[str, str]:
        return cls.STYLES.get(state, cls.STYLES["default"])

    def lines(self, state: str = "default") -> list[Text]:
        if self.value is None:
            return self._slot_lines()

        width = self.width
        pad = width - len(self.label)
        left = pad - pad // 2                      # extra space goes left
        inner = " " * left + self.label + " " * (pad - left)
        t = self.theme(state)
        fill = f"on {t['fill']}"
        edge, text = t["edge"], t["text"]

        top = Text()
        top.append("╭", style=f"{edge} {fill}")
        top.append("─" * width, style=f"{edge} {fill}")
        top.append("╮", style=f"{edge} {fill}")

        mid = Text()
        mid.append("│", style=f"{edge} {fill}")
        mid.append(inner, style=f"bold {text} {fill}")
        mid.append("│", style=f"{edge} {fill}")

        bottom = Text()
        bottom.append("╰", style=f"{edge} {fill}")
        bottom.append("─" * width, style=f"{edge} {fill}")
        bottom.append("╯", style=f"{edge} {fill}")

        return [top, mid, bottom]

    def _slot_lines(self) -> list[Text]:
        width = self.width
        ghost = f"{FAINT} on #0d1117"
        return [
            Text(f"╭{'╌' * width}╮", style=ghost),
            Text(f"│{' ' * width}│", style=ghost),
            Text(f"╰{'╌' * width}╯", style=ghost),
        ]

    def render(self, state: str = "default") -> Text:
        out = Text()
        for i, line in enumerate(self.lines(state)):
            if i:
                out.append("\n")
            out.append_text(line)
        return out


def fit_card_width(values: Sequence[int | None], columns: int) -> int | None:
    """Inner card width that makes the whole row fit inside ``columns``.

    Returns ``None`` when even the tightest card would overflow.
    """
    n = len(values)
    if n <= 0:
        return Card.MIN_WIDTH
    digits = max([len(str(v)) for v in values if v is not None] or [1])
    lo = max(1, digits)
    hi = max(Card.MIN_WIDTH, digits + 2)
    for width in range(hi, lo - 1, -1):
        if n * (width + 3) - 1 <= columns:   # cards + single-space gaps
            return width
    return None


class CardRow:
    """A whole array rendered as cards side by side, with an index rail below."""

    GAP = 1

    def __init__(self, values: Sequence[int | None], width: int | None = None) -> None:
        self.values = list(values)
        if width is None:
            digits = [len(str(v)) for v in self.values if v is not None]
            width = max([Card.MIN_WIDTH] + [d + 2 for d in digits])
        self.width = width
        self.cards = [Card(v, width) for v in self.values]

    @property
    def card_columns(self) -> int:
        return self.width + 2

    @property
    def pitch(self) -> int:
        return self.card_columns + self.GAP

    def _join(self, segments: Sequence[Text]) -> Text:
        out = Text()
        for i, seg in enumerate(segments):
            if i:
                out.append(" " * self.GAP)
            out.append_text(seg)
        return out

    def _track_line(self, hl: Mapping[int, str]) -> Text:
        out = Text()
        for i in range(len(self.cards)):
            if i:
                out.append(" " * self.GAP)
            state = hl.get(i, "default")
            theme = Card.theme(state)
            if state == "default":
                out.append("─" * self.width, style=f"{FAINT} dim")
            else:
                out.append("━" * self.width, style=f"bold {theme['track']}")
        return out

    def _index_line(self, hl: Mapping[int, str]) -> Text:
        out = Text()
        slot = self.card_columns
        for i in range(len(self.cards)):
            if i:
                out.append(" " * self.GAP)
            state = hl.get(i, "default")
            style = "dim" if state == "default" else f"bold {Card.theme(state)['text']}"
            label = str(i)
            pad = slot - len(label)
            left = pad - pad // 2
            out.append(" " * left, style=style)
            out.append(label, style=style)
            out.append(" " * (pad - left), style=style)
        return out

    def __rich__(self) -> Group:
        return self.render()

    def render(self, highlights: Mapping[int, str] | None = None) -> Group:
        hl = dict(highlights or {})
        lines: list[Text] = []
        n = len(self.cards)

        if not n:
            return Group(Text("(empty)", style="dim"))

        rendered = [card.lines(hl.get(i, "default")) for i, card in enumerate(self.cards)]

        for row_index in range(3):
            segments: list[Text] = []
            for i in range(n):
                segments.append(rendered[i][row_index])
            lines.append(self._join(segments))

        lines.append(self._track_line(hl))
        lines.append(self._index_line(hl))
        return Group(*lines)


def render_row(
    values: Sequence[int | None],
    columns: int,
    *,
    highlights: Mapping[int, str] | None = None,
) -> Group:
    """Render a row of cards in ``columns``, wrapping onto extra lines if needed."""
    hl = dict(highlights or {})
    n = len(values)
    if not n:
        return Group(Text("(empty)", style=DIM))

    width = fit_card_width(values, columns)
    if width is not None:
        return CardRow(values, width).render(hl)

    digits = max([len(str(v)) for v in values if v is not None] or [1])
    hi = max(Card.MIN_WIDTH, digits + 2)
    width: int | None = None
    per_line = 1
    for candidate in range(hi, digits - 1, -1):
        room = (columns + 1) // (candidate + 3)
        if room >= 1 and room * (candidate + 3) - 1 <= columns:
            width, per_line = candidate, room
            break
    if width is None:
        width = max(1, digits)

    blocks: list = []
    for start in range(0, n, per_line):
        stop = min(n, start + per_line)
        sub_hl = {i - start: state for i, state in hl.items() if start <= i < stop}
        blocks.append(CardRow(values[start:stop], width).render(sub_hl))
        blocks.append(Text(""))
    if blocks:
        blocks.pop()
    return Group(*blocks)


def counted(n: int, word: str) -> str:
    """``counted(1, 'swap')`` -> ``'1 swap'`` (simple English pluralising)."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def _ordered_marks(ordered: frozenset[int]) -> dict[int, str]:
    return {i: "ordered" for i in ordered}


class SortStrategy(ABC):
    """Abstract base class: a sort is a generator of :class:`Frame` records."""

    name: str = "Sort"
    unit: str = "swaps"
    singular: str = "swap"
    #: Loop variables this algorithm shows in the legend.
    roles: tuple[Role, ...] = (ROLE_I, ROLE_J)

    @abstractmethod
    def frames(self, values: Sequence[int]) -> Iterator[Frame]:
        """Yield one :class:`Frame` per iteration.  Never mutates ``values``."""

    def run(self, values: Sequence[int]) -> list[int]:
        """Sort a copy of ``values`` and return the final state."""
        result = list(values)
        for f in self.frames(values):
            result = [v for v in f.array]
        return result

    @staticmethod
    def _start(values: Sequence[int]) -> Frame:
        return Frame(
            array=list(values),
            note="watch the coloured counters walk through the numbers",
            kind="start",
        )

    @staticmethod
    def _done(arr: Sequence[int], comparisons: int, actions: int) -> Frame:
        n = len(arr)
        return Frame(
            array=list(arr),
            note="all numbers are in order",
            kind="done",
            comparisons=comparisons,
            actions=actions,
            ordered=frozenset(range(n)),
        )


class BubbleSort(SortStrategy):
    """Adjacent pairs are compared and swapped until nothing moves."""

    name = "Bubble Sort"
    unit = "swaps"
    singular = "swap"
    roles = (ROLE_I, ROLE_J)

    def frames(self, values: Sequence[int]) -> Iterator[Frame]:
        arr = list(values)
        n = len(arr)
        yield self._start(arr)
        if n <= 1:
            yield self._done(arr, 0, 0)
            return

        settled: set[int] = set()
        comparisons = actions = 0

        for i in range(n - 1):
            boundary = n - 1 - i          # index the largest value will land on
            swapped = False
            for j in range(n - 1 - i):
                a, b = arr[j], arr[j + 1]
                comparisons += 1
                marks = {boundary: "i", j: "j", j + 1: "j"}
                yield Frame(
                    array=list(arr),
                    marks=marks,
                    roles={"i": boundary, "j": j},
                    note=f"compare {a} and {b}",
                    kind="compare",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(settled),
                )
                if a > b:
                    arr[j], arr[j + 1] = b, a
                    actions += 1
                    swapped = True
                    yield Frame(
                        array=list(arr),
                        marks={boundary: "i", j: "j", j + 1: "j"},
                        roles={"i": boundary, "j": j},
                        note=f"{a} > {b} -- swap them",
                        kind="swap",
                        comparisons=comparisons,
                        actions=actions,
                        ordered=frozenset(settled),
                    )

            settled.add(boundary)
            if not swapped:
                settled.update(range(boundary + 1))
                yield Frame(
                    array=list(arr),
                    note="no swaps this pass -- the array is sorted",
                    kind="done",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(range(n)),
                )
                return

        yield self._done(arr, comparisons, actions)


class SelectionSort(SortStrategy):
    """Scan the unsorted tail for the minimum, then swap it into place."""

    name = "Selection Sort"
    unit = "swaps"
    singular = "swap"
    roles = (ROLE_I, ROLE_J, ROLE_MIN)

    def frames(self, values: Sequence[int]) -> Iterator[Frame]:
        arr = list(values)
        n = len(arr)
        yield self._start(arr)
        if n <= 1:
            yield self._done(arr, 0, 0)
            return

        settled: set[int] = set()
        comparisons = actions = 0

        for i in range(n - 1):
            min_idx = i
            yield Frame(
                array=list(arr),
                marks={i: "i", min_idx: "min"},
                roles={"i": i, "j": i, "min": min_idx},
                note=f"assume {arr[i]} at index {i} is the smallest",
                kind="mark",
                comparisons=comparisons,
                actions=actions,
                ordered=frozenset(settled),
            )
            for j in range(i + 1, n):
                a, b = arr[min_idx], arr[j]
                comparisons += 1
                yield Frame(
                    array=list(arr),
                    marks={i: "i", j: "j", min_idx: "min"},
                    roles={"i": i, "j": j, "min": min_idx},
                    note=f"compare {b} with smallest-so-far {a}",
                    kind="compare",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(settled),
                )
                if b < a:
                    min_idx = j
                    yield Frame(
                        array=list(arr),
                        marks={i: "i", j: "j", min_idx: "min"},
                        roles={"i": i, "j": j, "min": min_idx},
                        note=f"{b} is smaller -- new minimum at index {min_idx}",
                        kind="mark",
                        comparisons=comparisons,
                        actions=actions,
                        ordered=frozenset(settled),
                    )

            if min_idx != i:
                a, b = arr[i], arr[min_idx]
                arr[i], arr[min_idx] = arr[min_idx], arr[i]
                actions += 1
                yield Frame(
                    array=list(arr),
                    marks={i: "i", min_idx: "min"},
                    roles={"i": i, "min": i},
                    note=f"swap {a} and {b} into place",
                    kind="swap",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(settled),
                )
            settled.add(i)

        yield self._done(arr, comparisons, actions)


class InsertionSort(SortStrategy):
    """Pick a card up, slide larger cards right, drop it into the gap."""

    name = "Insertion Sort"
    unit = "shifts"
    singular = "shift"
    roles = (ROLE_I, ROLE_J, ROLE_KEY)

    def frames(self, values: Sequence[int]) -> Iterator[Frame]:
        arr = list(values)
        n = len(arr)
        yield self._start(arr)
        if n <= 1:
            yield self._done(arr, 0, 0)
            return

        comparisons = actions = 0
        ordered: set[int] = set()

        for i in range(1, n):
            key = arr[i]
            hole = i
            display: list[int | None] = list(arr)
            display[hole] = None
            yield Frame(
                array=list(display),
                marks={hole: "key"},
                roles={"i": i, "j": i - 1, "key": hole},
                note=f"pick up {key} from index {i}",
                kind="pick",
                comparisons=comparisons,
                actions=actions,
                ordered=frozenset(ordered),
            )

            j = i - 1
            while j >= 0:
                comparisons += 1
                if arr[j] <= key:
                    yield Frame(
                        array=list(display),
                        marks={j: "j", hole: "key"},
                        roles={"i": i, "j": j, "key": hole},
                        note=f"compare with {arr[j]} -- stop, the gap is here",
                        kind="compare",
                        comparisons=comparisons,
                        actions=actions,
                        ordered=frozenset(ordered),
                    )
                    break

                moved = arr[j]
                yield Frame(
                    array=list(display),
                    marks={j: "j", hole: "key"},
                    roles={"i": i, "j": j, "key": hole},
                    note=f"compare with {moved} -- it moves right",
                    kind="compare",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(ordered),
                )
                arr[j + 1] = arr[j]
                display[j + 1] = display[j]
                display[j] = None
                hole = j
                actions += 1
                yield Frame(
                    array=list(display),
                    marks={hole: "key", j + 1: "j"},
                    roles={"i": i, "j": j, "key": hole},
                    note=f"shift {moved} right to index {j + 1}",
                    kind="shift",
                    comparisons=comparisons,
                    actions=actions,
                    ordered=frozenset(ordered),
                )
                j -= 1

            arr[hole] = key
            display[hole] = key
            ordered = set(range(i + 1))
            yield Frame(
                array=list(display),
                marks={hole: "key"},
                roles={"i": i, "key": hole},
                note=f"drop {key} into index {hole}",
                kind="insert",
                comparisons=comparisons,
                actions=actions,
                ordered=frozenset(ordered),
            )

        yield self._done(arr, comparisons, actions)


#: Everything the menu can pick from, in menu order.
STRATEGIES: list[type[SortStrategy]] = [BubbleSort, SelectionSort, InsertionSort]


def run_to_completion(strategy: SortStrategy, values: Sequence[int]) -> SortSummary:
    """Run a strategy for real and collect its totals (used by 'compare')."""
    frames = list(strategy.frames(values))
    final = [v for v in frames[-1].array] if frames else list(values)
    return SortSummary(
        name=strategy.name,
        steps=len(frames),
        comparisons=frames[-1].comparisons if frames else 0,
        actions=frames[-1].actions if frames else 0,
        final=final,
        ok=final == sorted(values),
    )


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class DataManager:
    """Owns the untouched master list; everything else works on copies."""

    MAX_SIZE = 500
    ARRANGEMENTS = ("random", "sorted", "reverse")

    def __init__(self) -> None:
        self._master: list[int] = []

    @property
    def master(self) -> list[int]:
        return list(self._master)

    @property
    def is_empty(self) -> bool:
        return not self._master

    def set_values(self, values: Sequence[int]) -> None:
        self._master = list(values)

    @classmethod
    def parse(cls, raw: str) -> tuple[list[int], list[str]]:
        """Parse ``"1, 2, 3"`` -> ``(values, bad_tokens)``."""
        text = raw.replace(";", ",").replace(",", " ")
        values: list[int] = []
        bad: list[str] = []
        for token in text.split():
            try:
                values.append(int(token))
            except ValueError:
                bad.append(token)
        return values, bad

    @classmethod
    def generate(cls, size: int, low: int, high: int, arrangement: str) -> list[int]:
        import random

        if low > high:
            low, high = high, low
        if arrangement in ("sorted", "reverse"):
            if high - low + 1 >= size:
                values = sorted(random.sample(range(low, high + 1), size))
            else:
                values = sorted(random.randint(low, high) for _ in range(size))
            if arrangement == "reverse":
                values.reverse()
            return values
        return [random.randint(low, high) for _ in range(size)]


# ---------------------------------------------------------------------------
# Shared panel builders
# ---------------------------------------------------------------------------

def section_panel(
    title: str,
    renderable,
    style: str = "white",
    subtitle: str | None = None,
    border: str | None = None,
    border_box=None,
    title_align: str = "left",
) -> Panel:
    """A rounded panel used for every block on the screens."""
    return Panel(
        renderable,
        title=f"[bold {style}]{title}[/]",
        subtitle=f"[dim]{subtitle}[/]" if subtitle else None,
        title_align=title_align,
        subtitle_align="right",
        border_style=border or PANEL_EDGE,
        box=border_box or box.ROUNDED,
        padding=(0, 1),
    )


def card_panel(
    values: Sequence[int | None],
    title: str,
    style: str = "white",
    width: int | None = None,
    subtitle: str | None = None,
    border: str | None = None,
    highlights: Mapping[int, str] | None = None,
) -> Panel:
    body = render_row(values, width or 80, highlights=highlights)
    return section_panel(title, body, style, subtitle=subtitle, border=border)


# ---------------------------------------------------------------------------
# Live sorter -- replays frames one iteration at a time
# ---------------------------------------------------------------------------

class SortResult:
    """What a live run produced."""

    def __init__(
        self,
        strategy: str,
        original: list[int],
        final: list[int],
        steps: int,
        comparisons: int,
        actions: int,
        ok: bool,
    ) -> None:
        self.strategy = strategy
        self.original = original
        self.final = final
        self.steps = steps
        self.comparisons = comparisons
        self.actions = actions
        self.ok = ok


class LiveSorter:
    """Replays a strategy's frames on screen, one iteration at a time."""

    def __init__(
        self,
        strategy: SortStrategy,
        console: Console,
        mode: str = "step",
        delay: float = AUTOPLAY_DELAY,
    ) -> None:
        self.strategy = strategy
        self.console = console
        self.mode = mode            # "step" (Enter) or "auto" (sleep)
        self.delay = delay

    @property
    def cols(self) -> int:
        return self.console.width

    # -- small UI helpers -------------------------------------------------
    @staticmethod
    def _badge(text: str, fg: str = "#0d1117", bg: str = ACCENT) -> Text:
        chip = Text()
        chip.append(f" {text} ", style=f"bold {fg} on {bg}")
        return chip

    @staticmethod
    def _bar(fraction: float, width: int) -> Text:
        filled = max(0, min(width, round(width * fraction)))
        rail = Text()
        rail.append("━" * filled, style=f"bold {ACCENT}")
        rail.append("━" * (width - filled), style=FAINT)
        return rail

    def _header(self, step: int, total: int) -> Panel:
        cols = self.cols
        left = Text()
        left.append("◆ ", style=f"bold {ACCENT}")
        left.append("LIVE SORT" if cols >= 60 else "LIVE", style="bold #ffffff")
        left.append("  ")
        left.append_text(self._badge(self.strategy.name.upper()))

        right = Text()
        right.append(f"step {step}/{total}", style=f"bold {INK}")
        right.append("   ")
        right.append_text(self._bar(step / max(1, total), 14))
        right.append(f" {round(100 * step / max(1, total)):>3}%", style=f"bold {ACCENT}")

        grid = Table.grid(expand=True)
        grid.add_column(no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)
        grid.add_row(left, right)
        return Panel(grid, border_style=ACCENT, box=box.HEAVY, padding=(0, 1))

    def _legend(self, frame: Frame) -> Text:
        out = Text()
        for role in self.strategy.roles:
            idx = frame.roles.get(role.key)
            out.append("● ", style=f"bold {role.colour}")
            out.append(role.label, style=DIM)
            out.append(" ")
            out.append("→", style=FAINT)
            out.append(" ")
            out.append("–" if idx is None else str(idx), style=f"bold {role.colour}")
            out.append("     ")
        return out

    def _note(self, frame: Frame) -> Text:
        icon, colour = STEP_ICONS.get(frame.kind, ("•", DIM))
        out = Text()
        out.append("  " + icon + "  ", style=f"bold {colour}")
        out.append(frame.note, style=INK)
        out.append("     ", style="dim")
        out.append(counted(frame.comparisons, "comparison"), style=f"bold {ACCENT}")
        out.append("  ·  ", style=DIM)
        out.append(counted(frame.actions, self.strategy.singular), style=f"bold {GOOD}")
        return out

    def _marks(self, frame: Frame) -> dict[int, str]:
        marks = _ordered_marks(frame.ordered)
        marks.update(frame.marks)
        return marks

    def _advance(self) -> None:
        if self.mode == "step":
            ans = self.console.input(f"[bold {ACCENT}]⏎[/] [dim]next  ·  [/][bold {DANGER}]q[/][dim] quit [/]")
            self.console.print()
            if ans.strip().lower() in ("q", "-1"):
                raise KeyboardInterrupt
        else:
            time.sleep(self.delay)

    # -- screens ----------------------------------------------------------
    def _render(self, frame: Frame, step: int, total: int) -> None:
        self.console.clear()
        self.console.print(self._header(step, total))
        self.console.print(self._legend(frame))
        self.console.print(
            render_row(frame.array, self.cols, highlights=self._marks(frame))
        )
        self.console.print(self._note(frame))
        hint = "⏎ next step" if self.mode == "step" else "auto-play"
        self.console.print(Text(hint, style=DIM))

    def _final(self, original: Sequence[int], frames: list[Frame], ok: bool) -> None:
        self.console.clear()
        tone = GOOD if ok else DANGER
        cols = self.cols

        left = Text()
        left.append("◆ ", style=f"bold {ACCENT}")
        left.append("LIVE SORT", style="bold #ffffff")
        left.append("  ")
        left.append_text(self._badge(self.strategy.name.upper()))
        right = Text()
        right.append("✓ SORTED" if ok else "✕ MISMATCH", style=f"bold {tone}")

        grid = Table.grid(expand=True)
        grid.add_column(no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)
        grid.add_row(left, right)
        self.console.print(Panel(grid, border_style=tone, box=box.HEAVY, padding=(0, 1)))

        final = [v for v in frames[-1].array]
        self.console.print(
            render_row(final, cols, highlights={i: "ordered" for i in range(len(final))})
        )

        last = frames[-1]
        stats = Text()
        stats.append("steps ", style=DIM)
        stats.append(str(len(frames)), style=f"bold {ACCENT}")
        stats.append("   comparisons ", style=DIM)
        stats.append(str(last.comparisons), style=f"bold {ACCENT}")
        stats.append(f"   {self.strategy.unit} ", style=DIM)
        stats.append(str(last.actions), style=f"bold {GOOD}")
        self.console.print(stats)
        self.console.print(
            Text("press Enter to return to the menu", style=DIM)
        )

    # -- driver -----------------------------------------------------------
    def run(self, values: Sequence[int]) -> SortResult:
        original = list(values)
        frames = list(self.strategy.frames(original))
        total = len(frames)

        for step, frame in enumerate(frames, 1):
            self._render(frame, step, total)
            self._advance()

        final = [v for v in frames[-1].array] if frames else list(original)
        ok = final == sorted(original)
        self._final(original, frames, ok)
        self._advance()

        return SortResult(
            strategy=self.strategy.name,
            original=original,
            final=final,
            steps=len(frames),
            comparisons=frames[-1].comparisons if frames else 0,
            actions=frames[-1].actions if frames else 0,
            ok=ok,
        )


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

class Quit(Exception):
    """Raised when the user types a negative number anywhere."""


class Menu:
    """The interactive loop: draws the menu and dispatches each option."""

    OPTIONS = (
        ("Enter numbers manually", "type a comma separated list"),
        ("Generate a random list", "choose size and range"),
        ("Show current data as cards", "preview the current array"),
        ("Visualize a sort", "watch i and j move, step by step"),
        ("Compare all methods", "counters for every algorithm"),
        ("Exit", "close the visualizer"),
    )

    def __init__(self) -> None:
        self.console = Console()
        self.data = DataManager()
        self.last_result: SortResult | None = None

    # -- generic prompting ------------------------------------------------
    def _check_negative(self, raw: str) -> None:
        """Any negative number typed at a prompt quits the program."""
        try:
            if int(raw.strip()) < 0:
                raise Quit
        except ValueError:
            pass

    def ask_choice(self, message: str, labels: Sequence[str]) -> int:
        """Ask for a numbered *or* named choice; returns a 0-based index."""
        lookup: dict[str, int] = {}
        for i, label in enumerate(labels, 1):
            lookup[str(i)] = i - 1
            lookup[label.lower()] = i - 1
        hint = ", ".join(f"{i}={label}" for i, label in enumerate(labels, 1))
        self.console.print(f"[dim]{hint}[/]")
        prompt = f"[bold {ACCENT}]?[/] {message}"
        while True:
            raw = Prompt.ask(prompt).strip()
            self._check_negative(raw)
            if raw.lower() in lookup:
                return lookup[raw.lower()]
            self.console.print(f"[bold {DANGER}]✗[/] type one of: {hint}")

    def ask_int(self, message: str, low: int, high: int, default: int) -> int:
        """Ask for an integer inside ``[low, high]``; a negative quits."""
        while True:
            raw = Prompt.ask(f"[bold {ACCENT}]?[/] {message}", default=str(default)).strip()
            self._check_negative(raw)
            try:
                value = int(raw)
            except ValueError:
                self.console.print(f"[bold {DANGER}]✗[/] enter a whole number.")
                continue
            if low <= value <= high:
                return value
            self.console.print(
                f"[bold {DANGER}]✗[/] enter a number between {low} and {high}."
            )

    # -- header / menu ----------------------------------------------------
    def _exit_line(self) -> Text:
        out = Text()
        out.append("  ⚠  EXIT AT ANYTIME: type a negative number (e.g. -1)  ", style=f"bold #ffffff on {DANGER}")
        return out

    def _banner(self) -> Panel:
        title = Text()
        title.append("L I V E  ", style=f"bold {INK}")
        title.append("S O R T  ", style=f"bold {ACCENT}")
        title.append("V I S U A L I Z E R", style=f"bold {INK}")
        sub = Text(
            "watch the loop counters i and j walk through bubble, selection and insertion sort",
            style=DIM,
        )
        body = Group(Align.center(title), Align.center(Text("")), Align.center(sub))
        return Panel(body, box=box.DOUBLE, border_style=ACCENT, padding=(1, 2))

    def _status_panel(self) -> Panel:
        if self.data.is_empty:
            body = Text("nothing loaded yet -- pick 1 or 2 to load some numbers", style=DIM)
            return section_panel("current data", body, AMBER, border=FAINT)

        values = self.data.master
        preview = values[:10]
        rows: list = [render_row(preview, self.console.width - PANEL_PAD - 2)]
        if len(values) > 10:
            rows.append(Text(f"… + {counted(len(values) - 10, 'more card')}", style=DIM))
        shown = ", ".join(str(v) for v in values[:12])
        if len(values) > 12:
            shown += ", …"
        rows.append(Text(f"[{shown}]", style=DIM))
        return section_panel(
            "current data",
            Group(*rows),
            GOOD,
            subtitle=counted(len(values), "card"),
            border=FAINT,
        )

    def draw_menu(self) -> None:
        self.console.print()
        self.console.print(Align.center(self._exit_line()))
        self.console.print(self._banner())
        self.console.print(self._status_panel())

        table = Table(box=None, show_header=False, padding=(0, 2), expand=False)
        table.add_column(style=f"bold {ACCENT}", justify="right", width=2, no_wrap=True)
        table.add_column(style=f"bold {INK}", no_wrap=True)
        table.add_column(style=DIM)
        for i, (label, detail) in enumerate(self.OPTIONS, 1):
            table.add_row(str(i), label, detail)

        self.console.print(
            section_panel("menu", table, ACCENT, subtitle="type a number", border=FAINT)
        )

    # -- options ----------------------------------------------------------
    def option_manual(self) -> None:
        while True:
            raw = Prompt.ask(
                f"[bold {ACCENT}]?[/] Enter numbers separated by commas "
                "[dim](blank line cancels)[/]"
            )
            if not raw.strip():
                self.console.print("[dim]cancelled -- nothing changed.[/]")
                return

            values, bad = DataManager.parse(raw)
            if any(v < 0 for v in values):
                raise Quit
            if bad:
                self.console.print(
                    f"[bold {DANGER}]✗[/] not valid integers: {', '.join(bad)} -- try again."
                )
                continue
            if not values:
                self.console.print(f"[bold {DANGER}]✗[/] no numbers found -- try again.")
                continue

            self.data.set_values(values)
            self.console.print(f"[bold {GOOD}]✓[/] loaded {counted(len(values), 'number')}.")
            self.console.print(self._section_preview())
            return

    def option_generate(self) -> None:
        size = self.ask_int(
            f"How many numbers [1-{DataManager.MAX_SIZE}]", 1, DataManager.MAX_SIZE, 10
        )
        low = self.ask_int("Minimum value [-99999-99999]", -99999, 99999, 1)
        high = self.ask_int("Maximum value [-99999-99999]", -99999, 99999, 99)
        if low > high:
            self.console.print(f"[dim]swapped: {low} > {high}.[/]")
            low, high = high, low

        arrangement = self.ask_choice("Arrangement", DataManager.ARRANGEMENTS)
        kind = DataManager.ARRANGEMENTS[arrangement]
        values = DataManager.generate(size, low, high, kind)
        self.data.set_values(values)

        self.console.print(
            f"[bold {GOOD}]✓[/] generated {counted(size, kind + ' number')} in [{low}, {high}]."
        )
        self.console.print(self._section_preview())

    def option_show(self) -> None:
        if self.data.is_empty:
            self._no_data()
            return
        values = self.data.master
        self.console.print(
            self._row(values, "current data", GOOD, subtitle=counted(len(values), "card"))
        )

    def option_visualize(self) -> None:
        if self.data.is_empty:
            self._no_data()
            return

        values = self.data.master

        if len(values) > LIVE_LIMIT:
            self.console.print(
                f"[bold {AMBER}]![/] {len(values)} cards exceeds the live-mode "
                f"limit of {LIVE_LIMIT}."
            )
            keep = Confirm.ask(
                f"[bold {ACCENT}]?[/] Use the first {LIVE_LIMIT} cards for this run?"
            )
            if not keep:
                self.console.print("[dim]visualize cancelled.[/]")
                return
            values = values[:LIVE_LIMIT]
            self.console.print(f"[dim]using the first {LIVE_LIMIT} cards for this run.[/]")

        total = len(values)
        whole = values

        remaining = list(STRATEGIES)
        while remaining:
            which = self.ask_choice("Choose an algorithm", [s.name for s in remaining])
            strategy = remaining.pop(which)()

            mode_labels = ["step-by-step (press Enter)", "auto-play (timed)"]
            mode_pick = self.ask_choice("Choose a mode", mode_labels)
            mode = "step" if mode_pick == 0 else "auto"

            sorter = LiveSorter(strategy, self.console, mode=mode)
            self.last_result = sorter.run(values)

            if not remaining:
                break
            again = Confirm.ask(
                f"[bold {ACCENT}]?[/] Sort the same {counted(whole.__len__(), 'number')} "
                "with another algorithm?"
            )
            if not again:
                break

    def option_compare(self) -> None:
        if self.data.is_empty:
            self._no_data()
            return

        values = self.data.master
        summaries = [run_to_completion(cls(), values) for cls in STRATEGIES]

        def best(key) -> int:
            return min(key(s) for s in summaries)

        def cell(value: int, winner: int) -> Text:
            style = f"bold {GOOD}" if value == winner else DIM
            return Text(str(value), style=style)

        table = Table(
            box=box.SIMPLE_HEAVY,
            header_style=f"bold {ACCENT}",
            highlight=True,
            padding=(0, 1),
        )
        table.add_column("Method", style=INK)
        table.add_column("Steps", justify="right")
        table.add_column("Comparisons", justify="right")
        table.add_column("Swaps / Shifts", justify="right")
        table.add_column("Correct", justify="center")

        wins = (
            best(lambda s: s.steps),
            best(lambda s: s.comparisons),
            best(lambda s: s.actions),
        )
        for s in summaries:
            table.add_row(
                s.name,
                cell(s.steps, wins[0]),
                cell(s.comparisons, wins[1]),
                cell(s.actions, wins[2]),
                Text("✓ yes", style=f"bold {GOOD}") if s.ok
                else Text("✕ NO", style=f"bold {DANGER}"),
            )

        self.console.print(
            section_panel(
                "compare methods", table, ACCENT, subtitle=counted(len(values), "card")
            )
        )

        originals = values[:10]
        self.console.print(
            Text(style=DIM)
            .append("sorted(): ")
            .append_text(
                Text(f"{sorted(originals)}{' ...' if len(values) > 10 else ''}", style=INK)
            )
        )

    def _no_data(self) -> None:
        self.console.print(
            section_panel(
                "current data",
                Text("nothing loaded yet -- pick 1 or 2 first", style=DIM),
                AMBER,
                border=DANGER,
            )
        )

    def _row(
        self,
        values: Sequence[int | None],
        title: str,
        style: str = "white",
        subtitle: str | None = None,
    ) -> Panel:
        return card_panel(
            values, title, style, width=self.console.width, subtitle=subtitle
        )

    def _section_preview(self) -> Panel:
        return card_panel(
            self.data.master,
            "loaded",
            GOOD,
            width=self.console.width,
            subtitle=counted(len(self.data.master), "card"),
        )

    # -- loop -------------------------------------------------------------
    def run(self) -> None:
        try:
            while True:
                self.draw_menu()
                choice = self.ask_choice(
                    "Pick an option", [label for label, _ in self.OPTIONS]
                )
                if choice == 0:
                    self.option_manual()
                elif choice == 1:
                    self.option_generate()
                elif choice == 2:
                    self.option_show()
                elif choice == 3:
                    self.option_visualize()
                elif choice == 4:
                    self.option_compare()
                else:
                    self.console.print(f"\n[bold {GOOD}]✓[/] [dim]goodbye![/]")
                    return
        except Quit:
            self.console.print(f"\n[bold {GOOD}]✓[/] [dim]exiting -- goodbye![/]")
        except KeyboardInterrupt:
            self.console.print(f"\n[bold {AMBER}]![/] [dim]interrupted -- goodbye![/]")
        except EOFError:
            self.console.print("\n[dim]input closed -- goodbye![/]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the visualiser."""
    Menu().run()


if __name__ == "__main__":
    main()
