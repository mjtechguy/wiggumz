# Brownfield Codebase Analysis

You are analyzing an existing codebase to create comprehensive documentation (BROWNFIELD.md) for the Ralph autonomous development system.

## Quick Scan Results

{scan_data}

## Your Task

Using the scan results as a guide, explore the codebase at `{project_root}` to create **BROWNFIELD.md**.

## What to Document

### 1. Project Overview
- Project name and purpose (infer from README, package description, code)
- What this codebase does
- Who uses it (if discernible)

### 2. Technology Stack
- **Language**: [with version if detectable]
- **Framework**: [name + version]
- **Runtime**: [Node version, Python version, etc.]
- Key libraries and their purposes

### 3. Directory Structure
```
[Show tree structure with annotations]
```
For each major directory, add a brief comment about its purpose.

### 4. Dependencies
Create a table of key dependencies:

| Package | Version | Purpose (inferred) |
|---------|---------|-------------------|
| ... | ... | ... |

### 5. Existing Features
#### Routes/Endpoints (if applicable)
| Path | Type | Purpose |
|------|------|---------|

#### Main Components/Modules
- `module/path` - [Description]

### 6. Architectural Patterns
Document the patterns you discover:

#### State Management
[How is state managed? Redux? Context? Database? Include examples]

#### Routing
[How does routing work? React Router? FastAPI routes? Include examples]

#### Data Layer
[ORM? Direct SQL? API client? Include patterns]

#### Error Handling
[How are errors handled?]

### 7. Code Conventions
#### Naming
- Files: [snake_case / camelCase / PascalCase / kebab-case]
- Components: [pattern]
- Variables/Functions: [pattern]

#### Import Style
[How are imports organized? Relative vs absolute?]

#### File Organization
[Principles observed in codebase]

### 8. Testing Patterns
- Test framework: [name]
- Test location: [co-located / tests/ / __tests__/]
- Mocking patterns: [if any]

### 9. Build & Run
Commands from package.json scripts, Makefile, etc.:
- Build: `command`
- Dev: `command`
- Test: `command`
- Lint: `command`

### 10. External Integrations
| Service | Purpose | Location in code |
|---------|---------|------------------|

## How to Explore

1. **Read key files** to understand context:
   - README.md (if exists)
   - package.json or equivalent
   - Main entry points

2. **Use Glob** to find patterns:
   - Route files
   - Component files
   - Test files

3. **Use Grep** to find patterns:
   - Import statements
   - API calls
   - State management usage

## Output Format

Output a **comprehensive BROWNFIELD.md** file. Be thorough - this will be used for:
1. Understanding the existing codebase before making changes
2. Ensuring new code follows existing patterns
3. Identifying what needs to change vs. what to preserve

Start your analysis now. Output the complete BROWNFIELD.md file.
