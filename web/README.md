# KOPI AI AGENT — Web Interface

Web-based chat interface for [KOPI AI AGENT](https://kopiaiagent.com).

## Setup

```bash
npm install
kopi gateway start  # Gateway must be running
```

## Development

```bash
npm run dev
```

The web UI connects to the local KOPI gateway at `ws://localhost:9090`.

## Build

```bash
npm run build
```

## Deploy

Deploy the `dist/` directory to any static hosting. The web UI connects to `wss://kopiaiagent.com/gateway`.

## License

MIT
