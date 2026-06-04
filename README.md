# CI/CD Pipeline with Claude AI Review

Automated pipeline: tests → Claude AI code review → deploy.

## How it works

1. **Tests** — pytest runs on every push
2. **Claude AI Review** — changed `.py`, `.js`, `.ts`, `.html`, `.css` files are sent to Claude API for review. Score < 70 or any security issue = deployment blocked.
3. **Deploy** — SSH deploy to your server only if both above pass.

## Setup

### 1. Add GitHub Secrets
Go to **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |
| `SERVER_HOST` | Your server IP or domain |
| `SERVER_USER` | SSH username (e.g. `ubuntu`) |
| `SERVER_SSH_KEY` | Your private SSH key |
| `SERVER_PORT` | Usually `22` |

### 2. Update deploy path
Edit `scripts/deploy.sh` and set `APP_DIR` and `APP_SERVICE` to match your server.

### 3. Push to main
Every push to `main` triggers the full pipeline.

## Folder structure

```
.github/workflows/ci-cd.yml   ← Pipeline definition
scripts/
  claude_test_review.py       ← Claude AI reviewer
  deploy.sh                   ← SSH deploy script
src/                          ← Your Python source
tests/                        ← pytest test files
public/
  index.html                  ← HTML (reviewed by Claude)
  css/styles.css              ← CSS (reviewed by Claude)
  js/main.js                  ← JS (reviewed by Claude)
requirements.txt
```
