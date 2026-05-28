# Free LLM API Proxy for Vercel

This is an OpenAI-compatible API proxy deployed on Vercel. It uses a validated free API key for **DeepSeek Chat**, one of the smartest coding models available.

## Usage

### Endpoint
`POST https://your-project.vercel.app/api/chat`

### Payload (Standard OpenAI Format)
```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "user", "content": "Write a python script to sort a list."}
  ],
  "stream": true
}
```

### Example using cURL
```bash
curl https://your-project.vercel.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Deployment
1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel deploy`

## Key Information
- **Model:** DeepSeek Chat (V3)
- **Status:** Validated & Active
- **Provider:** alistaitsacle/free-llm-api-keys
