#!/bin/bash

# SnowOS Universal Command Bridge
# Intercepts failures and routes them to Nyx for analysis.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNOWOS_PYTHON="${SNOWOS_PYTHON:-python3}"
SNOWOS_BRIDGE_CLIENT="$SCRIPT_DIR/bridge_client.py"

if [ -n "$BASH_VERSION" ]; then
    command_not_found_handle() {
        local cmd="$1"
        $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$cmd" "127" "Command not found"
        return 127
    }

    snowos_post_command() {
        local exit_code=$?
        local last_cmd
        last_cmd=$(history 1 | sed 's/^[ ]*[0-9]*[ ]*//')

        if [ $exit_code -ne 0 ] && [ $exit_code -ne 127 ]; then
            $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$last_cmd" "$exit_code"
        fi
    }
    PROMPT_COMMAND="snowos_post_command; $PROMPT_COMMAND"
fi

if [ -n "$ZSH_VERSION" ]; then
    command_not_found_handler() {
        local cmd="$1"
        $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$cmd" "127" "Command not found"
        return 127
    }

    snowos_precmd() {
        local exit_code=$?
        if [ $exit_code -ne 0 ] && [ $exit_code -ne 127 ]; then
            local last_cmd
            last_cmd=$(fc -ln -1)
            $SNOWOS_PYTHON $SNOWOS_BRIDGE_CLIENT "$last_cmd" "$exit_code"
        fi
    }
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd snowos_precmd
fi

echo "SnowOS Bridge Active"
