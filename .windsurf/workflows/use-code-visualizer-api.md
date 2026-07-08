---
description: How agents should use the Code Visualizer API as GPS instead of reading files blindly
---

# Code Visualizer API — Agent GPS Workflow

## Why This Exists

Reading files blindly = filling your context window with raw code you may never use.
The Code Visualizer API gives you **exact file paths + line numbers** for every function, class, and endpoint in the entire codebase (29,000+ nodes). Use it as GPS first, then read only the exact lines you need.

---

## Step 1 — Scan the Repo (Get Your Map)

Call the CV API via the Docker container (most reliable path):

```bash
# Copy your zip into the CV container and upload
ssh deploy@dev-swat.com "python3 -c \"
import zipfile, os
z = zipfile.ZipFile('/tmp/scan.zip', 'w', zipfile.ZIP_DEFLATED)
[z.write(os.path.join(r,f), os.path.join(r,f)) for r,dirs,files in os.walk('YOUR_SERVICE_DIR') for f in files if f.endswith('.py') and '__pycache__' not in r]
z.close()
\""
ssh deploy@dev-swat.com "sudo docker cp /tmp/scan.zip code_visualizer_service:/tmp/scan.zip"
ssh deploy@dev-swat.com "sudo docker exec code_visualizer_service curl -s -X POST http://localhost:8000/api/v1/scan/upload \
  -H 'x-user-id: 0a4fbfd4-ee7c-446e-a9c7-9d7e55d6f2a6' \
  -H 'x-user-role: platform_owner' \
  -H 'x-is-superuser: true' \
  -F 'file=@/tmp/scan.zip' \
  -F 'project_name=my-service'"
```

**OR** use GitHub scan (requires PAT):

```bash
ssh deploy@dev-swat.com "sudo docker exec code_visualizer_service curl -s -X POST http://localhost:8000/api/v1/scan/github \
  -H 'Content-Type: application/json' \
  -H 'x-user-id: 0a4fbfd4-ee7c-446e-a9c7-9d7e55d6f2a6' \
  -H 'x-user-role: platform_owner' \
  -H 'x-is-superuser: true' \
  -d '{\"repo_url\":\"https://github.com/louienemesh/genesis2026_production_backend_2\",\"branch\":\"main\",\"token\":\"YOUR_PAT\",\"project_name\":\"resonant-backend\"}' \
  > /tmp/cv_full_scan.json"
```

**Save the full response** — it contains all nodes. Analysis IDs are NOT persisted to DB, so work with the response directly.

---

## Step 2 — Extract Exact Locations (No File Reading)

```bash
ssh deploy@dev-swat.com "python3 << 'PYEOF'
import json
with open('/tmp/cv_full_scan.json') as f:
    d = json.load(f)
nodes = d.get('analysis', {}).get('nodes', [])
print('TOTAL NODES:', len(nodes))

# Filter to your target service/files
target = [n for n in nodes if 'chat_service' in n.get('file_path','')]

# Find exact lines for any function by name
def find(name_fragment):
    seen = set()
    for n in target:
        if name_fragment.lower() in n.get('name','').lower() and n.get('type') in ('function','method','class'):
            key = (n.get('name'), n.get('file_path'))
            if key not in seen:
                seen.add(key)
                print(n.get('file_path'), 'L'+str(n.get('line_start'))+'-'+str(n.get('line_end')), '|', n.get('type'), '|', n.get('name'))

find('skill')      # Find all skill-related functions
find('agent')      # Find all agent-related functions
find('route')      # Find routing functions
find('detect')     # Find detection functions
PYEOF"
```

---

## Step 3 — Read ONLY the Exact Lines You Need

Once you have `file_path:line_start-line_end` from CV, use the Read tool with offset+limit:

```
Read file: chat_service/app/services/skill_executor.py
offset: 891  (line_start from CV)
limit: 40    (line_end - line_start + buffer)
```

This reads **40 lines** instead of **1,482 lines**. That's a 97% reduction in context usage.

---

## Step 4 — Available CV API Endpoints

All called via: `sudo docker exec code_visualizer_service curl -s http://localhost:8000/...`

| Endpoint | Use Case |
|---|---|
| `POST /api/v1/scan/github` | Scan full GitHub repo → get node map |
| `POST /api/v1/scan/upload` | Upload zip → get node map |
| `GET /api/analysis/{id}` | Get persisted analysis (only works if saved to DB) |
| `POST /api/analysis/{id}/trace` | Trace call graph from a node (requires persisted analysis) |
| `POST /api/analysis/{id}/filter` | Filter nodes by type/file |
| `GET /api/analysis/{id}/by-type/{type}` | Get all nodes of type: function/class/api_endpoint |
| `POST /api/analysis/{id}/governance` | Find broken imports, dead code, circular deps |
| `POST /api/analysis/{id}/full-pipeline` | Full pipeline analysis |
| `GET /api/analysis/{id}/functions` | List all functions |
| `POST /api/analysis/{id}/agent/scan` | AI-powered agent scan |

**Important**: `trace`, `filter`, `governance` endpoints require `analysis_id` from a **persisted** analysis. Upload/GitHub scans return inline results but don't persist by default. Always save the full response JSON and process it locally with Python.

---

## Step 5 — Get Node Types Breakdown

```python
types = {}
for n in nodes:
    t = n.get('type','?')
    types[t] = types.get(t,0) + 1
print(types)
# Example: {'service': 35, 'file': 1656, 'function': 17571, 'class': 6134, 'api_endpoint': 4254}
```

**Node types available**: `service`, `file`, `class`, `function`, `method`, `api_endpoint`, `external_service`

---

## Step 6 — Discover Unknown Files (CV as Discovery Engine)

CV found files that weren't known to be in the pipeline:

```python
# Find all files in a service
files = list(set(n.get('file_path','') for n in nodes if 'chat_service' in n.get('file_path','')))
files.sort()
for f in files: print(f)
```

In the Resonant Chat pipeline, CV revealed:
- `chat_service/app/domain/provider/facade.py` — streaming router (was unknown)
- `chat_service/app/services/provider_registry.py` — 3rd `_call_anthropic` implementation
- `llm_service/app/multi_provider/multi_ai_router.py` — duplicate router in different service

These were **invisible** without CV scan.

---

## When to Use CV vs Traditional File Reading

| Situation | Use CV | Use Read File |
|---|---|---|
| Don't know where a function is | ✅ CV scan → find exact location | ❌ Too slow |
| Need to understand a 1500-line file | ✅ CV gives you function map, read only what matters | ❌ Read all = waste |
| Know exact file + line range | Skip CV | ✅ Read directly |
| Tracing call graph between services | ✅ CV trace endpoint | ❌ Manual grep |
| Finding all API endpoints | ✅ CV `by-type/api_endpoint` | ❌ Manual search |
| Finding dead code / broken imports | ✅ CV governance | ❌ Manual analysis |
| Quick single-function edit | Skip CV | ✅ Read + edit |

---

## Performance Numbers (Real Session)

- **Codebase size**: 94 Python files in chat_service alone, 29,674 nodes total
- **CV scan time**: ~15 seconds for full GitHub repo
- **Result**: Exact line numbers for all 17,571 functions — no file reading needed
- **Context savings**: Read 40 lines vs 1,482 lines = **97% reduction**
- **New discoveries**: 3 unknown files revealed that contained critical bugs

---

## Required Headers for CV API

Always pass these to bypass credit limits for platform_owner:

```
x-user-id: 0a4fbfd4-ee7c-446e-a9c7-9d7e55d6f2a6
x-user-role: platform_owner
x-is-superuser: true
```

---

## Example: Full Agent Investigation Workflow

```bash
# 1. Scan repo (15 sec)
ssh deploy@dev-swat.com "sudo docker exec code_visualizer_service curl -s -X POST http://localhost:8000/api/v1/scan/github -H 'Content-Type: application/json' -H 'x-user-id: 0a4fbfd4-ee7c-446e-a9c7-9d7e55d6f2a6' -H 'x-user-role: platform_owner' -H 'x-is-superuser: true' -d '{\"repo_url\":\"https://github.com/louienemesh/genesis2026_production_backend_2\",\"token\":\"PAT\",\"branch\":\"main\"}' > /tmp/cv.json"

# 2. Find target function (2 sec)
ssh deploy@dev-swat.com "python3 -c \"
import json
nodes = json.load(open('/tmp/cv.json'))['analysis']['nodes']
[print(n['file_path'], n['line_start'], '-', n['line_end'], '|', n['name']) for n in nodes if 'FUNCTION_NAME' in n.get('name','') and n.get('type') in ('function','method')]
\""

# 3. Read ONLY those lines (instant)
# Use Read tool with offset=line_start, limit=(line_end - line_start + 5)

# 4. Fix and deploy
```

Total investigation time: ~17 seconds vs 5-10 minutes of blind file reading.
