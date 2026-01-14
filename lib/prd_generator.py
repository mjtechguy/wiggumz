"""
Ralph PRD Generator Module

Generates comprehensive PRD.md files from interview results
and optional brownfield analysis.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


def generate_prd(
    mode: str,
    interview_results: Dict[str, Any],
    brownfield_doc: Optional[str] = None,
    target_path: Optional[Path] = None,
    claude_cmd: str = "claude --dangerously-skip-permissions",
    ralph_dir: Optional[Path] = None,
) -> str:
    """
    Generate PRD.md from interview results and optional brownfield analysis.

    Args:
        mode: "brownfield" or "greenfield"
        interview_results: Results from the interview
        brownfield_doc: BROWNFIELD.md content (for brownfield mode)
        target_path: Path to the codebase
        claude_cmd: Claude command to use
        ralph_dir: Path to Ralph directory

    Returns:
        Generated PRD.md content
    """
    if ralph_dir is None:
        ralph_dir = Path(__file__).parent.parent

    # Load the PRD generation prompt template
    prompt_file = ralph_dir / "lib" / "prompts" / "prd_generation.md"

    if prompt_file.exists():
        template = prompt_file.read_text()
    else:
        template = get_prd_generation_template()

    # Build the context
    context_parts = []

    if mode == "brownfield" and brownfield_doc:
        context_parts.append(f"## Brownfield Analysis\n\n{brownfield_doc}")

    if interview_results:
        context_parts.append(f"## Interview Results\n\n```json\n{json.dumps(interview_results, indent=2)}\n```")

    context = "\n\n".join(context_parts)

    # Replace placeholders in template
    template = template.replace("{MODE}", mode)
    template = template.replace("{CONTEXT}", context)
    template = template.replace("{TARGET_PATH}", str(target_path or "."))
    template = template.replace("{DATE}", datetime.now().strftime("%Y-%m-%d"))

    print("  Running Claude to generate PRD...")

    # Parse claude_cmd into list
    import shlex
    cmd_parts = shlex.split(claude_cmd)

    # Run Claude to generate the PRD
    try:
        result = subprocess.run(
            cmd_parts,
            input=template,
            capture_output=True,
            text=True,
            cwd=target_path or Path.cwd()
        )

        return result.stdout

    except subprocess.CalledProcessError as e:
        return f"Error generating PRD: {e}"


def get_prd_generation_template() -> str:
    """Get the PRD generation prompt template."""
    return """# PRD Generation Task

You are generating a comprehensive Product Requirements Document (PRD) for autonomous development.

## Mode: {MODE}

{CONTEXT}

## Your Task

Generate a complete `prd.md` file that follows this structure:

```markdown
# Feature Name - Product Requirements Document

**Version:** 1.0
**Date:** {DATE}
**Status:** Draft

---

## 1. Executive Summary

[Brief description of the feature/project and its purpose. What problem does it solve? Who benefits?]

---

## 2. Goals & Success Metrics

### Goals
- [Primary goal 1]
- [Primary goal 2]
- [Primary goal 3]

### Success Metrics
- [How will you measure success?]
- [What KPIs matter?]

---

## 3. User Personas

1. **[Persona Name]** - [Description of who they are and what they need]
2. **[Secondary Persona]** - [Description]

---

## 4. Feature Scope

### 4.1 MVP (Phase 1) - Core Feature

**Priority: HIGHEST**

[Description of the core MVP functionality]

| Feature | Description | Priority |
|---------|-------------|----------|
| [Feature 1] | [What it does] | P0 |
| [Feature 2] | [What it does] | P0 |

### 4.2 Phase 2 - Enhancements

**Priority: HIGH**

| Feature | Description | Priority |
|---------|-------------|----------|
| [Feature 3] | [What it does] | P1 |

### 4.3 Phase 3 - Nice to Have

**Priority: MEDIUM**

| Feature | Description | Priority |
|---------|-------------|----------|
| [Feature 4] | [What it does] | P2 |

---

## 5. Data Model

### 5.1 New Database Tables

[If applicable, include SQL table definitions]

### 5.2 New Types/Schemas

[Describe any new TypeScript types, interfaces, Pydantic models, etc.]

### 5.3 Data Shape

[If creating new data shapes for the data registry]

---

## 6. Technical Architecture

### 6.1 External APIs Required

| Endpoint | Method | Use Case | Notes |
|----------|--------|----------|-------|
| [Path] | [GET/POST/etc] | [Purpose] | [Notes] |

### 6.2 New API Functions

[Describe new functions needed with signatures]

### 6.3 Background Jobs

[If background jobs are needed, list them with descriptions]

### 6.4 File Structure

[Show the expected file structure for the implementation]

---

## 7. User Interface

### 7.1 Access Point

- URL: [Path to the feature]
- Navigation: [How users get here]

### 7.2 UI Wireframes

[Describe or sketch the UI layout]

---

## 8. API Routes

### 8.1 API Endpoints

[Describe API routes with method, path, input, output]

---

## 9. Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| [Edge case 1] | [How to handle it] |
| [Error condition] | [How to handle it] |

---

## 10. Security & Privacy

- Authentication: [How is access controlled?]
- Authorization: [Who can do what?]
- Data privacy: [What data is sensitive?]

---

## 11. Implementation Phases

### Phase 1: MVP
- [ ] [Task 1]
- [ ] [Task 2]

### Phase 2: Enhancements
- [ ] [Task 3]

### Phase 3: Polish
- [ ] [Task 4]

---

## 12. Open Questions

1. [Question that needs answering]
2. [Decision that needs to be made]

---

## 13. References

- [Link to related documentation]
- [Link to design files]
- [Link to existing code patterns]
```

## CRITICAL REQUIREMENTS

1. **Be EXTREMELY detailed.** This PRD will be used for autonomous development. The developer should not need to ask clarifying questions.

2. **Specify exact versions.** When mentioning technologies, include exact versions:
   - ✅ Good: "Next.js 15.5.0", "Python 3.12", "FastAPI 0.110.0"
   - ❌ Bad: "Next.js", "the latest version"

3. **Include specific file paths.** When describing implementation, specify exact paths where files should be created.

4. **Detail exact data structures.** Include types, field names, constraints.

5. **List all edge cases.** Think about error states, empty states, concurrent operations, etc.

6. **Specify testing approach.** What tests should be written? What level of coverage?

7. **Include build/run/test commands.** Exact commands that should work.

8. **Follow existing patterns.** If this is brownfield, reference existing code patterns to follow.

## For Brownfield Projects

- Focus on what's CHANGING, not the entire existing system
- Reference the brownfield analysis for context
- Specify which files/directories will be modified
- List new files to create alongside existing structure
- Maintain consistency with existing patterns

## For Greenfield Projects

- Provide complete technical specifications
- Include full stack details
- Specify all architectural decisions upfront
- Include initial project structure

Generate the complete PRD.md file now. Output only the PRD content, not a summary.
"""


def save_prd_template(project_name: str, output_dir: Path) -> Path:
    """
    Save a basic PRD template to the output directory.

    Args:
        project_name: Name of the project
        output_dir: Output directory path

    Returns:
        Path to the created PRD file
    """
    prd_path = output_dir / "prd.md"

    content = f"""# {project_name.title()} - Product Requirements Document

**Version:** 1.0
**Date:** {datetime.now().strftime("%Y-%m-%d")}
**Status:** Draft

---

## 1. Executive Summary

[Describe the feature/project and its purpose. What problem does it solve?]

---

## 2. Goals & Success Metrics

### Goals
-

### Success Metrics
-

---

## 3. User Personas

-

---

## 4. Feature Scope

### 4.1 MVP (Phase 1)

-

### 4.2 Phase 2

-

### 4.3 Phase 3

-

---

## 5. Data Model

-

---

## 6. Technical Architecture

-

---

## 7. User Interface

-

---

## 8. API Routes

-

---

## 9. Edge Cases & Error Handling

-

---

## 10. Security & Privacy

-

---

## 11. Implementation Phases

-

---

## 12. Open Questions

-

---

## 13. References

-
"""

    prd_path.write_text(content)
    return prd_path


# Export functions
__all__ = ["generate_prd", "save_prd_template"]
