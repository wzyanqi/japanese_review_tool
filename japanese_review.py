import argparse
import csv
import json
import random
import shutil
import sys
from difflib import SequenceMatcher
from datetime import date, datetime
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


def append_mastered(entry):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_japanese_sentences = load_existing_japanese_sentences(MASTERED_FILE)
    japanese = entry["japanese"]

    if japanese in existing_japanese_sentences:
        print_warning(f"已在已掌握本中，跳过重复添加：{japanese}")
        return False

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

        file.write(f"- 首次加入错题本日期：{entry['added_date']}\n")
        file.write(f"- 掌握日期：{mastered_date}\n")
        file.write("- 状态：已掌握\n")

    return True


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

    existing_japanese_sentences = load_existing_japanese_sentences(OUTPUT_FILE)

    if japanese in existing_japanese_sentences:
        print_warning(f"已存在，跳过添加：{japanese}")
        return

    sentence = {
        "japanese": japanese,
        "chinese": chinese,
        "tag": normalize_optional_text(tag),
        "grammar": normalize_optional_text(grammar),
        "words": normalize_optional_text(words),
        "note": normalize_optional_text(note),
    }
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
    existing_japanese_sentences = load_existing_japanese_sentences(OUTPUT_FILE)
    new_sentences = []
    duplicate_count = 0
    duplicate_sentences = []

    for sentence in sentences:
        japanese = sentence["japanese"]

        if japanese in existing_japanese_sentences:
            duplicate_sentences.append(japanese)
            duplicate_count += 1
            continue

        existing_japanese_sentences.add(japanese)
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

    if duplicate_sentences:
        print_card_title("跳过重复句子")
        for sentence in duplicate_sentences[:5]:
            print(f"- {sentence}")
        if len(duplicate_sentences) > 5:
            print(f"- 还有 {len(duplicate_sentences) - 5} 条未显示。")

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
            ("跳过重复", f"{duplicate_count} 句"),
            ("格式错误", f"{error_count} 行"),
        ]
    )

    if not no_prompt:
        ask_clear_input()


def format_percentage(numerator, denominator):
    if denominator == 0:
        return None

    return f"{numerator / denominator * 100:.1f}%"


def build_stats_advice(wrong_count):
    if wrong_count > 20:
        return "当前错题较多，建议今天优先复习错题。"

    if wrong_count > 0:
        return "当前错题数量可控，建议做 5 题错题 quiz。"

    return "暂无错题，可以继续添加新句子或做普通 quiz。"


def count_filled_field(entries, field_name):
    return sum(1 for entry in entries if normalize_optional_text(entry.get(field_name, "")))


def run_stats():
    today = date.today().isoformat()
    daily_output_file = DAILY_OUTPUT_DIR / f"{today}.md"
    review_entries = load_quiz_sentences(OUTPUT_FILE)
    total_count = len(review_entries)
    wrong_count = len(load_wrong_book_entries())
    mastered_count = len(load_quiz_sentences(MASTERED_FILE))
    today_new_count = len(load_quiz_sentences(daily_output_file))
    grammar_count = count_filled_field(review_entries, "grammar")
    words_count = count_filled_field(review_entries, "words")
    note_count = count_filled_field(review_entries, "note")
    tag_counts = build_tag_counts(review_entries)
    wrong_rate = format_percentage(wrong_count, total_count)
    graduation_rate = format_percentage(mastered_count, wrong_count + mastered_count)

    print_header("📊 日语学习统计")
    print_summary(
        [
            ("总句子数", total_count),
            ("当前错题数", wrong_count),
            ("已掌握错题数", mastered_count),
            ("今日新增句子", today_new_count),
            ("已填写语法点", grammar_count),
            ("已填写重点单词", words_count),
            ("已填写备注", note_count),
        ]
    )

    if total_count == 0:
        print_warning("还没有积累句子，请先添加句子并运行普通模式。")

    print_blank_line()
    if wrong_rate is not None:
        print(f"当前错题率：{wrong_rate}")

    if graduation_rate is not None:
        print(f"错题毕业率：{graduation_rate}")

    if tag_counts:
        print_card_title("标签概览")
        print_summary([("标签总数", len(tag_counts))])
        top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        top_tags_text = "，".join(f"{tag}：{count}" for tag, count in top_tags)
        print(f"句子最多的前 5 个标签：{top_tags_text}")

    print_card_title("建议")
    print(build_stats_advice(wrong_count))


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

    print_check_section("1. 总复习本检查", "总句子数", len(review_entries), review_issues)
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

            if entry["japanese"] and entry["japanese"] not in review_sentence_set:
                wrong_issues.append(f"错题「{entry['japanese']}」不在总复习本中。")

    print_check_section("2. 错题本检查", "当前错题数", len(wrong_entries), wrong_issues)
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

            if entry["japanese"] and entry["japanese"] not in review_sentence_set:
                mastered_issues.append(f"已掌握句子「{entry['japanese']}」不在总复习本中。")

    conflict_issues = [
        f"发现状态冲突：{sentence} 同时存在于错题本和已掌握本。"
        for sentence in sorted(wrong_sentence_set & mastered_sentence_set)
    ]
    mastered_issues.extend(conflict_issues)

    print_check_section("3. 已掌握本检查", "已掌握句子数", len(mastered_entries), mastered_issues)
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


def run_retry_once(sentence, review_data):
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
    update_similarity_record(review_data, sentence, similarity_result["score"])
    save_review_data(DATA_FILE, review_data)
    return False, True


def run_regular_quiz(count, tag=None, loop=False, retry_wrong=True):
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

    while loop or index <= count:
        sentence = random.choice(sentences)
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
        else:
            added = append_wrong_book(sentence)

            if added:
                new_wrong_count += 1
                print_warning("已加入错题本。")
            else:
                duplicate_wrong_count += 1

            if retry_wrong:
                should_quit, retried = run_retry_once(sentence, review_data)

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

    print_quiz_summary(
        asked_count,
        mastered_count,
        new_wrong_count,
        duplicate_wrong_count,
        0,
        retry_count,
    )


def run_wrong_quiz(count, tag=None, loop=False, retry_wrong=True):
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

    while loop or index <= count:
        if not entries:
            print_success("错题本已经清空。")
            break

        entry = random.choice(entries)
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
                added_to_mastered = append_mastered(entry)
                entries.remove(entry)
                graduated_count += 1

                if added_to_mastered:
                    print(f"🎉 恭喜，这条错题已掌握并移入 mastered.md：{entry['japanese']}")
                else:
                    print_success(f"这条错题已从错题本移除：{entry['japanese']}")
        elif retry_wrong:
            should_quit, retried = run_retry_once(entry, review_data)

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


def run_quiz(count, wrong_only=False, tag=None, loop=False, retry_wrong=True):
    if loop and count != 1:
        print_warning("已启用 --loop，将忽略 --count。")

    if wrong_only:
        run_wrong_quiz(count, tag, loop, retry_wrong)
    else:
        run_regular_quiz(count, tag, loop, retry_wrong)


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
    print("1. 快速添加句子")
    print("2. 随机复习 5 题")
    print("3. 无限随机复习")
    print("4. 错题复习 5 题")
    print("5. 无限错题复习")
    print("6. 查看学习统计")
    print("7. 查看标签统计")
    print("8. 数据健康检查")
    print("9. 一键备份")
    print("10. 导出 CSV")
    print("11. 导出 Anki")
    print("0. 退出")
    print_blank_line()


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


def run_menu_add():
    japanese, canceled = read_menu_add_field(
        "请输入日语句子：",
        required=True,
        error_message="日语句子不能为空。",
    )

    if canceled:
        print_warning("已取消本次添加。")
        return

    chinese, canceled = read_menu_add_field(
        "请输入中文意思：",
        required=True,
        error_message="中文意思不能为空。",
    )

    if canceled:
        print_warning("已取消本次添加。")
        return

    tag, canceled = read_menu_add_field("请输入标签，可留空：")
    if canceled:
        print_warning("已取消本次添加。")
        return

    grammar, canceled = read_menu_add_field("请输入语法点，可留空：")
    if canceled:
        print_warning("已取消本次添加。")
        return

    words, canceled = read_menu_add_field("请输入重点单词，可留空：")
    if canceled:
        print_warning("已取消本次添加。")
        return

    note, canceled = read_menu_add_field("请输入备注，可留空：")
    if canceled:
        print_warning("已取消本次添加。")
        return

    run_add([japanese, chinese], tag, grammar, words, note)


def run_menu_action(choice):
    if choice == "1":
        run_menu_add()
    elif choice == "2":
        run_quiz(5)
    elif choice == "3":
        run_quiz(1, loop=True)
    elif choice == "4":
        run_quiz(5, wrong_only=True)
    elif choice == "5":
        run_quiz(1, wrong_only=True, loop=True)
    elif choice == "6":
        run_stats()
    elif choice == "7":
        run_tags()
    elif choice == "8":
        run_check()
    elif choice == "9":
        run_backup()
    elif choice == "10":
        run_export_csv()
    elif choice == "11":
        run_export_anki()


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

        run_menu_action(choice)
        print_blank_line()

        if wait_for_menu_return():
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
    parser.add_argument("--quiz", action="store_true", help="进入随机抽查模式")
    parser.add_argument("--loop", action="store_true", help="进入无限随机复习模式")
    parser.add_argument("--wrong", action="store_true", help="只复习错题本")
    parser.add_argument("--mastered", action="store_true", help="导出已掌握本")
    parser.add_argument("--stats", action="store_true", help="显示学习统计面板")
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
    elif args.stats:
        run_stats()
    elif args.quiz:
        run_quiz(
            args.count,
            args.wrong,
            args.tag,
            args.loop,
            retry_wrong=not args.no_retry,
        )
    else:
        run_review(args.no_prompt)


if __name__ == "__main__":
    main()
