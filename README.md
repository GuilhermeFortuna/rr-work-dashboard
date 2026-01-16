# Linear Dashboard Mirror

This repository mirrors a Linear dashboard view to GitHub Pages, automatically updating the dashboard on a schedule.

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
