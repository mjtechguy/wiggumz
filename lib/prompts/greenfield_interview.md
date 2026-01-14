# Ralph Interview - Greenfield Mode

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

After the interview is complete, output your results as JSON inside `<interview_results>` tags:

```json
<interview_results>
{
  "mode": "greenfield",
  "project_name": "...",
  "project_concept": "...",
  "purpose": "...",
  "target_users": "...",
  "unique_value": "...",
  "features": [
    {
      "name": "...",
      "description": "...",
      "user_interaction": "...",
      "acceptance_criteria": "...",
      "priority": "P0|P1|P2"
    }
  ],
  "tech_stack": {
    "language": "...",
    "language_version": "...",
    "framework": "...",
    "framework_version": "...",
    "database": "...",
    "database_version": "...",
    "frontend": "...",
    "frontend_version": "...",
    "key_libraries": [
      {"name": "...", "version": "...", "purpose": "..."}
    ]
  },
  "architecture": {
    "type": "web app|CLI tool|library|API|other",
    "structure": "monorepo|single package",
    "patterns": [...],
    "integrations": [...]
  },
  "data_models": [
    {
      "name": "...",
      "fields": [{"name": "...", "type": "..."}],
      "relationships": "...",
      "validation": "..."
    }
  ],
  "ui_design": {
    "has_ui": true/false,
    "main_pages": [...],
    "navigation": "...",
    "design_preference": "...",
    "responsive": true/false
  },
  "non_functional": {
    "performance": "...",
    "security": {
      "authentication": "...",
      "authorization": "...",
      "data_protection": "..."
    },
    "deployment": "...",
    "monitoring": "..."
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
