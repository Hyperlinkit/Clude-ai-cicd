#!/usr/bin/env python3
"""
Claude AI Code Review Script
Supports Python, JS, TS, HTML, CSS and more.
"""

import os
import sys
import json
import argparse
import anthropic

REVIEW_CRITERIA = """
You are a senior software engineer doing an automated code review.
Analyze the changed files across Python, JavaScript, TypeScript, HTML, and CSS.

Evaluate on:
1. Security - No secrets, injection risks, XSS vulnerabilities
2. Code Quality - No bugs, proper error handling, clean code
3. HTML - Semantic markup, accessibility (alt, aria, labels), no inline styles
4. CSS - No !important abuse, consistent units, no redundant rules
5. JavaScript - No console.log left in, proper async/await, no eval()
6. Performance - No blocking scripts, optimized assets, no memory leaks
7. Best Practices - Follows conventions, no dead code, DRY principles

Respond ONLY with a JSON object (no markdown fences):
{
  "passed": true or false,
  "score": <0-100>,
  "summary": "<one sentence>",
  "details": "<detailed findings in markdown>",
  "blocking_issues": ["<issue1>"],
  "warnings": ["<warning1>"],
  "suggestions": ["<suggestion1>"]
}

RULES:
- passed=false if score < 70 OR any critical security issue found
- passed=true if score >= 70 AND no critical security issues
"""

MAX_FILE_BYTES = 50_000

REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".scss", ".sass",
    ".java", ".go", ".rb", ".php", ".cs", ".rs"
}


def read_changed_files(path: str) -> dict:
    contents = {}
    if not os.path.exists(path):
        return contents
    with open(path) as f:
        files = [l.strip() for l in f if l.strip()]
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        if ext not in REVIEWABLE_EXTENSIONS:
            continue
        if not os.path.exists(fp):
            continue
        if os.path.getsize(fp) > MAX_FILE_BYTES:
            print(f"Skipping {fp} (too large)")
            continue
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                contents[fp] = f.read()
        except Exception as e:
            print(f"Cannot read {fp}: {e}")
    return contents


def build_prompt(file_contents: dict) -> str:
    if not file_contents:
        return "No reviewable files were changed."
    parts = ["Review these changed files:\n"]
    for fp, content in file_contents.items():
        parts.append(f"\n### `{fp}`\n```\n{content}\n```\n")
    return "\n".join(parts)


def run_review(file_contents: dict) -> dict:
    if not file_contents:
        return {
            "passed": True, "score": 100,
            "summary": "No reviewable files changed.",
            "details": "Nothing to review.", "blocking_issues": [],
            "warnings": [], "suggestions": []
        }

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print(f"Sending {len(file_contents)} file(s) to Claude...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=REVIEW_CRITERIA,
        messages=[{"role": "user", "content": build_prompt(file_contents)}]
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    file_contents = read_changed_files(args.changed_files)
    print(f"Files to review: {list(file_contents.keys())}")

    result = run_review(file_contents)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    status = "✅ PASSED" if result["passed"] else "❌ FAILED"
    print(f"\n{status} | Score: {result.get('score', 'N/A')}/100")
    print(f"Summary: {result['summary']}")

    if result.get("blocking_issues"):
        print("\n🚫 Blocking Issues:")
        for i in result["blocking_issues"]:
            print(f"  - {i}")

    if result.get("warnings"):
        print("\n⚠️  Warnings:")
        for w in result["warnings"]:
            print(f"  - {w}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
