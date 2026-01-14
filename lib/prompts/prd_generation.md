# PRD Generation Task

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

```sql
-- Example table
CREATE TABLE example_table (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  config JSONB NOT NULL DEFAULT '{}',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

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

```
[path/to/structure]
├── directory/
│   └── file.ts
```

---

## 7. User Interface

### 7.1 Access Point

- URL: [Path to the feature]
- Navigation: [How users get here]

### 7.2 UI Wireframes

[Describe or sketch the UI layout]

**Main Page:**
```
┌─────────────────────────────────────────┐
│ [Title]                    [+Button]    │
├─────────────────────────────────────────┤
│                                         │
│ [Item 1]                                │
│ [Description]                           │
│                                         │
│ [Item 2]                                │
│ [Description]                           │
│                                         │
└─────────────────────────────────────────┘
```

---

## 8. API Routes

### 8.1 API Endpoints

[Describe API routes with method, path, input, output]

```typescript
// Example
router.get('/api/resource', async (req, res) => {
  // Implementation
});
```

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

- Focus on what's **CHANGING**, not the entire existing system
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
