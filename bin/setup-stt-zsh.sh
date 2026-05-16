#!/usr/bin/env bash
# Install / uninstall zsh shell functions `dictate-stt` and `transscribe-stt`
# that wrap `speech-to-text-modern` with preset flags, plus tab-completion.
#
# Usage:
#   bin/setup-stt-zsh.sh install    # add functions + completions to ~/.zshrc
#   bin/setup-stt-zsh.sh uninstall  # remove them again
#   bin/setup-stt-zsh.sh status     # show whether currently installed
#
# Implementation: writes a self-contained snippet to
# ~/.config/python-speech-to-text-parakeet/stt.zsh and sources it from ~/.zshrc
# inside a marked block (BEGIN/END python-speech-to-text-parakeet stt) so install/uninstall stay
# idempotent and don't touch unrelated lines.

set -euo pipefail

SNIPPET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/python-speech-to-text-parakeet"
SNIPPET_PATH="$SNIPPET_DIR/stt.zsh"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
BEGIN_MARK="# >>> python-speech-to-text-parakeet stt >>>"
END_MARK="# <<< python-speech-to-text-parakeet stt <<<"

write_snippet() {
    mkdir -p "$SNIPPET_DIR"
    cat > "$SNIPPET_PATH" <<'EOF'
# python-speech-to-text-parakeet: speech-to-text shell helpers (managed file — do not edit).
# Regenerate via `bin/setup-stt-zsh.sh install`.

# Record mic + transcribe + copy to clipboard + system notification.
# Deletes both the recording and the generated transcription afterwards.
dictate-stt() {
    command speech-to-text-modern --record --cleanup all --copy --notify "$@"
}

# Same as dictate-stt but keeps the generated markdown file (deletes only the audio).
dictate-stt-md() {
    command speech-to-text-modern --record --format md --cleanup audio --copy --notify "$@"
}

# Same as dictate-stt but keeps only the audio recording (deletes the transcription).
dictate-stt-audio() {
    command speech-to-text-modern --record --cleanup transcription --copy --notify "$@"
}

# Same as dictate-stt but keeps both the audio recording and the markdown transcription.
dictate-stt-all() {
    command speech-to-text-modern --record --format md --copy --notify "$@"
}

# Transcribe a file or folder to a markdown file (always overwrites, notifies on done).
# Requires a path as first argument.
transscribe-stt() {
    if [[ $# -eq 0 ]]; then
        print -u2 "transscribe-stt: missing file or folder argument"
        return 2
    fi
    command speech-to-text-modern --format md --no-skip --notify "$@"
}

# --- Completions -------------------------------------------------------------
# `dictate-stt` takes no positional path, only flags forwarded to speech-to-text-modern.
_dictate_stt() {
    local -a flags
    flags=(
        '--no-skip[force re-transcription]'
        '--cleanup[items to delete: audio|transcription|all]:cleanup:(audio transcription all)'
        '--format[output format]:format:(txt md)'
        '--output-dir[custom output directory]:dir:_files -/'
        '--model[transcription model]:model:'
        '--provider[transcription provider]:provider:'
        '--copy[copy transcript to clipboard]'
        '--notify[send system notification]'
        '--pipe[print transcript to stdout only]'
        '-v[verbose]'
        '--verbose[verbose]'
    )
    _arguments -s $flags
}

# `transscribe-stt` takes a path (file or directory) + flags.
_transscribe_stt() {
    _arguments -s \
        '1:audio file or directory:_files' \
        '*:audio file or directory:_files' \
        '--recursive[walk folders recursively]' \
        '--no-skip[force re-transcription]' \
        '--cleanup[items to delete: audio|transcription|all]:cleanup:(audio transcription all)' \
        '--format[output format]:format:(txt md)' \
        '--output-dir[custom output directory]:dir:_files -/' \
        '--model[transcription model]:model:' \
        '--provider[transcription provider]:provider:' \
        '--copy[copy transcript to clipboard]' \
        '--notify[send system notification]' \
        '--pipe[print transcript to stdout only]' \
        '-v[verbose]' \
        '--verbose[verbose]'
}

compdef _dictate_stt dictate-stt
compdef _dictate_stt dictate-stt-md
compdef _dictate_stt dictate-stt-audio
compdef _dictate_stt dictate-stt-all
compdef _transscribe_stt transscribe-stt
EOF
}

install_block() {
    write_snippet
    touch "$ZSHRC"
    if grep -qF "$BEGIN_MARK" "$ZSHRC"; then
        echo "Already installed in $ZSHRC — snippet refreshed at $SNIPPET_PATH."
        return 0
    fi
    {
        echo ""
        echo "$BEGIN_MARK"
        echo "# Managed by bin/setup-stt-zsh.sh — do not edit between markers."
        echo "autoload -Uz compinit && compinit -i"
        echo "source \"$SNIPPET_PATH\""
        echo "$END_MARK"
    } >> "$ZSHRC"
    echo "Installed dictate-stt + dictate-stt-md + dictate-stt-audio + dictate-stt-all + transscribe-stt into $ZSHRC."
    echo "Run 'exec zsh' or open a new shell to activate."
}

uninstall_block() {
    if [[ -f "$ZSHRC" ]] && grep -qF "$BEGIN_MARK" "$ZSHRC"; then
        local tmp
        tmp="$(mktemp)"
        awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
            $0 == b {skip=1; next}
            $0 == e {skip=0; next}
            !skip
        ' "$ZSHRC" > "$tmp"
        mv "$tmp" "$ZSHRC"
        echo "Removed block from $ZSHRC."
    else
        echo "No installation marker found in $ZSHRC."
    fi
    if [[ -f "$SNIPPET_PATH" ]]; then
        rm -f "$SNIPPET_PATH"
        echo "Removed snippet $SNIPPET_PATH."
    fi
    echo "Run 'exec zsh' or open a new shell to apply."
}

status() {
    if [[ -f "$ZSHRC" ]] && grep -qF "$BEGIN_MARK" "$ZSHRC"; then
        echo "Installed (block present in $ZSHRC)."
    else
        echo "Not installed."
    fi
    if [[ -f "$SNIPPET_PATH" ]]; then
        echo "Snippet:  $SNIPPET_PATH"
    else
        echo "Snippet:  (missing)"
    fi
}

case "${1:-}" in
    install)   install_block ;;
    uninstall) uninstall_block ;;
    status)    status ;;
    *)
        echo "Usage: $0 {install|uninstall|status}" >&2
        exit 2
        ;;
esac
