"""Prompt templates for WorkClaw's AI agent."""

SYSTEM_PROMPT = """\
You are WorkClaw, an AI-powered developer assistant. You help developers by:

1. **Understanding Requirements**: Reading Jira stories and translating them into actionable technical tasks.
2. **Analyzing Code**: Reading codebases from GitHub or Bitbucket, understanding architecture, and identifying areas for improvement.
3. **Suggesting Improvements**: Finding bugs, refactoring opportunities, and code quality issues.
4. **Making Changes**: Modifying code to implement features, fix bugs, or refactor — then submitting pull requests.

## Your Capabilities
You have access to tools that let you:
- Read and write files
- Execute git operations (clone, branch, commit, push)
- Interact with GitHub/Bitbucket APIs (read repos, create PRs)
- Interact with Jira (read stories, update status, add comments)
- Run shell commands for building and testing
- Analyze code for bugs and refactoring opportunities

## Your Behavior
- Always explain your reasoning before taking actions
- Ask for confirmation before making irreversible changes (creating PRs, pushing code)
- Provide clear, structured reports when analyzing code
- When modifying code, show diffs and explain each change
- Be proactive: suggest improvements even when not explicitly asked
- Keep responses concise but thorough

## Output Format
- Use Markdown formatting for structured output
- Use code blocks with language identifiers for code
- Use tables for structured comparisons
- Use bullet points for lists of findings

## Project Code Analysis
When project code analysis context is provided, use it to understand the full codebase
architecture before suggesting changes. Reference specific repos, files, and patterns
from the analysis.
"""

ANALYZE_CODE_PROMPT = """\
Analyze the following code file and provide:

1. **Summary**: What this file does and its role in the project
2. **Code Quality**: Rate overall quality (1-10) with justification
3. **Issues Found**: List any bugs, security vulnerabilities, or logic errors
4. **Refactoring Opportunities**: Suggest improvements for readability, performance, or maintainability
5. **Best Practices**: Note any deviations from language/framework best practices

File: {file_path}
Language: {language}

```{language}
{code_content}
```

{additional_context}
"""

REFACTOR_PROMPT = """\
Review the following code and suggest specific refactoring improvements:

Focus on:
- Code duplication
- Long methods/functions that should be split
- Complex conditionals that can be simplified
- Unused imports or dead code
- Better naming for variables/functions/classes
- Design pattern opportunities
- Performance optimizations

For each suggestion:
1. Describe the issue
2. Show the current code
3. Show the refactored code
4. Explain the benefit

File: {file_path}

```{language}
{code_content}
```
"""

BUG_DETECT_PROMPT = """\
Carefully analyze the following code for potential bugs and security issues:

Look for:
- Null/None reference errors
- Off-by-one errors
- Resource leaks (unclosed files, connections)
- Race conditions
- SQL injection or other injection vulnerabilities
- Unhandled exceptions
- Type mismatches
- Logic errors in conditionals
- Edge cases not handled
- API misuse

For each bug found:
1. Location (line number or code snippet)
2. Severity (Critical / High / Medium / Low)
3. Description of the issue
4. Suggested fix

File: {file_path}

```{language}
{code_content}
```
"""

PR_DESCRIPTION_PROMPT = """\
Generate a pull request description for the following changes:

Jira Story: {jira_key} - {jira_summary}
Branch: {branch_name}
Target: {target_branch}

Changes made:
{changes_summary}

Files modified:
{files_changed}

Generate a PR description with:
1. **Title**: Clear, concise PR title
2. **Description**: What was changed and why
3. **Changes**: Bullet list of specific changes
4. **Testing**: How to test these changes
5. **Jira Link**: Link to the story
"""

JIRA_ANALYSIS_PROMPT = """\
Analyze the following Jira story and create a technical implementation plan:

Story Key: {issue_key}
Summary: {summary}
Description:
{description}

Acceptance Criteria:
{acceptance_criteria}

Repository: {repo_info}

Please provide:
1. **Understanding**: Restate the requirements in technical terms
2. **Files to Modify**: List specific files that likely need changes
3. **Implementation Steps**: Ordered list of changes to make
4. **Edge Cases**: Any edge cases to consider
5. **Testing Strategy**: How to verify the implementation
6. **Risks**: Potential risks or concerns
"""

PROJECT_CONSOLIDATION_PROMPT = """\
You are analyzing a multi-repository project. Given per-repo analysis summaries,
produce a unified architectural overview.

Project: {project_name}
Description: {project_description}

Per-repo summaries:
{repo_summaries}

Provide:
1. **Architecture Overview** — How the repos relate and interact
2. **Cross-Repository Patterns** — Shared patterns, duplicated logic, or common libraries
3. **Dependency Map** — How repos depend on each other or shared services
4. **Technology Stack** — Consolidated view of languages, frameworks, and tools
5. **Top 5 Recommendations** — Actionable improvements across the project
"""

PROJECT_STORY_ANALYSIS_PROMPT = """\
Using project analysis for "{project_name}":

{project_analysis_summary}

Create an implementation plan for Jira story {issue_key}:
Summary: {summary}
Description: {description}
Acceptance Criteria: {acceptance_criteria}

Provide:
1. **Affected Repositories** — Which repos need changes
2. **Files to Modify** — Specific files in each repo
3. **Implementation Steps** — Cross-repo ordered changes
4. **Cross-repo Impact** — How changes propagate across repos
5. **Testing Strategy** — How to verify across all affected repos
6. **Risks** — Potential risks and mitigations
"""
