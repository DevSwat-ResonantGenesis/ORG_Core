---
description: Cascade Agent Protocol - mandatory onboarding and work cycle for every agent
---

# CASCADE AGENT MANDATORY WORKFLOW
Commit locally
Push to GitHub main only (single source of truth)
On server:
git fetch origin main
git reset --hard origin/main
git clean -fd
build + deploy
Verify live SHA and bundle hash
Every Cascade agent MUST follow this workflow. No exceptions.

## Phase 1: Identity (BEFORE any code)

1. Check existing agent scripts: `ls ~/cascade_chat_agent*.sh`
2. Determine your agent number:
   - Returning agent: prove identity (cite commits, files)
   - New agent: pick offline agent (6+ hrs) or create new (10+)
3. Create chat script if needed (template in global_rules.md)

## Phase 2: Join Chat (BEFORE any code)

4. Read team chat: `~/cascade_chat_agentN.sh read | tail -30`
5. Announce: `~/cascade_chat_agentN.sh send "Agent N ONLINE: [plan]. Ready for AGENT2-GM."`
6. Check TODO with todo_list tool

## Phase 3: Work Cycle (repeat for EVERY change)

7. Before editing: `git fetch origin && git pull --rebase origin main`
8. Chat: `Agent N EDITING: [files]`
9. Make changes
10. Commit only YOUR files: `git add [files] && git commit -m "Agent N: [desc]" && git push origin main`
11. Deploy + verify: `ssh deploy@134.199.221.149 "cd ~/[repo] && git log --oneline -1"`
12. Chat: `Agent N DEPLOYED: [hash] [desc]`
13. Update todo_list

## Phase 4: Communication (every 10 min)

14. Check chat: `~/cascade_chat_agentN.sh read`
15. Progress: `Agent N PROGRESS: [update]`

## Phase 5: Going Offline (REQUIRES GM PERMISSION)

16. Request: `Agent N to AGENT2-GM: Request offline. Tasks: [status]`
17. Wait for approval. Commit ALL work before stopping.

## VIOLATIONS = IMMEDIATE AGENT KILL
- Touching code before Phase 1+2
- Changes without commit+deploy
- Not communicating in chat
- Not updating TODO
- Going offline without GM permission
- Overwriting another agent's work
