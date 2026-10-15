# AGENTS.md

## Code formatting
- Indent with 4 spaces.
- Follow PEP 8 for naming and imports; keep the existing double-quoted strings.
- Wrap long calls, literals, and signatures so each element sits on its own line, with the closing bracket on its own line, instead of aligning continuation lines under the opening bracket.
- Separate logical chunks of code with a blank line: a block of variable definitions from the code after it, a blank line before a `return` at the end of a function (unless it is the only statement in the function), and between conditional statement blocks (`if`/`elif`/`else`, `for`, `while`, `try`) and the code around them.
- Use two blank lines between top-level definitions and one blank line between methods.

## Git
Do not run git commands that change local files or git history (for example add, commit, checkout, switch, merge, rebase, reset, stash, branch, worktree, or push). Read-only commands such as git status, git diff, and git log are fine. Only run a state-changing git command when the user explicitly asks for it in their message.
