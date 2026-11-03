#!/usr/bin/env python3
"""Build a one-off feedback page from a spec JSON.

Usage: build.py spec.json -o page.html [--no-open]

The page is self-contained (no network), keeps the owner's answers in localStorage keyed by
the spec hash, and exports JSON (and Markdown when some blocks are editable) back to the agent.
Spec format: references/spec-format.md.
"""

import argparse
import hashlib
import json
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
TYPES = {"choice", "multi", "scale", "yesno", "text"}


class SpecError(ValueError):
    pass


def norm_options(q):
    out = []
    for o in q.get("options", []):
        if isinstance(o, dict):
            if "value" not in o:
                raise SpecError(f"question {q['id']}: option without value: {o}")
            out.append({"value": o["value"], "label": str(o.get("label", o["value"]))})
        else:
            out.append({"value": o, "label": str(o)})
    return out


def validate(spec):
    """Fail loudly on a broken spec; fill defaults so the page code stays simple."""
    if not isinstance(spec.get("items"), list) or not spec["items"]:
        raise SpecError("spec.items must be a non-empty list")
    spec.setdefault("title", "Обратная связь")
    spec.setdefault("intro", "")
    spec.setdefault(
        "task",
        "Примени ответы владельца из items. Каждый item содержит только то, что владелец тронул.",
    )
    spec.setdefault("decisions", [])
    spec.setdefault("general_comment", True)
    defaults = spec.setdefault("item_defaults", {})
    seen = set()
    for n, item in enumerate(spec["items"], 1):
        item["id"] = str(item.get("id", f"i{n}"))
        if item["id"] in seen:
            raise SpecError(f"duplicate item id {item['id']}")
        seen.add(item["id"])
        item.setdefault("n", n)
        item.setdefault("heading", "")
        item.setdefault("level", 2)
        item.setdefault("body", "")
        for key in ("editable", "status", "comment", "collapse"):
            item.setdefault(key, defaults.get(key, key == "comment"))
        qids = set()
        for q in item.setdefault("questions", []):
            if q.get("type") not in TYPES:
                raise SpecError(
                    f"item {item['id']}: unknown question type {q.get('type')!r}, expected {sorted(TYPES)}"
                )
            if not q.get("id"):
                raise SpecError(f"item {item['id']}: question without id")
            if q["id"] in qids:
                raise SpecError(f"item {item['id']}: duplicate question id {q['id']}")
            qids.add(q["id"])
            q.setdefault("label", q["id"])
            q.setdefault("required", q["type"] != "text")
            if q["type"] in ("choice", "multi"):
                q["options"] = norm_options(q)
                if not q["options"] and not q.get("free"):
                    raise SpecError(
                        f"question {q['id']}: choice without options and without free answer"
                    )
            if q["type"] == "scale":
                if len(q.get("levels", [])) < 2:
                    raise SpecError(
                        f"question {q['id']}: scale needs at least two levels"
                    )
                q.setdefault("start", 1)
            cond = q.get("show_if")
            if cond and (cond.get("question") not in qids or "equals" not in cond):
                raise SpecError(
                    f"question {q['id']}: show_if must name an earlier question and give equals"
                )
    spec["markdown_export"] = any(i["editable"] for i in spec["items"])
    return spec


def spec_hash(spec):
    return hashlib.sha1(
        json.dumps(spec, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:10]


def build(spec, out):
    spec = validate(spec)
    spec["spec_hash"] = spec_hash(spec)
    data = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(
        TEMPLATE.read_text(encoding="utf-8").replace("__SPEC__", data), encoding="utf-8"
    )
    return spec


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    try:
        spec = build(
            json.loads(Path(args.spec).read_text(encoding="utf-8")), Path(args.out)
        )
    except (SpecError, json.JSONDecodeError) as error:
        sys.exit(f"spec error: {error}")
    out = Path(args.out).resolve()
    questions = sum(len(i["questions"]) for i in spec["items"])
    print(
        f"{out}\nitems={len(spec['items'])} questions={questions} hash={spec['spec_hash']}"
    )
    if not args.no_open:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
