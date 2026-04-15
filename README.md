# OpenClaw for Home Assistant

Home Assistant integration that connects [OpenClaw](https://openclaw.com) agents as conversation agents for voice assistants.

## Features

- **Voice assistant** — Use OpenClaw agents in HA's Assist pipeline
- **Zero-config discovery** — Automatically detects the OpenClaw add-on
- **Persistent sessions** — Conversations persist per device, user, or session
- **Streaming** — SSE streaming with hard timeouts (never hangs)
- **Multi-agent** — Choose which agent handles voice (main, butler, etc.)

## Requirements

- Home Assistant 2025.4 or newer
- [OpenClaw add-on](https://github.com/bonzanni/openclaw-ha-app) installed and running

## Installation

### HACS (recommended)

1. Add this repository to HACS as a custom repository
2. Install **OpenClaw** from HACS
3. Restart Home Assistant

### Manual

Copy `custom_components/openclaw/` to your HA `config/custom_components/` directory and restart.

## Setup

### With the OpenClaw add-on (zero-config)

If the OpenClaw add-on is running, the integration is discovered automatically. Go to **Settings > Devices & Services** and click **Configure** on the discovered OpenClaw entry.

### Without the add-on (standalone gateway)

Go to **Settings > Devices & Services > Add Integration**, search for **OpenClaw**, and enter your gateway's host, port, and token.

## Configuration

After setup, go to the integration's options to configure:

| Option | Description | Default |
|---|---|---|
| **Agent** | Which OpenClaw agent handles conversations | `main` |
| **Session persistence** | How context persists: per device, per user, or per conversation | Per device |

## Voice assistant setup

1. Go to **Settings > Voice assistants**
2. Create or edit a voice assistant
3. Under **Conversation agent**, select **OpenClaw**

## Session persistence modes

| Mode | Behavior |
|---|---|
| **Per device** | Kitchen satellite remembers kitchen conversations |
| **Per user** | Your assistant remembers you across all devices |
| **Per conversation** | Each new voice session starts fresh |
