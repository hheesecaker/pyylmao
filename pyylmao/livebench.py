from __future__ import annotations

import csv
import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


LIVEBENCH_BASE_URL = "https://livebench.ai/"
LIVEBENCH_CACHE_SECONDS = 60 * 60

SIMPLE_COLUMNS = (
    "reasoning",
    "coding",
    "agentic_coding",
    "mathematics",
    "data_analysis",
    "language",
    "if",
)

FULL_COLUMNS = (
    "amps_hard",
    "code_completion",
    "code_generation",
    "connections",
    "consecutive_events",
    "integrals_with_game",
    "javascript",
    "logic_with_navigation",
    "math_comp",
    "olympiad",
    "paraphrase",
    "plot_unscrambling",
    "python",
    "simplify",
    "spatial",
    "story_generation",
    "summarize",
    "tablejoin",
    "tablereformat",
    "theory_of_mind",
    "typescript",
    "typos",
    "zebra_puzzle",
)


@dataclass(frozen=True)
class LiveBenchRequest:
    simple: bool
    columns: tuple[str, ...]
    top: int
    sort_by: str = ""
    sort_desc: bool = True


@dataclass(frozen=True)
class LiveBenchRow:
    model: str
    scores: dict[str, float]


@dataclass(frozen=True)
class LiveBenchDataset:
    date: str
    rows: tuple[LiveBenchRow, ...]
    categories: dict[str, tuple[str, ...]]
    source_url: str


class LiveBenchProvider(Protocol):
    def load(self) -> LiveBenchDataset:
        ...


class LiveBenchError(RuntimeError):
    pass


class LiveBenchOnlineProvider:
    def __init__(
        self,
        base_url: str = LIVEBENCH_BASE_URL,
        cache_seconds: int = LIVEBENCH_CACHE_SECONDS,
    ):
        self.base_url = base_url
        self.cache_seconds = cache_seconds
        self._cached_at = 0.0
        self._cached_dataset: LiveBenchDataset | None = None

    def load(self) -> LiveBenchDataset:
        now = time.time()
        if self._cached_dataset is not None and now - self._cached_at < self.cache_seconds:
            return self._cached_dataset

        date = self._discover_latest_date()
        date_slug = date.replace("-", "_")
        table_url = urljoin(self.base_url, f"table_{date_slug}.csv")
        categories_url = urljoin(self.base_url, f"categories_{date_slug}.json")
        table_text = fetch_text(table_url)
        categories_text = fetch_text(categories_url)
        dataset = parse_livebench_dataset(date, table_url, table_text, categories_text)
        self._cached_dataset = dataset
        self._cached_at = now
        return dataset

    def _discover_latest_date(self) -> str:
        html = fetch_text(self.base_url)
        main_js = discover_main_js_url(self.base_url, html)
        try:
            app_source = fetch_frontend_source(main_js, "App.js")
        except (LiveBenchError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            app_source = fetch_text(main_js)
        match = re.search(r"useState\(['\"](\d{4}-\d{2}-\d{2})['\"]\)", app_source)
        if match:
            return match.group(1)
        match = re.search(r"LiveBench-(\d{4}-\d{2}-\d{2})", app_source)
        if match:
            return match.group(1)
        raise LiveBenchError("could not discover latest LiveBench release date")


DEFAULT_PROVIDER = LiveBenchOnlineProvider()


def is_livebench_command(text: str) -> bool:
    return parse_livebench_command(text) is not None


def parse_livebench_command(text: str) -> LiveBenchRequest | None:
    match = re.match(r"^[!?]livebench(?:\s+(.*))?$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    raw_args = match.group(1) or ""
    top_match = re.search(r"(?:^|\s)-top\s+(\d+)(?:\s|$)", raw_args, flags=re.IGNORECASE)
    top = min(max(int(top_match.group(1)), 1), 50) if top_match else 20
    sort_by, sort_desc = parse_sort_option(raw_args)
    simple = "+simple" in raw_args.lower()
    cleaned = re.sub(r"(?:^|\s)-top\s+\d+(?:\s|$)", " ", raw_args, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"(?:^|\s)-sort\s+\S+(?:\s+(?:asc|desc))?(?:\s|$)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\+simple", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", " ")
    requested = tuple(
        normalized
        for token in cleaned.split()
        if (normalized := normalize_key(token)) in SIMPLE_COLUMNS or normalized in FULL_COLUMNS
    )
    if requested:
        return LiveBenchRequest(simple=True, columns=requested, top=top, sort_by=sort_by, sort_desc=sort_desc)
    if simple:
        return LiveBenchRequest(simple=True, columns=SIMPLE_COLUMNS, top=top, sort_by=sort_by, sort_desc=sort_desc)
    return LiveBenchRequest(simple=False, columns=FULL_COLUMNS, top=top, sort_by=sort_by, sort_desc=sort_desc)


def render_livebench_command(
    text: str,
    provider: LiveBenchProvider | None = None,
) -> list[str]:
    request = parse_livebench_command(text)
    if request is None:
        return []
    try:
        dataset = (provider or DEFAULT_PROVIDER).load()
    except (LiveBenchError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, csv.Error) as exc:
        return [f"LiveBench fetch failed: {exc}"]

    columns = tuple(column for column in request.columns if column_available(dataset, column))
    if not columns:
        columns = SIMPLE_COLUMNS if request.simple else full_columns_for(dataset)

    rows = sorted(
        dataset.rows,
        key=lambda row: sort_score(row, dataset, columns, request.sort_by),
        reverse=request.sort_desc,
    )
    return render_table(rows[: request.top], dataset, columns, fancy=request.simple)


def render_table(
    rows: list[LiveBenchRow],
    dataset: LiveBenchDataset,
    columns: tuple[str, ...],
    fancy: bool,
) -> list[str]:
    labels = ("model", "avg", *columns)
    widths = widths_for(rows, dataset, columns)
    rendered_rows = [render_header(labels, widths, fancy)]
    for row in rows:
        rendered_rows.append(render_row(row, dataset, columns, widths, fancy))
    if not fancy:
        return rendered_rows
    total_width = max(len(line) for line in rendered_rows)
    bottom = "🮝" + "🮘" * max(total_width - 2, 1) + "🮟"
    return ["", " " * total_width, *rendered_rows, bottom, "", ""]


def widths_for(
    rows: list[LiveBenchRow],
    dataset: LiveBenchDataset,
    columns: tuple[str, ...],
) -> dict[str, int]:
    widths = {"model": 51, "avg": 5}
    for column in columns:
        label = column.upper()
        values = [len(format_score(column_score(row, dataset, column))) for row in rows]
        widths[column] = max([len(label), *values])
    return widths


def render_header(labels: tuple[str, ...], widths: dict[str, int], fancy: bool) -> str:
    values = [label.upper() for label in labels]
    if fancy:
        return render_fancy_cells(values, labels, widths)
    return render_pipe_cells(values, labels, widths)


def render_row(
    row: LiveBenchRow,
    dataset: LiveBenchDataset,
    columns: tuple[str, ...],
    widths: dict[str, int],
    fancy: bool,
) -> str:
    labels = ("model", "avg", *columns)
    values = [
        row.model,
        format_score(score(row, dataset, columns)),
        *[format_score(column_score(row, dataset, column)) for column in columns],
    ]
    if fancy:
        return render_fancy_cells(values, labels, widths)
    return render_pipe_cells(values, labels, widths)


def render_pipe_cells(values: list[str], labels: tuple[str, ...], widths: dict[str, int]) -> str:
    return " | " + " | ".join(
        value.ljust(widths[label]) for value, label in zip(values, labels, strict=True)
    ) + " | "


def render_fancy_cells(values: list[str], labels: tuple[str, ...], widths: dict[str, int]) -> str:
    cells = [values[0].ljust(widths["model"])]
    for value, label in zip(values[1:], labels[1:], strict=True):
        cells.append(value.ljust(widths[label]))
    return " " + " 🭍  ".join(cells) + " 🭍"


def score(
    row: LiveBenchRow,
    dataset: LiveBenchDataset,
    columns: tuple[str, ...],
) -> float:
    if set(columns) == set(full_columns_for(dataset)):
        columns = tuple(column for column in SIMPLE_COLUMNS if column in dataset.categories)
    return average([column_score(row, dataset, column) for column in columns])


def sort_score(
    row: LiveBenchRow,
    dataset: LiveBenchDataset,
    columns: tuple[str, ...],
    sort_by: str,
) -> float:
    if sort_by and sort_by != "avg" and column_available(dataset, sort_by):
        return column_score(row, dataset, sort_by)
    return score(row, dataset, columns)


def column_score(row: LiveBenchRow, dataset: LiveBenchDataset, column: str) -> float:
    if column in dataset.categories:
        return average(row.scores[name] for name in dataset.categories[column] if name in row.scores)
    return row.scores[column]


def average(values: Iterable[float]) -> float:
    value_list = [float(value) for value in values]
    if not value_list:
        return 0.0
    return sum(value_list) / len(value_list)


def format_score(value: float | str) -> str:
    if isinstance(value, str):
        return value
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    if "." not in formatted:
        formatted += ".0"
    return formatted


def column_available(dataset: LiveBenchDataset, column: str) -> bool:
    return column in dataset.categories or any(column in row.scores for row in dataset.rows)


def full_columns_for(dataset: LiveBenchDataset) -> tuple[str, ...]:
    known = tuple(column for column in FULL_COLUMNS if column_available(dataset, column))
    if known:
        return known
    columns: list[str] = []
    for row in dataset.rows:
        for column in row.scores:
            if column not in columns:
                columns.append(column)
    return tuple(columns)


def parse_livebench_dataset(
    date: str,
    source_url: str,
    table_text: str,
    categories_text: str,
) -> LiveBenchDataset:
    categories_json = json.loads(categories_text)
    categories = {
        normalize_key(category): tuple(normalize_key(column) for column in columns)
        for category, columns in categories_json.items()
    }
    reader = csv.DictReader(StringIO(table_text))
    rows: list[LiveBenchRow] = []
    for raw_row in reader:
        model = (raw_row.get("model") or "").strip()
        if not model:
            continue
        scores: dict[str, float] = {}
        for key, value in raw_row.items():
            if key is None or normalize_key(key) == "model" or value in (None, ""):
                continue
            try:
                scores[normalize_key(key)] = float(value)
            except ValueError:
                continue
        rows.append(LiveBenchRow(model=model, scores=scores))
    if not rows:
        raise LiveBenchError("LiveBench table did not contain any model rows")
    return LiveBenchDataset(
        date=date,
        rows=tuple(rows),
        categories=categories,
        source_url=source_url,
    )


def parse_sort_option(raw_args: str) -> tuple[str, bool]:
    match = re.search(
        r"(?:^|\s)-sort\s+(\S+)(?:\s+(asc|desc))?(?=\s|$)",
        raw_args,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", True
    sort_token = match.group(1)
    sort_desc = True
    if sort_token.startswith("+"):
        sort_desc = False
        sort_token = sort_token[1:]
    elif sort_token.startswith("-"):
        sort_token = sort_token[1:]
    if match.group(2):
        sort_desc = match.group(2).lower() != "asc"
    return normalize_key(sort_token), sort_desc


def discover_main_js_url(base_url: str, html: str) -> str:
    match = re.search(r'<script[^>]+src=["\']([^"\']*static/js/main\.[^"\']+\.js)["\']', html)
    if not match:
        raise LiveBenchError("could not find LiveBench frontend bundle")
    return urljoin(base_url, match.group(1))


def fetch_frontend_source(main_js_url: str, source_name: str) -> str:
    source_map = json.loads(fetch_text(main_js_url + ".map"))
    for name, content in zip(
        source_map.get("sources", []),
        source_map.get("sourcesContent", []),
        strict=False,
    ):
        if name.endswith(source_name):
            return str(content)
    raise LiveBenchError(f"could not find {source_name} in LiveBench source map")


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "pyylmao"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8")


def normalize_key(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", value)
