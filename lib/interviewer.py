"""
Ralph Interviewer Module

Generates a prompt that users can paste into Claude to conduct the interview.
"""

import json
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
    Generate a pasteable interview prompt for Claude.

    Args:
        mode: "brownfield" or "greenfield"
        brownfield_doc: BROWNFIELD.md content (for brownfield mode)
        target_path: Path to the codebase being analyzed
        claude_cmd: Claude command to use (unused, for compatibility)
        ralph_dir: Path to Ralph directory (for prompt templates)

    Returns:
        Dictionary with interview results (placeholder for now)
    """
    if ralph_dir is None:
        ralph_dir = Path(__file__).parent.parent

    work_dir = target_path or Path.cwd()

    # Build the complete pasteable prompt
    pasteable_prompt = build_pasteable_prompt(
        mode=mode,
        brownfield_doc=brownfield_doc,
        target_path=work_dir,
        ralph_dir=ralph_dir
    )

    # Write to file for user to reference
    prompt_file = work_dir / ".ralph_interview_prompt.md"
    prompt_file.write_text(pasteable_prompt)

    print()
    print("=" * 60)
    print("  Interview Prompt Ready")
    print("=" * 60)
    print()
    print("  Paste the following into Claude at the root of your project:")
    print()
    print("-" * 60)
    print(pasteable_prompt)
    print("-" * 60)
    print()
    print(f"  Prompt also saved to: {prompt_file}")
    print()
    print("  After Claude completes the interview, it will write the PRD.")
    print()

    # Wait for user to confirm they've completed the interview
    try:
        input("  Press Enter when you've completed the interview in Claude...")
    except (EOFError, KeyboardInterrupt):
        print("\n  Continuing...")
    print()

    # Return a placeholder result
    return {
        "mode": mode,
        "manual_interview": True,
        "status": "prompt_generated"
    }


def build_pasteable_prompt(
    mode: str,
    brownfield_doc: Optional[str] = None,
    target_path: Optional[Path] = None,
    ralph_dir: Optional[Path] = None,
) -> str:
    """
    Build the complete pasteable prompt for Claude.

    Args:
        mode: "brownfield" or "greenfield"
        brownfield_doc: BROWNFIELD.md content (for brownfield mode)
        target_path: Path to the codebase being analyzed
        ralph_dir: Path to Ralph directory (for prompt templates)

    Returns:
        Complete prompt string ready to paste into Claude
    """
    if ralph_dir is None:
        ralph_dir = Path(__file__).parent.parent

    work_dir = target_path or Path.cwd()

    # Start with clear instructions
    prompt = """# Wiggumz PRD Interview

You are conducting an interview to generate a Product Requirements Document (PRD).

## Setup

First, read the following context files to understand the project:
"""

    # Add references to files Claude should read
    files_to_read = []

    # 1. CLAUDE.md if it exists (user's project-specific instructions)
    claude_md = work_dir / "CLAUDE.md"
    if claude_md.exists():
        files_to_read.append(f"1. Read `{claude_md}` - This project's specific development guidelines")

    # 2. BROWNFIELD.md if in brownfield mode
    if mode == "brownfield" and brownfield_doc:
        brownfield_file = work_dir / "BROWNFIELD.md"
        files_to_read.append(f"2. Read `{brownfield_file}` - Analysis of the existing codebase")

    if not files_to_read:
        files_to_read.append("1. Explore the codebase to understand the project structure")

    for file_ref in files_to_read:
        prompt += f"\n{file_ref}\n"

    # Add the interview instructions
    prompt += f"""

## Interview Mode

This is a **{mode.upper()}** project.
"""

    if mode == "brownfield":
        prompt += """

You are helping to define changes to an existing codebase.

Using the AskUserQuestion tool, interview the user about what changes they want to make.

### Interview Questions

Ask these questions one at a time:

1. **What is the main change?**
   - New feature, refactor, bug fix, or something else?
   - What do you want to accomplish?

2. **Scope & Constraints**
   - Are there parts of the codebase that should NOT be modified?
   - Are there existing patterns that MUST be reused?
   - Any constraints or limitations?

3. **Functional Requirements**
   - What should the new/changed behavior be?
   - Inputs and expected outputs?
   - What does "done" look like?

4. **Technical Requirements**
   - Specific libraries/packages to use?
   - Performance or security requirements?
   - Testing requirements?

5. **UI/Data/API Changes** (if applicable)
   - What UI changes are needed?
   - What data models or API endpoints need to change?

6. **Confirmation**
   - Summarize what you understood
   - Ask if anything needs to be clarified
"""

    else:  # greenfield
        prompt += """

You are helping to define a new project from scratch.

Using the AskUserQuestion tool, interview the user about what they want to build.

### Interview Questions

Ask these questions one at a time:

1. **What are you building?**
   - Main purpose of the project?
   - What problem does it solve?
   - Who are the primary users?

2. **Features**
   - What features should the project have?
   - For each feature: what does it do, how do users interact with it?

3. **Technology Stack**
   - Language/runtime (e.g., Python 3.12, Node.js 20, Rust)
   - Framework (e.g., FastAPI, Next.js, Django)
   - Database (if any)
   - Frontend framework (if applicable)
   - Key libraries to use

4. **Architecture**
   - Web app, CLI tool, library, API, or something else?
   - Any specific architectural patterns?
   - External services/integrations needed?

5. **Data Models** (if applicable)
   - What data needs to be stored?
   - What are the main entities and relationships?

6. **User Interface** (if applicable)
   - Main pages/screens?
   - Navigation structure?
   - Design preferences?

7. **Non-Functional Requirements**
   - Performance, security, deployment requirements?

8. **Confirmation**
   - Summarize what you understood
   - Ask if anything needs to be clarified
"""

    # Add output instructions
    prd_location = work_dir / "prd.md"

    prompt += f"""

## Output

After completing the interview, generate a comprehensive PRD and write it to:

**`{prd_location}`**

Use the Write tool to save the PRD.

### PRD Structure

The PRD should include:

1. **Overview** - Project name, purpose, target users
2. **Features** - Detailed feature descriptions with acceptance criteria
3. **Technical Requirements** - Tech stack, libraries, architecture
4. **Data Models** (if applicable) - Entities, relationships, validation
5. **API Endpoints** (if applicable) - Routes, request/response formats
6. **UI/UX** (if applicable) - Page structure, components, interactions
7. **Success Criteria** - How to know when the project is complete

---

Begin the interview now. Start by reading any context files, then use AskUserQuestion.
"""

    return prompt


# Legacy functions for compatibility
def build_interview_prompt(
    mode: str,
    brownfield_doc: Optional[str] = None,
    target_path: Optional[Path] = None,
    ralph_dir: Optional[Path] = None,
) -> str:
    """Build the interview prompt for Claude (legacy, use build_pasteable_prompt)."""
    return build_pasteable_prompt(mode, brownfield_doc, target_path, ralph_dir)


def parse_interview_results(output: str) -> Dict[str, Any]:
    """Placeholder for compatibility."""
    return {"manual_interview": True}


def get_brownfield_interview_template() -> str:
    """Placeholder for compatibility."""
    return ""


def get_greenfield_interview_template() -> str:
    """Placeholder for compatibility."""
    return ""


# Export the main function
__all__ = ["conduct_interview", "build_pasteable_prompt"]
