"""
POC: List all available models via GitHub Models API
Shows model names, rate limits, and tier (free vs premium)
"""
import os
import httpx
import json

TOKEN = os.environ.get("GITHUB_TOKEN", "")

if not TOKEN:
    print("ERROR: Set GITHUB_TOKEN environment variable first")
    print("  Windows: set GITHUB_TOKEN=ghp_your_token_here")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

print("Fetching available models from GitHub Models API...\n")

# GitHub Models catalog endpoint
response = httpx.get(
    "https://models.inference.ai.azure.com/models",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    },
    timeout=15,
)

print(f"Status: {response.status_code}\n")

if response.status_code == 200:
    models = response.json()
    if isinstance(models, list):
        print(f"{'Model ID':<50} {'Publisher':<20} {'Rate Limit Tier'}")
        print("-" * 100)
        for m in sorted(models, key=lambda x: x.get("name", "")):
            model_id = m.get("name", m.get("id", "unknown"))
            publisher = m.get("publisher", "unknown")
            # Rate limit info if available
            rate = m.get("rate_limit_tier", m.get("rateLimitTier", "unknown"))
            friendly = m.get("friendly_name", "")
            print(f"{model_id:<50} {publisher:<20} {rate}  {friendly}")
        print(f"\nTotal: {len(models)} models")
        # Save full response for inspection
        with open("github_models.json", "w") as f:
            json.dump(models, f, indent=2)
        print("Full details saved to github_models.json")
    else:
        print("Unexpected response format:")
        print(json.dumps(models, indent=2)[:2000])
else:
    print(f"Error response: {response.text[:500]}")
    print("\nTrying alternative endpoint...")
    # Try the OpenAI-compatible endpoint
    from openai import OpenAI
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=TOKEN,
    )
    try:
        models = client.models.list()
        print(f"\n{'Model ID':<50} {'Object'}")
        print("-" * 70)
        for m in models.data:
            print(f"{m.id:<50} {m.object}")
        print(f"\nTotal: {len(models.data)} models")
    except Exception as e:
        print(f"OpenAI SDK also failed: {e}")
