"""
Ralph Interviewer Module

Orchestrates the interview process using Claude Code CLI.
The interviewer invokes Claude which uses AskUserQuestion tool internally.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def conduct_interview(
    mode: str,
    brownfield_doc: Optional[str] = None,
    target_path: Optional[Path] = None,
    claude_cmd: str = "claude --dangerously-skip-permissions",
    ralph_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Conduct interview using Claude Code CLI.

    Args:
        mode: "brownfield" or "greenfield"
        brownfield_doc: BROWNFIELD.md content (for brownfield mode)
        target_path: Path to the codebase being analyzed
        claude_cmd: Claude command to use
        ralph_dir: Path to Ralph directory (for prompt templates)

    Returns:
        Dictionary of interview results
    """
    if ralph_dir is None:
        ralph_dir = Path(__file__).parent.parent

    # Build the interview prompt
    interview_prompt = build_interview_prompt(
        mode=mode,
        brownfield_doc=brownfield_doc,
        target_path=target_path,
        ralph_dir=ralph_dir
    )

    print("  Starting Claude interview...")
    print("  (Claude will ask you questions using AskUserQuestion)")
    print()

    # Parse claude_cmd into list
    import shlex
    cmd_parts = shlex.split(claude_cmd)

    # Run Claude with the interview prompt
    try:
        result = subprocess.run(
            cmd_parts,
            input=interview_prompt,
            capture_output=True,
            text=True,
            cwd=target_path or Path.cwd()
        )

        output = result.stdout

        # Parse the interview results from Claude's response
        interview_results = parse_interview_results(output)

        return interview_results

    except subprocess.CalledProcessError as e:
        print(f"Error running Claude: {e}")
        print(f"stderr: {e.stderr}")
        return {}
    except Exception as e:
        print(f"Error during interview: {e}")
        return {}


def build_interview_prompt(
    mode: str,
    brownfield_doc: Optional[str] = None,
    target_path: Optional[Path] = None,
    ralph_dir: Optional[Path] = None,
) -> str:
    """Build the interview prompt for Claude."""

    if ralph_dir is None:
        ralph_dir = Path(__file__).parent.parent

    # Load the appropriate interview prompt template
    if mode == "brownfield":
        prompt_file = ralph_dir / "lib" / "prompts" / "brownfield_interview.md"
    else:
        prompt_file = ralph_dir / "lib" / "prompts" / "greenfield_interview.md"

    if prompt_file.exists():
        template = prompt_file.read_text()
    else:
        # Fallback inline prompts
        if mode == "brownfield":
            template = get_brownfield_interview_template()
        else:
            template = get_greenfield_interview_template()

    # Replace placeholders
    context = ""
    if brownfield_doc:
        context = f"\n## Existing Codebase Context\n\nI've analyzed the codebase and created BROWNFIELD.md. Here's a summary:\n\n"
        context += brownfield_doc[:2000]  # First 2000 chars as preview
        context += "\n\n(Full BROWNFIELD.md is available for reference)"

    template = template.replace("{CONTEXT}", context)
    template = template.replace("{TARGET_PATH}", str(target_path or "."))

    return template


def parse_interview_results(output: str) -> Dict[str, Any]:
    """
    Parse interview results from Claude's response.

    Looks for <interview_results>...</interview_results> tags.

    Args:
        output: Claude's response text

    Returns:
        Parsed interview results as dictionary
    """
    # Try to extract JSON from interview_results tags
    pattern = r'<interview_results>\s*\n?(.*?)\n?</interview_results>'
    match = re.search(pattern, output, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: try to find any JSON in the output
    try:
        # Look for JSON objects
        json_match = re.search(r'\{[^{}]*\{.*\}[^{}]*\}', output, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except (json.JSONDecodeError, ValueError):
        pass

    # If no structured output, return basic info
    return {
        "raw_output": output,
        "parsed": False
    }


def get_brownfield_interview_template() -> str:
    """Get the brownfield interview prompt template."""
    return """# Ralph Interview - Brownfield Mode

You are conducting an interview for a **brownfield** project (modifying an existing codebase).

{CONTEXT}

## Your Task

Using the AskUserQuestion tool, interview the user about what changes they want to make to the existing codebase.

## Interview Flow

Ask questions in the following order, one section at a time:

### 1. High-Level Intent
**Ask:**
"What is the main change you want to make to this codebase? Is this:
- A new feature
- A refactor
- A bug fix
- Something else

Please describe what you want to accomplish."

### 2. Scope & Constraints
**Ask:**
"Regarding the scope of changes:
- Are there parts of the codebase that should NOT be modified?
- Are there existing patterns/components that MUST be reused?
- Should this change break any existing functionality?
- Any constraints or limitations I should know about?"

### 3. Functional Requirements
**Ask:**
"Let's detail the functional requirements:
- What should the new/changed behavior be?
- What are the inputs and expected outputs?
- What edge cases need to be handled?
- What does 'done' look like for this feature?"

### 4. Technical Requirements
**Ask:**
"Technical requirements:
- Are there specific libraries/packages that should be used?
- Any performance requirements?
- Security considerations?
- Should tests be written? What level of coverage?
- Should documentation be updated?"

### 5. UI Changes (Conditional)
**If the change involves UI:**
- Describe the UI changes needed
- Are there existing UI components to follow?
- Any design mockups or references?
- Mobile/responsive considerations?

### 6. Data/API Changes (Conditional)
**If the change involves data models:**
- What data models need to be created/modified?
- Database migrations needed?
- What relationships exist between entities?

**If the change involves APIs:**
- What endpoints need to be created/modified?
- Request/response formats?
- Authentication/authorization requirements?

### 7. Confirmation
**Present a summary:**
"Here's what I understand you want to do:
- [Summary of changes]
- [Scope constraints]
- [Key requirements]

Is this correct? Would you like to add, change, or clarify anything?"

## Output Format

After the interview is complete, output your results as JSON inside <interview_results> tags:

```json
<interview_results>
{
  "mode": "brownfield",
  "project_type": "...",
  "high_level_intent": "...",
  "scope_constraints": "...",
  "functional_requirements": ["...", "..."],
  "technical_requirements": {
    "libraries": [...],
    "performance": "...",
    "security": "...",
    "testing": "..."
  },
  "ui_changes": {  "if applicable": "..." },
  "data_changes": {  "if applicable": "..." },
  "api_changes": {  "if applicable": "..." },
  "user_confirmed": true/false,
  "additional_notes": "..."
}
</interview_results>
```

## Important Notes

- Be thorough but efficient. Most interviews should take 5-10 questions total.
- After each answer, confirm understanding before moving on.
- If the user gives a vague answer, ask a focused follow-up.
- The goal is to gather enough detail for autonomous development.

Begin the interview now.
"""


def get_greenfield_interview_template() -> str:
    """Get the greenfield interview prompt template."""
    return """# Ralph Interview - Greenfield Mode

You are conducting an interview for a **greenfield** project (building something new).

## Your Task

Using the AskUserQuestion tool, interview the user about what they want to build.

## Interview Flow

Ask questions in the following order, one section at a time:

### 1. Project Concept
**Ask:**
"What are you building? Please describe:
- What is the main purpose of this project?
- What problem does it solve?
- Who are the primary users?
- What makes this project unique or valuable?"

### 2. Features
**Ask:**
"What features should this project have?

For each feature, please tell me:
- What does it do?
- How will users interact with it?
- What makes this feature complete?

Please list all features you have in mind, even if they're 'nice to have'."

### 3. Technology Stack
**Ask:**
"What technology stack should be used?

Please specify:
- Language/runtime (e.g., Python 3.12, Node.js 20, Rust)
- Framework (e.g., FastAPI, Next.js, Django)
- Database (if any) (e.g., PostgreSQL, MongoDB, SQLite)
- Frontend framework (if applicable) (e.g., React, Vue, Svelte)
- Key libraries you want to use

If you're unsure, I can suggest based on your requirements."

### 4. Architecture
**Ask:**
"Let's define the architecture:
- Is this a web app, CLI tool, library, API, or something else?
- Should it be a monorepo or single package?
- Any specific architectural patterns to follow? (MVC, clean architecture, etc.)
- Any external services/integrations needed?"

### 5. Data Models (Conditional)
**If the project has data:**
"What data needs to be stored?

For each data entity:
- What are the main fields/properties?
- What are the relationships between entities?
- Any validation requirements?"

### 6. User Interface (Conditional)
**If the project has a UI:**
"For the user interface:
- What are the main pages/screens?
- How should users navigate through the app?
- Any specific design preferences or references?
- Mobile responsiveness requirements?"

### 7. Non-Functional Requirements
**Ask:**
"Non-functional requirements:
- Performance: Any specific requirements? (response times, throughput, etc.)
- Security: Authentication, authorization, data protection needs?
- Deployment: Where will this run? Any constraints?
- Monitoring/logging requirements?"

### 8. Confirmation
**Present a summary:**
"Here's what I understand about your project:
- [Project concept]
- [Key features]
- [Tech stack]
- [Architecture]

Does this look right? Would you like to add, change, or clarify anything?"

## Output Format

After the interview is complete, output your results as JSON inside <interview_results> tags:

```json
<interview_results>
{
  "mode": "greenfield",
  "project_name": "...",
  "project_concept": "...",
  "purpose": "...",
  "target_users": "...",
  "features": [
    {
      "name": "...",
      "description": "...",
      "user_interaction": "...",
      "acceptance_criteria": "..."
    }
  ],
  "tech_stack": {
    "language": "...",
    "framework": "...",
    "database": "...",
    "frontend": "...",
    "key_libraries": [...]
  },
  "architecture": {
    "type": "...",
    "structure": "...",
    "patterns": [...],
    "integrations": [...]
  },
  "data_models": [  "if applicable": "..." ],
  "ui_design": {  "if applicable": "..." },
  "non_functional": {
    "performance": "...",
    "security": "...",
    "deployment": "..."
  },
  "user_confirmed": true/false,
  "additional_notes": "..."
}
</interview_results>
```

## Important Notes

- Be thorough but efficient. Most interviews should take 5-10 questions total.
- After each answer, confirm understanding before moving on.
- If the user gives a vague answer, ask a focused follow-up.
- The goal is to gather enough detail for autonomous development.

Begin the interview now.
"""


# Export the main function
__all__ = ["conduct_interview"]
