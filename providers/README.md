# KOPI AI AGENT — Providers

Model provider configurations for [KOPI AI AGENT](https://kopiaiagent.com).

## Built-in Providers

| Provider | Default Models | Auth |
|----------|---------------|------|
| **KOPI Proxy** | kopi-o, kopi-o-flash, kopi-flash | `KOPI_PROXY_API_KEY` env var |
| OpenRouter | All models | `OPENROUTER_API_KEY` env var |
| OpenAI | GPT-4o, o3, etc. | `OPENAI_API_KEY` env var |
| Anthropic | Claude Sonnet 4, etc. | `ANTHROPIC_API_KEY` env var |
| Google | Gemini 2.5 Pro, etc. | `GOOGLE_API_KEY` env var |
| Custom | Any OpenAI-compatible endpoint | Config in `~/.kopi/config.yaml` |

## KOPI Proxy

The default provider. Auto-provisioned on install with 5M token quota.

```bash
# Check your quota
curl -H "Authorization: Bearer $KOPI_PROXY_API_KEY" https://kopiaiagent.com/kp/v1/quota

# List available models
curl -H "Authorization: Bearer $KOPI_PROXY_API_KEY" https://kopiaiagent.com/kp/v1/models
```

## Adding a Custom Provider

Edit `~/.kopi/config.yaml`:

```yaml
custom_providers:
  - name: My Provider
    base_url: https://my-endpoint.com/v1
    api_key_env: MY_API_KEY
    models:
      my-model:
        max_input_tokens: 128000
        max_output_tokens: 4096
```

## License

MIT
