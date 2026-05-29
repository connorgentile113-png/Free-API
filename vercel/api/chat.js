const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));

const README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md";
const BASE_URL = "https://aiapiv2.pekpik.com/v1/chat/completions";

// Prioritized list of "smartest" models for coding/text tasks
const MODEL_PRIORITY = [
    "claude-3-7-sonnet",
    "claude-3-5-sonnet",
    "gpt-5.5",
    "gpt-4o",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "deepseek-reasoner",
    "deepseek-chat",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "smart-chat",
    "kimi-k2.5"
];

async function fetchAndParseKeys() {
    try {
        const response = await fetch(README_URL);
        const content = await response.text();
        
        const pattern = /\| `(sk-[a-zA-Z0-9]+)` \| ([a-zA-Z0-9.-]+) \| [^|]+ \| ([^|]+) \| ([^|]+) \|/g;
        let match;
        const keys = [];
        
        while ((match = pattern.exec(content)) !== null) {
            keys.push({
                key: match[1],
                model: match[2],
                budget: match[3].trim(),
                rpm: match[4].trim()
            });
        }
        return keys;
    } catch (e) {
        console.error("Error fetching README:", e);
        return [];
    }
}

async function isKeyWorking(key, model) {
    try {
        const response = await fetch(BASE_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${key}`
            },
            body: JSON.stringify({
                messages: [{ role: 'user', content: 'hi' }],
                model: model,
                max_tokens: 1
            }),
            timeout: 5000 
        });
        return response.ok;
    } catch {
        return false;
    }
}

function initialRank(keys) {
    const textKeys = keys.filter(k => 
        !k.model.includes("embedding") && 
        !k.model.includes("tts") && 
        !k.model.includes("dall-e") &&
        !k.model.includes("whisper")
    );

    return textKeys.sort((a, b) => {
        let idxA = MODEL_PRIORITY.indexOf(a.model);
        let idxB = MODEL_PRIORITY.indexOf(b.model);
        if (idxA === -1) idxA = 999;
        if (idxB === -1) idxB = 999;
        return idxA - idxB;
    });
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Credentials', true);
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    // 1. Fetch all candidates from README
    const allKeys = await fetchAndParseKeys();
    let candidates = initialRank(allKeys);

    if (candidates.length === 0) {
        return res.status(503).json({ error: 'nomodels' });
    }

    // 2. ACTIVE HEALTH CHECK & RERANK
    // We check the top candidates to find what's ACTUALLY working right now
    console.log(`[*] Validating top ${Math.min(candidates.length, 5)} candidates...`);
    
    const validatedKeys = [];
    const checkLimit = Math.min(candidates.length, 8); // Check up to 8 top keys in parallel
    
    const checkPromises = candidates.slice(0, checkLimit).map(async (item) => {
        const working = await isKeyWorking(item.key, item.model);
        return working ? item : null;
    });

    const checkResults = await Promise.all(checkPromises);
    const workingCandidates = checkResults.filter(k => k !== null);

    // 3. Rerank: Put confirmed working keys at the absolute top, keeping priority order
    // If no working keys found in top 8, we might still have others to try, 
    // but we'll prioritize the ones we confirmed.
    const finalQueue = [...workingCandidates];
    
    // Add the rest of the candidates that weren't checked or failed check (just in case)
    candidates.forEach(c => {
        if (!finalQueue.find(q => q.key === c.key)) {
            finalQueue.push(c);
        }
    });

    if (workingCandidates.length === 0) {
        console.warn("[!] No confirmed working models found during health check.");
    }

    const { messages, stream, ...rest } = req.body;

    // 4. Try keys in the reranked order
    // We try until success or exhaustion of top 3 confirmed/best keys
    const maxTries = 3;
    for (let i = 0; i < Math.min(finalQueue.length, maxTries); i++) {
        const selected = finalQueue[i];
        console.log(`[*] Processing request with confirmed/best model: ${selected.model}`);

        try {
            const response = await fetch(BASE_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${selected.key}`
                },
                body: JSON.stringify({
                    messages,
                    model: selected.model,
                    stream: stream || false,
                    ...rest
                }),
                timeout: 10000 
            });

            if (response.ok) {
                if (stream) {
                    res.setHeader('Content-Type', 'text/event-stream');
                    res.setHeader('Cache-Control', 'no-cache');
                    res.setHeader('X-Model-Used', selected.model);
                    res.write(`data: ${JSON.stringify({ type: 'model', modelUsed: selected.model })}\n\n`);
                    response.body.pipe(res);
                } else {
                    const data = await response.json();
                    data.modelUsed = selected.model;
                    data.model = data.model || selected.model;
                    return res.status(200).json(data);
                }
                return;
            }
        } catch (err) {
            console.error(`[!] Final request error with ${selected.model}:`, err.message);
        }
    }

    return res.status(500).json({ error: 'nomodels', details: 'All health-checked models failed to process the request.' });
}
