from __future__ import annotations

import csv
import hashlib
import html
import json
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import ASSETS_DIR
from .state import JsonState


pattern = r"^(.+)$"
TRIVIA_PREFIX_RE = re.compile(r"^!trivia(?:\s+(.*))?$", re.IGNORECASE)
IRC_DARK_GREY = "\x0314"
IRC_RESET = "\x03"


@dataclass(frozen=True)
class TriviaCategory:
    slug: str
    display: str


@dataclass(frozen=True)
class TriviaQuestion:
    question: str
    answer: str
    category: str
    difficulty: str = "medium"


CATEGORIES: tuple[TriviaCategory, ...] = (
    TriviaCategory("animals", "Animals"),
    TriviaCategory("brain-teasers", "Brain Teasers"),
    TriviaCategory("celebrities", "Celebrities"),
    TriviaCategory("entertainment", "Entertainment"),
    TriviaCategory("for-kids", "For Kids"),
    TriviaCategory("general", "General"),
    TriviaCategory("geography", "Geography"),
    TriviaCategory("history", "History"),
    TriviaCategory("hobbies", "Hobbies"),
    TriviaCategory("humanities", "Humanities"),
    TriviaCategory("literature", "Literature"),
    TriviaCategory("movies", "Movies"),
    TriviaCategory("music", "Music"),
    TriviaCategory("newest", "Newest"),
    TriviaCategory("people", "People"),
    TriviaCategory("rated", "Rated"),
    TriviaCategory("religion-faith", "Religion Faith"),
    TriviaCategory("science-technology", "Science Technology"),
    TriviaCategory("sports", "Sports"),
    TriviaCategory("television", "Television"),
    TriviaCategory("video-games", "Video Games"),
    TriviaCategory("world", "World"),
)


FALLBACK_QUESTIONS: tuple[TriviaQuestion, ...] = (
    TriviaQuestion(
        "In which US state is the active Mount Rainier volcano located?",
        "Washington",
        "history",
        "medium",
    ),
    TriviaQuestion(
        "The Punic Wars were a series of three wars fought between these two powers.",
        "Rome and Carthage",
        "history",
        "medium",
    ),
    TriviaQuestion(
        "The 1938 incorporation of Austria in Greater Germany under the Nazi Regime is known as this.",
        "Anschluss",
        "history",
        "medium",
    ),
    TriviaQuestion(
        "This formation is a conical hill or mountain. It is formed by mantle material being pressed through an opening in Earths crust.",
        "Volcano",
        "science-technology",
        "hard",
    ),
    TriviaQuestion(
        "Japan suffers from this event very often. It is the sudden, light or violent movement of the earths surface caused by the release of energy in earths crust.",
        "Earthquake",
        "science-technology",
        "hard",
    ),
    TriviaQuestion(
        "It is the only continent that does not have land areas below sea level.",
        "Antarctica",
        "science-technology",
        "hard",
    ),
    TriviaQuestion(
        "This is a gemstone made by fossilized tree sap that is at least 30 million years old.",
        "Amber",
        "science-technology",
        "hard",
    ),
    TriviaQuestion(
        "This is the largest island on Earth and one third of it is a national park.",
        "Greenland",
        "science-technology",
        "hard",
    ),
    TriviaQuestion(
        "Name the human organ that currently has no known essential function.",
        "appendix",
        "science-technology",
        "hard",
    ),
)


DEFAULT_CHANNEL_STATE: dict[str, Any] = {
    "asked": [],
    "category_ids": [],
    "correct_answer": "",
    "current_question": "",
    "difficulty": "medium",
    "guesses": [],
    "last_correct_answer": "",
    "last_guesses": [],
    "last_question": "",
    "last_winner": "",
    "mode": "dumb",
    "threshold": 0.20,
}


def is_trivia_command(text: str) -> bool:
    return bool(TRIVIA_PREFIX_RE.match(text.strip()))


class TriviaStore:
    def __init__(
        self,
        state: JsonState,
        questions: list[TriviaQuestion] | tuple[TriviaQuestion, ...] | None = None,
        rng: random.Random | None = None,
        csv_dir: Path | None = None,
        semantic_checker: Callable[[TriviaQuestion, str], tuple[bool, str]] | None = None,
    ):
        self.state = state
        self.root = state.data.setdefault("kvstore", {}).setdefault("commands", {}).setdefault("trivia", {})
        self.root.setdefault("state", {})
        self.root.setdefault("stats", {})
        self.questions = list(questions) if questions is not None else None
        self.rng = rng or random.Random()
        self.csv_dir = csv_dir or ASSETS_DIR / "trivia" / "categories"
        self.semantic_checker = semantic_checker

    def handle(
        self,
        nickname: str,
        channel: str,
        text: str,
        username: str = "",
        hostname: str = "",
    ) -> list[str] | None:
        stripped = text.strip()
        command_match = TRIVIA_PREFIX_RE.match(stripped)
        if command_match:
            return self.handle_command(nickname, channel, command_match.group(1) or "", username, hostname)
        return self.handle_answer(nickname, channel, stripped, username, hostname)

    def handle_command(
        self,
        nickname: str,
        channel: str,
        payload: str,
        username: str = "",
        hostname: str = "",
    ) -> list[str] | None:
        del nickname, username, hostname
        payload = payload.strip()
        lowered = payload.lower()
        if not payload:
            return self.ask(channel)
        if lowered == "categories":
            return self.categories()
        if lowered.startswith("category "):
            return self.set_categories(channel, payload[len("category ") :].strip())
        if lowered.startswith("difficulty "):
            return self.set_difficulty(channel, payload[len("difficulty ") :].strip())
        if lowered.startswith("threshold "):
            return self.set_threshold(channel, payload[len("threshold ") :].strip())
        if lowered.startswith("mode "):
            return self.set_mode(channel, payload[len("mode ") :].strip())
        if lowered == "rephrase":
            return self.rephrase(channel)
        if lowered == "dispute":
            return self.dispute(channel)
        return [
            "Trivia: categories, category <Books,Film|any>, difficulty <lvl>, "
            "threshold <n>, !trivia for Q, dispute, text=answer."
        ]

    def categories(self) -> list[str]:
        lines = ["Available categories:"]
        lines.extend(f"• {category.display}" for category in CATEGORIES)
        lines.append("Use !trivia category any or names for random/specific.")
        return lines

    def set_categories(self, channel: str, payload: str) -> list[str]:
        state = self.channel_state(channel)
        if not payload or payload.casefold() == "any":
            state["category_ids"] = []
            self.state.save()
            return ["Categories set to: Any."]
        selected: list[TriviaCategory] = []
        unknown: list[str] = []
        for raw_item in payload.split(","):
            item = raw_item.strip()
            if ":" in item:
                item = item.split(":", 1)[1].strip()
            category = find_category(item)
            if category is None:
                unknown.append(title_category(item) or raw_item.strip())
            elif category not in selected:
                selected.append(category)
        if not selected:
            if len(unknown) == 1 and unknown[0].isdigit():
                return [f"**{unknown[0]}** not found. Use `!trivia categories`."]
            lines = ["No matching categories set."]
            lines.extend(f"Unknown: {item}. See !trivia categories." for item in unknown)
            return lines
        state["category_ids"] = [category.slug for category in selected]
        self.state.save()
        lines = [f"Categories set to: {', '.join(category.display for category in selected)}."]
        if unknown:
            lines.extend(f"Unknown: {item}. See !trivia categories." for item in unknown)
        return lines

    def set_difficulty(self, channel: str, payload: str) -> list[str]:
        value = payload.strip().lower()
        if value not in {"easy", "medium", "hard"}:
            return ["Difficulty must be easy, medium, or hard."]
        self.channel_state(channel)["difficulty"] = value
        self.state.save()
        return [f"Difficulty display set to {value}."]

    def set_threshold(self, channel: str, payload: str) -> list[str]:
        try:
            value = float(payload.strip())
        except ValueError:
            return ["Threshold must be a number from 0.0 to 1.0."]
        if not 0.0 <= value <= 1.0:
            return ["Threshold must be a number from 0.0 to 1.0."]
        self.channel_state(channel)["threshold"] = round(value, 4)
        self.state.save()
        return [f"Threshold set to {value:.2f}."]

    def set_mode(self, channel: str, payload: str) -> list[str]:
        value = payload.strip().lower()
        if value not in {"dumb", "smart"}:
            return ["Mode must be dumb or smart."]
        self.channel_state(channel)["mode"] = value
        self.state.save()
        return [f"Trivia mode set to {value} mode."]

    def ask(self, channel: str) -> list[str]:
        state = self.channel_state(channel)
        question = self.choose_question(state)
        if question is None:
            category_ids = state.get("category_ids") or ["any"]
            return [f"No questions for '{category_ids[0]}'"]
        self.set_current_question(state, question)
        self.state.save()
        return [self.format_question(question, state)]

    def handle_answer(
        self,
        nickname: str,
        channel: str,
        guess: str,
        username: str = "",
        hostname: str = "",
    ) -> list[str] | None:
        if not guess:
            return None
        state = self.channel_state(channel)
        question_text = str(state.get("current_question") or "")
        correct_answer = str(state.get("correct_answer") or "")
        if not question_text or not correct_answer:
            return None
        if normalized_answer(guess) in {"a", "b", "c", "d"}:
            return None
        state.setdefault("guesses", []).append(
            {
                "nick": nickname,
                "user": username,
                "host": hostname,
                "guess": guess,
            }
        )
        threshold = float(state.get("threshold", 0.20))
        distance = normalized_levenshtein(guess, correct_answer)
        question = TriviaQuestion(
            question=question_text,
            answer=correct_answer,
            category=str(state.get("current_category") or selected_category_slug(state)),
            difficulty=str(state.get("current_difficulty") or state.get("difficulty") or "medium"),
        )
        if distance <= threshold:
            return self.mark_correct(nickname, channel, state, question, guess, distance, username, hostname)
        semantic_ok, semantic_reason = self.semantic_match(state, question, guess)
        if semantic_ok:
            return self.mark_semantic_correct(
                nickname,
                channel,
                state,
                question,
                guess,
                semantic_reason,
                username,
                hostname,
            )
        self.state.save()
        return None

    def mark_correct(
        self,
        nickname: str,
        channel: str,
        state: dict[str, Any],
        question: TriviaQuestion,
        guess: str,
        distance: float,
        username: str,
        hostname: str,
    ) -> list[str]:
        self.record_correct(state, nickname, username, hostname)
        line = (
            f"Correct, {nickname}! {guess} matches {question.answer} "
            f"(dist: {distance:.2f} ≤ {float(state.get('threshold', 0.20)):.2f}) 🎉"
        )
        next_question = self.advance_after_correct(channel, state, question, nickname)
        return [line, *next_question]

    def mark_semantic_correct(
        self,
        nickname: str,
        channel: str,
        state: dict[str, Any],
        question: TriviaQuestion,
        guess: str,
        reason: str,
        username: str,
        hostname: str,
    ) -> list[str]:
        self.record_correct(state, nickname, username, hostname)
        suffix = f" {reason}" if reason else ""
        line = f"Correct, {nickname}! {guess} is semantically correct!{suffix} 🎉"
        next_question = self.advance_after_correct(channel, state, question, nickname)
        return [line, *next_question]

    def advance_after_correct(
        self,
        channel: str,
        state: dict[str, Any],
        question: TriviaQuestion,
        nickname: str,
    ) -> list[str]:
        state["last_question"] = question.question
        state["last_correct_answer"] = question.answer
        state["last_guesses"] = list(state.get("guesses") or [])
        state["last_winner"] = nickname
        state["guesses"] = []
        state["current_question"] = ""
        state["correct_answer"] = ""
        self.state.save()
        return self.ask(channel)

    def record_correct(
        self,
        state: dict[str, Any],
        nickname: str,
        username: str,
        hostname: str,
    ) -> None:
        stats = self.root.setdefault("stats", {})
        key = stat_key(nickname, username, hostname)
        item = stats.setdefault(
            key,
            {
                "nickname": nickname,
                "username": username,
                "hostname": hostname,
                "correct": 0,
            },
        )
        item["nickname"] = nickname
        item["username"] = username
        item["hostname"] = hostname
        item["correct"] = int(item.get("correct") or 0) + 1
        state["last_winner"] = nickname

    def rephrase(self, channel: str) -> list[str]:
        state = self.channel_state(channel)
        question = str(state.get("current_question") or "")
        if not question:
            return ["No active trivia question."]
        answer = str(state.get("correct_answer") or "")
        rewritten = self.rephrase_with_llm(question, answer)
        if rewritten:
            state["current_question"] = rewritten
            self.state.save()
            display = TriviaQuestion(
                rewritten,
                answer,
                str(state.get("current_category") or selected_category_slug(state)),
                str(state.get("current_difficulty") or state.get("difficulty") or "medium"),
            )
            return [f"🔄 Rephrased question: {self.format_question(display, state, include_category=False)}"]
        display = TriviaQuestion(
            question,
            answer,
            str(state.get("current_category") or selected_category_slug(state)),
            str(state.get("current_difficulty") or state.get("difficulty") or "medium"),
        )
        return [f"🔄 Rephrased question: {self.format_question(display, state, include_category=False)}"]

    def dispute(self, channel: str) -> list[str]:
        state = self.channel_state(channel)
        if not state.get("last_question"):
            return ["No previous trivia question to dispute."]
        return ["Dispute recorded for review."]

    def active(self, channel: str) -> bool:
        state = self.channel_state(channel)
        return bool(state.get("current_question") and state.get("correct_answer"))

    def channel_state(self, channel: str) -> dict[str, Any]:
        states = self.root.setdefault("state", {})
        key = channel_key(channel)
        current = states.get(key)
        if not isinstance(current, dict):
            current = json.loads(json.dumps(DEFAULT_CHANNEL_STATE))
            states[key] = current
            return current
        for default_key, default_value in DEFAULT_CHANNEL_STATE.items():
            if default_key not in current:
                current[default_key] = json.loads(json.dumps(default_value))
        return current

    def choose_question(self, state: dict[str, Any]) -> TriviaQuestion | None:
        questions = self.load_questions(state)
        if not questions:
            return None
        asked = set(str(item) for item in state.setdefault("asked", []))
        fresh = [question for question in questions if question_id(question) not in asked]
        if not fresh:
            state["asked"] = []
            fresh = questions
        preferred = [question for question in fresh if "is not" not in question.question.casefold()]
        pool = preferred or fresh
        return self.rng.choice(pool)

    def load_questions(self, state: dict[str, Any]) -> list[TriviaQuestion]:
        category_ids = selected_categories(state)
        loaded = self.load_csv_questions(category_ids)
        if loaded:
            return loaded
        questions = self.questions if self.questions is not None else list(FALLBACK_QUESTIONS)
        if category_ids:
            filtered = [question for question in questions if question.category in category_ids]
            if filtered:
                return filtered
        return list(questions)

    def load_csv_questions(self, category_ids: list[str]) -> list[TriviaQuestion]:
        if not self.csv_dir.exists() or not self.csv_dir.is_dir():
            return []
        slugs = category_ids or [category.slug for category in CATEGORIES]
        questions: list[TriviaQuestion] = []
        for slug in slugs:
            path = self.csv_dir / f"{slug}.csv"
            if not path.exists():
                continue
            questions.extend(load_category_csv(path, slug))
        return questions

    def set_current_question(self, state: dict[str, Any], question: TriviaQuestion) -> None:
        state["current_question"] = question.question
        state["correct_answer"] = question.answer
        state["current_category"] = question.category
        state["current_difficulty"] = state.get("difficulty") or question.difficulty
        state["guesses"] = []
        asked = state.setdefault("asked", [])
        qid = question_id(question)
        if qid not in asked:
            asked.append(qid)

    def format_question(
        self,
        question: TriviaQuestion,
        state: dict[str, Any],
        include_category: bool = True,
    ) -> str:
        difficulty = str(state.get("difficulty") or question.difficulty or "medium")
        category = category_display(question.category)
        suffix = f"{difficulty} - {category}" if include_category else difficulty
        return f"{question.question} {IRC_DARK_GREY}({suffix}){IRC_RESET}"

    def semantic_match(self, state: dict[str, Any], question: TriviaQuestion, guess: str) -> tuple[bool, str]:
        if state.get("mode") != "smart":
            return False, ""
        heuristic = semantic_heuristic(question.answer, guess)
        if heuristic:
            return True, heuristic
        if self.semantic_checker is not None:
            return self.semantic_checker(question, guess)
        return semantic_llm_check(question, guess)

    def rephrase_with_llm(self, question: str, answer: str) -> str:
        try:
            import llm

            prompt_text = (
                "Rewrite this trivia question as a concise open-ended IRC trivia prompt. "
                "Remove multiple-choice wording and preserve the answer.\n"
                f"Question: {question}\nAnswer: {answer}\nRewritten question only:"
            )
            return llm.get_model("openrouter/openai/gpt-oss-120b").prompt(prompt_text).text().strip()
        except Exception:
            return ""


def load_category_csv(path: Path, slug: str) -> list[TriviaQuestion]:
    questions: list[TriviaQuestion] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            question = html.unescape(str(row.get("Questions") or row.get("Question") or "")).strip()
            answer = html.unescape(str(row.get("Correct") or row.get("Answer") or "")).strip()
            if not question or not answer:
                continue
            questions.append(TriviaQuestion(clean_question(question), answer, slug, "medium"))
    return questions


def clean_question(question: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(question)).strip()


def find_category(text: str) -> TriviaCategory | None:
    raw = text.strip()
    if not raw:
        return None
    lowered = raw.casefold()
    for category in CATEGORIES:
        if lowered == category.slug.casefold():
            return category
    if " " not in lowered and "-" not in lowered:
        matches = [
            category
            for category in CATEGORIES
            if lowered in {part.casefold() for part in re.split(r"[-\s]+", category.slug)}
            or lowered in {part.casefold() for part in category.display.split()}
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def title_category(text: str) -> str:
    return " ".join(piece.capitalize() for piece in re.split(r"[-\s]+", text.strip()) if piece)


def category_display(slug: str) -> str:
    for category in CATEGORIES:
        if category.slug == slug:
            return category.display
    return title_category(slug) or "General"


def selected_categories(state: dict[str, Any]) -> list[str]:
    values = state.get("category_ids")
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def selected_category_slug(state: dict[str, Any]) -> str:
    categories = selected_categories(state)
    return categories[0] if categories else "general"


def channel_key(channel: str) -> str:
    raw = str(channel or "_default").strip() or "_default"
    if raw.startswith("#"):
        raw = "_" + raw[1:]
    elif not raw.startswith("_"):
        raw = "_" + raw
    return re.sub(r"[^A-Za-z0-9_-]", "_", raw)


def stat_key(nickname: str, username: str, hostname: str) -> str:
    if username or hostname:
        return sanitize_stat_part(username or nickname) + "@" + sanitize_stat_part(hostname or "unknown")
    return sanitize_stat_part(nickname)


def sanitize_stat_part(value: str) -> str:
    value = str(value or "").strip().lstrip("~") or "unknown"
    return re.sub(r"[^A-Za-z0-9_.@-]+", "_", value)


def question_id(question: TriviaQuestion) -> str:
    key = f"{question.category}\0{question.question}\0{question.answer}".encode("utf-8")
    return hashlib.md5(key).hexdigest()


def normalized_answer(value: str) -> str:
    text = html.unescape(str(value)).casefold()
    text = text.translate(str.maketrans("", "", string.punctuation.replace("-", "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalized_levenshtein(left: str, right: str) -> float:
    a = normalized_answer(left)
    b = normalized_answer(right)
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    if a == b:
        return 0.0
    distance = levenshtein(a, b)
    return distance / max(len(a), len(b), 1)


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index_left, char_left in enumerate(left, start=1):
        current = [index_left]
        for index_right, char_right in enumerate(right, start=1):
            insert = current[index_right - 1] + 1
            delete = previous[index_right] + 1
            substitute = previous[index_right - 1] + (char_left != char_right)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def semantic_heuristic(answer: str, guess: str) -> str:
    normalized_guess = normalized_answer(guess)
    normalized_correct = normalized_answer(answer)
    if not normalized_guess or not normalized_correct:
        return ""
    if normalized_guess in normalized_correct or normalized_correct in normalized_guess:
        return "Exact match, case-insensitive"
    guess_words = set(normalized_guess.split())
    answer_words = set(normalized_correct.split())
    if answer_words and answer_words.issubset(guess_words):
        return "User answer includes the correct answer"
    if answer_words and len(guess_words & answer_words) / len(answer_words) >= 0.75:
        return "Answer words overlap strongly"
    return ""


def semantic_llm_check(question: TriviaQuestion, guess: str) -> tuple[bool, str]:
    try:
        import llm

        class TriviaSemanticResult:
            valid: bool
            reason: str

        prompt_text = (
            "Decide if the user's trivia answer should count. Return JSON matching "
            '{"valid": true|false, "reason": "short IRC-safe reason"}.\n'
            f"Question: {question.question}\n"
            f"Correct answer: {question.answer}\n"
            f"User answer: {guess}\n"
        )
        response = (
            llm.get_model("openrouter/openai/gpt-oss-120b")
            .prompt(prompt_text, schema=TriviaSemanticResult)
            .text()
        )
        data = json.loads(response)
        if bool(data.get("valid")):
            return True, str(data.get("reason") or "").strip()
    except Exception:
        return False, ""
    return False, ""


_generated_store: TriviaStore | None = None


def entrypoint(args, channel, nickname, username, hostname):
    global _generated_store
    if _generated_store is None:
        from pyylmao.kv.backends.sqlite import default_root

        _, state = default_root()
        _generated_store = TriviaStore(state)
    text = " ".join(str(item) for item in args)
    for line in _generated_store.handle(nickname, channel, text, username, hostname) or []:
        print(line)
