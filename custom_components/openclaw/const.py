"""Constants for OpenClaw integration."""

from __future__ import annotations

DOMAIN = "openclaw"

# Config entry data keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"

# Options keys
CONF_AGENT_ID = "agent_id"
CONF_SESSION_MODE = "session_mode"

# Session modes
SESSION_MODE_DEVICE = "device"
SESSION_MODE_USER = "user"
SESSION_MODE_CONVERSATION = "conversation"

# Defaults
DEFAULT_PORT = 18789
DEFAULT_AGENT_ID = "default"
DEFAULT_SESSION_MODE = SESSION_MODE_DEVICE

# Timeouts (seconds)
TIMEOUT_CONNECT = 3
TIMEOUT_TOTAL = 30
TIMEOUT_HEALTH = 5

# Error messages (speech fallbacks for voice — must never hang silently)
ERROR_TIMEOUT = "Sorry, the assistant took too long to respond."
ERROR_CONNECTION = "Sorry, I'm having trouble reaching the assistant right now."
ERROR_AUTH = "Authentication with the assistant failed. Please reconfigure."
