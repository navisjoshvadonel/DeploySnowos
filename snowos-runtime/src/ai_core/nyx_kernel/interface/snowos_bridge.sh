#!/bin/bash

# SnowOS Universal Command Bridge
# Intercepts failures and routes them to Nyx for analysis.

SNOWOS_PYTHON="/home/develop/snowos/nyx/venv/bin/python3"
SNOWOS_BRIDGE_CLIENT="/home/develop/snowos/nyx/interface/bridge_client.py"

# --- Bash Integration ---
if [ -n "$BASH_VERSION" ]; then
    command_not_found_handle() {
        local cmd="$1"
        $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$cmd" "127" "Command not found"
        return 127
    }

    # Hook into prompt to catch non-zero exit codes
    snowos_post_command() {
        local exit_code=$?
        local last_cmd=$(history 1 | sed 's/^[ ]*[0-9]*[ ]*//')
        
        if [ $exit_code -ne 0 ] && [ $exit_code -ne 127 ]; then
            # We don't have stderr here easily without complex hacks, 
            # so we let Nyx infer it or we could redirect in a wrapper.
            $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$last_cmd" "$exit_code"
        fi
    }
    PROMPT_COMMAND="snowos_post_command; $PROMPT_COMMAND"
fi

# --- ZSH Integration ---
if [ -n "$ZSH_VERSION" ]; then
    command_not_found_handler() {
        local cmd="$1"
        $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$cmd" "127" "Command not found"
        return 127
    }

    snowos_precmd() {
        local exit_code=$?
        if [ $exit_code -ne 0 ] && [ $exit_code -ne 127 ]; then
            # Get last command from history
            local last_cmd=$(fc -ln -1)
            $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$last_cmd" "$exit_code"
        fi
    }
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd snowos_precmd
fi

echo -e "\033[1;36m❄️ SnowOS Bridge Active\033[0m"
