/**
 * Cloudflare Worker for Linear API proxy
 * Handles drag-and-drop updates from the dashboard
 */

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// Cache for state name to ID mapping (per request)
let stateCache = null;

/**
 * Fetch all workflow states and create a name-to-ID mapping
 */
async function getStateMapping(apiKey) {
  if (stateCache) return stateCache;

  const query = `
    query {
      workflowStates {
        nodes {
          id
          name
        }
      }
    }
  `;

  const response = await fetch('https://api.linear.app/graphql', {
    method: 'POST',
    headers: {
      'Authorization': apiKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(`Linear API error: ${response.status}`);
  }

  const data = await response.json();

  if (data.errors) {
    throw new Error(`Linear GraphQL error: ${JSON.stringify(data.errors)}`);
  }

  const states = data.data.workflowStates.nodes;
  stateCache = {};
  states.forEach(state => {
    stateCache[state.name] = state.id;
  });

  return stateCache;
}

/**
 * Update an issue's state
 */
async function updateIssueState(apiKey, issueId, stateId) {
  const mutation = `
    mutation($id: String!, $stateId: String!) {
      issueUpdate(id: $id, input: { stateId: $stateId }) {
        success
        issue {
          id
          state {
            id
            name
          }
        }
      }
    }
  `;

  const response = await fetch('https://api.linear.app/graphql', {
    method: 'POST',
    headers: {
      'Authorization': apiKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: mutation,
      variables: {
        id: issueId,
        stateId: stateId,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Linear API error: ${response.status}`);
  }

  const data = await response.json();

  if (data.errors) {
    throw new Error(`Linear GraphQL error: ${JSON.stringify(data.errors)}`);
  }

  return data.data.issueUpdate;
}

/**
 * Handle OPTIONS request for CORS preflight
 */
function handleOptions() {
  return new Response(null, {
    status: 204,
    headers: corsHeaders,
  });
}

/**
 * Handle POST /update request
 */
async function handleUpdate(request, apiKey) {
  try {
    const body = await request.json();
    const { issueId, targetState, targetStateId, order } = body;

    if (!issueId || !targetState) {
      return new Response(
        JSON.stringify({ error: 'Missing issueId or targetState' }),
        {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Get state ID if not provided
    let stateId = targetStateId;
    if (!stateId) {
      const stateMapping = await getStateMapping(apiKey);
      stateId = stateMapping[targetState];
      
      if (!stateId) {
        return new Response(
          JSON.stringify({ error: `State "${targetState}" not found` }),
          {
            status: 404,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }
    }

    // Update issue state
    const result = await updateIssueState(apiKey, issueId, stateId);

    // Note: Linear doesn't have a direct API for ordering issues within a state
    // The order is typically managed by Linear's internal sorting (priority, created date, etc.)
    // We'll log the order info but can't directly update it via GraphQL
    if (order && order.length > 0) {
      console.log('Order update requested:', order);
      // Future: If Linear adds ordering API, implement here
    }

    return new Response(
      JSON.stringify({
        success: true,
        issue: result.issue,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    console.error('Update error:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
}

/**
 * Main worker handler
 */
export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleOptions();
    }

    // Get API key from environment
    const apiKey = env.LINEAR_API_KEY;
    if (!apiKey) {
      return new Response(
        JSON.stringify({ error: 'LINEAR_API_KEY not configured' }),
        {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Reset state cache for each request (optional, can be kept for performance)
    stateCache = null;

    const url = new URL(request.url);
    
    // Route to update handler
    if (url.pathname === '/update' && request.method === 'POST') {
      return handleUpdate(request, apiKey);
    }

    // Health check endpoint
    if (url.pathname === '/health' && request.method === 'GET') {
      return new Response(
        JSON.stringify({ status: 'ok' }),
        {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // 404 for unknown routes
    return new Response('Not Found', {
      status: 404,
      headers: corsHeaders,
    });
  },
};
