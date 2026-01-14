"""
Ralph Interview Utilities

Utility functions for codebase analysis and project detection.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default Claude command
DEFAULT_CLAUDE_CMD = "claude --dangerously-skip-permissions"

# Project root markers - files that indicate a project directory
PROJECT_MARKERS = [
    # Node.js
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    # Python
    "requirements.txt", "requirements-dev.txt", "requirements-dev.in",
    "pyproject.toml", "poetry.lock", "Pipfile", "Pipfile.lock", "setup.py", "setup.cfg",
    # Rust
    "Cargo.toml", "Cargo.lock",
    # Go
    "go.mod", "go.sum",
    # Ruby
    "Gemfile", "Gemfile.lock",
    # Java
    "pom.xml", "build.gradle", "settings.gradle", "gradle.properties",
    # Dotnet
    ".csproj", ".sln",
    # PHP
    "composer.json", "composer.lock",
    # Dart/Flutter
    "pubspec.yaml", "pubspec.lock",
    # Swift
    "Package.swift", "Package.resolved",
    # General
    ".git", ".gitignore", ".gitattributes",
]

# Dependency files mapping
DEPENDENCY_FILES = {
    "node": ["package.json"],
    "python": ["requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "ruby": ["Gemfile"],
    "java": ["pom.xml", "build.gradle"],
    "php": ["composer.json"],
    "dart": ["pubspec.yaml"],
}

# Source file extensions by language
SOURCE_EXTENSIONS = {
    "python": [".py"],
    "javascript": [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "rust": [".rs"],
    "go": [".go"],
    "ruby": [".rb"],
    "java": [".java"],
    "php": [".php"],
    "dart": [".dart"],
    "swift": [".swift"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
}


def find_project_root(start_path: Path) -> Path:
    """
    Search upward from start_path to find project root.
    Project root is the directory containing project markers.

    Args:
        start_path: The starting directory to search from

    Returns:
        Path to the project root, or start_path if no markers found
    """
    current = Path(start_path).resolve()

    # First check if current directory has markers
    if any((current / marker).exists() for marker in PROJECT_MARKERS):
        return current

    # Search upward through parent directories
    for parent in current.parents:
        if any((parent / marker).exists() for marker in PROJECT_MARKERS):
            return parent

    # If no markers found, return the original path
    return current


def detect_project_type(project_root: Path) -> str:
    """
    Detect the project type based on files present.

    Args:
        project_root: Path to the project root

    Returns:
        Project type string (e.g., "node", "python", "rust")
    """
    for lang, files in DEPENDENCY_FILES.items():
        for filename in files:
            if (project_root / filename).exists():
                return lang

    # Try to detect from source files
    source_files = list_source_files(project_root, max_depth=2)
    extensions = set(f.suffix.lower() for f in source_files)

    for lang, exts in SOURCE_EXTENSIONS.items():
        if any(ext in extensions for ext in exts):
            return lang

    return "unknown"


def list_source_files(project_root: Path, max_depth: int = 5) -> List[Path]:
    """
    List all source files in the project directory.

    Args:
        project_root: Path to the project root
        max_depth: Maximum directory depth to search

    Returns:
        List of Path objects for source files
    """
    source_files = []
    all_extensions = []
    for exts in SOURCE_EXTENSIONS.values():
        all_extensions.extend(exts)

    # Common directories to skip
    skip_dirs = {
        "node_modules", ".git", ".svn", "venv", ".venv", "env",
        "__pycache__", ".pytest_cache", ".next", ".nuxt", "dist",
        "build", "target", "bin", "obj", ".vscode", ".idea",
        "coverage", ".coverage", "vendor", "bower_components",
    }

    try:
        for root, dirs, files in os.walk(project_root):
            # Filter out skip directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            # Check depth
            rel_path = Path(root).relative_to(project_root)
            depth = len(rel_path.parts)
            if depth > max_depth:
                dirs.clear()
                continue

            for filename in files:
                file_path = Path(root) / filename
                if file_path.suffix.lower() in all_extensions:
                    source_files.append(file_path)
    except (PermissionError, OSError):
        pass

    return source_files


def quick_scan(project_root: Path) -> Dict[str, Any]:
    """
    Fast programmatic scan to gather raw data about a codebase.

    Args:
        project_root: Path to the project root

    Returns:
        Dictionary containing:
        - project_root: Path to project root
        - project_type: Detected project type
        - dependencies: Parsed dependencies
        - directory_tree: Simplified directory structure
        - entry_points: Detected entry point files
        - config_files: Configuration files found
        - files: List of source files
    """
    result = {
        "project_root": str(project_root),
        "project_type": detect_project_type(project_root),
        "dependencies": {},
        "directory_tree": {},
        "entry_points": [],
        "config_files": [],
        "files": [],
    }

    # Get dependencies
    result["dependencies"] = parse_dependencies(project_root)

    # Get source files
    source_files = list_source_files(project_root)
    result["files"] = [str(f.relative_to(project_root)) for f in source_files]

    # Build directory tree (simplified)
    result["directory_tree"] = build_directory_tree(project_root)

    # Find entry points
    result["entry_points"] = find_entry_points(project_root, result["project_type"])

    # Find config files
    result["config_files"] = find_config_files(project_root)

    return result


def build_directory_tree(project_root: Path, max_depth: int = 3) -> Dict[str, Any]:
    """
    Build a simplified directory tree structure.

    Args:
        project_root: Path to the project root
        max_depth: Maximum depth to traverse

    Returns:
        Nested dictionary representing directory structure
    """
    tree = {}
    skip_dirs = {
        "node_modules", ".git", ".svn", "venv", ".venv", "env",
        "__pycache__", ".pytest_cache", ".next", ".nuxt", "dist",
        "build", "target", "bin", "obj", ".vscode", ".idea",
        "coverage", ".coverage", "vendor", "bower_components",
    }

    def _build_tree(path: Path, depth: int) -> Dict[str, Any]:
        if depth > max_depth:
            return {}

        result = {}
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    if item.name in skip_dirs:
                        continue
                    result[item.name] = _build_tree(item, depth + 1)
                elif item.is_file():
                    # Just note that a file exists, don't include contents
                    result[item.name] = None
        except (PermissionError, OSError):
            pass

        return result

    return _build_tree(project_root, 0)


def parse_dependencies(project_root: Path) -> Dict[str, Any]:
    """
    Parse dependencies from package manager files.

    Args:
        project_root: Path to the project root

    Returns:
        Dictionary with parsed dependencies
    """
    dependencies = {}

    # Node.js (package.json)
    package_json = project_root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
            deps = {}
            if "dependencies" in data:
                deps.update(data["dependencies"])
            if "devDependencies" in data:
                deps.update({f"dev:{k}": v for k, v in data["devDependencies"].items()})
            dependencies["node"] = {
                "runtime": data.get("dependencies", {}),
                "dev": data.get("devDependencies", {}),
                "all": deps,
            }
        except (json.JSONDecodeError, IOError):
            pass

    # Python (requirements.txt)
    requirements_txt = project_root / "requirements.txt"
    if requirements_txt.exists():
        deps = {}
        try:
            content = requirements_txt.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse requirement (simplified)
                    if ">=" in line:
                        name, version = line.split(">=", 1)
                        deps[name.strip()] = f">={version.strip()}"
                    elif "==" in line:
                        name, version = line.split("==", 1)
                        deps[name.strip()] = version.strip()
                    else:
                        deps[line] = "any"
            dependencies["python"] = {"all": deps}
        except IOError:
            pass

    # Python (pyproject.toml)
    pyproject_toml = project_root / "pyproject.toml"
    if pyproject_toml.exists():
        try:
            content = pyproject_toml.read_text()
            # Simple parsing for dependencies section
            # In production, use tomli or tomllib
            dependencies["python"] = {"from": "pyproject.toml"}
        except IOError:
            pass

    # Rust (Cargo.toml)
    cargo_toml = project_root / "Cargo.toml"
    if cargo_toml.exists():
        try:
            content = cargo_toml.read_text()
            # Simple parsing - in production use toml library
            dependencies["rust"] = {"from": "Cargo.toml"}
        except IOError:
            pass

    # Go (go.mod)
    go_mod = project_root / "go.mod"
    if go_mod.exists():
        try:
            content = go_mod.read_text()
            # Parse go.mod for dependencies
            deps = {}
            in_require = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("require"):
                    in_require = True
                    continue
                if in_require:
                    if line.startswith(")"):
                        break
                    parts = line.split()
                    if len(parts) >= 2:
                        deps[parts[0]] = parts[1]
            dependencies["go"] = {"all": deps}
        except IOError:
            pass

    return dependencies


def find_entry_points(project_root: Path, project_type: str) -> List[str]:
    """
    Find likely entry point files.

    Args:
        project_root: Path to the project root
        project_type: Detected project type

    Returns:
        List of entry point file paths
    """
    entry_points = []

    # Common entry points by project type
    common_entry_points = {
        "node": [
            "src/index.ts", "src/index.tsx", "src/main.tsx",
            "index.js", "main.js", "server.js",
            "app.js", "app.ts",
        ],
        "python": [
            "src/__init__.py", "src/main.py",
            "main.py", "app.py", "run.py",
            "manage.py", "wsgi.py",
        ],
        "rust": [
            "src/main.rs", "src/lib.rs",
        ],
        "go": [
            "main.go", "cmd/main.go",
        ],
        "java": [
            "src/main/java",
        ],
    }

    if project_type in common_entry_points:
        for entry in common_entry_points[project_type]:
            entry_path = project_root / entry
            if entry_path.exists():
                entry_points.append(entry)

    # Also check package.json "main" field for node
    if project_type == "node":
        package_json = project_root / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                if "main" in data:
                    main_path = project_root / data["main"]
                    if main_path.exists() and str(main_path) not in entry_points:
                        entry_points.append(data["main"])
            except (json.JSONDecodeError, IOError):
                pass

    return entry_points


def find_config_files(project_root: Path) -> List[str]:
    """
    Find configuration files in the project.

    Args:
        project_root: Path to the project root

    Returns:
        List of configuration file names
    """
    config_patterns = [
        "*.config.js", "*.config.ts",
        ".*rc.*", ".*rc",
        "tsconfig.json", "jsconfig.json",
        "vite.config.*", "webpack.config.*",
        ".env*", "*.env",
        "docker-compose.yml", "Dockerfile",
        "Makefile", "justfile",
    ]

    # Specific config files to look for
    specific_configs = [
        "tsconfig.json",
        "jsconfig.json",
        "vite.config.js", "vite.config.ts",
        "webpack.config.js",
        ".eslintrc", ".eslintrc.js", ".eslintrc.json",
        ".prettierrc", ".prettierrc.js", ".prettierrc.json",
        ".babelrc", "babel.config.js",
        "jest.config.js",
        "vitest.config.ts",
        "next.config.js",
        "nuxt.config.ts",
        "tailwind.config.js", "tailwind.config.ts",
        "postcss.config.js",
        ".gitignore", ".dockerignore",
        "Dockerfile", "docker-compose.yml",
        "Makefile",
    ]

    found = []
    for config in specific_configs:
        if (project_root / config).exists():
            found.append(config)

    return found


def get_relative_path(path: Path, base: Path) -> str:
    """
    Get relative path from base to path.

    Args:
        path: The target path
        base: The base path

    Returns:
        Relative path as string
    """
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


# ============================================================================
# Git Utilities
# ============================================================================

import subprocess


def is_git_repo(path: Path) -> bool:
    """
    Check if a directory is a git repository.

    Args:
        path: Path to check

    Returns:
        True if path is in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def get_current_branch(path: Path) -> Optional[str]:
    """
    Get the current git branch name.

    Args:
        path: Path to the git repository

    Returns:
        Current branch name, or None if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def get_default_branch(path: Path) -> str:
    """
    Get the default branch name (main/master).

    Args:
        path: Path to the git repository

    Returns:
        Default branch name
    """
    try:
        # Try using gh cli to get default branch
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Fallback: check if main or master exists
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Output is like "refs/remotes/origin/main"
            return result.stdout.strip().split("/")[-1]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Default to main
    return "main"


def list_branches(path: Path) -> List[str]:
    """
    List all local git branches.

    Args:
        path: Path to the git repository

    Returns:
        List of branch names
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [b.strip() for b in result.stdout.splitlines() if b.strip()]
        return []
    except (FileNotFoundError, subprocess.SubprocessError):
        return []


def branch_exists(path: Path, branch_name: str) -> bool:
    """
    Check if a branch exists locally.

    Args:
        path: Path to the git repository
        branch_name: Branch name to check

    Returns:
        True if branch exists
    """
    branches = list_branches(path)
    return branch_name in branches


def create_branch(path: Path, branch_name: str, base: str = None) -> bool:
    """
    Create a new git branch.

    Args:
        path: Path to the git repository
        branch_name: Name for the new branch
        base: Base branch to create from (default: current HEAD)

    Returns:
        True if successful
    """
    try:
        cmd = ["git", "checkout", "-b", branch_name]
        if base:
            cmd.extend(["--start-point", base])

        result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def switch_branch(path: Path, branch_name: str) -> bool:
    """
    Switch to an existing git branch.

    Args:
        path: Path to the git repository
        branch_name: Branch name to switch to

    Returns:
        True if successful
    """
    try:
        result = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def get_repo_name(path: Path) -> Optional[str]:
    """
    Get the repository name using gh CLI.

    Args:
        path: Path to the git repository

    Returns:
        Repository name, or None if not available
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "name", "-q", ".name"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def get_repo_owner(path: Path) -> Optional[str]:
    """
    Get the repository owner using gh CLI.

    Args:
        path: Path to the git repository

    Returns:
        Repository owner, or None if not available
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner", "-q", ".owner.login"],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def commit_files(
    path: Path,
    message: str,
    files: List[Path] = None
) -> bool:
    """
    Commit files to git.

    Args:
        path: Path to the git repository
        message: Commit message
        files: List of files to commit (None = stage all changes)

    Returns:
        True if successful
    """
    try:
        # Stage files
        if files:
            for file in files:
                subprocess.run(
                    ["git", "add", str(file)],
                    cwd=path,
                    capture_output=True,
                    text=True
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=path,
                capture_output=True,
                text=True
            )

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def has_uncommitted_changes(path: Path) -> bool:
    """
    Check if there are uncommitted changes.

    Args:
        path: Path to the git repository

    Returns:
        True if there are uncommitted changes
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip()) > 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
