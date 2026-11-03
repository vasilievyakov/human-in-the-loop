#!/usr/bin/env python3
"""Turn a Markdown document into a review spec for build.py.

Usage: from_markdown.py doc.md [-o spec.json] [--options options.json] [--title TITLE]

Every ## and ### section becomes an editable item with status buttons and a comment.
A section named "Открытые вопросы" / "Open questions" becomes one item with a choice question per
numbered entry ("1. **Title.** body"); suggested answers come from options.json: {"1": ["...", "..."]}.
Every question also takes a free answer.
"""

import argparse
import json
import re
from pathlib import Path

OPEN_QUESTIONS = re.compile(r"^(открытые вопросы|open questions)", re.I)

DECISIONS = [
    {"value": "approve", "label": "Утверждаю как есть"},
    {"value": "approve_with_changes", "label": "Утверждаю с правками ниже"},
    {"value": "hold", "label": "Не утверждаю, сначала правки и ответы"},
]


def split_sections(text):
    sections, cur = [], {"heading": "", "level": 1, "lines": []}
    for line in text.splitlines():
        m = re.match(r"^(#{2,3}) (.+)$", line)
        if m:
            sections.append(cur)
            cur = {"heading": m.group(2).strip(), "level": len(m.group(1)), "lines": []}
        else:
            cur["lines"].append(line)
    sections.append(cur)
    return [s for s in sections if s["heading"] or "\n".join(s["lines"]).strip()]


def parse_questions(body, options):
    qs = []
    for chunk in re.split(r"\n(?=\d+\. )", "\n" + body):
        m = re.match(r"^(\d+)\. \*\*(.+?)\*\*\s*(.*)$", chunk.strip(), re.S)
        if not m:
            continue
        n = m.group(1)
        qs.append(
            {
                "id": f"q{n}",
                "type": "choice",
                "label": f"{n}. {m.group(2).rstrip('.')}",
                "help": re.sub(r"\s*\n\s*", " ", m.group(3)).strip(),
                "options": options.get(n, []),
                "free": True,
                "required": True,
            }
        )
    return qs


def build_spec(path, options=None, title=None):
    text = Path(path).read_text(encoding="utf-8")
    options = {str(k): v for k, v in (options or {}).items()}
    doc_title = re.search(r"^# (.+)$", text, re.M)
    items = []
    for n, sec in enumerate(split_sections(text)):
        body = "\n".join(sec["lines"]).strip("\n")
        if sec["heading"] and OPEN_QUESTIONS.match(sec["heading"]):
            qs = parse_questions(body, options)
            if qs:
                items.append(
                    {
                        "id": f"s{n}",
                        "heading": sec["heading"],
                        "level": sec["level"],
                        "body": "",
                        "questions": qs,
                        "comment": True,
                    }
                )
                continue
        items.append(
            {
                "id": f"s{n}",
                "heading": sec["heading"] or "Начало",
                "level": sec["level"] if sec["heading"] else 2,
                "body": body,
                "editable": True,
                "status": True,
                "comment": True,
            }
        )
    name = doc_title.group(1) if doc_title else Path(path).name
    return {
        "title": title or f"{name}: правки владельца",
        "intro": f"Документ `{path}`. Отметь каждый раздел, поправь текст прямо здесь, ответь на открытые вопросы. "
        "В конце нажми «Скопировать JSON для агента».",
        "task": f"Обнови {Path(path).name} по правкам владельца: примени markdown_new, учти comment у разделов, "
        "впиши ответы на открытые вопросы в соответствующие разделы и убери их из открытых. Разделы со статусом ask — "
        "вопросы владельца к агенту: ответь на них отдельно. Если decision = approve или approve_with_changes, "
        "после правки документ считается утвержденным.",
        "source": str(path),
        "file_stem": Path(path).stem,
        "decisions": DECISIONS,
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("doc")
    ap.add_argument("-o", "--out")
    ap.add_argument("--options")
    ap.add_argument("--title")
    args = ap.parse_args()
    options = (
        json.loads(Path(args.options).read_text(encoding="utf-8"))
        if args.options
        else {}
    )
    spec = build_spec(args.doc, options, args.title)
    text = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(Path(args.out).resolve())
    else:
        print(text)


if __name__ == "__main__":
    main()
