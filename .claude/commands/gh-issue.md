Create a GitHub issue for: $ARGUMENTS

# GitHub Issue Conventions

## Issue Types

After creating the issue, set the type using:
`gh api -X PATCH repos/opensanctions/poliloom/issues/{number} --field type={Type}`

- **Bug**: Something isn't working correctly, security issues, broken behavior
- **Feature**: New functionality, enhancements, improvements, ideas
- **Task**: Maintenance, dependency updates, refactoring, questions/discussions

## Labels

Component labels (use one):
- **gui**: Frontend/interface issues (poliloom-gui)
- **loom**: Backend/core issues (poliloom Python)
- **map**: Mapping/scraper module issues (polimap)

Other labels:
- **question**: Signals that input/answer is requested

## Instructions

1. Create the issue with `gh issue create` including the appropriate component label
2. Set the issue type with `gh api -X PATCH`
3. Return the issue URL when done

Do NOT include any "Generated with Claude Code" or similar advertisements in the issue body.
