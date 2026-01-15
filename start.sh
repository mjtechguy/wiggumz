#!/bin/bash

# Ralph Start - Main execution loop with tmux support
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/circuit_breaker.sh"
source "$SCRIPT_DIR/lib/response_analyzer.sh"

# Signal handling for graceful exit
_cleanup_pid=""
cleanup_and_exit() {
    local exit_code=${1:-130}  # 128 + 2 (SIGINT)
    echo ""
    log "WARN" "🛑 Interrupted - exiting gracefully..."
    # Kill any tracked child processes
    if [[ -n "$_cleanup_pid" ]]; then
        kill "$_cleanup_pid" 2>/dev/null || true
    fi
    # Also kill any timeout/gtimeout processes in our group
    pkill -P $$ 2>/dev/null || true
    exit "$exit_code"
}

trap cleanup_and_exit SIGINT SIGTERM

# Configuration
CLAUDE_CMD=${CLAUDE_CMD:-"claude --dangerously-skip-permissions"}

# Use gtimeout on macOS (from brew install coreutils), timeout on Linux
if command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout"
else
    echo "ERROR: 'timeout' command not found. Install with: brew install coreutils"
    exit 1
fi
MAX_CALLS_PER_HOUR=${MAX_CALLS_PER_HOUR:-100}
CLAUDE_TIMEOUT_MINUTES=${CLAUDE_TIMEOUT_MINUTES:-20}
MAX_ITERATIONS=${MAX_ITERATIONS:-0}  # 0 = unlimited
COMPLETE_TOKEN=${COMPLETE_TOKEN:-"<promise>COMPLETE</promise>"}
USE_TMUX=false
VERBOSE=${VERBOSE:-false}

# Rate limiting files
CALL_COUNT_FILE=".call_count"
TIMESTAMP_FILE=".last_reset"

show_help() {
    cat << HELPEOF
Ralph Start - Run the autonomous development loop

Usage: $0 <project-name> [OPTIONS]

Arguments:
    project-name    Name of the Ralph project to run

Options:
    -m, --monitor           Start with tmux session and live monitor
    -v, --verbose           Show Claude output in real-time (also saves to log)
    -n, --max-iterations N  Max loop iterations (default: 0 = unlimited)
    -c, --calls NUM         Max calls per hour (default: $MAX_CALLS_PER_HOUR)
    -t, --timeout MIN       Claude timeout in minutes (default: $CLAUDE_TIMEOUT_MINUTES)
    --complete-token STR    Token that signals project completion
                            (default: $COMPLETE_TOKEN)
    --claude-cmd CMD        Override Claude command (default: claude --dangerously-skip-permissions)
    -s, --status            Show project status and exit
    --stop                  Stop a running project
    --doctor, --check       Verify dependencies and setup
    -r, --reset             Reset circuit breaker and continue
    -h, --help              Show this help

Examples:
    $0 signals                    # Run unlimited until complete
    $0 signals --monitor          # Run with tmux monitoring
    $0 signals -n 5               # Run max 5 iterations
    $0 signals -n 10 --monitor    # 10 iterations with monitoring
    $0 signals --status           # Show current status
    $0 signals --stop             # Stop running project
    $0 --doctor                   # Check setup
    $0 signals --reset            # Reset circuit breaker

Environment Variables:
    MAX_ITERATIONS          Override max iterations
    MAX_CALLS_PER_HOUR      Override rate limit
    CLAUDE_TIMEOUT_MINUTES  Override Claude timeout
    CLAUDE_CMD              Override Claude executable
    COMPLETE_TOKEN          Override completion token

HELPEOF
}

# Initialize rate limiting
init_rate_limiting() {
    local project_dir=$1
    local current_hour=$(date +%Y%m%d%H)
    local last_reset_hour=""
    
    local count_file="$project_dir/$CALL_COUNT_FILE"
    local ts_file="$project_dir/$TIMESTAMP_FILE"
    
    if [[ -f "$ts_file" ]]; then
        last_reset_hour=$(cat "$ts_file")
    fi
    
    if [[ "$current_hour" != "$last_reset_hour" ]]; then
        echo "0" > "$count_file"
        echo "$current_hour" > "$ts_file"
        log "INFO" "Rate limit counter reset for new hour"
    fi
}

# Check if we can make another call
can_make_call() {
    local project_dir=$1
    local count_file="$project_dir/$CALL_COUNT_FILE"
    local calls_made=0
    
    if [[ -f "$count_file" ]]; then
        calls_made=$(cat "$count_file")
    fi
    
    [[ $calls_made -lt $MAX_CALLS_PER_HOUR ]]
}

# Increment call counter
increment_call_counter() {
    local project_dir=$1
    local count_file="$project_dir/$CALL_COUNT_FILE"
    local calls_made=0
    
    if [[ -f "$count_file" ]]; then
        calls_made=$(cat "$count_file")
    fi
    
    calls_made=$((calls_made + 1))
    echo "$calls_made" > "$count_file"
    echo "$calls_made"
}

# Wait for rate limit reset
wait_for_reset() {
    local project_dir=$1
    local calls_made=$(cat "$project_dir/$CALL_COUNT_FILE" 2>/dev/null || echo "0")
    
    log "WARN" "Rate limit reached ($calls_made/$MAX_CALLS_PER_HOUR). Waiting for reset..."
    
    local wait_time=$(get_seconds_until_next_hour)
    log "INFO" "Sleeping for $(format_duration $wait_time) until next hour..."
    
    while [[ $wait_time -gt 0 ]]; do
        printf "\r${YELLOW}Time until reset: $(format_duration $wait_time)${NC}"
        sleep 1
        wait_time=$((wait_time - 1))
    done
    printf "\n"
    
    echo "0" > "$project_dir/$CALL_COUNT_FILE"
    echo "$(date +%Y%m%d%H)" > "$project_dir/$TIMESTAMP_FILE"
    log "SUCCESS" "Rate limit reset! Ready for new calls."
}

# Update status file
update_status() {
    local project_dir=$1
    local loop_count=$2
    local status=$3
    local current_story=${4:-""}
    
    local prd_file="$project_dir/prd.json"
    local complete=$(count_complete_stories "$prd_file")
    local total=$(count_total_stories "$prd_file")
    local calls=$(cat "$project_dir/$CALL_COUNT_FILE" 2>/dev/null || echo "0")
    
    cat > "$project_dir/status.json" << EOF
{
    "timestamp": "$(get_iso_timestamp)",
    "status": "$status",
    "loop_count": $loop_count,
    "current_story": "$current_story",
    "stories_complete": $complete,
    "stories_total": $total,
    "calls_this_hour": $calls,
    "max_calls_per_hour": $MAX_CALLS_PER_HOUR
}
EOF
}

# Generate the FULL prompt with ALL stories (like original ralph.sh)
generate_full_prompt() {
    local project_dir=$1
    
    local prompt_template=$(cat "$project_dir/PROMPT.md")
    local prd_content=$(cat "$project_dir/prd.json")
    local progress_content=$(cat "$project_dir/progress.txt" 2>/dev/null || echo "No progress yet.")
    local requirements_content=$(cat "$project_dir/requirements.md" 2>/dev/null || echo "No requirements yet.")
    
    # Count stories
    local complete=$(count_complete_stories "$project_dir/prd.json")
    local total=$(count_total_stories "$project_dir/prd.json")
    local incomplete=$((total - complete))
    
    # Get branch name if available
    local branch_name=$(get_branch_name "$project_dir/prd.json")
    local branch_info=""
    local branch_warning=""
    if [[ -n "$branch_name" ]]; then
        branch_info="**Branch:** \`$branch_name\`"
        branch_warning="
## ⛔ BRANCH RESTRICTION ⛔

**You are ONLY allowed to push to branch: \`$branch_name\`**
- DO NOT switch to any other branch, do not create new branches.
- DO NOT push to main, master, or any branch other than \`$branch_name\`
"
    fi

#         cat << EOF
# Return OK
# EOF
    
#     cat << EOF
# $prompt_template

# ---

# ## PRD User Stories ($project_dir/prd.json)

# Below are ALL the user stories for this project. Stories with \`"passes": true\` are complete.
# Stories with \`"passes": false\` still need to be implemented.

# $branch_info
# **Progress: $complete/$total complete ($incomplete remaining)**

# \`\`\`json
# $prd_content
# \`\`\`

# ---

# ## Progress So Far ($project_dir/progress.txt)

# $progress_content

# ---

# ## Technical Requirements ($project_dir/requirements.md)

# $requirements_content

# ---

# ## Instructions

# 1. **Pick the BEST user story to work on next where \`passes: false\`**
#    - Use priority as a guide, but consider the full context
#    - Read progress.txt to understand what was already done
#    - Check notes field on stories for blockers or context
#    - Consider dependencies - don't start something if prerequisites aren't done
#    - Use your judgment to pick what makes most sense right now

# 2. **Implement ONLY that single user story** - do not scope creep

# 3. **After implementation, verify your work:**
#    - Run: \`turbo check-types\` to verify no type errors
#    - Run: \`turbo test\` to verify tests pass

# 4. **If checks pass, commit and push your work:**
#    - Use a descriptive commit message
#    - Format: \`feat: [ID] - [Title]\`
#    - Example: \`git commit -m "feat: 1.1 - Create subscription database schema"\`
#    - **After committing, push to the current branch:** \`git push origin HEAD\`
#    - ONLY push to the current branch - NEVER push to main, master, or any other branch

# 5. **Update AGENTS.md if you discover reusable patterns:**
#    - Add learnings to AGENTS.md files in directories where you modified files
#    - Good additions: "When modifying X, also update Y", "This module uses pattern Z"
#    - Don't add: story-specific details, temporary notes

# 6. **Update prd.json:** Set \`passes: true\` for the completed user story

# 7. **Report your status using the RALPH_STATUS block** (see PROMPT.md for format)

# 8. **STOP IMMEDIATELY after completing ONE story**
#    - After updating prd.json and reporting status, YOU MUST STOP
#    - Do NOT start working on another story
#    - Do NOT continue to the next task
#    - The loop will call you again for the next story

# 9. **If ALL user stories now have \`passes: true\`:**
#    - Reply with: $COMPLETE_TOKEN
#    - This signals that the entire project is complete

# ## ⛔ CRITICAL: ONE STORY PER EXECUTION ⛔

# **YOU MUST STOP AFTER COMPLETING ONE STORY.**

# - Implement exactly ONE user story, then STOP
# - After commit + push + prd.json update → STOP WORKING
# - If you implement more than one story, you are breaking the system

# ## OTHER REMINDERS

# - **Priority field determines order** - Lower priority number = do first
# - **Check existing code first** - Don't reimplement what already exists
# - **Follow existing patterns** - Look at similar code in the codebase
# - **All commits MUST pass typecheck and tests**
# - **Update progress.txt with what you implemented**
# - **Update AGENTS.md with reusable learnings** (not story-specific notes)

# Now, analyze the PRD above and implement the next incomplete story (lowest priority number that has passes: false). STOP after completing it.
# EOF


cat << EOF
$prompt_template

---

## PRD User Stories 
@ralph/projects/$project_name/prd.json

Below are ALL the user stories for this project. Stories with \`"passes": true\` are complete.
Stories with \`"passes": false\` still need to be implemented.

$branch_info
**Progress: $complete/$total complete ($incomplete remaining)**
$branch_warning

## Find current progress in 
@ralph/projects/$project_name/progress.txt
## Read technical requirements in 
@ralph/projects/$project_name/requirements.md

---

## Instructions

1. **Pick the BEST/HIGHEST PRIORITY user story to work on next where \`passes: false\`**
   - Lower \`priority\` number = implement first (priority 1 before priority 10)
   - Consider dependencies - implement foundation before features
   - Look at the "steps" to understand what needs to be done
   - Consider dependencies - don't start something if prerequisites aren't done
   - Use your judgment to pick what makes most sense right now

2. **Implement ONLY that single user story** - do not scope creep

3. **Use Subagents for Complex Tasks:**

   For stories involving any of the following, use the Task tool with specialized subagents:

   **When to use the EXPLORE subagent:**
   - You need to find files by pattern (e.g., "all API route files")
   - You need to understand how a feature is implemented across the codebase
   - You're unsure where to start or what files to modify
   - You need to trace code flow or dependencies

   **When to use the PLAN subagent:**
   - The story involves multiple files or components
   - There are multiple valid implementation approaches
   - Architectural decisions need to be made
   - The requirements are unclear and need design

   **When to use the code-simplifier subagent:**
   - After implementing a complex feature, refactor for clarity
   - The code you wrote is getting long or complex
   - You want to ensure maintainability before committing

   **Subagent workflow:**
   - Use Task tool with appropriate subagent_type (Explore, Plan, code-simplifier)
   - Provide clear, specific prompts to the subagent
   - Review the subagent's findings/recommendations
   - Implement the changes yourself (subagents advise, you execute)

   Example:
   - For a new API endpoint: First use Explore to find existing API patterns, then implement
   - For a complex feature: Use Plan to design the approach, then implement
   - After implementation: Use code-simplifier to refine the code

4. **After implementation, verify your work:**
   - Run: \`turbo check-types\` to verify no type errors
   - Run: \`turbo test\` to verify tests pass

5. **If checks pass, commit and push your work:**
   - Use a descriptive commit message
   - Format: \`feat: [ID] - [Title]\`
   - Example: \`git commit -m "feat: 1.1 - Create subscription database schema"\`
   - **After committing, push to the current branch:** \`git push origin HEAD\`
   - ⛔ ONLY push to the designated branch (\`$branch_name\`) - NEVER push to main, master, or any other branch

6. **Update AGENTS.md if you discover reusable patterns:**
   - Add learnings to AGENTS.md files in directories where you modified files
   - Good additions: "When modifying X, also update Y", "This module uses pattern Z"
   - Don't add: story-specific details, temporary notes

7. **Update prd.json:** Set \`passes: true\` for the completed user story

8. **Update progress.txt with what you implemented**
    - Task completed and PRD item reference
    - Key decisions made and reasoning
    - Files changed
    - Any blockers or notes for next iteration
    Keep entries concise. Sacrifice grammar for the sake of concision. This file helps future iterations skip exploration.

9. **Report your status using the RALPH_STATUS block** (see PROMPT.md for format)

10. **If ALL user stories now have \`passes: true\`:**
   - Reply with: $COMPLETE_TOKEN
   - This signals that the entire project is complete

11. **STOP IMMEDIATELY after completing ONE story**
   - After updating prd.json and reporting status, YOU MUST STOP
   - Do NOT start working on another story
   - Do NOT continue to the next task
   - The loop will call you again for the next story



## CRITICAL REMINDERS

- Implement **ONE story per loop** - Focus completely on the selected story
- After commit + push + prd.json update → STOP WORKING
- **Priority field determines order** - Lower priority number = do first
- **Check existing code first** - Don't reimplement what already exists
- **Follow existing patterns** - Look at similar code in the codebase
- **All commits MUST pass typecheck and tests**
- **Update progress.txt with what you implemented**
- **Update AGENTS.md with reusable learnings** (not story-specific notes)

Now, analyze the PRD above and implement the next incomplete story (lowest priority number that has passes: false). STOP after completing it.
EOF
}






# Execute Claude Code with FULL context
# Returns: 0=success, 1=error, 2=project complete, 3=API limit, 4=timeout (after retries exhausted), 5=usage limit (with reset time)
execute_claude() {
    local project_dir=$1
    local loop_count=$2
    
    local max_timeout_retries=2  # Retry up to 2 more times on timeout (3 total attempts)
    local timeout_attempt=0
    
    log "LOOP" "Executing Claude Code (Loop #$loop_count)"
    
    # Generate prompt (not saved to disk)
    local prompt_content
    prompt_content=$(generate_full_prompt "$project_dir")
    
    local timeout_seconds=$((CLAUDE_TIMEOUT_MINUTES * 60))
    
    # Change to repo root for Claude
    cd "$REPO_ROOT"
    
    # Retry loop for timeout handling
    while true; do
        timeout_attempt=$((timeout_attempt + 1))
        
        local timestamp=$(date '+%Y-%m-%d_%H-%M-%S')
        local output_file="$project_dir/logs/claude_${timestamp}.log"
        
        if [[ $timeout_attempt -gt 1 ]]; then
            log "INFO" "⏳ Timeout retry $((timeout_attempt - 1))/$max_timeout_retries (timeout: ${CLAUDE_TIMEOUT_MINUTES}m)..."
        else
            log "INFO" "⏳ Starting Claude (timeout: ${CLAUDE_TIMEOUT_MINUTES}m)..."
        fi
        
        # Execute Claude
        if [[ "$VERBOSE" == "true" ]]; then
            log "INFO" "Running: $CLAUDE_CMD (output to terminal + $output_file)"
            log "INFO" "Press Ctrl+C to interrupt (no timeout in verbose mode)"
            # In verbose mode, show output in real-time AND save to file
            # Skip timeout in verbose mode so Ctrl+C works properly
            echo "$prompt_content" | $CLAUDE_CMD 2>&1 | tee "$output_file"
            claude_exit=${PIPESTATUS[0]}
        else
            echo "$prompt_content" | $TIMEOUT_CMD ${timeout_seconds}s $CLAUDE_CMD > "$output_file" 2>&1
            claude_exit=$?
        fi

        if [[ $claude_exit -eq 0 ]]; then
            log "SUCCESS" "✅ Claude execution completed"

            # Check for project completion token
            if grep -q "$COMPLETE_TOKEN" "$output_file"; then
                log "SUCCESS" "🎉 Claude signaled PROJECT COMPLETE!"
                return 2  # Special code for project complete
            fi

            # Analyze response
            analyze_response "$output_file" "$project_dir"
            local analysis_result=$?

            # Get analysis details
            local files_modified=$(get_analysis_result "$project_dir" "files_modified")
            local has_errors=$(get_analysis_result "$project_dir" "has_errors")
            local error_message=$(get_analysis_result "$project_dir" "error_message")
            local exit_signal=$(get_analysis_result "$project_dir" "exit_signal")
            local output_length=$(wc -c < "$output_file")

            # Record in circuit breaker
            record_loop_result "$project_dir" "$loop_count" "${files_modified:-0}" "$has_errors" "$output_length" "$error_message"

            # Log analysis
            log_analysis_summary "$project_dir"

            # Claude updates prd.json directly - no need to mark stories here
            # Just log completion status for visibility
            if [[ "$exit_signal" == "true" ]]; then
                log "SUCCESS" "📝 Claude signaled loop completion"
            fi

            return 0
        else
            # Check for "out of extra usage" first (before timeout retry logic)
            # This catches cases where Claude showed the limit message before we timed out
            if check_usage_limit "$output_file"; then
                log "WARN" "🚫 Claude out of extra usage - detected limit message"
                return 5  # Special code for usage limit with reset time
            fi

            # Check for timeout (exit code 124)
            if [[ $claude_exit -eq 124 ]]; then
                if [[ $timeout_attempt -le $max_timeout_retries ]]; then
                    log "WARN" "⏰ Claude timed out after ${CLAUDE_TIMEOUT_MINUTES} minutes (attempt $timeout_attempt/$((max_timeout_retries + 1)))"
                    log "INFO" "Retrying in 10 seconds..."
                    sleep 10
                    continue  # Retry
                else
                    log "ERROR" "❌ Claude timed out after ${CLAUDE_TIMEOUT_MINUTES} minutes (all $((max_timeout_retries + 1)) attempts exhausted)"
                    return 4  # Special code for timeout after retries
                fi
            else
                log "ERROR" "❌ Claude execution failed with code $claude_exit"
            fi

            # Check for 5-hour API limit
            if grep -qi "5.*hour.*limit\|limit.*reached\|usage.*limit" "$output_file" 2>/dev/null; then
                log "ERROR" "🚫 Claude API 5-hour usage limit reached"
                return 3  # Special code for API limit
            fi

            return 1
        fi
    done
}

# Setup tmux session
setup_tmux() {
    local project_name=$1
    local session_name="ralph-$project_name"

    log "INFO" "Setting up tmux session: $session_name"

    # Kill existing session if any
    log "INFO" "Cleaning up any existing session..."
    tmux kill-session -t "$session_name" 2>/dev/null || true

    # Create new session with the loop
    log "INFO" "Creating new tmux session: $session_name"
    if ! tmux new-session -d -s "$session_name" -c "$REPO_ROOT"; then
        log "ERROR" "Failed to create tmux session!"
        echo ""
        echo "Possible issues:"
        echo "  - tmux is not installed"
        echo "  - Another session with name '$session_name' is stuck"
        echo "  - Permission denied for tmux socket"
        echo ""
        echo "Try manually:"
        echo "  tmux kill-session -t $session_name"
        echo "  tmux new-session -s $session_name"
        echo ""
        echo "To list all sessions: tmux list-sessions"
        exit 1
    fi

    # Small delay to ensure session is ready
    sleep 0.2

    # Split horizontally
    log "INFO" "Splitting window for monitor..."
    if ! tmux split-window -h -t "$session_name" -c "$REPO_ROOT"; then
        log "ERROR" "Failed to split tmux window!"
        tmux kill-session -t "$session_name" 2>/dev/null || true
        exit 1
    fi

    # Start monitor in right pane
    log "INFO" "Starting monitor in right pane..."
    tmux send-keys -t "$session_name:0.1" "$SCRIPT_DIR/monitor.sh $project_name" Enter
    
    # Build command with options (without --monitor to avoid recursion)
    local start_cmd="$SCRIPT_DIR/start.sh $project_name"
    if [[ $MAX_ITERATIONS -gt 0 ]]; then
        start_cmd="$start_cmd -n $MAX_ITERATIONS"
    fi
    if [[ $MAX_CALLS_PER_HOUR -ne 100 ]]; then
        start_cmd="$start_cmd -c $MAX_CALLS_PER_HOUR"
    fi
    if [[ $CLAUDE_TIMEOUT_MINUTES -ne 20 ]]; then
        start_cmd="$start_cmd -t $CLAUDE_TIMEOUT_MINUTES"
    fi
    if [[ "$COMPLETE_TOKEN" != "<promise>COMPLETE</promise>" ]]; then
        start_cmd="$start_cmd --complete-token '$COMPLETE_TOKEN'"
    fi
    
    # Start loop in left pane
    tmux send-keys -t "$session_name:0.0" "$start_cmd" Enter

    # Select left pane
    tmux select-pane -t "$session_name:0.0"

    # Set window title
    tmux rename-window -t "$session_name:0" "Ralph: $project_name"

    # Save session info to a file for reference
    local project_dir="$SCRIPT_DIR/projects/$project_name"
    local session_info_file="$project_dir/tmux-session.txt"
    cat > "$session_info_file" << EOF
Wiggumz Tmux Session Info
==========================
Session Name: $session_name
Project: $project_name
Created: $(date)

Working Directory: $REPO_ROOT

Commands:
  To attach:    tmux attach -t $session_name
  To detach:    (press Ctrl+B, then D)
  To kill:      tmux kill-session -t $session_name
  To list all:  tmux list-sessions

Pane Layout:
  Left (0.0):  Ralph loop
  Right (0.1): Monitor
EOF

    log "SUCCESS" "tmux session created!"
    log "INFO" "Session info saved to: $session_info_file"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  tmux Controls"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Ctrl+B, D     - Detach (keeps Ralph running in background)"
    echo "  Ctrl+B, ←/→   - Switch between panes"
    echo "  Ctrl+B, [     - Scroll mode (use arrows, 'q' to exit)"
    echo ""
    echo "  To reattach:  tmux attach -t $session_name"
    echo "  To kill:      tmux kill-session -t $session_name"
    echo ""
    echo "  Session info: $session_info_file"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    # Attach to session
    tmux attach-session -t "$session_name"
    
    exit 0
}

# Validate that current branch matches prd.json branchName
validate_branch() {
    local project_dir=$1
    local prd_file="$project_dir/prd.json"
    
    local current_branch=$(git branch --show-current 2>/dev/null)
    local expected_branch=$(get_branch_name "$prd_file")
    
    if [[ -z "$current_branch" ]]; then
        log "WARN" "Not in a git repository or detached HEAD"
        return 0
    fi
    
    if [[ -z "$expected_branch" ]]; then
        log "WARN" "No branchName specified in prd.json - skipping branch validation"
        return 0
    fi
    
    if [[ "$current_branch" != "$expected_branch" ]]; then
        echo ""
        log "ERROR" "═══════════════════════════════════════════════════════════"
        log "ERROR" "  BRANCH MISMATCH DETECTED"
        log "ERROR" "═══════════════════════════════════════════════════════════"
        log "ERROR" ""
        log "ERROR" "  Current branch:   $current_branch"
        log "ERROR" "  Expected branch:  $expected_branch"
        log "ERROR" ""
        log "ERROR" "  The prd.json requires work to be done on: $expected_branch"
        log "ERROR" ""
        log "ERROR" "  Please switch to the correct branch:"
        log "ERROR" "    git checkout $expected_branch"
        log "ERROR" ""
        log "ERROR" "═══════════════════════════════════════════════════════════"
        exit 1
    fi
    
    return 0
}

# Confirm current branch before starting
confirm_branch() {
    local project_dir=$1
    local prd_file="$project_dir/prd.json"
    
    local current_branch=$(git branch --show-current 2>/dev/null)
    local expected_branch=$(get_branch_name "$prd_file")

    if [[ -z "$current_branch" ]]; then
        log "WARN" "Not in a git repository or detached HEAD"
        return 0
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Branch: $current_branch"
    if [[ -n "$expected_branch" ]]; then
        echo "  ⚠️  IMPORTANT: You can ONLY push to this branch!"
        echo "  ⚠️  Switching branches during execution is FORBIDDEN."
    fi
    echo "═══════════════════════════════════════════════════════════"
    read -p "Continue? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "INFO" "Aborted by user"
        exit 0
    fi

    return 0
}

# Main loop
main_loop() {
    local project_name=$1
    local project_dir="$SCRIPT_DIR/projects/$project_name"
    
    # Ensure logs directory exists
    mkdir -p "$project_dir/logs"
    
    # Set log file for this session
    mkdir -p "$project_dir/logs"
    export LOG_FILE="$project_dir/logs/ralph_$(date '+%Y%m%d').log"
    
    log "SUCCESS" "🚀 Ralph starting for project: $project_name"
    log "INFO" "Max calls/hour: $MAX_CALLS_PER_HOUR | Timeout: ${CLAUDE_TIMEOUT_MINUTES}m"
    if [[ $MAX_ITERATIONS -gt 0 ]]; then
        log "INFO" "Max iterations: $MAX_ITERATIONS"
    else
        log "INFO" "Max iterations: unlimited"
    fi
    log "INFO" "Complete token: $COMPLETE_TOKEN"
    
    # Validate branch matches prd.json branchName
    validate_branch "$project_dir"
    
    # Confirm current branch before starting
    confirm_branch "$project_dir"
    
    # Show initial status
    local total=$(count_total_stories "$project_dir/prd.json")
    local complete=$(count_complete_stories "$project_dir/prd.json")
    log "INFO" "Stories: $complete/$total complete"
    
    # Initialize
    init_rate_limiting "$project_dir"
    init_circuit_breaker "$project_dir"
    
    local loop_count=0
    
    # Main loop
    while true; do
        loop_count=$((loop_count + 1))
        
        if [[ $MAX_ITERATIONS -gt 0 ]]; then
            log "LOOP" "🔁  Loop #$loop_count / $MAX_ITERATIONS"
        else
            log "LOOP" "🔁  Loop #$loop_count"
        fi
        
        # Check max iterations
        if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $loop_count -gt $MAX_ITERATIONS ]]; then
            log "WARN" "✋ Max iterations reached ($MAX_ITERATIONS)"
            update_status "$project_dir" "$loop_count" "max_iterations" ""
            break
        fi
        
        # Check circuit breaker
        if should_halt_execution "$project_dir"; then
            log "ERROR" "🛑 Circuit breaker is OPEN - execution halted"
            log "INFO" "Run: ./ralph/start.sh $project_name --reset"
            update_status "$project_dir" "$loop_count" "halted" ""
            break
        fi
        
        # Check rate limit
        if ! can_make_call "$project_dir"; then
            wait_for_reset "$project_dir"
            continue
        fi
        
        # Check if all stories are complete BEFORE running Claude
        local incomplete=$(count_incomplete_stories "$project_dir/prd.json")
        if [[ "$incomplete" -eq 0 ]]; then
            log "SUCCESS" "🎉 All stories completed!"
            update_status "$project_dir" "$loop_count" "complete" ""
            
            local total=$(count_total_stories "$project_dir/prd.json")
            log "INFO" "Completed $total stories in $loop_count loops"
            break
        fi
        
        log "INFO" "Incomplete stories: $incomplete"

        # Get current story for tracking and logging
        local current_story=$(get_next_story "$project_dir/prd.json")
        local current_story_id=""
        local current_story_title=""

        if [[ -n "$current_story" ]]; then
            current_story_id=$(get_story_id "$current_story")
            current_story_title=$(get_story_title "$current_story")
            log "INFO" "Working on: [$current_story_id] $current_story_title"
            update_status "$project_dir" "$loop_count" "running" "$current_story_id"
        else
            update_status "$project_dir" "$loop_count" "running" ""
        fi

        # Increment call counter
        local calls=$(increment_call_counter "$project_dir")
        log "INFO" "API call $calls/$MAX_CALLS_PER_HOUR this hour"

        # Execute Claude with FULL context
        # Capture exit code manually to prevent set -e from exiting on non-zero
        local exec_result=0
        execute_claude "$project_dir" "$loop_count" || exec_result=$?

        if [[ $exec_result -eq 0 ]]; then
            # Fallback: Mark story complete if Claude reported success but didn't update prd.json
            if [[ -n "$current_story_id" ]]; then
                local status=$(get_analysis_result "$project_dir" "status")
                local tests=$(get_analysis_result "$project_dir" "tests_status")
                local has_block=$(get_analysis_result "$project_dir" "has_status_block")

                # DEBUG: Log what we got from analysis
                if [[ "$VERBOSE" == "true" ]]; then
                    log "DEBUG" "Analysis: status='$status' tests='$tests' has_status_block=$has_block"
                fi

                # Check if story is still incomplete before marking
                local still_incomplete=$(jq -r --arg id "$current_story_id" '
                    if type == "object" then
                        .userStories
                    else
                        .
                    end | [.[] | select(.id == $id and .passes == false)] | length
                ' "$project_dir/prd.json" 2>/dev/null)

                if [[ "$still_incomplete" -eq 1 ]]; then
                    # Mark complete if:
                    # - Status is COMPLETE (explicit), OR
                    # - Status is empty but tests are PASSING/NOT_RUN (implicit success), OR
                    # - Has no status block but exit was successful
                    local should_mark=false

                    if [[ "$status" == "COMPLETE" ]]; then
                        should_mark=true
                    elif [[ -z "$status" || "$status" == "null" ]]; then
                        if [[ "$tests" == "PASSING" || "$tests" == "NOT_RUN" ]]; then
                            should_mark=true
                        fi
                    fi

                    if [[ "$should_mark" == "true" ]]; then
                        mark_story_complete "$project_dir/prd.json" "$current_story_id"
                        local reason="status=$status"
                        log "SUCCESS" "✓ Marked story [$current_story_id] as complete ($reason)"
                    elif [[ "$VERBOSE" == "true" ]]; then
                        log "DEBUG" "Story [$current_story_id] not marked (status=$status, tests=$tests)"
                    fi
                fi
            fi

            update_status "$project_dir" "$loop_count" "success" ""
            log "INFO" "Pausing 5s before next loop..."
            sleep 5
        elif [[ $exec_result -eq 2 ]]; then
            # Project complete
            update_status "$project_dir" "$loop_count" "complete" ""
            log "SUCCESS" "🎉 Project marked as COMPLETE!"
            break
        elif [[ $exec_result -eq 5 ]]; then
            # Usage limit with reset time - wait until reset
            update_status "$project_dir" "$loop_count" "usage_limit" "" || true
            
            # Find the latest log file and wait for reset
            local latest_log
            latest_log=$(ls -t "$project_dir/logs/claude_"*.log 2>/dev/null | head -1) || true
            
            if [[ -n "$latest_log" ]]; then
                wait_for_usage_reset "$latest_log" || sleep 3600
            else
                log "WARN" "Could not find log file, waiting 1 hour..."
                sleep 3600
            fi
            
            log "SUCCESS" "✅ Limit reset! Resuming execution..."
        elif [[ $exec_result -eq 3 ]]; then
            # API limit
            update_status "$project_dir" "$loop_count" "api_limit" ""
            log "ERROR" "API limit reached. Waiting 60 minutes..."
            
            # Countdown
            local wait_seconds=3600
            while [[ $wait_seconds -gt 0 ]]; do
                printf "\r${YELLOW}Time until retry: $(format_duration $wait_seconds)${NC}"
                sleep 10
                wait_seconds=$((wait_seconds - 10))
            done
            printf "\n"
        elif [[ $exec_result -eq 4 ]]; then
            # Timeout after all retries exhausted
            update_status "$project_dir" "$loop_count" "timeout" ""
            log "WARN" "All timeout retries exhausted, waiting 60s before next loop..."
            sleep 60
        else
            update_status "$project_dir" "$loop_count" "error" ""
            log "WARN" "Execution failed, waiting 30s before retry..."
            sleep 30
        fi
        
        log "LOOP" "═══════════════════════════════════════════════════════════"
        log "LOOP" "  End Loop #$loop_count"
        log "LOOP" "═══════════════════════════════════════════════════════════"
        echo ""
    done
    
    log "INFO" "Ralph loop finished"
}

# Stop a running project
stop_project() {
    local project_name=$1
    local session_name="ralph-$project_name"
    local stopped=false

    echo ""
    echo "Stopping project: $project_name"

    # Try tmux session first
    if command -v tmux &>/dev/null; then
        if tmux list-sessions 2>/dev/null | grep -q "^$session_name"; then
            tmux kill-session -t "$session_name" 2>/dev/null
            echo "  ✓ Killed tmux session: $session_name"
            stopped=true
        fi
    fi

    # Kill any start.sh processes for this project
    if pkill -f "start.sh.*$project_name" 2>/dev/null; then
        echo "  ✓ Killed start.sh processes"
        stopped=true
    fi

    # Kill any claude processes for this project
    if pkill -f "claude.*$project_name" 2>/dev/null; then
        echo "  ✓ Killed claude processes"
        stopped=true
    fi

    if [[ "$stopped" == "true" ]]; then
        echo ""
        log "SUCCESS" "✓ Stopped project: $project_name"
    else
        echo ""
        log "WARN" "No running processes found for: $project_name"
    fi
}

# Setup verification (doctor)
doctor() {
    local all_good=true
    local errors=()

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Ralph Setup Verification"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Checking dependencies..."
    echo ""

    # Check required commands
    local required_cmds=("jq" "claude")
    local optional_cmds=("tmux" "gh" "uv" "timeout" "gtimeout")

    for cmd in "${required_cmds[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            local version=$($cmd --version 2>/dev/null | head -1 || echo "ok")
            echo "  ✓ $cmd${version:+ ($version)}"
        else
            echo "  ✗ $cmd - REQUIRED but not found"
            errors+=("Install $cmd")
            all_good=false
        fi
    done

    for cmd in "${optional_cmds[@]}"; do
        if [[ "$cmd" == "timeout" ]]; then
            if command -v gtimeout &>/dev/null || command -v timeout &>/dev/null; then
                echo "  ✓ $cmd (or gtimeout)"
            else
                echo "  ⚠ $cmd - Recommended (install coreutils on macOS)"
            fi
        elif command -v "$cmd" &>/dev/null; then
            echo "  ✓ $cmd"
        else
            echo "  ⚠ $cmd - Optional but recommended"
        fi
    done

    echo ""

    # Check git
    if git rev-parse --git-dir >/dev/null 2>&1; then
        local branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        echo "  ✓ git repository (branch: $branch)"
    else
        echo "  ✗ not a git repository"
        errors+=("Initialize git repository")
        all_good=false
    fi

    # Check projects directory
    if [[ -d "$SCRIPT_DIR/projects" ]]; then
        local count=$(find "$SCRIPT_DIR/projects" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        echo "  ✓ projects directory ($count projects)"
    else
        echo "  ⚠ projects directory not found (will be created on first use)"
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════"

    if [[ "$all_good" == "true" ]]; then
        log "SUCCESS" "✓ All required dependencies installed!"
        echo ""
        echo "You're ready to run:"
        echo "  ./start.sh <project-name> --verbose"
        return 0
    else
        log "ERROR" "✗ Some required dependencies are missing"
        echo ""
        echo "Fixes needed:"
        for err in "${errors[@]}"; do
            echo "  • $err"
        done
        echo ""
        return 1
    fi
}

# Show project status
show_status() {
    local project_name=$1
    local project_dir="$SCRIPT_DIR/projects/$project_name"
    
    if [[ ! -f "$project_dir/status.json" ]]; then
        log "ERROR" "No status file found"
        exit 1
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Project: $project_name"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    jq -r '
        "  Status:          \(.status)",
        "  Loop count:      \(.loop_count)",
        "  Current story:   \(.current_story // "none")",
        "  Progress:        \(.stories_complete)/\(.stories_total) stories",
        "  Calls this hour: \(.calls_this_hour)/\(.max_calls_per_hour)",
        "  Last updated:    \(.timestamp)"
    ' "$project_dir/status.json"
    echo ""
    
    # Show incomplete stories (handle both formats)
    echo "───────────────────────────────────────────────────────────"
    echo "  Pending Stories"
    echo "───────────────────────────────────────────────────────────"
    jq -r 'if type == "object" then .userStories else . end | [.[] | select(.passes == false)] | sort_by(.priority // 999) | .[:5][] | "  ○ [\(.id)] P\(.priority // "?") \(.story | .[0:45])"' "$project_dir/prd.json" 2>/dev/null || echo "  (none)"
    echo ""
    
    # Show circuit breaker status
    show_circuit_status "$project_dir"
}

# Parse arguments
PROJECT_NAME=""
ACTION="run"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -m|--monitor)
            USE_TMUX=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -n|--max-iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        -c|--calls)
            MAX_CALLS_PER_HOUR="$2"
            shift 2
            ;;
        -t|--timeout)
            CLAUDE_TIMEOUT_MINUTES="$2"
            shift 2
            ;;
        --complete-token)
            COMPLETE_TOKEN="$2"
            shift 2
            ;;
        --claude-cmd)
            CLAUDE_CMD="$2"
            shift 2
            ;;
        -s|--status)
            ACTION="status"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --doctor|--check)
            ACTION="doctor"
            shift
            ;;
        -r|--reset)
            ACTION="reset"
            shift
            ;;
        *)
            if [[ -z "$PROJECT_NAME" ]]; then
                PROJECT_NAME="$1"
            fi
            shift
            ;;
    esac
done

# Handle doctor (no project required)
if [[ "$ACTION" == "doctor" ]]; then
    doctor
    exit $?
fi

# Validate project name for actions that need it
if [[ -z "$PROJECT_NAME" ]]; then
    log "ERROR" "Project name is required"
    show_help
    exit 1
fi

PROJECT_DIR="$SCRIPT_DIR/projects/$PROJECT_NAME"

# For stop action, project may not exist (just kill processes)
if [[ "$ACTION" != "stop" ]]; then
    # Check if project exists
    if [[ ! -d "$PROJECT_DIR" ]]; then
        log "ERROR" "Project '$PROJECT_NAME' does not exist"
        log "INFO" "Create it first with: ./ralph/new.sh $PROJECT_NAME"
        exit 1
    fi

    # Check dependencies
    check_dependencies || exit 1
fi

# Execute action
case "$ACTION" in
    "status")
        show_status "$PROJECT_NAME"
        ;;
    "stop")
        stop_project "$PROJECT_NAME"
        ;;
    "reset")
        reset_circuit_breaker "$PROJECT_DIR" "Manual reset via CLI"
        ;;
    "run")
        if [[ "$USE_TMUX" == "true" ]]; then
            setup_tmux "$PROJECT_NAME"
        else
            main_loop "$PROJECT_NAME"
        fi
        ;;
esac