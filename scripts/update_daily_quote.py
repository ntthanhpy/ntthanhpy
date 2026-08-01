from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]
README_FILE = ROOT_DIR / "README.md"
QUOTES_FILE = ROOT_DIR / "data" / "quotes.json"

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

START_MARKER = "<!-- DAILY_QUOTE:START -->"
END_MARKER = "<!-- DAILY_QUOTE:END -->"


def load_quotes() -> list[dict[str, str]]:
    """Load and validate quotes from the JSON file."""
    if not QUOTES_FILE.exists():
        raise FileNotFoundError(f"Quote file not found: {QUOTES_FILE}")

    with QUOTES_FILE.open("r", encoding="utf-8") as file:
        quotes = json.load(file)

    if not isinstance(quotes, list) or not quotes:
        raise ValueError("quotes.json must contain a non-empty JSON array.")

    required_fields = {"id", "type", "text", "author"}

    for index, quote in enumerate(quotes):
        if not isinstance(quote, dict):
            raise ValueError(f"Quote at index {index} must be an object.")

        missing_fields = required_fields - quote.keys()

        if missing_fields:
            raise ValueError(
                f"Quote at index {index} is missing: "
                f"{', '.join(sorted(missing_fields))}"
            )

    return quotes


def create_daily_order(quotes_count: int, year: int) -> list[int]:
    """
    Create a deterministic shuffled order for a year.

    The result looks random but remains stable when the workflow
    is rerun multiple times on the same day.
    """
    seed_text = f"ntthanhpy-daily-quotes-{year}"
    seed = int(
        hashlib.sha256(seed_text.encode("utf-8")).hexdigest(),
        16,
    )

    order = list(range(quotes_count))
    random.Random(seed).shuffle(order)

    return order

def select_quote_index(target_time: datetime, quotes_count: int, ) -> int:
    """
    Chọn một câu cho mỗi khung thời gian 30 phút.

    Trong cùng một khung 30 phút, chạy lại workflow
    vẫn cho ra cùng một câu.
    """
    if quotes_count == 1:
        return 0

    slot_start = target_time.replace(
        minute=(target_time.minute // 30) * 30,
        second=0,
        microsecond=0,
    )

    previous_slot = slot_start - timedelta(minutes=30)

    def index_for_slot(slot_time: datetime) -> int:
        slot_key = slot_time.strftime("%Y-%m-%d-%H-%M")
        seed_text = f"ntthanhpy-quote-{slot_key}"

        digest = hashlib.sha256(
            seed_text.encode("utf-8")
        ).hexdigest()

        return int(digest, 16) % quotes_count

    selected_index = index_for_slot(slot_start)
    previous_index = index_for_slot(previous_slot)

    # Không để hai khung 30 phút liên tiếp trùng câu.
    if selected_index == previous_index:
        selected_index = (selected_index + 1) % quotes_count

    return selected_index

def select_quote_index_day(target_date: date, quotes_count: int) -> int:
    """Select a quote based on the local calendar date."""
    if quotes_count == 1:
        return 0

    order = create_daily_order(quotes_count, target_date.year)
    day_position = (target_date.timetuple().tm_yday - 1) % quotes_count
    selected_index = order[day_position]

    # Avoid repeating the same quote at a year boundary.
    previous_date = target_date - timedelta(days=1)
    previous_order = create_daily_order(quotes_count, previous_date.year)
    previous_position = (
        previous_date.timetuple().tm_yday - 1
    ) % quotes_count
    previous_index = previous_order[previous_position]

    if selected_index == previous_index:
        selected_index = order[(day_position + 1) % quotes_count]

    return selected_index


def clean_text(value: object) -> str:
    """Normalize whitespace to keep generated Markdown clean."""
    return " ".join(str(value).split())


def build_markdown(quote: dict[str, str], today: date) -> str:
    quote_type = clean_text(quote["type"])
    text = clean_text(quote["text"])
    author = clean_text(quote["author"])
    quote_id = clean_text(quote["id"])
    url = clean_text(quote.get("url", ""))

    if url:
        attribution = f"— **[{author}]({url})**"
    else:
        attribution = f"— **{author}**"

    formatted_date = today.strftime("%d/%m/%Y")

    return "\n".join(
        [
            START_MARKER,
            f"### {quote_type}",
            "",
            f'> “{text}”',
            ">",
            f"> {attribution}",
            "",
            f"<sub>🗓️ Cập nhật ngày {formatted_date}</sub>",
            f"<!-- quote-id: {quote_id} -->",
            END_MARKER,
        ]
    )


def update_readme(markdown: str) -> None:
    if not README_FILE.exists():
        raise FileNotFoundError(f"README not found: {README_FILE}")

    readme_content = README_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )

    if not pattern.search(readme_content):
        raise ValueError(
            "Daily quote markers were not found in README.md."
        )

    updated_content = pattern.sub(
        lambda _: markdown,
        readme_content,
        count=1,
    )

    README_FILE.write_text(updated_content, encoding="utf-8")


# def main() -> None:
#     today = datetime.now(TIMEZONE).date()
#     quotes = load_quotes()

#     selected_index = select_quote_index_day(today, len(quotes))
#     selected_quote = quotes[selected_index]

#     markdown = build_markdown(selected_quote, today)
#     update_readme(markdown)

#     print(
#         f"Updated README with quote: "
#         f"{selected_quote['id']} for {today.isoformat()}"
#     )
def main() -> None:
    current_time = datetime.now(TIMEZONE)
    quotes = load_quotes()

    selected_index = select_quote_index(current_time, len(quotes), )
    selected_quote = quotes[selected_index]

    markdown = build_markdown(selected_quote, current_time,    )

    update_readme(markdown)

    print(
        f"Updated README with quote "
        f"{selected_quote['id']} at "
        f"{current_time.isoformat()}"
    )


if __name__ == "__main__":
    main()
