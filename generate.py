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

# Worker URL for drag-and-drop updates (optional)
worker_url = os.environ.get("WORKER_URL", "")

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
          id
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
    "      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif;",
    "      background: linear-gradient(135deg, #001a14 0%, #003c2b 50%, #002a20 100%);",
    "      background-attachment: fixed;",
    "      color: #e0e8ea;",
    "      padding: 24px;",
    "      min-height: 100vh;",
    "      letter-spacing: -0.01em;",
    "    }",
    "    .header {",
    "      margin-bottom: 32px;",
    "      padding: 24px 32px;",
    "      background: rgba(15, 22, 24, 0.6);",
    "      backdrop-filter: blur(20px) saturate(180%);",
    "      -webkit-backdrop-filter: blur(20px) saturate(180%);",
    "      border: 1px solid rgba(0, 255, 136, 0.1);",
    "      border-radius: 16px;",
    "      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);",
    "      display: flex;",
    "      justify-content: space-between;",
    "      align-items: center;",
    "      flex-wrap: wrap;",
    "      gap: 16px;",
    "    }",
    "    .header-left {",
    "      display: flex;",
    "      flex-direction: column;",
    "      gap: 8px;",
    "    }",
    "    .header h1 {",
    "      color: #00ff88;",
    "      font-size: 28px;",
    "      font-weight: 700;",
    "      letter-spacing: -0.02em;",
    "      margin: 0;",
    "      text-shadow: 0 0 20px rgba(0, 255, 136, 0.3);",
    "    }",
    "    .header small {",
    "      color: #6b7d85;",
    "      font-size: 13px;",
    "      font-weight: 400;",
    "      letter-spacing: 0.01em;",
    "    }",
    "    .brand-logos {",
    "      display: flex;",
    "      align-items: center;",
    "      gap: 20px;",
    "      padding: 8px 0;",
    "    }",
    "    .brand-logo {",
    "      height: 32px;",
    "      width: auto;",
    "      opacity: 0.7;",
    "      filter: grayscale(100%) brightness(1.2) contrast(1.1);",
    "      transition: all 0.3s ease;",
    "    }",
    "    .brand-logo:hover {",
    "      opacity: 1;",
    "      filter: grayscale(80%) brightness(1.3) contrast(1.15);",
    "      transform: scale(1.05);",
    "    }",
    "    .board {",
    "      display: flex;",
    "      gap: 16px;",
    "      overflow-x: auto;",
    "      padding-bottom: 16px;",
    "    }",
    "    .column {",
    "      min-width: 300px;",
    "      background: rgba(15, 22, 24, 0.7);",
    "      backdrop-filter: blur(10px) saturate(150%);",
    "      -webkit-backdrop-filter: blur(10px) saturate(150%);",
    "      border-radius: 12px;",
    "      border: 1px solid rgba(0, 255, 136, 0.08);",
    "      display: flex;",
    "      flex-direction: column;",
    "      max-height: calc(100vh - 180px);",
    "      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.03);",
    "      transition: all 0.3s ease;",
    "    }",
    "    .column:hover {",
    "      border-color: rgba(0, 255, 136, 0.15);",
    "      box-shadow: 0 6px 32px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 255, 136, 0.1);",
    "    }",
    "    .column-header {",
    "      padding: 16px 20px;",
    "      border-bottom: 1px solid rgba(0, 255, 136, 0.08);",
    "      display: flex;",
    "      justify-content: space-between;",
    "      align-items: center;",
    "      background: rgba(0, 0, 0, 0.2);",
    "    }",
    "    .column-title {",
    "      color: #00ff88;",
    "      font-weight: 600;",
    "      font-size: 15px;",
    "      letter-spacing: -0.01em;",
    "    }",
    "    .column-count {",
    "      color: #6b7d85;",
    "      font-size: 12px;",
    "      font-weight: 600;",
    "      background: rgba(0, 255, 136, 0.1);",
    "      padding: 4px 10px;",
    "      border-radius: 12px;",
    "      border: 1px solid rgba(0, 255, 136, 0.15);",
    "      min-width: 24px;",
    "      text-align: center;",
    "    }",
    "    .column-content {",
    "      flex: 1;",
    "      overflow-y: auto;",
    "      padding: 12px;",
    "      scrollbar-width: thin;",
    "      scrollbar-color: rgba(0, 255, 136, 0.2) transparent;",
    "    }",
    "    .column-content::-webkit-scrollbar {",
    "      width: 6px;",
    "    }",
    "    .column-content::-webkit-scrollbar-track {",
    "      background: transparent;",
    "    }",
    "    .column-content::-webkit-scrollbar-thumb {",
    "      background: rgba(0, 255, 136, 0.2);",
    "      border-radius: 3px;",
    "    }",
    "    .column-content::-webkit-scrollbar-thumb:hover {",
    "      background: rgba(0, 255, 136, 0.3);",
    "    }",
    "    .card {",
    "      background: rgba(20, 30, 34, 0.8);",
    "      backdrop-filter: blur(8px);",
    "      -webkit-backdrop-filter: blur(8px);",
    "      border: 1px solid rgba(0, 255, 136, 0.1);",
    "      border-radius: 10px;",
    "      padding: 14px;",
    "      margin-bottom: 10px;",
    "      cursor: grab;",
    "      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);",
    "      position: relative;",
    "      user-select: none;",
    "      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);",
    "    }",
    "    .card:hover {",
    "      border-color: rgba(0, 255, 136, 0.4);",
    "      box-shadow: 0 4px 16px rgba(0, 255, 136, 0.25), 0 0 0 1px rgba(0, 255, 136, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.08);",
    "      transform: translateY(-3px);",
    "      background: rgba(20, 30, 34, 0.95);",
    "    }",
    "    .card.dragging {",
    "      opacity: 0.5;",
    "      cursor: grabbing;",
    "      transform: rotate(2deg);",
    "    }",
    "    .column-content.drag-over {",
    "      background: rgba(0, 255, 136, 0.05);",
    "      border-radius: 4px;",
    "    }",
    "    .card.drag-over {",
    "      border-top: 2px solid #00ff88;",
    "      margin-top: 4px;",
    "    }",
    "    .card-link {",
    "      text-decoration: none;",
    "      color: inherit;",
    "      display: block;",
    "      pointer-events: auto;",
    "      -webkit-user-drag: none;",
    "      user-select: none;",
    "    }",
    "    .card.dragging .card-link {",
    "      pointer-events: none;",
    "    }",
    "    .card-identifier {",
    "      color: #6b7d85;",
    "      font-size: 11px;",
    "      font-weight: 600;",
    "      margin-bottom: 6px;",
    "      letter-spacing: 0.02em;",
    "    }",
    "    .card-title {",
    "      color: #e0e8ea;",
    "      font-size: 14px;",
    "      line-height: 1.5;",
    "      margin-bottom: 10px;",
    "      font-weight: 500;",
    "      letter-spacing: -0.01em;",
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
    "      body { padding: 16px; }",
    "      .header {",
    "        padding: 20px;",
    "        flex-direction: column;",
    "        align-items: flex-start;",
    "      }",
    "      .brand-logos {",
    "        width: 100%;",
    "        justify-content: flex-start;",
    "        gap: 16px;",
    "      }",
    "      .brand-logo {",
    "        height: 28px;",
    "      }",
    "      .board { flex-direction: column; }",
    "      .column { min-width: 100%; max-height: none; }",
    "    }",
    "  </style>",
    "</head>",
    "<body>",
    "  <div class='header'>",
    "    <div class='header-left'>",
    f"      <h1>{view_name}</h1>",
    f"      <small>Updated {dt.datetime.utcnow().isoformat()}Z</small>",
    "    </div>",
    "    <div class='brand-logos'>",
    "      <img src='assets/png/brx_preto_logo.svg' alt='BRX' class='brand-logo' />",
    "      <img src='assets/png/multibet_logo.png' alt='Multibet' class='brand-logo' />",
    "      <img src='assets/png/ricodark.png' alt='Rico' class='brand-logo' />",
    "    </div>",
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
    html.append(f"      <div class='column-content' data-state-name='{state_name}'>")
    
    for idx, issue in enumerate(state_issues):
        issue_id = issue.get("id", "")
        state_id = issue.get("state", {}).get("id", "")
        identifier = issue.get("identifier", "")
        title = issue.get("title", "Untitled")
        url = issue.get("url", "")
        assignee = issue.get("assignee")
        assignee_name = assignee.get("name") if assignee else None
        assignee_avatar = assignee.get("avatarUrl") if assignee else None
        labels = issue.get("labels", {}).get("nodes", [])
        status_class = get_status_class(state_name)
        
        html.append(f"        <div class='card' draggable='true' data-issue-id='{issue_id}' data-state-id='{state_id}' data-state-name='{state_name}' data-order-index='{idx}'>")
        html.append(f"          <span class='status-indicator {status_class}'></span>")
        html.append(f"          <a href='{url}' target='_blank' class='card-link' draggable='false'>")
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
        html.append(f"      <div class='column-content' data-state-name='{state_name}'>")
        
        for idx, issue in enumerate(state_issues):
            issue_id = issue.get("id", "")
            state_id = issue.get("state", {}).get("id", "")
            identifier = issue.get("identifier", "")
            title = issue.get("title", "Untitled")
            url = issue.get("url", "")
            assignee = issue.get("assignee")
            assignee_name = assignee.get("name") if assignee else None
            assignee_avatar = assignee.get("avatarUrl") if assignee else None
            labels = issue.get("labels", {}).get("nodes", [])
            status_class = get_status_class(state_name)
            
            html.append(f"        <div class='card' draggable='true' data-issue-id='{issue_id}' data-state-id='{state_id}' data-state-name='{state_name}' data-order-index='{idx}'>")
            html.append(f"          <span class='status-indicator {status_class}'></span>")
            html.append(f"          <a href='{url}' target='_blank' class='card-link' draggable='false'>")
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
    "  <script>",
    f"    const WORKER_URL = '{worker_url}';",
    "    let draggedCard = null;",
    "    let draggedOverCard = null;",
    "    let isDragging = false;",
    "    let dragEndTime = 0;",
    "",
    "    // Initialize drag and drop",
    "    document.addEventListener('DOMContentLoaded', function() {",
    "      if (!WORKER_URL) {",
    "        console.warn('WORKER_URL not set - drag and drop will work visually but changes will not sync to Linear');",
    "      }",
    "",
    "      const cards = document.querySelectorAll('.card');",
    "      const columns = document.querySelectorAll('.column-content');",
    "",
    "      // Handle link clicks - allow normal click unless we just finished dragging",
    "      document.querySelectorAll('.card-link').forEach(link => {",
    "        link.addEventListener('click', function(e) {",
    "          // Prevent link navigation if we just finished dragging (within 100ms)",
    "          if (Date.now() - dragEndTime < 100) {",
    "            e.preventDefault();",
    "            e.stopPropagation();",
    "          }",
    "        });",
    "        link.addEventListener('mousedown', function(e) {",
    "          // Allow dragging to start even from link",
    "          e.stopPropagation();",
    "        });",
    "      });",
    "",
    "      // Card drag events",
    "      cards.forEach(card => {",
    "        card.addEventListener('dragstart', handleDragStart);",
    "        card.addEventListener('dragend', handleDragEnd);",
    "        card.addEventListener('dragover', handleCardDragOver);",
    "        card.addEventListener('drop', handleCardDrop);",
    "        card.addEventListener('dragleave', handleCardDragLeave);",
    "      });",
    "",
    "      // Column drop zones",
    "      columns.forEach(column => {",
    "        column.addEventListener('dragover', handleColumnDragOver);",
    "        column.addEventListener('drop', handleColumnDrop);",
    "        column.addEventListener('dragleave', handleColumnDragLeave);",
    "      });",
    "    });",
    "",
    "    function handleDragStart(e) {",
    "      draggedCard = this;",
    "      isDragging = true;",
    "      this.classList.add('dragging');",
    "      e.dataTransfer.effectAllowed = 'move';",
    "      e.dataTransfer.setData('text/html', this.outerHTML);",
    "      // Allow dragging even if started from link area",
    "      e.stopPropagation();",
    "    }",
    "",
    "    function handleDragEnd(e) {",
    "      isDragging = false;",
    "      dragEndTime = Date.now();",
    "      this.classList.remove('dragging');",
    "      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));",
    "      draggedCard = null;",
    "      draggedOverCard = null;",
    "    }",
    "",
    "    function handleCardDragOver(e) {",
    "      if (e.preventDefault) e.preventDefault();",
    "      if (this === draggedCard) return;",
    "      this.classList.add('drag-over');",
    "      draggedOverCard = this;",
    "      return false;",
    "    }",
    "",
    "    function handleCardDragLeave(e) {",
    "      this.classList.remove('drag-over');",
    "    }",
    "",
    "    function handleCardDrop(e) {",
    "      if (e.stopPropagation) e.stopPropagation();",
    "      this.classList.remove('drag-over');",
    "",
    "      if (draggedCard === null) return false;",
    "",
    "      const targetColumn = this.closest('.column-content');",
    "      const targetState = targetColumn.dataset.stateName;",
    "      // Get state ID from first card in target column, or use null (worker will look it up)",
    "      const firstCard = targetColumn.querySelector('.card');",
    "      const targetStateId = firstCard ? firstCard.dataset.stateId : null;",
    "      const issueId = draggedCard.dataset.issueId;",
    "",
    "      // Insert before this card",
    "      const parent = this.parentNode;",
    "      const nextSibling = this.nextSibling;",
    "      parent.insertBefore(draggedCard, this);",
    "",
    "      // Update order indices",
    "      updateOrderIndices(parent);",
    "",
    "      // Send update to worker",
    "      const newOrder = Array.from(parent.querySelectorAll('.card')).map((card, idx) => ({",
    "        issueId: card.dataset.issueId,",
    "        order: idx",
    "      }));",
    "",
    "      updateIssue(issueId, targetState, targetStateId, newOrder).catch(err => {",
    "        console.error('Failed to update issue:', err);",
    "        // Revert on error",
    "        const originalColumn = document.querySelector(`[data-state-name='${draggedCard.dataset.stateName}']`);",
    "        if (originalColumn) {",
    "          originalColumn.appendChild(draggedCard);",
    "          updateOrderIndices(originalColumn);",
    "        }",
    "        alert('Failed to update issue. Please refresh the page.');",
    "      });",
    "",
    "      return false;",
    "    }",
    "",
    "    function handleColumnDragOver(e) {",
    "      if (e.preventDefault) e.preventDefault();",
    "      this.classList.add('drag-over');",
    "      e.dataTransfer.dropEffect = 'move';",
    "      return false;",
    "    }",
    "",
    "    function handleColumnDrop(e) {",
    "      if (e.stopPropagation) e.stopPropagation();",
    "      this.classList.remove('drag-over');",
    "",
    "      if (draggedCard === null) return false;",
    "",
    "      const targetState = this.dataset.stateName;",
    "      // Get state ID from first card in target column, or use null (worker will look it up)",
    "      const firstCard = this.querySelector('.card');",
    "      const targetStateId = firstCard ? firstCard.dataset.stateId : null;",
    "      const issueId = draggedCard.dataset.issueId;",
    "",
    "      // Move card to end of column",
    "      this.appendChild(draggedCard);",
    "",
    "      // Update order indices",
    "      updateOrderIndices(this);",
    "",
    "      // Send update to worker",
    "      const newOrder = Array.from(this.querySelectorAll('.card')).map((card, idx) => ({",
    "        issueId: card.dataset.issueId,",
    "        order: idx",
    "      }));",
    "",
    "      updateIssue(issueId, targetState, null, newOrder).catch(err => {",
    "        console.error('Failed to update issue:', err);",
    "        // Revert on error",
    "        const originalColumn = document.querySelector(`[data-state-name='${draggedCard.dataset.stateName}']`);",
    "        if (originalColumn) {",
    "          originalColumn.appendChild(draggedCard);",
    "          updateOrderIndices(originalColumn);",
    "        }",
    "        alert('Failed to update issue. Please refresh the page.');",
    "      });",
    "",
    "      return false;",
    "    }",
    "",
    "    function handleColumnDragLeave(e) {",
    "      this.classList.remove('drag-over');",
    "    }",
    "",
    "    function updateOrderIndices(column) {",
    "      const cards = column.querySelectorAll('.card');",
    "      cards.forEach((card, idx) => {",
    "        card.dataset.orderIndex = idx;",
    "      });",
    "    }",
    "",
    "    async function updateIssue(issueId, targetState, targetStateId, newOrder) {",
    "      // Skip API call if WORKER_URL is not set",
    "      if (!WORKER_URL) {",
    "        console.log('WORKER_URL not set - updating UI only (changes will not sync to Linear)');",
    "        // Update card data attributes for UI consistency",
    "        draggedCard.dataset.stateName = targetState;",
    "        if (targetStateId) {",
    "          draggedCard.dataset.stateId = targetStateId;",
    "        }",
    "        // Update column counts",
    "        updateColumnCounts();",
    "        return;",
    "      }",
    "",
    "      const response = await fetch(WORKER_URL + '/update', {",
    "        method: 'POST',",
    "        headers: {",
    "          'Content-Type': 'application/json',",
    "        },",
    "        body: JSON.stringify({",
    "          issueId: issueId,",
    "          targetState: targetState,",
    "          targetStateId: targetStateId,",
    "          order: newOrder,",
    "        }),",
    "      });",
    "",
    "      if (!response.ok) {",
    "        const error = await response.text();",
    "        throw new Error(error || `HTTP ${response.status}`);",
    "      }",
    "",
    "      // Update card data attributes",
    "      draggedCard.dataset.stateName = targetState;",
    "      if (targetStateId) {",
    "        draggedCard.dataset.stateId = targetStateId;",
    "      }",
    "",
    "      // Update column counts",
    "      updateColumnCounts();",
    "    }",
    "",
    "    function updateColumnCounts() {",
    "      document.querySelectorAll('.column').forEach(column => {",
    "        const count = column.querySelectorAll('.card').length;",
    "        const countEl = column.querySelector('.column-count');",
    "        if (countEl) countEl.textContent = count;",
    "      });",
    "    }",
    "  </script>",
    "</body>",
    "</html>"
])

# Step 5: Write to docs/index.html
os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(html))

# Step 6: Copy assets to docs folder for GitHub Pages
import shutil
assets_src = "assets/png"
assets_dst = "docs/assets/png"
if os.path.exists(assets_src):
    os.makedirs(assets_dst, exist_ok=True)
    for file in os.listdir(assets_src):
        src_file = os.path.join(assets_src, file)
        dst_file = os.path.join(assets_dst, file)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)
    print(f"Copied assets to {assets_dst}")

print(f"Successfully generated docs/index.html with {len(issues)} issues from view '{view_name}'")
