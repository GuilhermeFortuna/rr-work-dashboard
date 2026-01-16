# Linear Dashboard Cloudflare Worker

This Cloudflare Worker acts as a secure proxy between the GitHub Pages dashboard and Linear's API, allowing drag-and-drop updates without exposing API keys.

## Setup

### Prerequisites

- A Cloudflare account (free tier works)
- Wrangler CLI installed: `npm install -g wrangler`
- Your Linear API key

### Deployment

1. **Login to Cloudflare:**
   ```bash
   wrangler login
   ```

2. **Set your Linear API key as a secret:**
   ```bash
   wrangler secret put LINEAR_API_KEY
   ```
   When prompted, enter your Linear API key.

3. **Deploy the worker:**
   ```bash
   cd worker
   wrangler deploy
   ```

4. **Get your worker URL:**
   After deployment, you'll get a URL like: `https://linear-dashboard-proxy.your-subdomain.workers.dev`

5. **Update your environment:**
   Add the worker URL to your `.env` file:
   ```env
   WORKER_URL=https://linear-dashboard-proxy.your-subdomain.workers.dev
   ```

   Or set it as a GitHub Actions secret/variable if using CI/CD.

## API Endpoints

- `POST /update` - Update an issue's state
  - Body: `{ issueId, targetState, targetStateId?, order? }`
  - Returns: `{ success: true, issue: {...} }`

- `GET /health` - Health check endpoint
  - Returns: `{ status: 'ok' }`

## CORS

The worker allows requests from any origin (`*`). For production, you may want to restrict this to your GitHub Pages domain.

To restrict CORS, update the `corsHeaders` in `index.js`:
```javascript
const corsHeaders = {
  'Access-Control-Allow-Origin': 'https://yourusername.github.io',
  // ...
};
```

## Local Development

To test locally:

```bash
cd worker
wrangler dev
```

Make sure to set the secret locally:
```bash
wrangler secret put LINEAR_API_KEY
```

## Notes

- Linear's GraphQL API doesn't currently support direct ordering of issues within a state. The `order` parameter is logged but not applied.
- State name to ID mapping is cached per request for performance.
- The worker handles CORS automatically for cross-origin requests from GitHub Pages.
