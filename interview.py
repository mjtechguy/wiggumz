#!/usr/bin/env python3
"""
Ralph Interview - Interactive PRD generation system

Analyzes codebase (brownfield) or conducts interview (greenfield)
to generate comprehensive prd.md for Ralph autonomous development.

Usage:
    python3 interview.py <project-name> [OPTIONS]

Options:
    -p, --path PATH      Path to codebase to analyze (brownfield)
    -o, --output-dir PATH  Output directory (default: ralph/projects/<name>)
    -m, --mode MODE       Force mode: brownfield or greenfield (default: interactive)
    -c, --claude-cmd CMD  Claude command to use (default: claude --dangerously-skip-permissions)
    -h, --help            Show help message
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add lib directory to path
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from interview_utils import (
    find_project_root,
    quick_scan,
    detect_project_type,
    DEFAULT_CLAUDE_CMD,
    PROJECT_MARKERS,
    # Git utilities
    is_git_repo,
    get_current_branch,
    get_default_branch,
    list_branches,
    branch_exists,
    create_branch,
    switch_branch,
    get_repo_name,
    get_repo_owner,
    commit_files,
    has_uncommitted_changes,
)
from interviewer import conduct_interview
from prd_generator import generate_prd


# ============================================================================
# Branch Management
# ============================================================================

def prompt_for_branch(project_name: str, target_path: Path, mode: str) -> Optional[str]:
    """
    Prompt user for branch selection/creation.

    Args:
        project_name: Ralph project name
        target_path: Path to the codebase
        mode: "brownfield" or "greenfield"

    Returns:
        Selected branch name, or None if not in a git repo
    """
    if not is_git_repo(target_path):
        print(f"  Note: Not in a git repository")
        return None

    current_branch = get_current_branch(target_path)
    default_branch = get_default_branch(target_path)
    all_branches = list_branches(target_path)

    print()
    print("=" * 60)
    print("  Git Repository Detected")
    print("=" * 60)
    print(f"  Current branch: {current_branch if current_branch else '(detached)'}")
    print(f"  Default branch: {default_branch}")
    print(f"  Available branches: {', '.join(all_branches)}")
    print()

    if mode == "brownfield":
        # Suggest a feature branch name
        suggested_branch = f"ralph/{project_name}"

        print(f"  Suggested feature branch: {suggested_branch}")
        print()

        print("Options:")
        print("  1) Create and use feature branch")
        print(f"     (Will create: {suggested_branch})")
        print("  2) Use current branch")
        print(f"     (Current: {current_branch})")
        print("  3) Use existing branch")
        print("     (Select from available branches)")
        print("  4) Enter custom branch name")
        print("  5) Skip branch management")
        print("     (Proceed without changing branches)")
        print()

        while True:
            try:
                choice = input("Select option (1-5): ").strip()

                if choice == "1":
                    # Create feature branch
                    if branch_exists(target_path, suggested_branch):
                        print(f"  Branch '{suggested_branch}' already exists.")
                        if input("  Switch to it? (y/n): ").strip().lower() == 'y':
                            if switch_branch(target_path, suggested_branch):
                                print(f"  ✓ Switched to {suggested_branch}")
                                return suggested_branch
                        else:
                            continue
                    else:
                        if create_branch(target_path, suggested_branch):
                            print(f"  ✓ Created and switched to {suggested_branch}")
                            return suggested_branch
                        else:
                            print(f"  ✗ Failed to create branch")
                            return None

                elif choice == "2":
                    print(f"  Using current branch: {current_branch}")
                    return current_branch

                elif choice == "3":
                    print("  Available branches:")
                    for i, branch in enumerate(all_branches, 1):
                        current = " (current)" if branch == current_branch else ""
                        print(f"    {i}) {branch}{current}")
                    print()

                    branch_choice = input("  Select branch number: ").strip()
                    try:
                        branch_idx = int(branch_choice) - 1
                        if 0 <= branch_idx < len(all_branches):
                            selected = all_branches[branch_idx]
                            if selected != current_branch:
                                if switch_branch(target_path, selected):
                                    print(f"  ✓ Switched to {selected}")
                                    return selected
                            else:
                                print(f"  Already on {selected}")
                                return selected
                        else:
                            print("  Invalid selection")
                    except ValueError:
                        print("  Please enter a number")

                elif choice == "4":
                    custom = input("  Enter branch name: ").strip()
                    if custom:
                        if branch_exists(target_path, custom):
                            if switch_branch(target_path, custom):
                                print(f"  ✓ Switched to {custom}")
                                return custom
                        else:
                            if create_branch(target_path, custom):
                                print(f"  ✓ Created and switched to {custom}")
                                return custom
                            else:
                                print(f"  ✗ Failed to create branch")
                    continue

                elif choice == "5":
                    print("  Skipping branch management")
                    return current_branch

                else:
                    print("  Invalid option. Please enter 1-5.")

            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                return None

    else:  # greenfield
        print(f"  Current branch: {current_branch}")
        print()

        confirm = input(f"  Use current branch '{current_branch}'? (Y/n): ").strip()
        if confirm.lower() == 'n':
            custom = input("  Enter branch name (or leave empty to skip): ").strip()
            if custom:
                if branch_exists(target_path, custom):
                    if switch_branch(target_path, custom):
                        print(f"  ✓ Switched to {custom}")
                        return custom
                else:
                    if create_branch(target_path, custom):
                        print(f"  ✓ Created and switched to {custom}")
                        return custom

        return current_branch


def confirm_branch(target_path: Path, branch_name: str) -> bool:
    """
    Confirm the current branch before proceeding.

    Args:
        target_path: Path to the git repository
        branch_name: Expected/current branch name

    Returns:
        True if user confirms
    """
    if not is_git_repo(target_path):
        return True

    current = get_current_branch(target_path)

    print()
    print("=" * 60)
    print("  Branch Confirmation")
    print("=" * 60)
    print(f"  Current branch: {current}")
    print()

    if has_uncommitted_changes(target_path):
        print("  ⚠️  Warning: You have uncommitted changes")
        print()

    response = input(f"  Continue on branch '{current}'? (Y/n): ").strip()
    return response.lower() != 'n'


def setup_branch_info(output_dir: Path, branch_name: str, project_name: str) -> None:
    """
    Update prd.json with the branch name.

    Args:
        output_dir: Path to the Ralph project directory
        branch_name: Branch name to use
        project_name: Ralph project name
    """
    import json

    prd_json_path = output_dir / "prd.json"

    if prd_json_path.exists():
        try:
            data = json.loads(prd_json_path.read_text())
            data["branchName"] = branch_name or f"ralph/{project_name}"
            prd_json_path.write_text(json.dumps(data, indent=2) + "\n")
        except (json.JSONDecodeError, IOError):
            pass


# ============================================================================
# Argument Parsing
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate PRD.md via interactive interview for Ralph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode selection
  python3 interview.py myproject

  # Brownfield with specific path
  python3 interview.py myproject -p ../myapp

  # Greenfield (skip analysis)
  python3 interview.py myproject -m greenfield

  # Use alternative Claude command
  python3 interview.py myproject --claude-cmd "glmclaude"
        """
    )
    parser.add_argument(
        "project_name",
        help="Name for the Ralph project"
    )
    parser.add_argument(
        "-p", "--path",
        dest="target_path",
        default=None,
        help="Path to codebase to analyze (for brownfield, default: auto-detect)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        default=None,
        help="Output directory (default: ralph/projects/<name>)"
    )
    parser.add_argument(
        "-m", "--mode",
        dest="mode",
        choices=["brownfield", "greenfield", "auto"],
        default="auto",
        help="Force mode (default: auto -> interactive prompt)"
    )
    parser.add_argument(
        "-c", "--claude-cmd",
        dest="claude_cmd",
        default=None,
        help=f"Claude command to use (default: {DEFAULT_CLAUDE_CMD}, or RALPH_CLAUDE_CMD env var)"
    )
    return parser.parse_args()


def prompt_for_mode() -> str:
    """Prompt user to select brownfield or greenfield mode."""
    print()
    print("=" * 60)
    print("  Ralph Interview - PRD Generation")
    print("=" * 60)
    print()
    print("What type of project is this?")
    print()
    print("  1) Brownfield - Modifying an existing codebase")
    print("  2) Greenfield - Building something new")
    print()

    while True:
        try:
            choice = input("Enter choice (1 or 2): ").strip()
            if choice == "1":
                return "brownfield"
            elif choice == "2":
                return "greenfield"
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)


def get_claude_cmd(args) -> str:
    """Get Claude command from args or environment."""
    if args.claude_cmd:
        return args.claude_cmd
    env_cmd = os.getenv("RALPH_CLAUDE_CMD")
    if env_cmd:
        return env_cmd
    return DEFAULT_CLAUDE_CMD


def ensure_ralph_project(project_name: str, output_dir: Path) -> Path:
    """Ensure Ralph project directory exists with required files."""
    output_dir = output_dir.resolve()

    # Create directory if it doesn't exist
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created project directory: {output_dir}")

    # Copy PROMPT.md if not present
    ralph_dir = Path(__file__).parent
    prompt_src = ralph_dir / "templates" / "PROMPT.md"
    prompt_dst = output_dir / "PROMPT.md"

    if not prompt_dst.exists() and prompt_src.exists():
        import shutil
        shutil.copy(prompt_src, prompt_dst)
        print(f"Copied PROMPT.md to {output_dir}")

    # Create empty prd.json if not present
    prd_json = output_dir / "prd.json"
    if not prd_json.exists():
        prd_json.write_text(json.dumps({
            "branchName": f"ralph/{project_name}",
            "userStories": []
        }, indent=2) + "\n")
        print(f"Created prd.json")

    # Create requirements.md if not present
    req_src = ralph_dir / "templates" / "requirements.md"
    req_dst = output_dir / "requirements.md"
    if not req_dst.exists() and req_src.exists():
        import shutil
        shutil.copy(req_src, req_dst)
        print(f"Copied requirements.md to {output_dir}")

    # Create progress.txt if not present
    progress_file = output_dir / "progress.txt"
    if not progress_file.exists():
        progress_file.write_text(f"# Progress Log: {project_name}\n\n"
                                 f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                 f"## Notes\n"
                                 f"- Generated via interview.py\n")
        print(f"Created progress.txt")

    # Create logs directory
    logs_dir = output_dir / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created logs/ directory")

    return output_dir


def run_claude_command(prompt: str, claude_cmd: str, cwd: Path) -> str:
    """
    Run Claude Code CLI with a prompt and return the output.

    Args:
        prompt: The prompt to send to Claude
        claude_cmd: The Claude command to use
        cwd: Working directory for the command

    Returns:
        Claude's response as a string
    """
    # Parse claude_cmd into list
    import shlex
    cmd_parts = shlex.split(claude_cmd)

    result = subprocess.run(
        cmd_parts,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=cwd
    )

    return result.stdout


def show_directory_preview(path: Path, max_depth: int = 2, max_items: int = 20) -> None:
    """
    Show a simplified directory tree preview for user confirmation.

    Args:
        path: Path to the directory to preview
        max_depth: Maximum depth to show
        max_items: Maximum items per level
    """
    import os

    skip_dirs = {
        "node_modules", ".git", ".svn", "venv", ".venv", "env",
        "__pycache__", ".pytest_cache", ".next", ".nuxt", "dist",
        "build", "target", "bin", "obj", ".vscode", ".idea",
        "coverage", ".coverage", "vendor", "bower_components",
        "wiggumz", "ralph", "ralph-cli", "wiggumz-cli", "projects",
    }

    def _show_tree(current: Path, depth: int, prefix: str = "", is_last: bool = True) -> None:
        if depth > max_depth:
            return

        try:
            items = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            # Filter out hidden files and skip directories
            items = [i for i in items if not i.name.startswith(".") and i.name not in skip_dirs]

            # Limit items
            if len(items) > max_items and depth == 0:
                items = items[:max_items]

            for i, item in enumerate(items):
                is_dir = item.is_dir()
                is_last_item = i == len(items) - 1

                # Tree connector
                connector = "└──" if is_last_item else "├──"
                dir_indicator = "/" if is_dir else ""

                print(f"  {prefix}{connector} {item.name}{dir_indicator}")

                # Recurse into directories
                if is_dir and depth < max_depth:
                    next_prefix = prefix + ("    " if is_last_item else "│   ")
                    _show_tree(item, depth + 1, next_prefix, is_last_item)

            if len(items) > max_items and depth == 0:
                print(f"  {prefix}└── ... ({len(items) - max_items} more items)")

        except (PermissionError, OSError):
            pass

    _show_tree(path, 0)


def main():
    args = parse_args()

    # Determine mode
    if args.mode == "auto":
        mode = prompt_for_mode()
    else:
        mode = args.mode

    # Resolve paths
    if args.target_path:
        target_path = Path(args.target_path).resolve()
    elif mode == "brownfield":
        # Prompt for path to analyze
        print()
        print("=" * 60)
        print("  Brownfield Mode - Codebase Path Required")
        print("=" * 60)
        print()
        print("  Please enter the path to the codebase you want to modify.")
        print("  (This is the project you'll be making changes to)")
        print()

        # Suggest current directory but exclude wiggumz/ralph
        suggested_path = Path.cwd()
        project_name_str = suggested_path.name

        # If we're inside wiggumz/ralph, suggest the parent
        if project_name_str in ["wiggumz", "ralph", "ralph-cli", "wiggumz-cli"]:
            suggested_path = suggested_path.parent
            print(f"  Note: You're inside the wiggumz/ralph directory.")
            print(f"  Suggested parent directory: {suggested_path}")
            print()

        while True:
            try:
                path_input = input(f"  Path to analyze [{suggested_path}]: ").strip()
                if path_input:
                    target_path = Path(path_input).resolve()
                else:
                    target_path = suggested_path

                # Verify the path exists
                if not target_path.exists():
                    print(f"  ✗ Path does not exist: {target_path}")
                    print()
                    continue

                # Detect and show project root
                detected_root = find_project_root(target_path)
                if detected_root != target_path:
                    print(f"  → Detected project root: {detected_root}")
                    target_path = detected_root

                # Show directory structure for confirmation
                print()
                print("  Directory structure:")
                print("  " + "-" * 56)
                show_directory_preview(target_path)
                print("  " + "-" * 56)
                print()

                # Confirm
                confirm = input(f"  Analyze this directory? (Y/n): ").strip().lower()
                if confirm != 'n':
                    break
                else:
                    print()
                    path_input = input("  Enter a different path (or press Ctrl+C to cancel): ").strip()
                    if path_input:
                        target_path = Path(path_input).resolve()

            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                sys.exit(0)

        print()
    else:
        # Greenfield - current directory is fine
        target_path = Path.cwd()

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        # Default to ralph/projects/<name>
        script_dir = Path(__file__).parent
        output_dir = script_dir / "projects" / args.project_name

    # Get Claude command
    claude_cmd = get_claude_cmd(args)

    # Ensure Ralph project structure exists
    output_dir = ensure_ralph_project(args.project_name, output_dir)

    # Branch handling (for git repos)
    branch_name = None
    if is_git_repo(target_path):
        branch_name = prompt_for_branch(args.project_name, target_path, mode)
        if branch_name is None:
            print("  Continuing without branch management")
            branch_name = get_current_branch(target_path)

        # Update prd.json with branch info
        setup_branch_info(output_dir, branch_name, args.project_name)

        # Confirm branch before proceeding
        if not confirm_branch(target_path, branch_name):
            print("\n  Interview cancelled by user.")
            sys.exit(0)

    print()
    print("=" * 60)
    print(f"  Mode: {mode.upper()}")
    print(f"  Target path: {target_path}")
    print(f"  Output: {output_dir}")
    print(f"  Claude command: {claude_cmd}")
    if branch_name:
        print(f"  Branch: {branch_name}")
    print("=" * 60)
    print()

    brownfield_doc = None

    # Step 1: Brownfield analysis (if applicable)
    if mode == "brownfield":
        print("Step 1: Analyzing existing codebase...")
        print("-" * 60)

        # Quick scan (Python)
        scan_data = quick_scan(target_path)
        project_type = detect_project_type(target_path)

        print(f"  Detected project type: {project_type}")
        print(f"  Found {len(scan_data.get('dependencies', {}))} dependencies")
        print(f"  Scanned {len(scan_data.get('files', []))} files")
        print()

        # Claude refinement
        print("  Running Claude analysis...")

        # Load the brownfield analysis prompt
        ralph_dir = Path(__file__).parent
        prompt_file = ralph_dir / "lib" / "prompts" / "brownfield_analysis.md"

        if prompt_file.exists():
            analysis_prompt_template = prompt_file.read_text()
        else:
            analysis_prompt_template = """You are analyzing a codebase to create comprehensive documentation.

## Quick Scan Results:

{scan_data}

## Your Task:

Using the scan results as a guide, explore the codebase at {project_root} to create BROWNFIELD.md.

Focus on:
1. Project purpose (infer from README, package description, code)
2. Architectural patterns (state, routing, data layer)
3. Code conventions (naming, imports, organization)
4. Existing features (routes, components, modules)
5. Build/run commands (package.json scripts, Makefile, etc.)

Read key files to understand context. The scan data is just a map - you need to explore to understand.

Output a comprehensive BROWNFIELD.md file.
"""

        analysis_prompt = analysis_prompt_template.format(
            scan_data=json.dumps(scan_data, indent=2),
            project_root=target_path
        )

        brownfield_doc = run_claude_command(analysis_prompt, claude_cmd, target_path)

        # Write BROWNFIELD.md
        brownfield_path = output_dir / "BROWNFIELD.md"
        brownfield_path.write_text(brownfield_doc)
        print(f"  Wrote: {brownfield_path}")
        print()

    # Step 2: Conduct interview
    print("Step 2: Conducting interview...")
    print("-" * 60)
    print()

    interview_results = conduct_interview(
        mode=mode,
        brownfield_doc=brownfield_doc,
        target_path=target_path,
        claude_cmd=claude_cmd,
        ralph_dir=Path(__file__).parent
    )

    print()
    print("=" * 60)
    print("  Interview Complete")
    print("=" * 60)
    print()

    # Step 3: Generate PRD
    print("Step 3: Generating PRD...")
    print("-" * 60)

    prd_content = generate_prd(
        mode=mode,
        interview_results=interview_results,
        brownfield_doc=brownfield_doc,
        target_path=target_path,
        ralph_dir=Path(__file__).parent
    )

    # Write PRD
    prd_path = output_dir / "prd.md"
    prd_path.write_text(prd_content)
    print(f"  Wrote: {prd_path}")
    print()

    # Update status.json
    status_path = output_dir / "status.json"
    status_json = {
        "project": args.project_name,
        "mode": mode,
        "created_at": datetime.now().isoformat(),
        "target_path": str(target_path),
        "branch": branch_name,
        "status": "interview_complete"
    }
    status_path.write_text(json.dumps(status_json, indent=2) + "\n")

    # Auto-commit PRD files if in a git repo
    if is_git_repo(target_path) and branch_name:
        print()
        print("=" * 60)
        print("  Committing PRD files...")
        print("=" * 60)

        files_to_commit = [prd_path]
        if mode == "brownfield":
            files_to_commit.append(output_dir / "BROWNFIELD.md")

        # Get repo info for commit message
        repo_name = get_repo_name(target_path)
        repo_owner = get_repo_owner(target_path)

        commit_msg = f"feat: {args.project_name} - Generate PRD via interview.py\n\n"
        commit_msg += f"Mode: {mode}\n"
        if repo_name:
            commit_msg += f"Repo: {repo_owner + '/' if repo_owner else ''}{repo_name}\n"
        commit_msg += f"Branch: {branch_name}\n"
        commit_msg += f"\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

        if commit_files(target_path, commit_msg, files_to_commit):
            print(f"  ✓ Committed PRD files")
        else:
            print(f"  ✗ Failed to commit (no changes or git error)")
        print()

    print()
    print("=" * 60)
    print("  Success!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  1. Review PRD: {prd_path}")
    if mode == "brownfield":
        print(f"  2. Review analysis: {output_dir / 'BROWNFIELD.md'}")
    print(f"  3. Convert to tasks: ./ralph/convert.sh {args.project_name}")
    if branch_name:
        print(f"  4. Push branch: git push origin {branch_name}")
    print(f"  5. Start loop: ./ralph/start.sh {args.project_name}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
