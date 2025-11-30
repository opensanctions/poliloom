---
name: gh-issue
description: Use when creating, editing, or managing GitHub issues. Provides issue type and label conventions for this project.
---

# GitHub Issue Management

## Issue Types

Set the issue type using `gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field type={Type}`:

- **Bug**: Something isn't working correctly, security issues, broken behavior
- **Feature**: New functionality, enhancements, improvements, ideas
- **Task**: Maintenance, dependency updates, refactoring, questions/discussions

## Labels

Component labels:
- **gui**: Frontend/interface issues (poliloom-gui)
- **loom**: Backend/core issues (poliloom Python)
- **map**: Mapping/scraper module issues (polimap)

Other labels:
- **question**: Signals that input/answer is requested

## Creating an Issue

```bash
# Create issue with label
gh issue create \
  --title "Issue title" \
  --body "Description" \
  --label "loom"

# Set the type if appropriate (gh issue create doesn't support types yet)
gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field type=Bug
```
