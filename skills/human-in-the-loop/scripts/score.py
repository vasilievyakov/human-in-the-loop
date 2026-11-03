#!/usr/bin/env python3
"""Blind mode: compare the owner's labels with hidden answers kept in a sidecar file.

Usage: score.py labels.json sidecar.json [--spec spec.json] [--threshold 90]

labels.json  - JSON exported from the page (items[].answers), or a path to it.
sidecar.json - {"answers": {"<item id>": {"<question id>": value, ...}}}; the page never sees it.
--spec       - optional; applies show_if to both sides (a question counts only where both sides show it)
               and adds +-1 agreement for scale questions.

Prints agreement per question and every disagreement. Exit code 1 if any question is below the threshold.
"""

import argparse
import json
import sys
from pathlib import Path


def shown(q, answers):
    cond = (q or {}).get("show_if")
    return not cond or answers.get(cond["question"]) == cond["equals"]


def score(labels, sidecar, spec=None):
    questions, headings = {}, {}
    if spec:
        for item in spec["items"]:
            headings[str(item.get("id"))] = item.get("heading", "")
            for q in item.get("questions", []):
                questions.setdefault(q["id"], q)
    hidden = sidecar["answers"]
    rows, near, misses = {}, {}, []
    for item in labels["items"]:
        mine = item.get("answers", {})
        theirs = hidden.get(str(item["id"]))
        if theirs is None:
            continue
        for qid, value in mine.items():
            if qid not in theirs or theirs[qid] is None or value is None:
                continue
            q = questions.get(qid)
            if q and not (shown(q, mine) and shown(q, theirs)):
                continue
            other = theirs[qid]
            same = (
                sorted(value) == sorted(other)
                if isinstance(value, list)
                else value == other
            )
            rows.setdefault(qid, []).append(same)
            if q and q.get("type") == "scale":
                near.setdefault(qid, []).append(abs(value - other) <= 1)
            if not same:
                misses.append(
                    f"{item['id']} {(item.get('heading') or headings.get(str(item['id']), ''))[:50]!r} {qid}: владелец {value!r}, скрытый ответ {other!r}"
                )
    return rows, near, misses


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("labels")
    ap.add_argument("sidecar")
    ap.add_argument("--spec")
    ap.add_argument("--threshold", type=float, default=90)
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    rows, near, misses = score(
        load(args.labels), load(args.sidecar), load(args.spec) if args.spec else None
    )
    if not rows:
        sys.exit("нет пар для сравнения: проверь id в labels и sidecar")
    below = False
    for qid, oks in rows.items():
        pct = 100 * sum(oks) / len(oks)
        below |= pct < args.threshold
        line = f"{qid:16} {sum(oks)}/{len(oks)} = {pct:.0f}%"
        if qid in near:
            line += f"   +-1: {sum(near[qid])}/{len(near[qid])} = {100 * sum(near[qid]) / len(near[qid]):.0f}%"
        print(
            line
            + ("" if pct >= args.threshold else f"   ниже порога {args.threshold:.0f}%")
        )
    print("\nРасхождения:" if misses else "\nРасхождений нет.")
    for m in misses:
        print("  " + m)
    sys.exit(1 if below else 0)


if __name__ == "__main__":
    main()
