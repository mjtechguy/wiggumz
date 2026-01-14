# Ralph Interview - Brownfield Mode

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

After the interview is complete, output your results as JSON inside `<interview_results>` tags:

```json
<interview_results>
{
  "mode": "brownfield",
  "project_type": "...",
  "high_level_intent": "...",
  "change_type": "new feature|refactor|bug fix|other",
  "scope_constraints": "...",
  "do_not_modify": [...],
  "must_reuse": [...],
  "functional_requirements": [
    {
      "requirement": "...",
      "input": "...",
      "output": "...",
      "edge_cases": [...],
      "acceptance_criteria": "..."
    }
  ],
  "technical_requirements": {
    "libraries": [...],
    "performance": "...",
    "security": "...",
    "testing": "...",
    "documentation": "..."
  },
  "ui_changes": {
    "has_ui": true/false,
    "description": "...",
    "follow_existing": true/false,
    "mockups": "...",
    "responsive": "..."
  },
  "data_changes": {
    "has_data_changes": true/false,
    "new_models": [...],
    "modified_models": [...],
    "migrations_needed": true/false,
    "relationships": "..."
  },
  "api_changes": {
    "has_api_changes": true/false,
    "new_endpoints": [...],
    "modified_endpoints": [...],
    "auth_requirements": "..."
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
