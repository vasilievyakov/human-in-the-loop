#!/usr/bin/env python3
"""End-to-end check: build the three examples, click through in headless Chromium, check the exports.

Usage: python3 tests/selftest.py [screenshot_dir]   (needs playwright with chromium)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS, EX = ROOT / "scripts", ROOT / "examples"
OUT = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(tempfile.mkdtemp(prefix="human-in-the-loop-"))
)
OUT.mkdir(parents=True, exist_ok=True)


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True, capture_output=True)


def check(cond, msg):
    if not cond:
        sys.exit(f"FAIL: {msg}")
    print(f"ok  {msg}")


run(
    SCRIPTS / "from_markdown.py",
    EX / "spec-review/doc.md",
    "--options",
    EX / "spec-review/options.json",
    "-o",
    OUT / "review-spec.json",
)
run(
    SCRIPTS / "build.py",
    OUT / "review-spec.json",
    "-o",
    OUT / "review.html",
    "--no-open",
)
run(
    SCRIPTS / "build.py",
    EX / "gold-labeling/spec.json",
    "-o",
    OUT / "gold.html",
    "--no-open",
)
run(
    SCRIPTS / "build.py",
    EX / "spec-questions/spec.json",
    "-o",
    OUT / "questions.html",
    "--no-open",
)

with sync_playwright() as p:
    browser = p.chromium.launch()

    # document review: decision, statuses, edit text, open question, export JSON and Markdown
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((OUT / "review.html").as_uri())
    page.click("text=Утверждаю с правками ниже")
    cards = page.locator("section.card")
    cards.nth(1).locator("button", has_text="Согласен").click()
    edit_card = cards.nth(4)
    edit_card.locator("button", has_text="Править текст").click()
    edit_card.locator("textarea.src").fill("- новая строка")
    edit_card.locator("textarea.src").blur()
    q_card = page.locator("section.card", has=page.locator(".qs")).first
    q_card.locator("button.opt").first.click()
    q_card.locator("textarea[data-note]").nth(1).fill("свой ответ")
    exp = page.evaluate("exportJson()")
    md = page.evaluate("exportMd()")
    page.screenshot(path=str(OUT / "review.png"), full_page=False)
    check(not errors, f"review page: no console errors {errors}")
    check(exp["decision"] == "approve_with_changes", "review: decision exported")
    ids = {i["id"]: i for i in exp["items"]}
    check(any(i.get("status") == "ok" for i in exp["items"]), "review: status exported")
    check(
        any(
            i.get("markdown_new") == "- новая строка" and i.get("markdown_old")
            for i in exp["items"]
        ),
        "review: edited markdown exported with old text",
    )
    qi = next(i for i in exp["items"] if i.get("answers"))
    check(
        qi["answers"].get("q1") and qi["notes"].get("q2") == "свой ответ",
        "review: choice answer and free answer exported",
    )
    check(
        "- новая строка" in md and "Ответы владельца" in md,
        "review: markdown export has edit and answers",
    )
    check(
        set(exp)
        == {
            "task",
            "title",
            "spec_hash",
            "exported_at",
            "decision",
            "general_comment",
            "items",
        },
        "review: export keys",
    )
    page.reload()
    check(
        page.evaluate("exportJson()")["items"] == exp["items"],
        "review: state survives reload",
    )

    # gold labeling: yes/no reveals conditional questions, scale, progress, score.py on the export
    page = browser.new_page(viewport={"width": 1100, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((OUT / "gold.html").as_uri())
    first = lambda: page.locator("section.card").first
    check(
        first().locator("text=О какой компании").count() == 0,
        "gold: company hidden until AI = yes",
    )
    first().locator("button.opt", has_text="да").click()
    first().locator("button.opt", has_text="ни одной из списка").click()
    first().locator("button.opt", has_text="4 скорее хорошо").click()
    page.locator("section.card").nth(1).locator("button.opt", has_text="нет").click()
    stat = page.inner_text("#stat")
    page.screenshot(path=str(OUT / "gold.png"), full_page=False)
    exp = page.evaluate("exportJson()")
    check(not errors, f"gold page: no console errors {errors}")
    check("готово 2 из 30" in stat, f"gold: progress counts complete items ({stat})")
    check(
        exp["items"][0]["answers"] == {"ai": True, "company": "none", "tone": 4},
        "gold: answers exported with typed values",
    )
    check(
        exp["items"][1]["answers"] == {"ai": False},
        "gold: hidden questions not exported",
    )
    labels = OUT / "gold-labels.json"
    labels.write_text(json.dumps(exp, ensure_ascii=False))
    r = subprocess.run(
        [
            sys.executable,
            SCRIPTS / "score.py",
            labels,
            EX / "gold-labeling/sidecar.json",
            "--spec",
            EX / "gold-labeling/spec.json",
        ],
        capture_output=True,
        text=True,
    )
    check("ai" in r.stdout and "2" in r.stdout, "gold: score.py reads the page export")

    # questionnaire: choice, multi, own answer; export carries the task for the agent
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((OUT / "questions.html").as_uri())
    goal = page.locator("section.card").first
    goal.locator("button.opt", has_text="Команда").click()
    goal.locator("button.opt", has_text="Новость, а не мнение").click()
    goal.locator("button.opt", has_text="Вышла за последние сутки").click()
    goal.locator("textarea[data-note]").first.fill("команда продукта")
    page.screenshot(path=str(OUT / "questions.png"), full_page=False)
    exp = page.evaluate("exportJson()")
    check(not errors, f"questions page: no console errors {errors}")
    ans = exp["items"][0]["answers"]
    check(
        ans.get("reader") == "team" and sorted(ans.get("useful", [])) == ["fresh", "news"],
        "questions: choice and multi answers exported",
    )
    check(exp["task"].startswith("Ответы владельца"), "questions: task for the agent exported")
    browser.close()

# a broken spec fails loudly
bad = OUT / "bad.json"
bad.write_text(
    json.dumps({"items": [{"id": "a", "questions": [{"id": "x", "type": "slider"}]}]})
)
r = subprocess.run(
    [sys.executable, SCRIPTS / "build.py", bad, "-o", OUT / "bad.html", "--no-open"],
    capture_output=True,
    text=True,
)
check(
    r.returncode != 0 and "unknown question type" in r.stderr,
    "build: broken spec rejected",
)
print(f"\nALL PASS, screenshots in {OUT}")
