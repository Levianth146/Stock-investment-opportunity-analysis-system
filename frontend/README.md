<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# Run and deploy your AI Studio app

For the integrated StockAI frontend, follow [FASTAPI_FRONTEND.md](../docs/FASTAPI_FRONTEND.md) and run `scripts/run_api.py` from the repository root. FastAPI serves the committed `dist` build, including the full snapshot ticker picker and backend analysis panels. The React source retained from `main` does not yet include all of those integrations; port the adapters into `src` before rebuilding `dist`.

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/b0deeb6d-f839-496d-9f69-0aea8b4790f4

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`
