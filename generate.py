import os, requests, datetime as dt

q = """
{ issues(filter:{assignee:{isMe:true}} first:50){
  nodes{ title state{name} updatedAt }
}}
"""

r = requests.post(
    "https://api.linear.app/graphql",
    json={"query": q},
    headers={"Authorization": os.environ["LINEAR_API_KEY"]}
).json()

issues = r["data"]["issues"]["nodes"]

html = ["<h1>Work Progress</h1><ul>"]
for i in issues:
    html.append(f"<li>{i['title']} — {i['state']['name']}</li>")
html.append("</ul><small>Updated " + dt.datetime.utcnow().isoformat() + "Z</small>")

open("index.html", "w", encoding="utf-8").write("\n".join(html))
