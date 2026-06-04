#!/usr/bin/env python3
"""
Gemini AI Code Review Script
3-stage review: Quality → Auto Test Cases → Structure
Generates full pass/fail report.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime

MAX_FILE_BYTES = 50_000

REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".scss", ".sass",
    ".java", ".go", ".rb", ".php", ".cs", ".rs"
}

# ─────────────────────────────────────────
# STAGE 1: Code Quality & Bug Detection
# ─────────────────────────────────────────
QUALITY_PROMPT = """
You are a senior software engineer doing strict automated code quality review.

Analyze the provided code and check for:
1. Bugs - logic errors, null pointer risks, off-by-one errors, unhandled exceptions
2. Security - hardcoded secrets, SQL injection, XSS, unsafe eval(), exposed credentials
3. Code Smells - duplicated code, magic numbers, overly long functions (>50 lines), deep nesting
4. Error Handling - missing try/catch, silent failures, unhandled promise rejections
5. Dead Code - unused variables, unreachable code, commented-out code blocks

Respond ONLY with this exact JSON (no markdown, no fences):
{
  "passed": true or false,
  "score": <0-100>,
  "summary": "<one sentence>",
  "bugs": ["<bug description>"],
  "security_issues": ["<issue>"],
  "code_smells": ["<smell>"],
  "dead_code": ["<location>"],
  "details": "<detailed markdown findings>"
}

RULES:
- passed=false if score < 70 OR any bug found OR any security issue found
- passed=true only if score >= 70 AND no bugs AND no security issues
"""

# ─────────────────────────────────────────
# STAGE 2: Auto-generate & Run Test Cases
# ─────────────────────────────────────────
TEST_GEN_PROMPT = """
You are a QA engineer. Based on the provided source code, generate comprehensive test cases
that cover the full code flow including edge cases.

For each function/component/endpoint found, create test scenarios covering:
1. Happy path (normal expected input)
2. Edge cases (empty, null, boundary values)
3. Error cases (invalid input, exceptions)
4. Integration points (API calls, DB operations, event handlers)

Then simulate running these tests against the code by carefully reading the logic.
Mark each test PASS or FAIL based on whether the code actually handles that case correctly.

Respond ONLY with this exact JSON (no markdown, no fences):
{
  "passed": true or false,
  "total_tests": <number>,
  "passed_tests": <number>,
  "failed_tests": <number>,
  "summary": "<one sentence>",
  "test_results": [
    {
      "test_name": "<name>",
      "description": "<what it tests>",
      "status": "PASS" or "FAIL",
      "reason": "<why it passed or failed>"
    }
  ],
  "details": "<overall test findings in markdown>"
}

RULES:
- passed=false if ANY test fails OR passed_tests/total_tests < 0.8
- passed=true only if all critical tests pass AND pass rate >= 80%
"""

# ─────────────────────────────────────────
# STAGE 3: Code Structure Review
# ─────────────────────────────────────────
STRUCTURE_PROMPT = """
You are a software architect doing a strict code structure review.

Analyze the code and check for:
1. File/Folder Organization - logical grouping, separation of concerns
2. Function Design - single responsibility, correct naming, appropriate size
3. Code Modularity - reusable components, no tight coupling
4. Naming Conventions - consistent naming (camelCase/snake_case), descriptive names
5. Documentation - missing docstrings, unclear variable names, no inline comments for complex logic
6. Dependency Management - circular imports, unnecessary dependencies, missing imports
7. Design Patterns - anti-patterns (god class, spaghetti code), missing abstractions

Respond ONLY with this exact JSON (no markdown, no fences):
{
  "passed": true or false,
  "score": <0-100>,
  "summary": "<one sentence>",
  "structure_issues": ["<issue>"],
  "naming_issues": ["<issue>"],
  "design_issues": ["<issue>"],
  "missing_docs": ["<location>"],
  "details": "<detailed markdown findings>"
}

RULES:
- passed=false if score < 70 OR more than 3 structure issues OR any design anti-pattern found
- passed=true if score >= 70 AND structure is clean
"""


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
            print(f"  Skipping {fp} (too large)")
            continue
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                contents[fp] = f.read()
        except Exception as e:
            print(f"  Cannot read {fp}: {e}")
    return contents


def build_code_block(file_contents: dict) -> str:
    parts = []
    for fp, content in file_contents.items():
        parts.append(f"\n### File: `{fp}`\n```\n{content}\n```\n")
    return "\n".join(parts)


def call_gemini(system_prompt: str, user_content: str) -> dict:
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_content}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Strip markdown fences if Gemini wraps response
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def run_stage(stage_num: int, name: str, prompt: str, code_block: str) -> dict:
    print(f"\n{'='*50}")
    print(f"  STAGE {stage_num}: {name}")
    print(f"{'='*50}")
    try:
        result = call_gemini(prompt, code_block)
        status = "✅ PASSED" if result.get("passed") else "❌ FAILED"
        print(f"  Result : {status}")
        print(f"  Summary: {result.get('summary', 'N/A')}")
        result["stage"] = stage_num
        result["stage_name"] = name
        return result
    except Exception as e:
        print(f"  ❌ Stage error: {e}")
        return {
            "stage": stage_num,
            "stage_name": name,
            "passed": False,
            "summary": f"Stage failed with error: {str(e)}",
            "details": str(e)
        }


def generate_report(file_contents: dict, stage_results: list) -> dict:
    total_stages = len(stage_results)
    passed_stages = sum(1 for s in stage_results if s.get("passed"))
    overall_passed = all(s.get("passed") for s in stage_results)

    # Collect test stats from stage 2
    test_stage = next((s for s in stage_results if s.get("stage") == 2), {})
    total_tests = test_stage.get("total_tests", 0)
    passed_tests = test_stage.get("passed_tests", 0)
    failed_tests = test_stage.get("failed_tests", 0)
    test_results = test_stage.get("test_results", [])

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "files_reviewed": list(file_contents.keys()),
        "overall_passed": overall_passed,
        "overall_summary": "All checks passed. Ready to deploy." if overall_passed else "Pipeline REJECTED. Fix issues before deploying.",
        "stages_passed": passed_stages,
        "stages_total": total_stages,
        "test_summary": {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pass_rate": f"{round(passed_tests / total_tests * 100)}%" if total_tests > 0 else "N/A"
        },
        "stage_results": stage_results,
        "test_cases": test_results,
        "passed": overall_passed,
        "summary": "All 3 stages passed." if overall_passed else f"Failed {total_stages - passed_stages} of {total_stages} stages."
    }
    return report


def print_final_report(report: dict):
    print(f"\n{'#'*60}")
    print(f"  FINAL REPORT")
    print(f"{'#'*60}")
    print(f"  Generated : {report['generated_at']}")
    print(f"  Files     : {', '.join(report['files_reviewed']) or 'None'}")
    print(f"  Stages    : {report['stages_passed']}/{report['stages_total']} passed")

    ts = report["test_summary"]
    if ts["total"] > 0:
        print(f"  Tests     : {ts['passed']}/{ts['total']} passed ({ts['pass_rate']})")

    print(f"\n  {'✅ PIPELINE APPROVED' if report['overall_passed'] else '❌ PIPELINE REJECTED'}")
    print(f"  {report['overall_summary']}")

    if report.get("test_cases"):
        print(f"\n  Test Cases:")
        for tc in report["test_cases"]:
            icon = "  ✅" if tc["status"] == "PASS" else "  ❌"
            print(f"  {icon} {tc['test_name']} — {tc['reason']}")

    for stage in report["stage_results"]:
        if not stage.get("passed"):
            print(f"\n  ── Stage {stage['stage']} failures ({stage['stage_name']}):")
            for key in ["bugs", "security_issues", "structure_issues", "design_issues"]:
                for item in stage.get(key, []):
                    print(f"     • {item}")

    print(f"\n{'#'*60}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        sys.exit(1)

    file_contents = read_changed_files(args.changed_files)

    if not file_contents:
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "files_reviewed": [],
            "overall_passed": True,
            "overall_summary": "No reviewable files changed.",
            "stages_passed": 3, "stages_total": 3,
            "test_summary": {"total": 0, "passed": 0, "failed": 0, "pass_rate": "N/A"},
            "stage_results": [], "test_cases": [],
            "passed": True, "summary": "No files to review."
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print("✅ No reviewable files. Pipeline approved.")
        sys.exit(0)

    print(f"\nFiles to review: {list(file_contents.keys())}")
    code_block = build_code_block(file_contents)

    # Run all 3 stages
    stage_results = [
        run_stage(1, "Code Quality & Bug Detection",   QUALITY_PROMPT,   code_block),
        run_stage(2, "Auto Test Cases & Flow Check",   TEST_GEN_PROMPT,  code_block),
        run_stage(3, "Code Structure Review",          STRUCTURE_PROMPT, code_block),
    ]

    report = generate_report(file_contents, stage_results)
    print_final_report(report)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    sys.exit(0 if report["overall_passed"] else 1)


if __name__ == "__main__":
    main()
