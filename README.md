# Excerpt Player

Local Mac app that reads a scanned or photographed violin excerpt and plays it back. Spec is in `BUILD_PLAN.md`, background in `BRAINSTORM.md`.

Status: milestone 1 (skeleton). The app starts and shows which OMR engines are installed. Upload, rendering and playback come in later milestones.

## Install

```bash
brew install uv node
```

Install Audiveris from its GitHub releases page (the macOS `.dmg`). On first launch macOS may need it allowed under System Settings → Privacy & Security. If it lives somewhere other than `/Applications/Audiveris.app`, set `AUDIVERIS_BIN` to the binary path.

```bash
make setup
```

## Run

```bash
make start
```

Builds the frontend, starts the server and opens `http://localhost:8000`.

## Develop

```bash
make dev
```

Backend with reload on `:8000`, Vite dev server on `http://localhost:5173` proxying `/api`.

```bash
make test
```
