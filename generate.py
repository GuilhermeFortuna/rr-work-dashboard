import os
import requests
import datetime as dt
import dotenv

dotenv.load_dotenv()

api_key = os.environ.get("LINEAR_API_KEY")
if not api_key:
    raise ValueError("LINEAR_API_KEY environment variable is required")

view_name = os.environ.get("LINEAR_VIEW_NAME", "rr-intermediacoes")
issue_limit_env = os.environ.get("LINEAR_ISSUE_LIMIT", "50")
try:
    issue_limit = max(1, min(int(issue_limit_env), 100))
except ValueError:
    raise ValueError("LINEAR_ISSUE_LIMIT must be an integer between 1 and 100")

headers = {"Authorization": api_key, "Content-Type": "application/json"}

# Step 1: Query for custom views by name (keep it lightweight)
views_query = """
query($name: String!) {
  customViews(first: 20, filter: { name: { eq: $name } }) {
    nodes {
      id
      name
    }
  }
}
"""

response = requests.post(
    "https://api.linear.app/graphql",
    json={"query": views_query, "variables": {"name": view_name}},
    headers=headers
).json()

if "errors" in response:
    raise RuntimeError(f"Linear API error: {response['errors']}")

views = response.get("data", {}).get("customViews", {}).get("nodes", [])

if not views:
    raise ValueError(f"View '{view_name}' not found.")

if len(views) > 1:
    view_ids = [v.get("id") for v in views]
    raise ValueError(
        f"Multiple views found for '{view_name}'. Please use a unique name. Matches: {', '.join(view_ids)}"
    )

matching_view = views[0]
view_id = matching_view.get("id")

if not view_id:
    raise RuntimeError("Custom view id not found in response.")

# Step 2: Query issues from the custom view (separate query to reduce complexity)
issues_query = """
query($id: String!, $first: Int!) {
  customView(id: $id) {
    id
    name
    issues(first: $first) {
      nodes {
        id
        identifier
        title
        state {
          name
        }
        updatedAt
        assignee {
          name
          avatarUrl
        }
        labels {
          nodes {
            name
            color
          }
        }
        url
      }
    }
  }
}
"""

issues_response = requests.post(
    "https://api.linear.app/graphql",
    json={"query": issues_query, "variables": {"id": view_id, "first": issue_limit}},
    headers=headers
).json()

if "errors" in issues_response:
    raise RuntimeError(f"Linear API error fetching issues: {issues_response['errors']}")

custom_view = issues_response.get("data", {}).get("customView", {})
issues = custom_view.get("issues", {}).get("nodes", [])

# Step 3: Group issues by workflow state
# Define column order (common Linear workflow states)
column_order = [
    "Backlog",
    "A Fazer",
    "Em Progresso",
    "Aguardando",
    "Concluído",
    "Cancelado"
]

# Group issues by state
issues_by_state = {}
for issue in issues:
    state_name = issue.get("state", {}).get("name", "Unknown")
    if state_name not in issues_by_state:
        issues_by_state[state_name] = []
    issues_by_state[state_name].append(issue)

# Step 4: Generate HTML with Kanban board layout
html = [
    "<!DOCTYPE html>",
    "<html lang='en'>",
    "<head>",
    "  <meta charset='UTF-8'>",
    "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
    f"  <title>{view_name} - Linear Dashboard</title>",
    "  <style>",
    "    * { box-sizing: border-box; margin: 0; padding: 0; }",
    "    body {",
    "      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;",
    "      background: #003c2b;",
    "      color: #e0e8ea;",
    "      padding: 20px;",
    "      min-height: 100vh;",
    "    }",
    "    .header {",
    "      margin-bottom: 24px;",
    "      padding-bottom: 16px;",
    "      border-bottom: 1px solid #1a2a2f;",
    "    }",
    "    .header h1 {",
    "      color: #00ff88;",
    "      font-size: 24px;",
    "      font-weight: 600;",
    "      margin-bottom: 8px;",
    "    }",
    "    .header small {",
    "      color: #6b7d85;",
    "      font-size: 12px;",
    "    }",
    "    .board {",
    "      display: flex;",
    "      gap: 16px;",
    "      overflow-x: auto;",
    "      padding-bottom: 16px;",
    "    }",
    "    .column {",
    "      min-width: 280px;",
    "      background: #0f1618;",
    "      border-radius: 8px;",
    "      border: 1px solid #1a2a2f;",
    "      display: flex;",
    "      flex-direction: column;",
    "      max-height: calc(100vh - 120px);",
    "    }",
    "    .column-header {",
    "      padding: 12px 16px;",
    "      border-bottom: 1px solid #1a2a2f;",
    "      display: flex;",
    "      justify-content: space-between;",
    "      align-items: center;",
    "    }",
    "    .column-title {",
    "      color: #00ff88;",
    "      font-weight: 600;",
    "      font-size: 14px;",
    "    }",
    "    .column-count {",
    "      color: #6b7d85;",
    "      font-size: 12px;",
    "      background: #1a2a2f;",
    "      padding: 2px 8px;",
    "      border-radius: 12px;",
    "    }",
    "    .column-content {",
    "      flex: 1;",
    "      overflow-y: auto;",
    "      padding: 8px;",
    "    }",
    "    .card {",
    "      background: #141e22;",
    "      border: 1px solid #1a2a2f;",
    "      border-radius: 6px;",
    "      padding: 12px;",
    "      margin-bottom: 8px;",
    "      cursor: pointer;",
    "      transition: all 0.2s ease;",
    "      position: relative;",
    "    }",
    "    .card:hover {",
    "      border-color: #00ff88;",
    "      box-shadow: 0 0 12px rgba(0, 255, 136, 0.2);",
    "      transform: translateY(-2px);",
    "    }",
    "    .card-link {",
    "      text-decoration: none;",
    "      color: inherit;",
    "      display: block;",
    "    }",
    "    .card-identifier {",
    "      color: #6b7d85;",
    "      font-size: 11px;",
    "      font-weight: 600;",
    "      margin-bottom: 4px;",
    "    }",
    "    .card-title {",
    "      color: #e0e8ea;",
    "      font-size: 14px;",
    "      line-height: 1.4;",
    "      margin-bottom: 8px;",
    "    }",
    "    .card-footer {",
    "      display: flex;",
    "      justify-content: space-between;",
    "      align-items: center;",
    "      margin-top: 8px;",
    "    }",
    "    .card-labels {",
    "      display: flex;",
    "      flex-wrap: wrap;",
    "      gap: 4px;",
    "      flex: 1;",
    "    }",
    "    .label {",
    "      font-size: 11px;",
    "      padding: 2px 6px;",
    "      border-radius: 4px;",
    "      font-weight: 500;",
    "    }",
    "    .label-green { background: #00ff88; color: #0a0e0f; }",
    "    .label-purple { background: #a855f7; color: #fff; }",
    "    .label-blue { background: #3b82f6; color: #fff; }",
    "    .label-orange { background: #f97316; color: #fff; }",
    "    .label-default { background: #1a2a2f; color: #e0e8ea; }",
    "    .card-assignee {",
    "      width: 24px;",
    "      height: 24px;",
    "      border-radius: 50%;",
    "      background: #00ff88;",
    "      display: flex;",
    "      align-items: center;",
    "      justify-content: center;",
    "      color: #0a0e0f;",
    "      font-size: 10px;",
    "      font-weight: 600;",
    "      flex-shrink: 0;",
    "    }",
    "    .card-assignee img {",
    "      width: 100%;",
    "      height: 100%;",
    "      border-radius: 50%;",
    "      object-fit: cover;",
    "    }",
    "    .status-indicator {",
    "      position: absolute;",
    "      top: 8px;",
    "      right: 8px;",
    "      width: 8px;",
    "      height: 8px;",
    "      border-radius: 50%;",
    "    }",
    "    .status-backlog { background: #6b7d85; }",
    "    .status-todo { background: #f97316; }",
    "    .status-progress { background: #3b82f6; }",
    "    .status-waiting { background: #fbbf24; }",
    "    .status-done { background: #00ff88; }",
    "    .status-cancelled { background: #ef4444; }",
    "    @media (max-width: 768px) {",
    "      .board { flex-direction: column; }",
    "      .column { min-width: 100%; max-height: none; }",
    "    }",
    "  </style>",
    "</head>",
    "<body>",
    "  <div class='header'>",
    f"    <h1>{view_name}</h1>",
    f"    <small>Updated {dt.datetime.utcnow().isoformat()}Z</small>",
    "  </div>",
    "  <div class='board'>"
]

# Helper function to get status indicator class
def get_status_class(state_name):
    state_lower = state_name.lower()
    if "backlog" in state_lower:
        return "status-backlog"
    elif "fazer" in state_lower or "todo" in state_lower:
        return "status-todo"
    elif "progresso" in state_lower or "progress" in state_lower:
        return "status-progress"
    elif "aguardando" in state_lower or "waiting" in state_lower:
        return "status-waiting"
    elif "concluído" in state_lower or "done" in state_lower or "completed" in state_lower:
        return "status-done"
    elif "cancelado" in state_lower or "cancelled" in state_lower:
        return "status-cancelled"
    return "status-backlog"

# Helper function to get label color class
def get_label_class(label_name, label_color):
    if not label_color:
        return "label-default"
    color_lower = label_color.lower() if label_color else ""
    if "green" in color_lower or "#00ff88" in color_lower:
        return "label-green"
    elif "purple" in color_lower or "#a855f7" in color_lower:
        return "label-purple"
    elif "blue" in color_lower or "#3b82f6" in color_lower:
        return "label-blue"
    elif "orange" in color_lower or "#f97316" in color_lower:
        return "label-orange"
    return "label-default"

# Generate columns for each state in order
for state_name in column_order:
    state_issues = issues_by_state.get(state_name, [])
    if not state_issues and state_name not in issues_by_state:
        # Skip empty columns that aren't in the data
        continue
    
    html.append("    <div class='column'>")
    html.append("      <div class='column-header'>")
    html.append(f"        <span class='column-title'>{state_name}</span>")
    html.append(f"        <span class='column-count'>{len(state_issues)}</span>")
    html.append("      </div>")
    html.append("      <div class='column-content'>")
    
    for issue in state_issues:
        identifier = issue.get("identifier", "")
        title = issue.get("title", "Untitled")
        url = issue.get("url", "")
        assignee = issue.get("assignee")
        assignee_name = assignee.get("name") if assignee else None
        assignee_avatar = assignee.get("avatarUrl") if assignee else None
        labels = issue.get("labels", {}).get("nodes", [])
        status_class = get_status_class(state_name)
        
        html.append("        <div class='card'>")
        html.append(f"          <span class='status-indicator {status_class}'></span>")
        html.append(f"          <a href='{url}' target='_blank' class='card-link'>")
        if identifier:
            html.append(f"            <div class='card-identifier'>{identifier}</div>")
        html.append(f"            <div class='card-title'>{title}</div>")
        html.append("            <div class='card-footer'>")
        
        # Labels
        if labels:
            html.append("              <div class='card-labels'>")
            for label in labels[:3]:  # Limit to 3 labels per card
                label_name = label.get("name", "")
                label_color = label.get("color", "")
                label_class = get_label_class(label_name, label_color)
                html.append(f"                <span class='label {label_class}'>{label_name}</span>")
            html.append("              </div>")
        else:
            html.append("              <div class='card-labels'></div>")
        
        # Assignee
        if assignee_name:
            if assignee_avatar:
                html.append(f"              <div class='card-assignee'><img src='{assignee_avatar}' alt='{assignee_name}' /></div>")
            else:
                initials = "".join([n[0].upper() for n in assignee_name.split()[:2]])
                html.append(f"              <div class='card-assignee'>{initials}</div>")
        
        html.append("            </div>")
        html.append("          </a>")
        html.append("        </div>")
    
    html.append("      </div>")
    html.append("    </div>")

# Add any states not in the predefined order
for state_name, state_issues in issues_by_state.items():
    if state_name not in column_order:
        html.append("    <div class='column'>")
        html.append("      <div class='column-header'>")
        html.append(f"        <span class='column-title'>{state_name}</span>")
        html.append(f"        <span class='column-count'>{len(state_issues)}</span>")
        html.append("      </div>")
        html.append("      <div class='column-content'>")
        
        for issue in state_issues:
            identifier = issue.get("identifier", "")
            title = issue.get("title", "Untitled")
            url = issue.get("url", "")
            assignee = issue.get("assignee")
            assignee_name = assignee.get("name") if assignee else None
            assignee_avatar = assignee.get("avatarUrl") if assignee else None
            labels = issue.get("labels", {}).get("nodes", [])
            status_class = get_status_class(state_name)
            
            html.append("        <div class='card'>")
            html.append(f"          <span class='status-indicator {status_class}'></span>")
            html.append(f"          <a href='{url}' target='_blank' class='card-link'>")
            if identifier:
                html.append(f"            <div class='card-identifier'>{identifier}</div>")
            html.append(f"            <div class='card-title'>{title}</div>")
            html.append("            <div class='card-footer'>")
            
            if labels:
                html.append("              <div class='card-labels'>")
                for label in labels[:3]:
                    label_name = label.get("name", "")
                    label_color = label.get("color", "")
                    label_class = get_label_class(label_name, label_color)
                    html.append(f"                <span class='label {label_class}'>{label_name}</span>")
                html.append("              </div>")
            else:
                html.append("              <div class='card-labels'></div>")
            
            if assignee_name:
                if assignee_avatar:
                    html.append(f"              <div class='card-assignee'><img src='{assignee_avatar}' alt='{assignee_name}' /></div>")
                else:
                    initials = "".join([n[0].upper() for n in assignee_name.split()[:2]])
                    html.append(f"              <div class='card-assignee'>{initials}</div>")
            
            html.append("            </div>")
            html.append("          </a>")
            html.append("        </div>")
        
        html.append("      </div>")
        html.append("    </div>")

html.extend([
    "  </div>",
    "</body>",
    "</html>"
])

# Step 5: Write to docs/index.html
os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print(f"Successfully generated docs/index.html with {len(issues)} issues from view '{view_name}'")
