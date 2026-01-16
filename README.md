# Linear Dashboard Mirror

This repository mirrors a Linear dashboard view to GitHub Pages, automatically updating the dashboard on a schedule. The dashboard features **interactive drag-and-drop** functionality, allowing you to move cards between columns and automatically sync changes back to Linear.

## Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- A Linear API key (get it from [Linear Settings](https://linear.app/settings/api))

### Installation

1. Install dependencies using uv:
   ```bash
   uv sync
   ```

2. Create a `.env` file in the root directory:
   ```env
   LINEAR_API_KEY=your_linear_api_key_here
   LINEAR_VIEW_NAME=rr-intermediacoes
   WORKER_URL=https://your-worker.workers.dev  # Optional: for drag-and-drop updates
   ```

### Usage

Run the script to generate the dashboard:

```bash
uv run python generate.py
```

This will:
- Query your Linear workspace for the view named "rr-intermediacoes" (or the name specified in `LINEAR_VIEW_NAME`)
- Fetch all issues matching that view's filters
- Generate `docs/index.html` with the dashboard

### GitHub Pages Setup

1. In your repository settings, go to Pages
2. Set the source to "Deploy from a branch"
3. Select branch: `main` and folder: `/docs`
4. The dashboard will be available at `https://yourusername.github.io/rr-work-dashboard/`

### GitHub Actions (Optional)

If you want to automatically update the dashboard, set up a GitHub Actions workflow that:
- Runs on a schedule (e.g., every 30 minutes)
- Uses `uv run python generate.py` to regenerate the dashboard
- Commits the updated `docs/index.html` back to the repository

Make sure to add `LINEAR_API_KEY` as a GitHub secret in your repository settings.

## Drag-and-Drop Updates

The dashboard supports interactive drag-and-drop to move issues between columns. Changes are automatically synced back to Linear via a Cloudflare Worker proxy.

### Setting Up the Cloudflare Worker

1. **Deploy the worker** (see `worker/README.md` for detailed instructions):
   ```bash
   cd worker
   wrangler login
   wrangler secret put LINEAR_API_KEY
   wrangler deploy
   ```

2. **Add the worker URL** to your environment:
   - For local development: Add `WORKER_URL` to your `.env` file
   - For GitHub Actions: Add `WORKER_URL` as a repository variable or secret

3. **Regenerate the dashboard** with the worker URL:
   ```bash
   uv run python generate.py
   ```

The dashboard will automatically enable drag-and-drop when `WORKER_URL` is set. Without it, the dashboard works in read-only mode.

### How It Works

- Drag a card to move it between columns
- The worker securely updates Linear's API (your API key stays server-side)
- Changes are reflected immediately in the UI
- If an update fails, the card reverts to its original position

See `worker/README.md` for more details on the Cloudflare Worker setup.
