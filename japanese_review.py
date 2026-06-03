import argparse
import csv
import json
import random
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TAG = ""
TEXT_ENCODING = "utf-8"
CSV_ENCODING = "utf-8-sig"
INPUT_FILE = BASE_DIR / "input" / "sentences.txt"
INPUT_ARCHIVE_DIR = BASE_DIR / "input" / "archive"
DATA_FILE = BASE_DIR / "data.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "japanese_review.md"
ACTIVITY_LOG_FILE = OUTPUT_DIR / "activity_log.json"
DAILY_OUTPUT_DIR = OUTPUT_DIR / "daily"
WRONG_BOOK_FILE = OUTPUT_DIR / "wrong_book.md"
MASTERED_FILE = OUTPUT_DIR / "mastered.md"
EXPORT_DIR = OUTPUT_DIR / "export"
JAPANESE_REVIEW_CSV = EXPORT_DIR / "japanese_review.csv"
ANKI_IMPORT_CSV = EXPORT_DIR / "anki_import.csv"
WRONG_BOOK_CSV = EXPORT_DIR / "wrong_book.csv"
MASTERED_CSV = EXPORT_DIR / "mastered.csv"
BACKUP_DIR = BASE_DIR / "backup"
GRADUATION_THRESHOLD = 3
SEPARATOR = "────────────────────────────"
USE_COLOR = True
DEBUG_INPUT = False
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RED = "\033[31m"
GRAY = "\033[90m"


def color_text(text, color):
    if not USE_COLOR:
        return text

    return f"{color}{text}{RESET}"


def set_color_enabled(enabled):
    global USE_COLOR
    USE_COLOR = enabled


def set_debug_input_enabled(enabled):
    global DEBUG_INPUT
    DEBUG_INPUT = enabled


def configure_console_encoding():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding=TEXT_ENCODING)
            except (OSError, ValueError):
                pass


def display_path(path):
    if not isinstance(path, Path):
        return path

    try:
        return path.resolve().relative_to(BASE_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def print_header(title, mode=None):
    if mode:
        print(color_text(f"{title}｜{mode}", BOLD))
    else:
        print(color_text(title, BOLD))
    print(SEPARATOR)


def print_section(title):
    print("")
    print(title)


def print_card_title(title, icon="📌"):
    print("")
    print(color_text(f"{icon} {title}", BOLD))
    print(SEPARATOR)


def print_blank_line():
    print("")


def print_success(message):
    print(color_text(f"✅ {message}", GREEN))


def print_warning(message):
    print(color_text(f"⚠️ 提示：{message}", YELLOW))


def print_error(message):
    print(color_text(f"❌ 错误：{message}", RED))


def print_summary(items):
    for label, value in items:
        value = display_path(value)
        print(f"{label}：{value}")


def print_field(label, value):
    value = display_path(value)
    print(f"{label}：{value}")


def print_optional_field(label, value):
    value = normalize_optional_text(value)

    if value:
        print_field(label, value)


def normalize_optional_text(value):
    return value.strip() if value else ""


def add_optional_markdown_lines(lines, entry):
    optional_fields = [
        ("标签", entry.get("tag", "")),
        ("语法点", entry.get("grammar", "")),
        ("重点单词", entry.get("words", "")),
        ("备注", entry.get("note", "")),
    ]

    for label, value in optional_fields:
        value = normalize_optional_text(value)

        if value:
            lines.append(f"- {label}：{value}")


def get_entry_tag(entry):
    return normalize_optional_text(entry.get("tag", ""))


def get_entry_grammar(entry):
    return normalize_optional_text(entry.get("grammar", ""))


def get_entry_words(entry):
    return normalize_optional_text(entry.get("words", ""))


def get_entry_note(entry):
    return normalize_optional_text(entry.get("note", ""))


def normalize_for_similarity(text):
    normalized_text = normalize_optional_text(text)
    ignored_characters = str.maketrans("", "", " 　。、.,!！?？")
    return normalized_text.translate(ignored_characters)


def calculate_similarity_score(answer, reference):
    normalized_answer = normalize_for_similarity(answer)
    normalized_reference = normalize_for_similarity(reference)

    if not normalized_answer and not normalized_reference:
        return 100

    if not normalized_answer or not normalized_reference:
        return 0

    return round(
        SequenceMatcher(None, normalized_answer, normalized_reference).ratio() * 100
    )


def get_similarity_feedback(score):
    if score >= 95:
        return "✅ 很好，基本完全正确", GREEN

    if score >= 80:
        return "🟡 接近正确，有少量差异", YELLOW

    if score >= 60:
        return "⚠️ 部分正确，需要复习", YELLOW

    return "❌ 差异较大，建议加入错题", RED


def build_review_data_key(entry):
    return f"{entry['japanese']}|{entry['chinese']}"


def normalize_similarity_score(value):
    if value is None:
        return None

    try:
        score = int(value)
    except (TypeError, ValueError):
        return None

    if score < 0 or score > 100:
        return None

    return score


def normalize_similarity_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0

    return max(0, count)


def get_similarity_record(review_data, entry):
    record = review_data.get(build_review_data_key(entry), {})

    if not isinstance(record, dict):
        record = {}

    return {
        "last_similarity_score": normalize_similarity_score(
            record.get("last_similarity_score")
        ),
        "best_similarity_score": normalize_similarity_score(
            record.get("best_similarity_score")
        ),
        "similarity_count": normalize_similarity_count(
            record.get("similarity_count", 0)
        ),
    }


def update_similarity_record(review_data, entry, score):
    key = build_review_data_key(entry)
    record = review_data.get(key, {})

    if not isinstance(record, dict):
        record = {}

    previous_record = get_similarity_record(review_data, entry)
    previous_best = previous_record["best_similarity_score"]
    best_score = score if previous_best is None else max(previous_best, score)

    record.update(
        {
            "japanese": entry["japanese"],
            "chinese": entry["chinese"],
            "tag": get_entry_tag(entry),
            "grammar": get_entry_grammar(entry),
            "words": get_entry_words(entry),
            "note": get_entry_note(entry),
            "last_similarity_score": score,
            "best_similarity_score": best_score,
            "similarity_count": previous_record["similarity_count"] + 1,
        }
    )
    record["review_count"] = normalize_similarity_count(record.get("review_count", 0))
    review_data[key] = record

    return record


def normalize_review_data_records(data):
    for key, record in list(data.items()):
        if not isinstance(record, dict):
            data[key] = {}
            record = data[key]

        record["last_similarity_score"] = normalize_similarity_score(
            record.get("last_similarity_score")
        )
        record["best_similarity_score"] = normalize_similarity_score(
            record.get("best_similarity_score")
        )
        record["similarity_count"] = normalize_similarity_count(
            record.get("similarity_count", 0)
        )

    return data


def format_similarity_change(current_score, previous_score):
    if previous_score is None:
        return "首次记录", None

    change = current_score - previous_score

    if change > 0:
        return f"+{change}%｜有进步", GREEN

    if change < 0:
        return f"{change}%｜有所下降", RED

    return "0%｜保持不变", YELLOW


def build_similarity_result(answer, entry, review_data):
    score = calculate_similarity_score(answer, entry["japanese"])
    feedback, feedback_color = get_similarity_feedback(score)
    record = get_similarity_record(review_data, entry)
    previous_score = record["last_similarity_score"]
    previous_best = record["best_similarity_score"]
    best_score = score if previous_best is None else max(previous_best, score)
    change_text, change_color = format_similarity_change(score, previous_score)

    return {
        "score": score,
        "feedback": feedback,
        "feedback_color": feedback_color,
        "previous_score": previous_score,
        "best_score": best_score,
        "change_text": change_text,
        "change_color": change_color,
    }


def print_debug_input(answer):
    if not DEBUG_INPUT:
        return

    normalized_answer = normalize_for_similarity(answer)
    print_card_title("输入调试", icon="🧪")
    print(f"原始输入 repr：{answer!r}")
    print(f"原始输入长度：{len(answer)}")
    print(f"normalize 后 repr：{normalized_answer!r}")
    print(f"normalize 后长度：{len(normalized_answer)}")


def read_sentences(input_file):
    sentences = []
    total_lines = 0
    error_count = 0
    format_errors = []

    if not input_file.exists():
        format_errors.append(f"找不到输入文件：{display_path(input_file)}")
        return sentences, total_lines, error_count, format_errors

    with input_file.open("r", encoding=TEXT_ENCODING) as file:
        for line_number, raw_line in enumerate(file, start=1):
            total_lines += 1
            line = raw_line.strip()

            if not line:
                continue

            parts = [part.strip() for part in line.split("|")]

            if len(parts) < 2:
                format_errors.append(f"第 {line_number} 行：缺少 | 分隔符")
                error_count += 1
                continue

            if len(parts) > 6:
                format_errors.append(f"第 {line_number} 行：字段过多，最多支持 6 个字段")
                error_count += 1
                continue

            japanese = parts[0]
            chinese = parts[1]
            tag = parts[2] if len(parts) >= 3 else ""
            grammar = parts[3] if len(parts) >= 4 else ""
            words = parts[4] if len(parts) >= 5 else ""
            note = parts[5] if len(parts) >= 6 else ""

            if not japanese or not chinese:
                format_errors.append(f"第 {line_number} 行：日语或中文内容为空")
                error_count += 1
                continue

            sentences.append(
                {
                    "japanese": japanese,
                    "chinese": chinese,
                    "tag": normalize_optional_text(tag),
                    "grammar": normalize_optional_text(grammar),
                    "words": normalize_optional_text(words),
                    "note": normalize_optional_text(note),
                }
            )

    return sentences, total_lines, error_count, format_errors


def load_existing_japanese_sentences(output_file):
    existing_sentences = set()

    if not output_file.exists():
        return existing_sentences

    with output_file.open("r", encoding=TEXT_ENCODING) as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("- 日语："):
                existing_sentences.add(line.removeprefix("- 日语：").strip())

    return existing_sentences


def load_quiz_sentences(output_file):
    sentences = []
    current_sentence = None

    if not output_file.exists():
        return sentences

    with output_file.open("r", encoding=TEXT_ENCODING) as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("- 日语："):
                if current_sentence:
                    sentences.append(current_sentence)

                current_sentence = {
                    "japanese": line.removeprefix("- 日语：").strip(),
                    "chinese": "",
                    "tag": DEFAULT_TAG,
                    "grammar": "",
                    "words": "",
                    "note": "",
                }
                continue

            if not current_sentence:
                continue

            if line.startswith("- 中文："):
                current_sentence["chinese"] = line.removeprefix("- 中文：").strip()
            elif line.startswith("- 标签："):
                tag = line.removeprefix("- 标签：").strip()
                current_sentence["tag"] = tag or DEFAULT_TAG
            elif line.startswith("- 语法点："):
                current_sentence["grammar"] = line.removeprefix("- 语法点：").strip()
            elif line.startswith("- 重点单词："):
                current_sentence["words"] = line.removeprefix("- 重点单词：").strip()
            elif line.startswith("- 备注："):
                current_sentence["note"] = line.removeprefix("- 备注：").strip()

    if current_sentence:
        sentences.append(current_sentence)

    return sentences


def load_review_entries(output_file):
    entries = []
    current_entry = None
    current_section_date = ""

    if not output_file.exists():
        return entries

    with output_file.open("r", encoding=TEXT_ENCODING) as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("## "):
                current_section_date = line.removeprefix("## ").strip()
                continue

            if line.startswith("- 日语："):
                if current_entry:
                    entries.append(current_entry)

                current_entry = {
                    "japanese": line.removeprefix("- 日语：").strip(),
                    "chinese": "",
                    "tag": DEFAULT_TAG,
                    "grammar": "",
                    "words": "",
                    "note": "",
                    "status": "待复习",
                    "review_count": 1,
                    "date": current_section_date,
                }
                continue

            if not current_entry:
                continue

            if line.startswith("- 中文："):
                current_entry["chinese"] = line.removeprefix("- 中文：").strip()
            elif line.startswith("- 标签："):
                tag = line.removeprefix("- 标签：").strip()
                current_entry["tag"] = tag or DEFAULT_TAG
            elif line.startswith("- 语法点："):
                current_entry["grammar"] = line.removeprefix("- 语法点：").strip()
            elif line.startswith("- 重点单词："):
                current_entry["words"] = line.removeprefix("- 重点单词：").strip()
            elif line.startswith("- 备注："):
                current_entry["note"] = line.removeprefix("- 备注：").strip()
            elif line.startswith("- 状态："):
                status = line.removeprefix("- 状态：").strip()
                current_entry["status"] = status or "待复习"
            elif line.startswith("- 复习次数："):
                value = line.removeprefix("- 复习次数：").strip()

                try:
                    current_entry["review_count"] = int(value)
                except ValueError:
                    current_entry["review_count"] = 1

    if current_entry:
        entries.append(current_entry)

    return entries


def load_wrong_book_entries():
    entries = []
    current_entry = None
    current_section_date = ""

    if not WRONG_BOOK_FILE.exists():
        return entries

    with WRONG_BOOK_FILE.open("r", encoding=TEXT_ENCODING) as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("## "):
                current_section_date = line.removeprefix("## ").strip()
                continue

            if line.startswith("- 日语："):
                if current_entry:
                    entries.append(current_entry)

                current_entry = {
                    "japanese": line.removeprefix("- 日语：").strip(),
                    "chinese": "",
                    "tag": DEFAULT_TAG,
                    "grammar": "",
                    "words": "",
                    "note": "",
                    "added_date": current_section_date,
                    "mastery_count": 0,
                    "status": "待复习",
                }
                continue

            if not current_entry:
                continue

            if line.startswith("- 中文："):
                current_entry["chinese"] = line.removeprefix("- 中文：").strip()
            elif line.startswith("- 标签："):
                tag = line.removeprefix("- 标签：").strip()
                current_entry["tag"] = tag or DEFAULT_TAG
            elif line.startswith("- 语法点："):
                current_entry["grammar"] = line.removeprefix("- 语法点：").strip()
            elif line.startswith("- 重点单词："):
                current_entry["words"] = line.removeprefix("- 重点单词：").strip()
            elif line.startswith("- 备注："):
                current_entry["note"] = line.removeprefix("- 备注：").strip()
            elif line.startswith("- 加入日期："):
                current_entry["added_date"] = line.removeprefix("- 加入日期：").strip()
            elif line.startswith("- 掌握次数："):
                value = line.removeprefix("- 掌握次数：").strip()

                try:
                    current_entry["mastery_count"] = int(value)
                except ValueError:
                    current_entry["mastery_count"] = 0
            elif line.startswith("- 状态："):
                current_entry["status"] = line.removeprefix("- 状态：").strip()

    if current_entry:
        entries.append(current_entry)

    return entries


def load_mastered_entries():
    entries = []
    current_entry = None
    current_section_date = ""

    if not MASTERED_FILE.exists():
        return entries

    with MASTERED_FILE.open("r", encoding=TEXT_ENCODING) as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("## "):
                current_section_date = line.removeprefix("## ").strip()
                continue

            if line.startswith("- 日语："):
                if current_entry:
                    entries.append(current_entry)

                current_entry = {
                    "japanese": line.removeprefix("- 日语：").strip(),
                    "chinese": "",
                    "tag": DEFAULT_TAG,
                    "grammar": "",
                    "words": "",
                    "note": "",
                    "wrong_date": "",
                    "mastered_source": "",
                    "mastered_date": current_section_date,
                    "status": "已掌握",
                }
                continue

            if not current_entry:
                continue

            if line.startswith("- 中文："):
                current_entry["chinese"] = line.removeprefix("- 中文：").strip()
            elif line.startswith("- 标签："):
                tag = line.removeprefix("- 标签：").strip()
                current_entry["tag"] = tag or DEFAULT_TAG
            elif line.startswith("- 语法点："):
                current_entry["grammar"] = line.removeprefix("- 语法点：").strip()
            elif line.startswith("- 重点单词："):
                current_entry["words"] = line.removeprefix("- 重点单词：").strip()
            elif line.startswith("- 备注："):
                current_entry["note"] = line.removeprefix("- 备注：").strip()
            elif line.startswith("- 首次加入错题本日期："):
                current_entry["wrong_date"] = line.removeprefix("- 首次加入错题本日期：").strip()
            elif line.startswith("- 掌握来源："):
                current_entry["mastered_source"] = line.removeprefix("- 掌握来源：").strip()
            elif line.startswith("- 掌握日期："):
                current_entry["mastered_date"] = line.removeprefix("- 掌握日期：").strip()
            elif line.startswith("- 状态："):
                status = line.removeprefix("- 状态：").strip()
                current_entry["status"] = status or "已掌握"

    if current_entry:
        entries.append(current_entry)

    return entries


def save_wrong_book_entries(entries):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with WRONG_BOOK_FILE.open("w", encoding=TEXT_ENCODING) as file:
        file.write("# 错题本\n")

        for entry in entries:
            file.write("\n")
            file.write(f"## {entry['added_date']}\n\n")
            file.write(f"- 日语：{entry['japanese']}\n")
            file.write(f"- 中文：{entry['chinese']}\n")
            optional_lines = []
            add_optional_markdown_lines(optional_lines, entry)

            for line in optional_lines:
                file.write(f"{line}\n")

            file.write(f"- 加入日期：{entry['added_date']}\n")
            file.write(f"- 掌握次数：{entry['mastery_count']}\n")
            file.write("- 状态：待复习\n")


def append_mastered(entry, source="错题毕业"):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_japanese_sentences = load_existing_japanese_sentences(MASTERED_FILE)
    japanese = entry["japanese"]

    if japanese in existing_japanese_sentences:
        print_warning(f"已在已掌握本中，跳过重复添加：{japanese}")
        return "exists"

    mastered_date = date.today().isoformat()
    is_new_file = not MASTERED_FILE.exists()

    with MASTERED_FILE.open("a", encoding=TEXT_ENCODING) as file:
        if is_new_file:
            file.write("# 已掌握本\n\n")
        else:
            file.write("\n\n")

        file.write(f"## {mastered_date}\n\n")
        file.write(f"- 日语：{japanese}\n")
        file.write(f"- 中文：{entry['chinese']}\n")
        optional_lines = []
        add_optional_markdown_lines(optional_lines, entry)

        for line in optional_lines:
            file.write(f"{line}\n")

        wrong_date = entry.get("added_date") or entry.get("wrong_date", "")

        if wrong_date:
            file.write(f"- 首次加入错题本日期：{wrong_date}\n")

        file.write(f"- 掌握来源：{source}\n")
        file.write(f"- 掌握日期：{mastered_date}\n")
        file.write("- 状态：已掌握\n")

    print_success(f"已加入已掌握本：{japanese}")
    return "added"


def load_review_data(data_file):
    if not data_file.exists():
        return {}

    try:
        with data_file.open("r", encoding=TEXT_ENCODING) as file:
            data = json.load(file)
    except json.JSONDecodeError:
        print_warning(f"{display_path(data_file)} 格式错误，将重新创建复习次数数据。")
        return {}

    if not isinstance(data, dict):
        print_warning(f"{display_path(data_file)} 内容格式错误，将重新创建复习次数数据。")
        return {}

    return normalize_review_data_records(data)


def save_review_data(data_file, data):
    with data_file.open("w", encoding=TEXT_ENCODING) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def update_review_counts(sentences, data):
    reviewed_sentences = []

    for sentence in sentences:
        japanese = sentence["japanese"]
        chinese = sentence["chinese"]
        key = build_review_data_key(sentence)
        current_record = data.get(key, {})

        if not isinstance(current_record, dict):
            current_record = {}

        review_count = int(current_record.get("review_count", 0)) + 1
        record = {
            "japanese": japanese,
            "chinese": chinese,
            "tag": get_entry_tag(sentence),
            "grammar": get_entry_grammar(sentence),
            "words": get_entry_words(sentence),
            "note": get_entry_note(sentence),
            "review_count": review_count,
            "last_similarity_score": normalize_similarity_score(
                current_record.get("last_similarity_score")
            ),
            "best_similarity_score": normalize_similarity_score(
                current_record.get("best_similarity_score")
            ),
            "similarity_count": normalize_similarity_count(
                current_record.get("similarity_count", 0)
            ),
        }

        data[key] = record
        reviewed_sentences.append(record)

    return reviewed_sentences


def build_review_section(sentences, review_date):
    lines = [
        f"## {review_date}",
        "",
    ]

    for index, sentence in enumerate(sentences, start=1):
        lines.extend(
            [
                f"### {index}.",
                "",
                f"- 日语：{sentence['japanese']}",
                f"- 中文：{sentence['chinese']}",
            ]
        )
        add_optional_markdown_lines(lines, sentence)
        lines.extend(
            [
                "- 状态：待复习",
                f"- 复习次数：{sentence['review_count']}",
                "",
            ]
        )

    return "\n".join(lines)


def save_review_entries(entries):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding=TEXT_ENCODING) as file:
        file.write("# 日语复习本\n")

        grouped_entries = {}
        for entry in entries:
            entry_date = entry.get("date") or date.today().isoformat()
            grouped_entries.setdefault(entry_date, []).append(entry)

        for entry_date, dated_entries in grouped_entries.items():
            file.write("\n\n")
            file.write(build_review_section(dated_entries, entry_date))

        file.write("\n")


def remove_from_review_book(japanese_sentence, quiet=False):
    if not OUTPUT_FILE.exists():
        return False

    entries = load_review_entries(OUTPUT_FILE)
    kept_entries = [
        entry for entry in entries if entry.get("japanese") != japanese_sentence
    ]

    if len(kept_entries) == len(entries):
        if not quiet:
            print_warning(f"review 池中未找到：{japanese_sentence}")
        return False

    save_review_entries(kept_entries)
    return True


def append_review_file(output_file, sentences, review_date):
    if not sentences:
        return

    is_new_file = not output_file.exists()

    with output_file.open("a", encoding=TEXT_ENCODING) as file:
        if is_new_file:
            file.write("# 日语复习本\n\n")
        else:
            file.write("\n\n")

        file.write(build_review_section(sentences, review_date))
        file.write("\n")


def append_wrong_book(sentence):
    japanese = sentence["japanese"]
    entries = load_wrong_book_entries()
    existing_japanese_sentences = {entry["japanese"] for entry in entries}

    if japanese in existing_japanese_sentences:
        print_warning(f"已在错题本中，跳过重复添加：{japanese}")
        return False

    entries.append(
        {
            "japanese": japanese,
            "chinese": sentence["chinese"],
            "tag": get_entry_tag(sentence),
            "grammar": get_entry_grammar(sentence),
            "words": get_entry_words(sentence),
            "note": get_entry_note(sentence),
            "added_date": date.today().isoformat(),
            "mastery_count": 0,
            "status": "待复习",
        }
    )
    save_wrong_book_entries(entries)

    return True


def remove_from_wrong_book(japanese_sentence):
    entries = load_wrong_book_entries()
    kept_entries = [
        entry for entry in entries if entry.get("japanese") != japanese_sentence
    ]

    if len(kept_entries) == len(entries):
        return False

    save_wrong_book_entries(kept_entries)
    return True


def exists_in_review(japanese_sentence):
    return japanese_sentence in load_existing_japanese_sentences(OUTPUT_FILE)


def exists_in_wrong(japanese_sentence):
    return any(
        entry.get("japanese") == japanese_sentence
        for entry in load_wrong_book_entries()
    )


def exists_in_master(japanese_sentence):
    return japanese_sentence in load_existing_japanese_sentences(MASTERED_FILE)


def get_sentence_pool_state(japanese_sentence):
    return {
        "review": exists_in_review(japanese_sentence),
        "wrong": exists_in_wrong(japanese_sentence),
        "master": exists_in_master(japanese_sentence),
    }


def cleanup_after_mastered(japanese_sentence):
    removed_from_review = remove_from_review_book(japanese_sentence, quiet=True)
    removed_from_wrong = remove_from_wrong_book(japanese_sentence)

    if removed_from_review:
        print_success(f"已从 review 池移除：{japanese_sentence}")

    if removed_from_wrong:
        print_success(f"已从 wrong 池移除：{japanese_sentence}")

    return {
        "removed_from_review": removed_from_review,
        "removed_from_wrong": removed_from_wrong,
    }


def sync_sentence_state(entry, target_pool, source_pool=None):
    japanese = entry["japanese"]
    state = get_sentence_pool_state(japanese)
    result = {
        "target_pool": target_pool,
        "added": False,
        "already_exists": False,
        "removed_from_review": False,
        "removed_from_wrong": False,
        "skipped_reason": "",
    }

    if target_pool == "review":
        if state["master"]:
            result["skipped_reason"] = "master"
            print_warning(f"该句已在 master 池中，跳过导入：{japanese}")
            return result

        if state["wrong"]:
            result["skipped_reason"] = "wrong"
            print_warning(f"该句已在 wrong 池中，跳过导入：{japanese}")
            return result

        if state["review"]:
            result["already_exists"] = True
            result["skipped_reason"] = "review"
            print_warning(f"该句已在 review 池中，跳过重复：{japanese}")
            return result

        result["added"] = True
        return result

    if target_pool == "wrong":
        if state["master"]:
            result["skipped_reason"] = "master"
            print_warning(f"该句已在 master 池中，跳过写入 wrong：{japanese}")
            result["removed_from_review"] = remove_from_review_book(japanese, quiet=True)

            if result["removed_from_review"]:
                print_success(f"已从 review 池移除：{japanese}")

            return result

        if state["wrong"]:
            result["already_exists"] = True
            result["skipped_reason"] = "wrong"
            print_warning(f"该句已在 wrong 池中，跳过重复写入：{japanese}")
        else:
            result["added"] = append_wrong_book(entry)

            if result["added"]:
                print_success(f"已加入 wrong 池：{japanese}")

        result["removed_from_review"] = remove_from_review_book(japanese, quiet=True)

        if result["removed_from_review"]:
            print_success(f"已从 review 池移除：{japanese}")

        return result

    if target_pool == "master":
        mastered_status = append_mastered(entry, source="普通 Quiz" if source_pool == "review" else "错题毕业")
        result["added"] = mastered_status == "added"
        result["already_exists"] = mastered_status == "exists"
        cleanup_result = cleanup_after_mastered(japanese)
        result["removed_from_review"] = cleanup_result["removed_from_review"]
        result["removed_from_wrong"] = cleanup_result["removed_from_wrong"]
        return result

    raise ValueError(f"未知目标池：{target_pool}")


def filter_sentences_by_tag(sentences, tag):
    if not tag:
        return sentences

    return [sentence for sentence in sentences if get_entry_tag(sentence) == tag]


def build_tag_counts(sentences):
    tag_counts = {}

    for sentence in sentences:
        tag = get_entry_tag(sentence)

        if not tag:
            continue

        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return tag_counts


def print_no_tag_message(tag):
    print_warning(f"没有找到标签为「{tag}」的句子。")


def get_unique_input_archive_file():
    today = date.today().isoformat()
    archive_file = INPUT_ARCHIVE_DIR / f"{today}_sentences.txt"

    if not archive_file.exists():
        return archive_file

    index = 1

    while True:
        archive_file = INPUT_ARCHIVE_DIR / f"{today}_sentences_{index}.txt"

        if not archive_file.exists():
            return archive_file

        index += 1


def archive_and_clear_input():
    if not INPUT_FILE.exists():
        print_error(f"找不到输入文件：{display_path(INPUT_FILE)}")
        return

    original_content = INPUT_FILE.read_text(encoding=TEXT_ENCODING)

    if not original_content.strip():
        print_warning("input/sentences.txt 已经是空的，无需清理。")
        return

    INPUT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_file = get_unique_input_archive_file()
    archive_file.write_text(original_content, encoding=TEXT_ENCODING)
    INPUT_FILE.write_text("", encoding=TEXT_ENCODING)

    print_success("输入文件已清理")
    print_summary(
        [
            ("已归档到", archive_file),
            ("已清空", INPUT_FILE),
        ]
    )


def ask_clear_input():
    while True:
        answer = input("是否清空 input/sentences.txt？y/n：").strip().lower()

        if answer == "y":
            archive_and_clear_input()
            return

        if answer == "n":
            print_warning("已保留 input/sentences.txt")
            return

        print_warning("请输入 y 或 n。")


def print_add_usage():
    print("用法：")
    print('python3 japanese_review.py --add "日语句子" "中文意思" --tag "标签" --grammar "语法点" --words "重点单词" --note "备注"')


def print_add_result(sentence):
    print_success("添加成功")
    print_card_title("本次添加")
    print_field("日语", sentence["japanese"])
    print_field("中文", sentence["chinese"])
    print_optional_field("标签", get_entry_tag(sentence))
    print_optional_field("语法点", get_entry_grammar(sentence))
    print_optional_field("重点单词", get_entry_words(sentence))
    print_optional_field("备注", get_entry_note(sentence))


def run_add(add_values, tag="", grammar="", words="", note=""):
    print_header("📘 日语复习工具", "快速添加")

    if len(add_values) != 2:
        print_error("--add 需要同时提供日语句子和中文意思。")
        print_blank_line()
        print_add_usage()
        return

    japanese = add_values[0].strip()
    chinese = add_values[1].strip()

    if not japanese:
        print_error("日语句子不能为空。")
        return

    if not chinese:
        print_error("中文意思不能为空。")
        return

    sentence = {
        "japanese": japanese,
        "chinese": chinese,
        "tag": normalize_optional_text(tag),
        "grammar": normalize_optional_text(grammar),
        "words": normalize_optional_text(words),
        "note": normalize_optional_text(note),
    }
    sync_result = sync_sentence_state(sentence, target_pool="review")

    if not sync_result["added"]:
        return

    review_data = load_review_data(DATA_FILE)
    reviewed_sentences = update_review_counts([sentence], review_data)
    save_review_data(DATA_FILE, review_data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    review_date = date.today().isoformat()
    daily_output_file = DAILY_OUTPUT_DIR / f"{review_date}.md"

    append_review_file(OUTPUT_FILE, reviewed_sentences, review_date)
    append_review_file(daily_output_file, reviewed_sentences, review_date)
    print_add_result(reviewed_sentences[0])


def run_review(no_prompt=False):
    print_header("📘 日语复习工具", "普通追加模式")
    sentences, total_lines, error_count, format_errors = read_sentences(INPUT_FILE)
    new_sentences = []
    skipped_sentences = []
    pending_review_sentences = set()

    for sentence in sentences:
        if sentence["japanese"] in pending_review_sentences:
            print_warning(f"该句已在本次导入中出现，跳过重复：{sentence['japanese']}")
            skipped_sentences.append(
                {
                    "japanese": sentence["japanese"],
                    "reason": "本次重复",
                }
            )
            continue

        sync_result = sync_sentence_state(sentence, target_pool="review")

        if not sync_result["added"]:
            skipped_sentences.append(
                {
                    "japanese": sentence["japanese"],
                    "reason": sync_result["skipped_reason"] or "重复",
                }
            )
            continue

        pending_review_sentences.add(sentence["japanese"])
        new_sentences.append(sentence)

    review_data = load_review_data(DATA_FILE)
    reviewed_sentences = update_review_counts(new_sentences, review_data)
    save_review_data(DATA_FILE, review_data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    review_date = date.today().isoformat()
    daily_output_file = DAILY_OUTPUT_DIR / f"{review_date}.md"

    append_review_file(OUTPUT_FILE, reviewed_sentences, review_date)
    append_review_file(daily_output_file, reviewed_sentences, review_date)

    if reviewed_sentences:
        print_success(f"已追加到复习文件：{display_path(OUTPUT_FILE)}")
        print_success(f"已生成每日归档：{display_path(daily_output_file)}")
    else:
        print_warning("没有新增句子，未追加复习文件。")

    if skipped_sentences:
        print_card_title("跳过重复句子")
        for item in skipped_sentences[:5]:
            print(f"- {item['japanese']}（{item['reason']}）")
        if len(skipped_sentences) > 5:
            print(f"- 还有 {len(skipped_sentences) - 5} 条未显示。")

    if format_errors:
        print_card_title("格式错误")
        for error in format_errors[:5]:
            print(f"- {error}")
        if len(format_errors) > 5:
            print(f"- 还有 {len(format_errors) - 5} 条未显示。")

    print_section("✅ 运行完成")
    print_blank_line()
    print_summary(
        [
            ("本次读取", f"{total_lines} 行"),
            ("成功新增", f"{len(reviewed_sentences)} 句"),
            ("跳过重复", f"{len(skipped_sentences)} 句"),
            ("格式错误", f"{error_count} 行"),
        ]
    )

    if not no_prompt:
        ask_clear_input()


def format_percentage(numerator, denominator):
    if denominator == 0:
        return None

    return f"{numerator / denominator * 100:.1f}%"


def display_percentage(value):
    return value if value is not None else "暂无"


def load_all_pool_entries():
    return {
        "review": load_quiz_sentences(OUTPUT_FILE),
        "wrong": load_wrong_book_entries(),
        "master": load_mastered_entries(),
    }


def get_pool_counts(pool_entries=None):
    if pool_entries is None:
        pool_entries = load_all_pool_entries()

    review_count = len(pool_entries["review"])
    wrong_count = len(pool_entries["wrong"])
    master_count = len(pool_entries["master"])

    return {
        "review_count": review_count,
        "wrong_count": wrong_count,
        "master_count": master_count,
        "total_managed_count": review_count + wrong_count + master_count,
    }


def build_stats_advices(pool_counts):
    review_count = pool_counts["review_count"]
    wrong_count = pool_counts["wrong_count"]
    master_count = pool_counts["master_count"]
    total_managed_count = pool_counts["total_managed_count"]

    if total_managed_count == 0:
        return ["当前还没有句子，请先用 --add 或 input/sentences.txt 添加句子。"]

    if wrong_count >= 10:
        return [
            "当前 wrong 错题池较多，建议优先做错题 Quiz。",
            "推荐命令：python3 japanese_review.py --quiz --wrong --count 5",
        ]

    if review_count > 0:
        advices = [
            f"review 待复习池还有 {review_count} 句，可以继续普通 Quiz。",
            "推荐命令：python3 japanese_review.py --quiz --count 5",
        ]

        if wrong_count > 0:
            advices.append(f"wrong 错题池还有 {wrong_count} 句，也建议安排错题 Quiz。")

        return advices

    if wrong_count > 0:
        return ["review 池已清空，当前重点是消化 wrong 错题池。"]

    if master_count > 0:
        return ["当前 review 和 wrong 都已清空，说明当前句子基本都已掌握。可以新增 1-3 句。"]

    return ["当前还没有句子，请先用 --add 或 input/sentences.txt 添加句子。"]


def count_filled_field(entries, field_name):
    return sum(1 for entry in entries if normalize_optional_text(entry.get(field_name, "")))


def get_today_new_count():
    today = date.today().isoformat()
    daily_output_file = DAILY_OUTPUT_DIR / f"{today}.md"
    return len(load_quiz_sentences(daily_output_file))


def default_activity_record():
    return {
        "quiz_count": 0,
        "similarity_scores": [],
        "wrong_added": 0,
        "master_added": 0,
        "retry_count": 0,
        "review_to_wrong": 0,
        "review_to_master": 0,
        "wrong_to_master": 0,
    }


def normalize_activity_record(record):
    normalized = default_activity_record()

    if not isinstance(record, dict):
        return normalized

    for key in normalized:
        if key == "similarity_scores":
            scores = record.get(key, [])

            if isinstance(scores, list):
                normalized[key] = [
                    int(score)
                    for score in scores
                    if isinstance(score, (int, float))
                ]
        else:
            value = record.get(key, 0)
            normalized[key] = value if isinstance(value, int) and value >= 0 else 0

    return normalized


def load_activity_log():
    if not ACTIVITY_LOG_FILE.exists():
        return {}

    try:
        with ACTIVITY_LOG_FILE.open("r", encoding=TEXT_ENCODING) as file:
            data = json.load(file)
    except json.JSONDecodeError:
        print_warning("activity_log.json 损坏，已跳过趋势日志读取。")
        return {}
    except OSError as error:
        print_warning(f"读取 activity_log.json 失败，已跳过。{error}")
        return {}

    if not isinstance(data, dict):
        print_warning("activity_log.json 格式异常，已跳过趋势日志读取。")
        return {}

    return {
        day: normalize_activity_record(record)
        for day, record in data.items()
        if isinstance(day, str)
    }


def save_activity_log(activity_log):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with ACTIVITY_LOG_FILE.open("w", encoding=TEXT_ENCODING) as file:
        json.dump(activity_log, file, ensure_ascii=False, indent=2)


def get_today_activity_record(activity_log):
    today = date.today().isoformat()
    activity_log[today] = normalize_activity_record(activity_log.get(today, {}))
    return activity_log[today]


def record_quiz_activity(
    score=None,
    wrong_added=0,
    master_added=0,
    retry_count=0,
    review_to_wrong=0,
    review_to_master=0,
    wrong_to_master=0,
    count_as_quiz=True,
):
    try:
        activity_log = load_activity_log()
        record = get_today_activity_record(activity_log)

        if count_as_quiz:
            record["quiz_count"] += 1

        if score is not None:
            record["similarity_scores"].append(int(score))

        record["wrong_added"] += wrong_added
        record["master_added"] += master_added
        record["retry_count"] += retry_count
        record["review_to_wrong"] += review_to_wrong
        record["review_to_master"] += review_to_master
        record["wrong_to_master"] += wrong_to_master
        save_activity_log(activity_log)
    except (OSError, TypeError, ValueError) as error:
        print_warning(f"记录学习趋势失败，已跳过。{error}")


def get_recent_dates(days):
    today = date.today()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days - 1, -1, -1)
    ]


def format_trend_date(day):
    return day[5:]


def build_bar(value, max_value, width=10, char="█"):
    if max_value <= 0 or value <= 0:
        return ""

    length = round(value / max_value * width)
    length = max(1, min(width, length))
    return char * length


def get_activity_average_score(record):
    scores = record.get("similarity_scores", [])

    if not scores:
        return None

    return round(sum(scores) / len(scores))


def get_trend_rows(activity_log, days):
    rows = []

    for day in get_recent_dates(days):
        record = normalize_activity_record(activity_log.get(day, {}))
        rows.append(
            {
                "date": day,
                "quiz_count": record["quiz_count"],
                "average_score": get_activity_average_score(record),
                "master_added": record["master_added"],
                "retry_count": record["retry_count"],
            }
        )

    return rows


def print_count_trend_section(title, rows, key, icon, char="█"):
    print_card_title(title, icon=icon)
    max_value = max((row[key] for row in rows), default=0)

    for row in rows:
        value = row[key]
        bar = build_bar(value, max_value, char=char)
        suffix = f"  {bar}" if bar else ""
        print(f"{format_trend_date(row['date'])}   {value:<3}{suffix}")


def print_score_trend_section(rows):
    print_card_title("平均正确度", icon="📊")

    for row in rows:
        score = row["average_score"]

        if score is None:
            print(f"{format_trend_date(row['date'])}   暂无")
            continue

        bar = build_bar(score, 100)
        print(f"{format_trend_date(row['date'])}   {score:>3}%  {bar}")


def build_trend_summary(rows, days):
    active_days = sum(1 for row in rows if row["quiz_count"] > 0)
    scored_rows = [row for row in rows if row["average_score"] is not None]
    master_added_total = sum(row["master_added"] for row in rows)
    lines = [f"最近 {days} 天有 {active_days} 天进行了复习。"]

    if len(scored_rows) >= 2:
        score_delta = scored_rows[-1]["average_score"] - scored_rows[0]["average_score"]

        if score_delta >= 5:
            lines.append("平均正确度整体略有提升。")
        elif score_delta <= -5:
            lines.append("平均正确度有所下降，建议放慢节奏复盘错题。")
        else:
            lines.append("平均正确度基本稳定。")
    elif len(scored_rows) == 1:
        lines.append("目前正确度样本还少，可以继续积累几天。")
    else:
        lines.append("还没有正确度记录，可以先做一次 Quiz。")

    lines.append(f"最近 {days} 天共有 {master_added_total} 句进入 master。")
    return lines


def run_trend(days=7):
    activity_log = load_activity_log()
    rows = get_trend_rows(activity_log, days)

    print_header(f"📈 最近 {days} 天学习趋势")
    print_count_trend_section("Quiz 次数", rows, "quiz_count", "📚")
    print_score_trend_section(rows)
    print_count_trend_section("进入 master", rows, "master_added", "🎓", char="▊")
    print_count_trend_section("重答次数", rows, "retry_count", "🔁", char="▊")

    print_card_title("简单判断", icon="📎")
    for line in build_trend_summary(rows, days):
        print(line)


def run_stats():
    pool_entries = load_all_pool_entries()
    pool_counts = get_pool_counts(pool_entries)
    all_entries = pool_entries["review"] + pool_entries["wrong"] + pool_entries["master"]
    today_new_count = get_today_new_count()
    grammar_count = count_filled_field(all_entries, "grammar")
    words_count = count_filled_field(all_entries, "words")
    note_count = count_filled_field(all_entries, "note")
    tag_counts = build_tag_counts(all_entries)
    wrong_rate = format_percentage(
        pool_counts["wrong_count"],
        pool_counts["total_managed_count"],
    )
    master_rate = format_percentage(
        pool_counts["master_count"],
        pool_counts["total_managed_count"],
    )
    graduation_rate = format_percentage(
        pool_counts["master_count"],
        pool_counts["wrong_count"] + pool_counts["master_count"],
    )

    print_header("📊 日语学习统计")

    print_card_title("三池状态", icon="📚")
    print_summary(
        [
            ("review 待复习池", f"{pool_counts['review_count']} 句"),
            ("wrong 错题池", f"{pool_counts['wrong_count']} 句"),
            ("master 已掌握池", f"{pool_counts['master_count']} 句"),
            ("全部已管理句子", f"{pool_counts['total_managed_count']} 句"),
            ("今日新增句子", f"{today_new_count} 句"),
        ]
    )

    if pool_counts["total_managed_count"] == 0:
        print_warning("还没有句子，请先用 --add 或 input/sentences.txt 添加句子。")

    print_card_title("字段完整度", icon="🧩")
    print_summary(
        [
            ("已填写语法点", f"{grammar_count} 句"),
            ("已填写重点单词", f"{words_count} 句"),
            ("已填写备注", f"{note_count} 句"),
        ]
    )

    print_card_title("学习质量", icon="📈")
    print_summary(
        [
            ("当前错题占比", display_percentage(wrong_rate)),
            ("已掌握占比", display_percentage(master_rate)),
            ("错题毕业率", display_percentage(graduation_rate)),
        ]
    )

    print_card_title("标签概览", icon="🏷️")
    if tag_counts:
        print_summary([("标签总数", len(tag_counts))])
        top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        top_tags_text = "，".join(f"{tag}：{count}" for tag, count in top_tags)
        print(f"句子最多的前 5 个标签：{top_tags_text}")
    else:
        print("暂无标签。")

    print_card_title("建议", icon="📎")
    for advice in build_stats_advices(pool_counts):
        print(advice)


def limited_lines(lines, limit=3):
    return lines[:limit]


def build_plan_advice(pool_counts, today_new_count):
    review_count = pool_counts["review_count"]
    wrong_count = pool_counts["wrong_count"]
    master_count = pool_counts["master_count"]
    total_managed_count = pool_counts["total_managed_count"]
    advice_lines = []
    command_lines = []

    if total_managed_count == 0:
        advice_lines = [
            "当前还没有句子，先添加 3 条 N5-N4 句子。",
            "添加后做一次普通 Quiz。",
        ]
        command_lines = [
            'python3 japanese_review.py --add "日语句子" "中文意思"',
            "python3 japanese_review.py --quiz --count 3",
        ]
        return {
            "advice_lines": advice_lines,
            "command_lines": command_lines,
        }

    if today_new_count > 5:
        advice_lines.append("今天已经新增较多，不建议继续大量新增，优先复习消化。")

        if wrong_count > 0:
            advice_lines.append("先做错题 Quiz 5 题。")
            command_lines.append("python3 japanese_review.py --quiz --wrong --count 5")

        if review_count > 0:
            advice_lines.append("再做普通 Quiz 5 题。")
            command_lines.append("python3 japanese_review.py --quiz --count 5")

        if not command_lines:
            command_lines.append("python3 japanese_review.py --today")

        return {
            "advice_lines": limited_lines(advice_lines),
            "command_lines": limited_lines(command_lines),
        }

    if wrong_count >= 10:
        wrong_quiz_count = 10 if wrong_count >= 20 else 5
        advice_lines = [
            f"当前错题较多，先做错题 Quiz {wrong_quiz_count} 题。",
            "今天不要继续大量新增句子。",
            "错题复习后再看是否做普通 Quiz。",
        ]
        command_lines = [
            f"python3 japanese_review.py --quiz --wrong --count {wrong_quiz_count}",
        ]
        return {
            "advice_lines": advice_lines,
            "command_lines": command_lines,
        }

    if wrong_count > 0:
        wrong_quiz_count = 3 if wrong_count < 5 else 5
        advice_lines = [
            f"先做错题 Quiz {wrong_quiz_count} 题。",
            "如果还有精力，再做普通 Quiz 5 题。",
        ]
        command_lines = [
            f"python3 japanese_review.py --quiz --wrong --count {wrong_quiz_count}",
        ]

        if review_count > 0:
            command_lines.append("python3 japanese_review.py --quiz --count 5")

        return {
            "advice_lines": advice_lines,
            "command_lines": limited_lines(command_lines),
        }

    if review_count >= 30:
        advice_lines = [
            "review 待复习池较多，先做普通 Quiz 10 题。",
            "通过 Quiz 把句子流转到 wrong 或 master。",
            "暂时不要继续大量新增句子。",
        ]
        command_lines = ["python3 japanese_review.py --quiz --count 10"]
        return {
            "advice_lines": advice_lines,
            "command_lines": command_lines,
        }

    if review_count >= 5:
        advice_lines = [
            "做普通 Quiz 5 题。",
            "如果答错较多，再做错题 Quiz。",
        ]
        command_lines = ["python3 japanese_review.py --quiz --count 5"]
        return {
            "advice_lines": advice_lines,
            "command_lines": command_lines,
        }

    if review_count < 5 and wrong_count < 3:
        advice_lines = [
            "当前待复习压力较小，可以新增 1-3 句。",
            "新增后做普通 Quiz 巩固。",
        ]
        command_lines = [
            'python3 japanese_review.py --add "日语句子" "中文意思"',
            "python3 japanese_review.py --quiz --count 3",
        ]
        return {
            "advice_lines": advice_lines,
            "command_lines": command_lines,
        }

    advice_lines = ["先查看今日学习面板，再选择普通 Quiz 或错题 Quiz。"]
    command_lines = ["python3 japanese_review.py --today"]
    return {
        "advice_lines": advice_lines,
        "command_lines": command_lines,
    }


def run_plan():
    pool_counts = get_pool_counts()
    today_new_count = get_today_new_count()
    plan = build_plan_advice(pool_counts, today_new_count)

    print_header("📌 今日复习建议")

    print_card_title("当前状态", icon="📚")
    print_summary(
        [
            ("review 待复习池", f"{pool_counts['review_count']} 句"),
            ("wrong 错题池", f"{pool_counts['wrong_count']} 句"),
            ("master 已掌握池", f"{pool_counts['master_count']} 句"),
            ("全部已管理句子", f"{pool_counts['total_managed_count']} 句"),
            ("今日新增句子", f"{today_new_count} 句"),
        ]
    )

    print_card_title("建议", icon="📎")
    for index, advice in enumerate(plan["advice_lines"], start=1):
        print(f"{index}. {advice}")

    print_card_title("推荐命令", icon="⌨️")
    for command in plan["command_lines"]:
        print(command)


def build_today_reminder(today_new_count, pool_counts):
    review_count = pool_counts["review_count"]
    wrong_count = pool_counts["wrong_count"]
    master_count = pool_counts["master_count"]
    total_managed_count = pool_counts["total_managed_count"]

    if total_managed_count == 0:
        return "当前还没有句子，请先用 --add 或 input/sentences.txt 添加句子。"

    if wrong_count >= 10:
        return "当前 wrong 错题池较多，建议优先做错题 Quiz。"

    if wrong_count > 0:
        return "当前 wrong 错题池还有句子，建议做一次错题 Quiz。"

    if review_count > 0:
        if today_new_count == 0:
            return "今天还没有新增句子，可以先添加 1-3 条，或做 5 题普通 Quiz。"

        return "今天已经有新增句子，可以做 5 题普通 Quiz 巩固。"

    if master_count > 0:
        return "当前 review 和 wrong 都已清空，可以新增 1-3 句继续积累。"

    return "当前还没有句子，请先用 --add 或 input/sentences.txt 添加句子。"


def get_today_backup_files(today):
    if not BACKUP_DIR.exists():
        return []

    return sorted(BACKUP_DIR.glob(f"{today}_*_backup.zip"))


def print_today_new_sentences(sentences):
    print_card_title("今日新增句子")

    if not sentences:
        print("今天还没有新增句子。")
        return

    for index, sentence in enumerate(sentences[:10], start=1):
        tag = get_entry_tag(sentence)
        suffix = f"｜{tag}" if tag else ""
        print(f"{index}. {sentence['japanese']}{suffix}")

    remaining_count = len(sentences) - 10

    if remaining_count > 0:
        print(f"还有 {remaining_count} 条未显示。")


def run_today():
    today = date.today().isoformat()
    daily_output_file = DAILY_OUTPUT_DIR / f"{today}.md"
    today_sentences = load_quiz_sentences(daily_output_file)
    pool_counts = get_pool_counts()
    today_backup_files = get_today_backup_files(today)
    latest_backup = today_backup_files[-1] if today_backup_files else "无"

    print_header("📅 今日学习面板")
    print_field("日期", today)
    print_blank_line()
    print_summary([("今日新增句子", f"{len(today_sentences)} 句")])

    print_card_title("三池状态", icon="📚")
    print_summary(
        [
            ("review 待复习池", f"{pool_counts['review_count']} 句"),
            ("wrong 错题池", f"{pool_counts['wrong_count']} 句"),
            ("master 已掌握池", f"{pool_counts['master_count']} 句"),
            ("全部已管理句子", f"{pool_counts['total_managed_count']} 句"),
        ]
    )

    print_today_new_sentences(today_sentences)

    print_card_title("今日备份", icon="📦")
    print_summary(
        [
            ("今日备份次数", f"{len(today_backup_files)} 次"),
            ("最近备份", latest_backup),
        ]
    )

    print_card_title("提醒", icon="📎")
    print_warning(
        build_today_reminder(
            len(today_sentences),
            pool_counts,
        )
    )


def run_tags():
    sentences = load_quiz_sentences(OUTPUT_FILE)
    tag_counts = build_tag_counts(sentences)

    if not tag_counts:
        print_warning("当前没有可统计的标签，请先添加句子并运行普通模式。")
        return

    print_header("🏷️ 标签统计")

    for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True):
        print(f"{tag}：{count}")


def write_csv(output_file, fieldnames, rows):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding=CSV_ENCODING, newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print_success("导出完成")
    print_blank_line()
    print_summary(
        [
            ("文件位置", output_file),
            ("导出数量", f"{len(rows)} 条"),
        ]
    )


def print_no_export_data():
    print_warning("没有找到可导出的数据，请先添加句子。")


def run_export_review_csv():
    entries = load_review_entries(OUTPUT_FILE)

    if not entries:
        print_no_export_data()
        return

    fieldnames = ["japanese", "chinese", "tag", "grammar", "words", "note", "status", "date"]
    rows = [
        {
            "japanese": entry["japanese"],
            "chinese": entry["chinese"],
            "tag": get_entry_tag(entry),
            "grammar": get_entry_grammar(entry),
            "words": get_entry_words(entry),
            "note": get_entry_note(entry),
            "status": entry.get("status", "待复习"),
            "date": entry.get("date", ""),
        }
        for entry in entries
    ]
    write_csv(JAPANESE_REVIEW_CSV, fieldnames, rows)


def build_anki_back(entry):
    lines = [entry["japanese"]]
    grammar = get_entry_grammar(entry)
    words = get_entry_words(entry)
    note = get_entry_note(entry)

    if grammar:
        lines.extend(["", f"语法点：{grammar}"])

    if words:
        lines.extend(["", f"重点单词：{words}"])

    if note:
        lines.extend(["", f"备注：{note}"])

    return "\n".join(lines)


def run_export_anki():
    entries = load_review_entries(OUTPUT_FILE)

    if not entries:
        print_no_export_data()
        return

    fieldnames = ["front", "back", "tag"]
    rows = [
        {
            "front": entry["chinese"],
            "back": build_anki_back(entry),
            "tag": get_entry_tag(entry),
        }
        for entry in entries
    ]
    write_csv(ANKI_IMPORT_CSV, fieldnames, rows)


def run_export_wrong_csv():
    entries = load_wrong_book_entries()

    if not entries:
        print_no_export_data()
        return

    fieldnames = [
        "japanese",
        "chinese",
        "tag",
        "grammar",
        "words",
        "note",
        "added_date",
        "review_count",
        "status",
    ]
    rows = [
        {
            "japanese": entry["japanese"],
            "chinese": entry["chinese"],
            "tag": get_entry_tag(entry),
            "grammar": get_entry_grammar(entry),
            "words": get_entry_words(entry),
            "note": get_entry_note(entry),
            "added_date": entry.get("added_date", ""),
            "review_count": entry.get("mastery_count", 0),
            "status": entry.get("status", "待复习"),
        }
        for entry in entries
    ]
    write_csv(WRONG_BOOK_CSV, fieldnames, rows)


def run_export_mastered_csv():
    entries = load_mastered_entries()

    if not entries:
        print_no_export_data()
        return

    fieldnames = [
        "japanese",
        "chinese",
        "tag",
        "grammar",
        "words",
        "note",
        "wrong_date",
        "mastered_date",
        "status",
    ]
    rows = [
        {
            "japanese": entry["japanese"],
            "chinese": entry["chinese"],
            "tag": get_entry_tag(entry),
            "grammar": get_entry_grammar(entry),
            "words": get_entry_words(entry),
            "note": get_entry_note(entry),
            "wrong_date": entry.get("wrong_date", ""),
            "mastered_date": entry.get("mastered_date", ""),
            "status": entry.get("status", "已掌握"),
        }
        for entry in entries
    ]
    write_csv(MASTERED_CSV, fieldnames, rows)


def run_export_csv(wrong=False, mastered=False):
    if wrong:
        run_export_wrong_csv()
    elif mastered:
        run_export_mastered_csv()
    else:
        run_export_review_csv()


def format_file_size(size):
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"

    return f"{max(1, round(size / 1024))} KB"


def should_skip_backup_path(path):
    if path.name == ".DS_Store":
        return True

    if path.suffix == ".pyc":
        return True

    skip_names = {".git", "__pycache__", ".venv", "venv", "backup"}
    return any(part in skip_names for part in path.relative_to(BASE_DIR).parts)


def collect_backup_files(path):
    if path.is_file():
        return [] if should_skip_backup_path(path) else [path]

    files = []

    for child in sorted(path.rglob("*")):
        if child.is_file() and not should_skip_backup_path(child):
            files.append(child)

    return files


def get_backup_targets():
    backup_targets = [
        DATA_FILE,
        BASE_DIR / "japanese_review.py",
        BASE_DIR / "README.md",
        INPUT_FILE,
        INPUT_ARCHIVE_DIR,
        ACTIVITY_LOG_FILE,
        OUTPUT_FILE,
        WRONG_BOOK_FILE,
        MASTERED_FILE,
        DAILY_OUTPUT_DIR,
        EXPORT_DIR,
    ]

    return backup_targets


def create_backup():
    backup_files = []
    missing_items = []

    for target in get_backup_targets():
        if not target.exists():
            missing_name = display_path(target)

            if target.suffix == "":
                missing_name = f"{missing_name}/"

            missing_items.append(missing_name)
            continue

        backup_files.extend(collect_backup_files(target))

    unique_files = sorted(set(backup_files), key=lambda file_path: file_path.as_posix())

    if not unique_files:
        return None, [], missing_items

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{timestamp}_backup.zip"

    with ZipFile(backup_file, "w", ZIP_DEFLATED) as zip_file:
        for file_path in unique_files:
            zip_file.write(file_path, file_path.relative_to(BASE_DIR).as_posix())

    return backup_file, unique_files, missing_items


def run_backup():
    print_header("📦 日语复习工具", "一键备份")
    backup_file, unique_files, missing_items = create_backup()

    if not backup_file:
        print_warning("没有找到可备份的数据。")
        return

    print_success("备份完成")
    print_blank_line()
    print_summary(
        [
            ("文件位置", backup_file),
            ("备份文件数", len(unique_files)),
            ("跳过缺失", len(missing_items)),
            ("文件大小", format_file_size(backup_file.stat().st_size)),
        ]
    )

    if missing_items:
        print_card_title("跳过缺失项目")

        for missing_item in missing_items[:5]:
            print(f"- {missing_item}")

        if len(missing_items) > 5:
            print(f"- 还有 {len(missing_items) - 5} 项未显示。")


def is_safe_reset_target(path):
    resolved_path = path.resolve()
    protected_paths = {
        BASE_DIR.resolve(),
        BACKUP_DIR.resolve(),
        (BASE_DIR / ".git").resolve(),
    }

    if resolved_path in protected_paths:
        return False

    try:
        resolved_path.relative_to(BASE_DIR.resolve())
    except ValueError:
        return False

    return True


def clear_file(path):
    if not is_safe_reset_target(path):
        raise ValueError(f"拒绝清空不安全路径：{display_path(path)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding=TEXT_ENCODING)
    return "cleared"


def safe_delete_file(path):
    if not is_safe_reset_target(path):
        raise ValueError(f"拒绝删除不安全路径：{display_path(path)}")

    if not path.exists():
        return "missing"

    if not path.is_file():
        return "missing"

    path.unlink()
    return "deleted"


def safe_delete_dir(path):
    if not is_safe_reset_target(path):
        raise ValueError(f"拒绝删除不安全路径：{display_path(path)}")

    if not path.exists():
        return "missing"

    if not path.is_dir():
        return "missing"

    shutil.rmtree(path)
    return "deleted"


def confirm_reset():
    print_warning("危险操作：即将清空所有学习数据。")
    try:
        answer = input("请输入 RESET 确认继续：").strip()
    except EOFError:
        return False

    return answer == "RESET"


def print_reset_summary(cleared_items, deleted_items, missing_count):
    print_success("已恢复到初始状态")
    print_blank_line()

    for item in cleared_items:
        print(f"已清空：{display_path(item)}")

    for item in deleted_items:
        suffix = "/" if item.suffix == "" else ""
        print(f"已删除：{display_path(item)}{suffix}")

    print("已保留：backup/")

    if missing_count:
        print(f"跳过缺失：{missing_count} 项")


def run_reset(skip_confirm=False):
    print_header("🧹 日语复习工具", "恢复初始状态")

    if not skip_confirm and not confirm_reset():
        print_warning("已取消 reset 操作。")
        return

    try:
        backup_file, backup_files, _missing_items = create_backup()
    except (OSError, ValueError) as error:
        print_error(f"reset 前备份失败，已取消 reset 操作。{error}")
        return

    if not backup_file:
        print_error("reset 前备份失败，已取消 reset 操作。")
        return

    print(color_text("📦 reset 前自动备份完成", GREEN))
    print_field("文件位置", backup_file)
    print_field("备份文件数", len(backup_files))
    print_blank_line()

    cleared_items = []
    deleted_items = []
    missing_count = 0
    delete_targets = [
        DATA_FILE,
        OUTPUT_FILE,
        WRONG_BOOK_FILE,
        MASTERED_FILE,
        DAILY_OUTPUT_DIR,
        EXPORT_DIR,
        INPUT_ARCHIVE_DIR,
    ]

    try:
        clear_file(INPUT_FILE)
        cleared_items.append(INPUT_FILE)

        for target in delete_targets:
            if target.is_dir() or (not target.exists() and target.suffix == ""):
                result = safe_delete_dir(target)
            else:
                result = safe_delete_file(target)

            if result == "deleted":
                deleted_items.append(target)
            elif result == "missing":
                missing_count += 1

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        print_error(f"reset 执行失败：{error}")
        return

    print_reset_summary(cleared_items, deleted_items, missing_count)


def find_duplicates(values):
    seen = set()
    duplicates = []

    for value in values:
        if not value:
            continue

        if value in seen and value not in duplicates:
            duplicates.append(value)

        seen.add(value)

    return duplicates


def parse_markdown_entries_for_check(file_path, defaults):
    entries = []
    issues = []
    current_entry = None
    current_section_date = ""

    if not file_path.exists():
        return entries, issues

    def finish_current_entry():
        if not current_entry:
            return

        if not current_entry["japanese"]:
            issues.append("发现空日语句子。")

        if not current_entry["chinese"]:
            issues.append(f"「{current_entry['japanese'] or '未知句子'}」缺少中文意思。")

        entries.append(current_entry)

    with file_path.open("r", encoding=TEXT_ENCODING) as file:
        for line_number, raw_line in enumerate(file, start=1):
            raw_without_newline = raw_line.rstrip("\n")
            line = raw_without_newline.strip()

            if not line:
                continue

            if line.startswith("## "):
                current_section_date = line.removeprefix("## ").strip()
                continue

            if line.startswith("- 日语："):
                finish_current_entry()
                current_entry = {
                    "japanese": line.removeprefix("- 日语：").strip(),
                    "chinese": "",
                    "tag": defaults["tag"],
                    "grammar": "",
                    "words": "",
                    "note": "",
                    "status": defaults["status"],
                    "date": current_section_date,
                    "added_date": current_section_date,
                    "wrong_date": "",
                    "mastered_date": current_section_date,
                    "mastered_source": "",
                    "mastery_count": "",
                    "has_tag": False,
                    "has_status": False,
                    "has_mastery_count": False,
                    "has_mastered_date": False,
                    "raw_tags": [],
                }
                continue

            if line.startswith("- ") and not current_entry:
                issues.append(f"第 {line_number} 行格式异常：字段出现在日语句子之前。")
                continue

            if not current_entry:
                continue

            if line.startswith("- 中文："):
                if current_entry["chinese"]:
                    issues.append(f"第 {line_number} 行格式异常：同一记录出现多个中文字段。")
                current_entry["chinese"] = line.removeprefix("- 中文：").strip()
            elif line.startswith("- 标签："):
                raw_tag = raw_without_newline.removeprefix("- 标签：")
                current_entry["raw_tags"].append(raw_tag)
                current_entry["has_tag"] = True
                current_entry["tag"] = raw_tag.strip()
            elif line.startswith("- 语法点："):
                current_entry["grammar"] = line.removeprefix("- 语法点：").strip()
            elif line.startswith("- 重点单词："):
                current_entry["words"] = line.removeprefix("- 重点单词：").strip()
            elif line.startswith("- 备注："):
                current_entry["note"] = line.removeprefix("- 备注：").strip()
            elif line.startswith("- 状态："):
                current_entry["has_status"] = True
                current_entry["status"] = line.removeprefix("- 状态：").strip()
            elif line.startswith("- 加入日期："):
                current_entry["added_date"] = line.removeprefix("- 加入日期：").strip()
            elif line.startswith("- 掌握次数："):
                current_entry["has_mastery_count"] = True
                current_entry["mastery_count"] = line.removeprefix("- 掌握次数：").strip()
            elif line.startswith("- 复习次数："):
                pass
            elif line.startswith("- 首次加入错题本日期："):
                current_entry["wrong_date"] = line.removeprefix("- 首次加入错题本日期：").strip()
            elif line.startswith("- 掌握来源："):
                current_entry["mastered_source"] = line.removeprefix("- 掌握来源：").strip()
            elif line.startswith("- 掌握日期："):
                current_entry["has_mastered_date"] = True
                current_entry["mastered_date"] = line.removeprefix("- 掌握日期：").strip()
            elif line.startswith("- "):
                issues.append(f"第 {line_number} 行格式异常：无法识别字段「{line}」。")

    finish_current_entry()
    return entries, issues


def parse_review_for_check(file_path):
    return parse_markdown_entries_for_check(
        file_path,
        {
            "tag": DEFAULT_TAG,
            "status": "待复习",
        },
    )


def parse_wrong_for_check(file_path):
    return parse_markdown_entries_for_check(
        file_path,
        {
            "tag": DEFAULT_TAG,
            "status": "待复习",
        },
    )


def parse_mastered_for_check(file_path):
    return parse_markdown_entries_for_check(
        file_path,
        {
            "tag": DEFAULT_TAG,
            "status": "已掌握",
        },
    )


def is_english_tag(tag):
    return bool(tag) and all(char.isascii() and (char.isalpha() or char.isspace()) for char in tag)


def collect_tag_issues(entries):
    issues = []
    lowercase_to_tags = {}

    for entry in entries:
        tag = entry.get("tag", "")

        for raw_tag in entry.get("raw_tags", []):
            if raw_tag != raw_tag.strip():
                issues.append(f"标签「{raw_tag}」前后存在多余空格。")

        if is_english_tag(tag):
            lowercase_to_tags.setdefault(tag.lower(), set()).add(tag)

    for variants in lowercase_to_tags.values():
        if len(variants) > 1:
            issues.append(f"英文标签大小写可能不一致：{', '.join(sorted(variants))}")

    return issues


def print_limited_issues(issues, limit=5):
    if not issues:
        print("关键问题：无")
        return

    print("关键问题：")
    for issue in issues[:limit]:
        print(f"* {issue}")

    if len(issues) > limit:
        print(f"* 还有 {len(issues) - limit} 个问题未显示。")


def print_check_section(title, status_count_label, count, issues):
    print_card_title(title)
    status = "✅ 正常" if not issues else "⚠️ 有问题"
    print_field("状态", status)
    print_field(status_count_label, count)
    print_field("问题数量", len(issues))
    print_limited_issues(issues)


def run_check():
    print_header("🔍 数据健康检查")
    all_issues = []

    if not OUTPUT_FILE.exists():
        review_entries = []
        review_issues = [f"未找到 {display_path(OUTPUT_FILE)}，请先添加句子。"]
    else:
        review_entries, review_issues = parse_review_for_check(OUTPUT_FILE)
        review_duplicates = find_duplicates([entry["japanese"] for entry in review_entries])
        review_issues.extend(f"重复日语句子：{sentence}" for sentence in review_duplicates)

    print_check_section("1. review 池检查", "当前待复习句子数", len(review_entries), review_issues)
    all_issues.extend(review_issues)

    review_sentence_set = {entry["japanese"] for entry in review_entries if entry["japanese"]}

    wrong_entries, wrong_issues = parse_wrong_for_check(WRONG_BOOK_FILE)

    if WRONG_BOOK_FILE.exists():
        wrong_duplicates = find_duplicates([entry["japanese"] for entry in wrong_entries])
        wrong_issues.extend(f"重复错题：{sentence}" for sentence in wrong_duplicates)

        for entry in wrong_entries:
            japanese = entry["japanese"] or "未知句子"

            if not entry["has_mastery_count"]:
                wrong_issues.append(f"「{japanese}」缺少掌握次数。")
            elif not entry["mastery_count"].isdigit():
                wrong_issues.append(f"「{japanese}」掌握次数不是有效数字：{entry['mastery_count']}")

    print_check_section("2. wrong 池检查", "当前错题数", len(wrong_entries), wrong_issues)
    all_issues.extend(wrong_issues)

    wrong_sentence_set = {entry["japanese"] for entry in wrong_entries if entry["japanese"]}

    mastered_entries, mastered_issues = parse_mastered_for_check(MASTERED_FILE)
    mastered_sentence_set = {entry["japanese"] for entry in mastered_entries if entry["japanese"]}

    if MASTERED_FILE.exists():
        mastered_duplicates = find_duplicates([entry["japanese"] for entry in mastered_entries])
        mastered_issues.extend(f"重复已掌握句子：{sentence}" for sentence in mastered_duplicates)

        for entry in mastered_entries:
            japanese = entry["japanese"] or "未知句子"

            if not entry["has_mastered_date"] or not entry["mastered_date"]:
                mastered_issues.append(f"「{japanese}」缺少掌握日期。")

    conflict_issues = [
        f"发现状态冲突：{sentence} 同时存在于 review 和 wrong。"
        for sentence in sorted(review_sentence_set & wrong_sentence_set)
    ]
    conflict_issues.extend(
        f"发现状态冲突：{sentence} 同时存在于 review 和 master。"
        for sentence in sorted(review_sentence_set & mastered_sentence_set)
    )
    conflict_issues.extend(
        f"发现状态冲突：{sentence} 同时存在于 wrong 和 master。"
        for sentence in sorted(wrong_sentence_set & mastered_sentence_set)
    )
    mastered_issues.extend(conflict_issues)

    print_check_section("3. master 池检查", "已掌握句子数", len(mastered_entries), mastered_issues)
    all_issues.extend(mastered_issues)

    tag_issues = collect_tag_issues(review_entries + wrong_entries + mastered_entries)
    all_tags = {
        entry.get("tag", "")
        for entry in review_entries + wrong_entries + mastered_entries
        if entry.get("tag", "") != ""
    }
    print_check_section("4. 标签检查", "标签数量", len(all_tags), tag_issues)
    all_issues.extend(tag_issues)

    print_card_title("5. 总体建议")

    if all_issues:
        print(f"* 发现 {len(all_issues)} 个需要关注的问题。")
        print("* 当前版本只做检查和提示，不会自动修改文件。")
    else:
        print("✅ 未发现明显问题，数据状态良好。")


def ask_self_assessment():
    while True:
        print(color_text("这题掌握了吗？y/n，输入 q 退出：", CYAN))
        assessment = input("> ").strip().lower()

        if assessment in ("y", "n", "q", "quit"):
            return assessment

        print_warning("请输入 y、n、q 或 quit。")


def ask_mark_mastered():
    while True:
        print(color_text("这题正确度很高，是否标记为完全掌握并加入 mastered.md？y/n，输入 q 退出：", CYAN))
        answer = input("> ").strip().lower()

        if answer in ("y", "n", "q", "quit"):
            return answer

        print_warning("请输入 y、n、q 或 quit。")


def print_quiz_summary(
    asked_count,
    mastered_count,
    new_wrong_count,
    duplicate_wrong_count,
    graduated_count,
    retry_count=0,
):
    print_section("✅ Quiz 结束")
    print_blank_line()
    print_summary(
        [
            ("本次抽查", f"{asked_count} 题"),
            ("标记掌握", f"{mastered_count} 题"),
            ("新增错题", f"{new_wrong_count} 题"),
            ("跳过重复错题", f"{duplicate_wrong_count} 题"),
            ("毕业错题", f"{graduated_count} 题"),
            ("重答次数", f"{retry_count} 次"),
        ]
    )


def format_quiz_index(index, count, loop=False):
    if loop:
        return str(index)

    return f"{index}/{count}"


def print_quiz_prompt(index, count, sentence, wrong_mode=False, loop=False):
    print("")
    print(color_text(f"🎯 Quiz {format_quiz_index(index, count, loop)}", BOLD))
    print(SEPARATOR)
    tag = get_entry_tag(sentence)

    if tag:
        print(f"{color_text('🏷️ 标签：', YELLOW)}{color_text(tag, BOLD)}")

    if wrong_mode:
        mastery_text = f"当前掌握次数：{sentence.get('mastery_count', 0)}/{GRADUATION_THRESHOLD}"
        print(color_text(mastery_text, YELLOW))

    print("")
    print(color_text("🇨🇳 中文：", CYAN))
    print(color_text(sentence["chinese"], CYAN))
    print("")
    print(color_text("请输入日语，输入 q 退出：", BOLD))
    answer = input("> ").strip()
    print_debug_input(answer)
    return answer


def print_similarity_panel(similarity_result):
    score = similarity_result["score"]
    feedback = similarity_result["feedback"]
    feedback_color = similarity_result["feedback_color"]
    previous_score = similarity_result["previous_score"]
    best_score = similarity_result["best_score"]
    change_text = similarity_result["change_text"]
    change_color = similarity_result["change_color"]

    print_card_title("正确度", icon="📊")
    print(color_text(f"本次：{score}%｜{feedback}", feedback_color))

    if previous_score is None:
        print("上次：暂无")
    else:
        print(f"上次：{previous_score}%")

    if change_color:
        print(color_text(f"变化：{change_text}", change_color))
    else:
        print(f"变化：{change_text}")

    print(f"历史最高：{best_score}%")


def print_retry_similarity_panel(similarity_result):
    score = similarity_result["score"]
    feedback = similarity_result["feedback"]
    feedback_color = similarity_result["feedback_color"]

    print_card_title("重答正确度", icon="📊")
    print(color_text(f"本次：{score}%｜{feedback}", feedback_color))
    print("")
    print(color_text("✅ 参考答案：", GREEN))
    print(color_text(similarity_result["reference_answer"], GREEN))


def print_quiz_answer(answer, sentence, similarity_result):
    print_card_title("参考答案", icon="📖")
    print(color_text("你的输入：", GRAY))
    print(color_text(answer, GRAY))
    print("")
    print(color_text("✅ 参考答案：", GREEN))
    print(color_text(sentence["japanese"], GREEN))
    print_similarity_panel(similarity_result)
    print("")
    print(color_text("🇨🇳 中文意思：", CYAN))
    print(color_text(sentence["chinese"], CYAN))
    grammar = get_entry_grammar(sentence)
    words = get_entry_words(sentence)
    note = get_entry_note(sentence)

    if grammar:
        print("")
        print(color_text("📚 语法点：", YELLOW))
        print(color_text(grammar, YELLOW))

    if words:
        print("")
        print(color_text("📝 重点单词：", CYAN))
        print(color_text(words, BOLD))

    if note:
        print("")
        print(color_text("💡 备注：", YELLOW))
        print(note)

    print("")


def run_retry_once(sentence, review_data, speak_enabled=False, voice="Kyoko", speak_state=None):
    print_card_title("再练一次")
    print(color_text("🇨🇳 中文：", CYAN))
    print(color_text(sentence["chinese"], CYAN))
    print("")
    print(color_text("请重新输入这句日语，输入 q 退出：", BOLD))
    retry_answer = input("> ").strip()
    print_debug_input(retry_answer)

    if retry_answer.lower() in ("q", "quit"):
        return True, False

    similarity_result = build_similarity_result(retry_answer, sentence, review_data)
    similarity_result["reference_answer"] = sentence["japanese"]
    print_retry_similarity_panel(similarity_result)
    if speak_enabled:
        maybe_speak_japanese(sentence["japanese"], voice, speak_state)
    record_quiz_activity(score=similarity_result["score"], retry_count=1)
    update_similarity_record(review_data, sentence, similarity_result["score"])
    save_review_data(DATA_FILE, review_data)
    return False, True


def is_say_available():
    return shutil.which("say") is not None


def speak_japanese(text, voice="Kyoko"):
    text = normalize_optional_text(text)

    if not text:
        return False

    if not is_say_available():
        print_warning("当前系统不支持 say 命令，已跳过朗读。")
        return False

    try:
        print(color_text(f"🔊 朗读：{text}", CYAN))
        subprocess.run(["say", "-v", voice, text], check=False)
        return True
    except OSError:
        print_warning("朗读失败，已跳过。")
        return False


def maybe_speak_japanese(text, voice, speak_state):
    if speak_state is None:
        speak_state = {}

    if not is_say_available():
        if not speak_state.get("warning_shown"):
            print_warning("当前系统不支持 say 命令，已跳过朗读。")
            speak_state["warning_shown"] = True
        return False

    return speak_japanese(text, voice)


def choose_next_question(candidates, last_japanese=None):
    if not candidates:
        return None

    if len(candidates) == 1:
        return random.choice(candidates)

    available_candidates = [
        item
        for item in candidates
        if item.get("japanese") != last_japanese
    ]

    if not available_candidates:
        available_candidates = candidates

    return random.choice(available_candidates)


def run_regular_quiz(count, tag=None, loop=False, retry_wrong=True, speak_enabled=False, voice="Kyoko"):
    sentences = load_quiz_sentences(OUTPUT_FILE)
    sentences = filter_sentences_by_tag(sentences, tag)

    if not sentences:
        if tag:
            print_no_tag_message(tag)
        else:
            print_warning("没有可抽查的句子，请先添加句子。")
        return

    print_header("📘 日语复习工具", "Quiz 模式")
    asked_count = 0
    mastered_count = 0
    new_wrong_count = 0
    duplicate_wrong_count = 0
    retry_count = 0
    index = 1
    review_data = load_review_data(DATA_FILE)
    last_japanese = None
    speak_state = {"warning_shown": False}

    while loop or index <= count:
        sentence = choose_next_question(sentences, last_japanese)

        if sentence is None:
            print_warning("review 池已经没有可复习句子。")
            break

        last_japanese = sentence["japanese"]
        asked_count += 1

        answer = print_quiz_prompt(index, count, sentence, loop=loop)

        if answer.lower() in ("q", "quit"):
            print_quiz_summary(
                asked_count - 1,
                mastered_count,
                new_wrong_count,
                duplicate_wrong_count,
                0,
                retry_count,
            )
            return

        similarity_result = build_similarity_result(answer, sentence, review_data)
        print_quiz_answer(answer, sentence, similarity_result)
        if speak_enabled:
            maybe_speak_japanese(sentence["japanese"], voice, speak_state)
        record_quiz_activity(score=similarity_result["score"])
        update_similarity_record(review_data, sentence, similarity_result["score"])
        save_review_data(DATA_FILE, review_data)

        assessment = ask_self_assessment()

        if assessment in ("q", "quit"):
            print_quiz_summary(
                asked_count,
                mastered_count,
                new_wrong_count,
                duplicate_wrong_count,
                0,
                retry_count,
            )
            return

        if assessment == "y":
            mastered_count += 1

            if similarity_result["score"] >= 95:
                mastery_answer = ask_mark_mastered()

                if mastery_answer in ("q", "quit"):
                    print_quiz_summary(
                        asked_count,
                        mastered_count,
                        new_wrong_count,
                        duplicate_wrong_count,
                        0,
                        retry_count,
                    )
                    return

                if mastery_answer == "y":
                    sync_result = sync_sentence_state(
                        sentence,
                        target_pool="master",
                        source_pool="review",
                    )
                    record_quiz_activity(
                        master_added=1 if sync_result["added"] else 0,
                        review_to_master=1 if sync_result["removed_from_review"] else 0,
                        count_as_quiz=False,
                    )

                    if sync_result["removed_from_review"]:
                        print_success(f"已从 review 移入 master：{sentence['japanese']}")
                        sentences = [
                            item
                            for item in sentences
                            if item.get("japanese") != sentence["japanese"]
                        ]
        else:
            sync_result = sync_sentence_state(
                sentence,
                target_pool="wrong",
                source_pool="review",
            )

            if sync_result["added"]:
                new_wrong_count += 1
            else:
                duplicate_wrong_count += 1

            record_quiz_activity(
                wrong_added=1 if sync_result["added"] else 0,
                review_to_wrong=1 if sync_result["removed_from_review"] else 0,
                count_as_quiz=False,
            )

            if sync_result["removed_from_review"]:
                sentences = [
                    item
                    for item in sentences
                    if item.get("japanese") != sentence["japanese"]
                ]

            if retry_wrong:
                should_quit, retried = run_retry_once(
                    sentence,
                    review_data,
                    speak_enabled,
                    voice,
                    speak_state,
                )

                if retried:
                    retry_count += 1

                if should_quit:
                    print_quiz_summary(
                        asked_count,
                        mastered_count,
                        new_wrong_count,
                        duplicate_wrong_count,
                        0,
                        retry_count,
                    )
                    return

        index += 1

        if not sentences:
            print_warning("review 池已经没有可复习句子。")
            break

    print_quiz_summary(
        asked_count,
        mastered_count,
        new_wrong_count,
        duplicate_wrong_count,
        0,
        retry_count,
    )


def run_wrong_quiz(count, tag=None, loop=False, retry_wrong=True, speak_enabled=False, voice="Kyoko"):
    entries = load_wrong_book_entries()
    entries = filter_sentences_by_tag(entries, tag)

    if not entries:
        if tag:
            print_no_tag_message(tag)
        else:
            print_warning("目前没有错题，可以先进行普通 quiz。")
        return

    print_header("📘 日语复习工具", "错题 Quiz 模式")
    asked_count = 0
    mastered_count = 0
    graduated_count = 0
    retry_count = 0
    index = 1
    review_data = load_review_data(DATA_FILE)
    last_japanese = None
    speak_state = {"warning_shown": False}

    while loop or index <= count:
        if not entries:
            print_success("错题本已经清空。")
            break

        entry = choose_next_question(entries, last_japanese)

        if entry is None:
            print_success("错题本已经清空。")
            break

        last_japanese = entry["japanese"]
        asked_count += 1

        answer = print_quiz_prompt(index, count, entry, wrong_mode=True, loop=loop)

        if answer.lower() in ("q", "quit"):
            save_wrong_book_entries(entries)
            print_quiz_summary(
                asked_count - 1,
                mastered_count,
                0,
                0,
                graduated_count,
                retry_count,
            )
            return

        similarity_result = build_similarity_result(answer, entry, review_data)
        print_quiz_answer(answer, entry, similarity_result)
        if speak_enabled:
            maybe_speak_japanese(entry["japanese"], voice, speak_state)
        record_quiz_activity(score=similarity_result["score"])
        update_similarity_record(review_data, entry, similarity_result["score"])
        save_review_data(DATA_FILE, review_data)

        assessment = ask_self_assessment()

        if assessment in ("q", "quit"):
            save_wrong_book_entries(entries)
            print_quiz_summary(
                asked_count,
                mastered_count,
                0,
                0,
                graduated_count,
                retry_count,
            )
            return

        if assessment == "y":
            mastered_count += 1
            entry["mastery_count"] += 1
            print_success(f"掌握次数已更新为：{entry['mastery_count']}/{GRADUATION_THRESHOLD}")

            if entry["mastery_count"] >= GRADUATION_THRESHOLD:
                sync_result = sync_sentence_state(
                    entry,
                    target_pool="master",
                    source_pool="wrong",
                )
                record_quiz_activity(
                    master_added=1 if sync_result["added"] else 0,
                    wrong_to_master=1 if sync_result["removed_from_wrong"] else 0,
                    count_as_quiz=False,
                )
                entries = [
                    item
                    for item in entries
                    if item.get("japanese") != entry["japanese"]
                ]
                graduated_count += 1

                if sync_result["added"]:
                    print(f"🎉 恭喜，这条错题已掌握并移入 mastered.md：{entry['japanese']}")
                else:
                    print_success(f"这条错题已从错题本移除：{entry['japanese']}")
        elif retry_wrong:
            should_quit, retried = run_retry_once(
                entry,
                review_data,
                speak_enabled,
                voice,
                speak_state,
            )

            if retried:
                retry_count += 1

            if should_quit:
                save_wrong_book_entries(entries)
                print_quiz_summary(
                    asked_count,
                    mastered_count,
                    0,
                    0,
                    graduated_count,
                    retry_count,
                )
                return

        index += 1

    save_wrong_book_entries(entries)
    print_quiz_summary(asked_count, mastered_count, 0, 0, graduated_count, retry_count)


def run_quiz(count, wrong_only=False, tag=None, loop=False, retry_wrong=True, speak_enabled=False, voice="Kyoko"):
    if loop and count != 1:
        print_warning("已启用 --loop，将忽略 --count。")

    if wrong_only:
        run_wrong_quiz(count, tag, loop, retry_wrong, speak_enabled, voice)
    else:
        run_regular_quiz(count, tag, loop, retry_wrong, speak_enabled, voice)


def is_quit_input(value):
    return value.strip().lower() in {"q", "quit"}


def read_menu_input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return "q"


def print_menu():
    print_header("📘 日语复习工具", "菜单模式")
    print_blank_line()
    print("请选择功能：")
    print_blank_line()
    print("1. 普通 Quiz")
    print("2. 错题 Quiz")
    print("3. 完全掌握确认")
    print("4. 快速添加句子")
    print("5. 导入句子 (input/sentences.txt)")
    print("6. 备份数据")
    print("7. 重置 / 清空当前状态")
    print("8. 今日学习面板 (--today)")
    print("9. 三池统计面板 (--stats)")
    print("10. 查看复习建议 (--plan)")
    print("11. 查看学习趋势 (--trend)")
    print("0. 退出")
    print_blank_line()
    print("0 / q：退出")
    print("数字键：选择功能")
    print_blank_line()


def print_quiz_menu(title):
    print_header("📘 日语复习工具", title)
    print_blank_line()


def read_positive_int_from_menu(prompt, default_value=1):
    value = read_menu_input(prompt)

    if not value:
        return default_value, False

    if is_quit_input(value) or value == "0":
        return None, True

    try:
        number = int(value)
    except ValueError:
        print_warning("请输入有效数字。")
        return None, True

    if number < 1:
        print_warning("数量需要大于 0。")
        return None, True

    return number, False


def read_trend_days_from_menu():
    value = read_menu_input("显示最近几天？回车默认 7：")

    if not value:
        return 7, False

    if is_quit_input(value) or value == "0":
        return None, True

    try:
        days = int(value)
    except ValueError:
        print_warning("请输入有效数字，已使用默认 7 天。")
        return 7, False

    if days < 1:
        print_warning("趋势天数需要大于 0，已使用默认 7 天。")
        return 7, False

    if days > 30:
        print_warning("趋势天数最多显示 30 天，已使用 30 天。")
        return 30, False

    return days, False


def wait_for_menu_return():
    answer = read_menu_input("按回车返回菜单，输入 q 退出：")
    return is_quit_input(answer)


def read_menu_add_field(prompt, required=False, error_message=""):
    value = read_menu_input(prompt)

    if is_quit_input(value):
        return None, True

    if required and not value:
        print_error(error_message)
        return None, True

    return value, False


def confirm_menu_action(prompt):
    while True:
        answer = read_menu_input(prompt).lower()

        if answer == "y":
            return True

        if answer in {"n", "0"} or is_quit_input(answer):
            return False

        print_warning("请输入 y 或 n。")


def ask_menu_speak_enabled():
    return confirm_menu_action("是否开启日语朗读？y/n：")


def run_menu_regular_quiz():
    while True:
        print_quiz_menu("普通 Quiz")
        print("普通 Quiz：")
        print("1. 随机抽题")
        print("2. 指定数量")
        print("3. 指定标签")
        print("0. 返回主菜单")
        print_blank_line()
        print("回车：随机抽题 1 题")
        choice = read_menu_input("请输入数字：")

        if not choice or choice == "1":
            speak_enabled = ask_menu_speak_enabled()
            run_quiz(1, speak_enabled=speak_enabled)
            return True

        if choice == "0" or is_quit_input(choice):
            return False

        if choice == "2":
            count, canceled = read_positive_int_from_menu("请输入抽题数量：")

            if not canceled and count:
                speak_enabled = ask_menu_speak_enabled()
                run_quiz(count, speak_enabled=speak_enabled)
                return True

            return False

        if choice == "3":
            tag = read_menu_input("请输入标签：")

            if tag == "0" or is_quit_input(tag):
                return False

            if not tag:
                print_warning("标签不能为空。")
                return False

            count, canceled = read_positive_int_from_menu("请输入抽题数量，回车默认 5：", 5)

            if not canceled and count:
                speak_enabled = ask_menu_speak_enabled()
                run_quiz(count, tag=tag, speak_enabled=speak_enabled)
                return True

            return False

        print_warning("请输入有效选项。")


def run_menu_wrong_quiz():
    while True:
        print_quiz_menu("错题 Quiz")
        print("错题 Quiz：")
        print("1. 随机抽题")
        print("2. 指定数量")
        print("3. loop 模式")
        print("0. 返回主菜单")
        print_blank_line()
        print("回车：错题随机抽题 1 题")
        choice = read_menu_input("请输入数字：")

        if not choice or choice == "1":
            speak_enabled = ask_menu_speak_enabled()
            run_quiz(1, wrong_only=True, speak_enabled=speak_enabled)
            return True

        if choice == "0" or is_quit_input(choice):
            return False

        if choice == "2":
            count, canceled = read_positive_int_from_menu("请输入抽题数量：")

            if not canceled and count:
                speak_enabled = ask_menu_speak_enabled()
                run_quiz(count, wrong_only=True, speak_enabled=speak_enabled)
                return True

            return False

        if choice == "3":
            speak_enabled = ask_menu_speak_enabled()
            run_quiz(1, wrong_only=True, loop=True, speak_enabled=speak_enabled)
            return True

        print_warning("请输入有效选项。")


def run_menu_mastery_quiz():
    print_header("📘 日语复习工具", "完全掌握确认")
    print_warning("该入口会进入普通 Quiz。正确度很高且自评掌握时，可确认移入 master。")
    count, canceled = read_positive_int_from_menu("请输入抽题数量，回车默认 1：", 1)

    if not canceled and count:
        speak_enabled = ask_menu_speak_enabled()
        run_quiz(count, speak_enabled=speak_enabled)
        return True

    return False


def run_menu_add():
    japanese, canceled = read_menu_add_field(
        "请输入日语句子：",
        required=True,
        error_message="日语句子不能为空。",
    )

    if canceled:
        print_warning("已取消本次添加。")
        return False

    chinese, canceled = read_menu_add_field(
        "请输入中文意思：",
        required=True,
        error_message="中文意思不能为空。",
    )

    if canceled:
        print_warning("已取消本次添加。")
        return False

    tag, canceled = read_menu_add_field("标签（可选）：")
    if canceled:
        print_warning("已取消本次添加。")
        return False

    grammar, canceled = read_menu_add_field("语法点（可选）：")
    if canceled:
        print_warning("已取消本次添加。")
        return False

    words, canceled = read_menu_add_field("重点单词（可选）：")
    if canceled:
        print_warning("已取消本次添加。")
        return False

    note, canceled = read_menu_add_field("备注（可选）：")
    if canceled:
        print_warning("已取消本次添加。")
        return False

    if not confirm_menu_action("是否加入 review 池？y/n："):
        print_warning("已取消本次添加。")
        return False

    run_add([japanese, chinese], tag, grammar, words, note)
    return True


def run_menu_import():
    print_header("📘 日语复习工具", "导入句子")

    if not confirm_menu_action("是否从 input/sentences.txt 导入句子？y/n："):
        print_warning("已取消导入。")
        return False

    run_review(no_prompt=True)
    return True


def run_menu_backup():
    print_header("📘 日语复习工具", "备份数据")

    if not confirm_menu_action("是否立即执行备份？y/n："):
        print_warning("已取消备份。")
        return False

    run_backup()
    return True


def run_menu_reset():
    print_header("📘 日语复习工具", "重置 / 清空当前状态")
    print_warning("确认要清空当前 review / wrong / master 状态吗？")
    print_warning("为了安全，下一步仍需输入 RESET 才会真正执行。")

    if not confirm_menu_action("是否继续？y/n："):
        print_warning("已取消重置。")
        return False

    run_reset(skip_confirm=False)
    return True


def run_menu_action(choice):
    if choice == "1":
        return run_menu_regular_quiz()
    elif choice == "2":
        return run_menu_wrong_quiz()
    elif choice == "3":
        return run_menu_mastery_quiz()
    elif choice == "4":
        return run_menu_add()
    elif choice == "5":
        return run_menu_import()
    elif choice == "6":
        return run_menu_backup()
    elif choice == "7":
        return run_menu_reset()
    elif choice == "8":
        run_today()
        return True
    elif choice == "9":
        run_stats()
        return True
    elif choice == "10":
        run_plan()
        return True
    elif choice == "11":
        days, canceled = read_trend_days_from_menu()

        if canceled:
            return False

        run_trend(days)
        return True

    return False


def run_menu():
    valid_choices = {str(number) for number in range(1, 12)}

    while True:
        print_menu()
        choice = read_menu_input("请输入数字：")

        if choice == "0" or is_quit_input(choice):
            print(color_text("👋 已退出菜单模式。", GREEN))
            return

        if choice not in valid_choices:
            print_warning("请输入有效选项。")
            print_blank_line()
            continue

        should_wait = run_menu_action(choice)
        print_blank_line()

        if should_wait and wait_for_menu_return():
            print(color_text("👋 已退出菜单模式。", GREEN))
            return


def parse_args():
    parser = argparse.ArgumentParser(description="本地日语复习小工具")
    parser.add_argument("--add", nargs="*", metavar="文本", help="快速添加一句日语和中文意思")
    parser.add_argument("--menu", action="store_true", help="进入菜单模式")
    parser.add_argument("--clear-input", action="store_true", help="归档并清空输入文件")
    parser.add_argument("--no-prompt", action="store_true", help="普通模式结束后不询问清空输入文件")
    parser.add_argument("--no-color", action="store_true", help="关闭 ANSI 彩色输出")
    parser.add_argument("--debug-input", action="store_true", help="显示 Quiz 输入调试信息")
    parser.add_argument("--no-retry", action="store_true", help="答错后不进行重答")
    parser.add_argument("--speak", action="store_true", help="Quiz 中朗读日语参考答案")
    parser.add_argument("--voice", default="Kyoko", help="朗读语音，默认 Kyoko")
    parser.add_argument("--quiz", action="store_true", help="进入随机抽查模式")
    parser.add_argument("--loop", action="store_true", help="进入无限随机复习模式")
    parser.add_argument("--wrong", action="store_true", help="只复习错题本")
    parser.add_argument("--mastered", action="store_true", help="导出已掌握本")
    parser.add_argument("--stats", action="store_true", help="显示学习统计面板")
    parser.add_argument("--today", action="store_true", help="显示今日学习面板")
    parser.add_argument("--plan", action="store_true", help="显示今日复习建议")
    parser.add_argument("--trend", action="store_true", help="显示最近学习趋势")
    parser.add_argument("--tags", action="store_true", help="显示标签统计")
    parser.add_argument("--tag", help="按指定标签抽查")
    parser.add_argument("--grammar", default="", help="快速添加时填写语法点")
    parser.add_argument("--words", default="", help="快速添加时填写重点单词")
    parser.add_argument("--note", default="", help="快速添加时填写备注")
    parser.add_argument("--export-csv", action="store_true", help="导出 CSV")
    parser.add_argument("--export-anki", action="store_true", help="导出 Anki 导入 CSV")
    parser.add_argument("--check", action="store_true", help="检查复习数据健康状态")
    parser.add_argument("--backup", action="store_true", help="一键备份学习数据")
    parser.add_argument("--reset", action="store_true", help="清空学习数据并恢复初始状态")
    parser.add_argument("--yes", action="store_true", help="跳过 reset 二次确认")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="随机抽查题数，默认 1",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="趋势显示天数，默认 7 天",
    )
    return parser.parse_args()


def main():
    configure_console_encoding()
    args = parse_args()
    set_color_enabled(not args.no_color)
    set_debug_input_enabled(args.debug_input)

    if args.yes and not args.reset:
        print_error("--yes 只能和 --reset 搭配使用。")
        return

    if args.count < 1 and not args.loop:
        print_error("--count 需要是大于 0 的整数。")
        return

    if args.trend and not 1 <= args.days <= 30:
        print_error("--days 需要在 1 到 30 之间。")
        return

    if args.reset:
        run_reset(skip_confirm=args.yes)
    elif args.menu:
        run_menu()
    elif args.add is not None:
        run_add(args.add, args.tag or "", args.grammar, args.words, args.note)
    elif args.clear_input:
        archive_and_clear_input()
    elif args.check:
        run_check()
    elif args.backup:
        run_backup()
    elif args.export_csv:
        run_export_csv(args.wrong, args.mastered)
    elif args.export_anki:
        run_export_anki()
    elif args.tags:
        run_tags()
    elif args.today:
        run_today()
    elif args.plan:
        run_plan()
    elif args.trend:
        run_trend(args.days)
    elif args.stats:
        run_stats()
    elif args.quiz:
        run_quiz(
            args.count,
            args.wrong,
            args.tag,
            args.loop,
            retry_wrong=not args.no_retry,
            speak_enabled=args.speak,
            voice=args.voice,
        )
    else:
        run_review(args.no_prompt)


if __name__ == "__main__":
    main()
