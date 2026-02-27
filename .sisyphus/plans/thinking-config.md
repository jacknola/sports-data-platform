# OpenCode Thinking Variants Configuration Plan

**Status**: Ready for execution  
**Created**: 2026-02-27  
**Estimated Duration**: 15-20 minutes  
**Risk Level**: Medium (authentication required, model version changes)

---

## Executive Summary

Configure OpenCode with `opencode-google-antigravity-auth` plugin to enable thinking variants for Gemini 3 and Claude 4.5 models. Replace existing `opencode-gemini-auth` plugin with unified Antigravity OAuth authentication. Migrate OpenAgent from Claude 4.6 to Claude 4.5 with thinking enabled. Keep Flash-based agents on Gemini 2.5 for speed/cost optimization.

**Key Changes:**
- Plugin swap: `opencode-gemini-auth` → `opencode-google-antigravity-auth`
- Add 5 models with thinking variants (Gemini 3 Pro/Flash, Claude Sonnet/Opus 4.5)
- Migrate OpenAgent to `gemini-claude-opus-4-5-thinking-high`
- TaskManager upgrade to `gemini-3-pro-medium`
- Auth via Google OAuth (no API keys)

---

## Prerequisites

### Required Tools
- OpenCode CLI (already installed)
- Access to Google account for OAuth
- Write access to `.opencode/opencode.json`

### Required Knowledge
- Current config location: `/Users/bb.jr/sports-data-platform/.opencode/opencode.json`
- Backup location: `/Users/bb.jr/sports-data-platform/.opencode/opencode.json.pre-antigravity.bak`
- Auth tokens stored: `~/.local/share/opencode/antigravity-accounts.json`

---

## Context & Constraints

### Current State
```json
{
  "plugin": [
    "opencode-gemini-auth@latest",
    "@tarquinen/opencode-dcp@latest",
    "opencode-pty@latest",
    "@franlol/opencode-md-table-formatter@latest",
    "@zenobius/opencode-skillful"
  ],
  "model": "gemini/gemini-2.5-pro",
  "small_model": "gemini/gemini-2.5-flash",
  "agent": {
    "OpenAgent": { "model": "opencode/claude-opus-4-6" },
    "TaskManager": { "model": "gemini/gemini-3-pro" },
    "ContextScout": { "model": "gemini/gemini-2.5-flash" },
    "ExternalScout": { "model": "gemini/gemini-2.5-flash" },
    "DocWriter": { "model": "gemini/gemini-2.5-flash" },
    "ContextOrganizer": { "model": "gemini/gemini-2.5-flash" }
  }
}
```

### Target State
```json
{
  "plugin": [
    "opencode-google-antigravity-auth",
    "@tarquinen/opencode-dcp@latest",
    "opencode-pty@latest",
    "@franlol/opencode-md-table-formatter@latest",
    "@zenobius/opencode-skillful"
  ],
  "model": "google/gemini-3-pro-medium",
  "small_model": "google/gemini-3-flash-medium",
  "agent": {
    "OpenAgent": { "model": "google/gemini-claude-opus-4-5-thinking-high" },
    "TaskManager": { "model": "google/gemini-3-pro-medium" },
    "ContextScout": { "model": "gemini/gemini-2.5-flash" },
    "ExternalScout": { "model": "gemini/gemini-2.5-flash" },
    "DocWriter": { "model": "gemini/gemini-2.5-flash" },
    "ContextOrganizer": { "model": "gemini/gemini-2.5-flash" }
  },
  "provider": {
    "google": {
      "models": { /* 5 model definitions with thinking variants */ }
    }
  }
}
```

### Technical Constraints
- **Model version downgrade**: OpenAgent migrates from Claude 4.6 → 4.5 (user approved)
- **Auth required FIRST**: Cannot test models until OAuth completed
- **Flash agents stay on 2.5**: Speed/cost prioritized over thinking quality
- **Sequential phases**: Plugin → Auth → Models → Agents (strict ordering)
- **Backup mandatory**: Config must be backed up before any changes

### Risk Mitigation
| Risk | Severity | Mitigation |
|------|----------|------------|
| OpenAgent model downgrade (4.6→4.5) | Medium | User approved; thinking variants may offset quality loss |
| Google account ban (ToS violation) | Medium | User accepts risk; Antigravity ToS warns against third-party use |
| Auth failure blocks all changes | High | First task verifies auth; rollback if failed |
| JSON syntax error breaks config | Medium | Validate after each edit with `python3 -c "import json; json.load(...)"` |
| `@zenobius/opencode-skillful` compatibility | Low | Different from warned `opencode-skills`; test after changes |

---

## Implementation Tasks


### TODO-1: Create Backup
**Priority**: Critical  
**Estimated Time**: 1 minute  
**Dependencies**: None

**Objective**: Create backup of current config before any modifications.

**Implementation Steps**:
1. Copy `.opencode/opencode.json` to `.opencode/opencode.json.pre-antigravity.bak`
2. Verify backup exists and is readable
3. Record backup timestamp in git commit message later

**Commands**:
```bash
cp .opencode/opencode.json .opencode/opencode.json.pre-antigravity.bak
ls -lh .opencode/opencode.json*
```

**QA Scenarios**:
- ✅ Backup file created with `.bak` extension
- ✅ Backup file size matches original
- ✅ Backup file is readable (cat first 10 lines)

**Rollback**: Delete backup if creation fails

---

### TODO-2: Run Antigravity OAuth Authentication
**Priority**: Critical  
**Estimated Time**: 3-5 minutes  
**Dependencies**: TODO-1

**Objective**: Authenticate OpenCode CLI with Google account via Antigravity OAuth.

**Implementation Steps**:
1. Run `opencode auth login` command
2. Select Google provider from list
3. Choose "OAuth with Google (Antigravity)" option
4. Complete browser authentication flow (opens http://localhost:36742/oauth-callback)
5. Verify auth tokens saved to `~/.local/share/opencode/antigravity-accounts.json`
6. Optional: Add additional Google accounts for load balancing when prompted

**Commands**:
```bash
opencode auth login
# Follow prompts:
# 1. Select: Google
# 2. Select: OAuth with Google (Antigravity)
# 3. Authenticate in browser
# 4. Optionally add more accounts (y/n)

# Verify auth completed:
ls -lh ~/.local/share/opencode/antigravity-accounts.json
```

**QA Scenarios**:
- ✅ Browser opens to Google OAuth consent screen
- ✅ After approval, lands on "Authentication complete" page
- ✅ CLI shows "✓ Account 1 authenticated (user@gmail.com)"
- ✅ `antigravity-accounts.json` exists with account metadata
- ✅ Test basic model call: `opencode run -m google/gemini-2.5-flash-lite -p "respond with just OK"`

**Rollback**: Remove `~/.local/share/opencode/antigravity-accounts.json` if auth fails

**BLOCKER**: Cannot proceed to TODO-3 until auth succeeds

---

### TODO-3: Replace Plugin in Config
**Priority**: High  
**Estimated Time**: 2 minutes  
**Dependencies**: TODO-2 (auth must succeed)

**Objective**: Swap `opencode-gemini-auth` with `opencode-google-antigravity-auth` in plugin array.

**Implementation Steps**:
1. Read current `.opencode/opencode.json`
2. Locate `plugin` array
3. Replace `"opencode-gemini-auth@latest"` with `"opencode-google-antigravity-auth"`
4. Keep all other plugins unchanged: `@tarquinen/opencode-dcp@latest`, `opencode-pty@latest`, `@franlol/opencode-md-table-formatter@latest`, `@zenobius/opencode-skillful`
5. Validate JSON syntax
6. Save file

**Before**:
```json
"plugin": [
  "opencode-gemini-auth@latest",
  "@tarquinen/opencode-dcp@latest",
  "opencode-pty@latest",
  "@franlol/opencode-md-table-formatter@latest",
  "@zenobius/opencode-skillful"
]
```

**After**:
```json
"plugin": [
  "opencode-google-antigravity-auth",
  "@tarquinen/opencode-dcp@latest",
  "opencode-pty@latest",
  "@franlol/opencode-md-table-formatter@latest",
  "@zenobius/opencode-skillful"
]
```

**QA Scenarios**:
- ✅ JSON validates: `python3 -c "import json; json.load(open('.opencode/opencode.json'))"`
- ✅ Exactly 5 plugins in array (not 4 or 6)
- ✅ No `@latest` suffix on `opencode-google-antigravity-auth` (plugin convention)
- ✅ All other plugins preserved unchanged

**Rollback**: Restore from `.opencode/opencode.json.pre-antigravity.bak`

---
### TODO-4: Add Provider Models Configuration
**Priority**: High  
**Estimated Time**: 5 minutes  
**Dependencies**: TODO-3

**Objective**: Add `provider.google.models` section with 5 models and thinking variants.

**Implementation Steps**:
1. Read current `.opencode/opencode.json`
2. Add new top-level `provider` object (insert after `agent` section, before closing `}`)
3. Copy EXACT configuration from antigravity plugin README for all 5 models:
   - `gemini-3-pro-preview` (variants: low/medium/high)
   - `gemini-3-flash` (variants: minimal/low/medium/high)
   - `gemini-2.5-flash-lite` (no variants, basic model)
   - `gemini-claude-sonnet-4-5-thinking` (variants: none/low/medium/high)
   - `gemini-claude-opus-4-5-thinking` (variants: low/medium/high)
4. Ensure every model includes `modalities` field (required for image support)
5. Validate JSON syntax
6. Save file

**Configuration to Add**:
```json
"provider": {
  "google": {
    "npm": "@ai-sdk/google",
    "models": {
      "gemini-3-pro-preview": {
        "id": "gemini-3-pro-preview",
        "name": "Gemini 3 Pro",
        "release_date": "2025-11-18",
        "reasoning": true,
        "limit": { "context": 1000000, "output": 64000 },
        "cost": { "input": 2, "output": 12, "cache_read": 0.2 },
        "modalities": {
          "input": ["text", "image", "video", "audio", "pdf"],
          "output": ["text"]
        },
        "variants": {
          "low": { "options": { "thinkingConfig": { "thinkingLevel": "low", "includeThoughts": true } } },
          "medium": { "options": { "thinkingConfig": { "thinkingLevel": "medium", "includeThoughts": true } } },
          "high": { "options": { "thinkingConfig": { "thinkingLevel": "high", "includeThoughts": true } } }
        }
      },
      "gemini-3-flash": {
        "id": "gemini-3-flash",
        "name": "Gemini 3 Flash",
        "release_date": "2025-12-17",
        "reasoning": true,
        "limit": { "context": 1048576, "output": 65536 },
        "cost": { "input": 0.5, "output": 3, "cache_read": 0.05 },
        "modalities": {
          "input": ["text", "image", "video", "audio", "pdf"],
          "output": ["text"]
        },
        "variants": {
          "minimal": { "options": { "thinkingConfig": { "thinkingLevel": "minimal", "includeThoughts": true } } },
          "low": { "options": { "thinkingConfig": { "thinkingLevel": "low", "includeThoughts": true } } },
          "medium": { "options": { "thinkingConfig": { "thinkingLevel": "medium", "includeThoughts": true } } },
          "high": { "options": { "thinkingConfig": { "thinkingLevel": "high", "includeThoughts": true } } }
        }
      },
      "gemini-2.5-flash-lite": {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "reasoning": false,
        "modalities": {
          "input": ["text", "image"],
          "output": ["text"]
        }
      },
      "gemini-claude-sonnet-4-5-thinking": {
        "id": "gemini-claude-sonnet-4-5-thinking",
        "name": "Claude Sonnet 4.5",
        "reasoning": true,
        "limit": { "context": 200000, "output": 64000 },
        "modalities": {
          "input": ["text", "image", "pdf"],
          "output": ["text"]
        },
        "variants": {
          "none": { "reasoning": false, "options": { "thinkingConfig": { "includeThoughts": false } } },
          "low": { "options": { "thinkingConfig": { "thinkingBudget": 4000, "includeThoughts": true } } },
          "medium": { "options": { "thinkingConfig": { "thinkingBudget": 16000, "includeThoughts": true } } },
          "high": { "options": { "thinkingConfig": { "thinkingBudget": 32000, "includeThoughts": true } } }
        }
      },
      "gemini-claude-opus-4-5-thinking": {
        "id": "gemini-claude-opus-4-5-thinking",
        "name": "Claude Opus 4.5",
        "release_date": "2025-11-24",
        "reasoning": true,
        "limit": { "context": 200000, "output": 64000 },
        "modalities": {
          "input": ["text", "image", "pdf"],
          "output": ["text"]
        },
        "variants": {
          "low": { "options": { "thinkingConfig": { "thinkingBudget": 4000, "includeThoughts": true } } },
          "medium": { "options": { "thinkingConfig": { "thinkingBudget": 16000, "includeThoughts": true } } },
          "high": { "options": { "thinkingConfig": { "thinkingBudget": 32000, "includeThoughts": true } } }
        }
      }
    }
  }
}
```

**QA Scenarios**:
- ✅ JSON validates: `python3 -c "import json; json.load(open('.opencode/opencode.json'))"`
- ✅ Exactly 5 models under `provider.google.models`
- ✅ All models have `modalities` field
- ✅ Gemini 3 models use `thinkingLevel` (low/medium/high)
- ✅ Claude models use `thinkingBudget` (4000/16000/32000)
- ✅ All thinking variants have `includeThoughts: true`

**Rollback**: Restore from backup if JSON invalid

---
### TODO-5: Update Top-Level Model References
**Priority**: Medium  
**Estimated Time**: 2 minutes  
**Dependencies**: TODO-4

**Objective**: Update default `model` and `small_model` to use thinking variants.

**Implementation Steps**:
1. Read current `.opencode/opencode.json`
2. Locate `model` field (currently `"gemini/gemini-2.5-pro"`)
3. Update to `"google/gemini-3-pro-medium"`
4. Locate `small_model` field (currently `"gemini/gemini-2.5-flash"`)
5. Update to `"google/gemini-3-flash-medium"`
6. Validate JSON syntax
7. Save file

**Before**:
```json
"model": "gemini/gemini-2.5-pro",
"small_model": "gemini/gemini-2.5-flash"
```

**After**:
```json
"model": "google/gemini-3-pro-medium",
"small_model": "google/gemini-3-flash-medium"
```

**Rationale**: Medium thinking level balances quality and cost for general use. High thinking reserved for complex tasks via explicit model selection.

**QA Scenarios**:
- ✅ JSON validates
- ✅ Model IDs match provider format: `google/` prefix, `-medium` suffix
- ✅ Test default model: `opencode run -p "what is 2+2, show reasoning"`
- ✅ Output shows thinking blocks (extended reasoning visible)

**Rollback**: Restore from backup if default model fails

---

### TODO-6: Update Agent Model Assignments
**Priority**: High  
**Estimated Time**: 3 minutes  
**Dependencies**: TODO-4

**Objective**: Migrate OpenAgent to Claude 4.5 thinking, upgrade TaskManager, keep Flash agents on 2.5.

**Implementation Steps**:
1. Read current `.opencode/opencode.json`
2. Locate `agent` section
3. Update OpenAgent: `opencode/claude-opus-4-6` → `google/gemini-claude-opus-4-5-thinking-high`
4. Update TaskManager: `gemini/gemini-3-pro` → `google/gemini-3-pro-medium`
5. Keep ContextScout, ExternalScout, DocWriter, ContextOrganizer on `gemini/gemini-2.5-flash` (no changes)
6. Validate JSON syntax
7. Save file

**Before**:
```json
"agent": {
  "OpenAgent": { "model": "opencode/claude-opus-4-6" },
  "TaskManager": { "model": "gemini/gemini-3-pro" },
  "ContextScout": { "model": "gemini/gemini-2.5-flash" },
  "ExternalScout": { "model": "gemini/gemini-2.5-flash" },
  "DocWriter": { "model": "gemini/gemini-2.5-flash" },
  "ContextOrganizer": { "model": "gemini/gemini-2.5-flash" }
}
```

**After**:
```json
"agent": {
  "OpenAgent": { "model": "google/gemini-claude-opus-4-5-thinking-high" },
  "TaskManager": { "model": "google/gemini-3-pro-medium" },
  "ContextScout": { "model": "gemini/gemini-2.5-flash" },
  "ExternalScout": { "model": "gemini/gemini-2.5-flash" },
  "DocWriter": { "model": "gemini/gemini-2.5-flash" },
  "ContextOrganizer": { "model": "gemini/gemini-2.5-flash" }
}
```

**Rationale**:
- OpenAgent: High thinking (32k tokens) for complex reasoning tasks
- TaskManager: Medium thinking balances quality and speed for task orchestration
- Flash agents: No thinking needed for simple context operations (speed/cost optimized)

**QA Scenarios**:
- ✅ JSON validates
- ✅ OpenAgent model ID matches Claude proxy format: `google/gemini-claude-opus-4-5-thinking-high`
- ✅ TaskManager model ID matches Gemini format: `google/gemini-3-pro-medium`
- ✅ Flash agents unchanged (4 agents still on `gemini/gemini-2.5-flash`)
- ✅ Test OpenAgent: Create simple task that uses OpenAgent, verify completion

**Rollback**: Restore from backup if agent model resolution fails

---
### TODO-7: Verify Gemini Thinking Models
**Priority**: Critical  
**Estimated Time**: 3 minutes  
**Dependencies**: TODO-4, TODO-5

**Objective**: Confirm Gemini 3 thinking variants respond correctly with reasoning visible.

**Implementation Steps**:
1. Test Gemini 3 Pro with low thinking:
   ```bash
   opencode run -m google/gemini-3-pro-low -p "what is 2+2, show your reasoning" 2>&1 | head -30
   ```
2. Test Gemini 3 Pro with high thinking:
   ```bash
   opencode run -m google/gemini-3-pro-high -p "explain why the sky is blue using physics" 2>&1 | head -50
   ```
3. Test Gemini 3 Flash with medium thinking:
   ```bash
   opencode run -m google/gemini-3-flash-medium -p "list 3 prime numbers and explain why" 2>&1 | head -30
   ```
4. Verify each response:
   - Contains thinking blocks (extended reasoning)
   - Shows `<thinking>` tags or reasoning steps
   - Returns correct answer after reasoning
   - No auth errors or model not found errors

**Expected Output Pattern**:
```
<thinking>
[Extended reasoning about the problem]
[Step-by-step analysis]
</thinking>

[Final answer based on reasoning]
```

**QA Scenarios**:
- ✅ All 3 model variants respond successfully
- ✅ Thinking blocks visible in output
- ✅ Higher thinking levels produce more detailed reasoning
- ✅ No "model not found" or "authentication failed" errors
- ✅ Response latency reasonable (<30s for high thinking)

**Rollback**: If models fail, verify TODO-4 config matches README exactly

---

### TODO-8: Verify Claude Proxy Models
**Priority**: Critical  
**Estimated Time**: 3 minutes  
**Dependencies**: TODO-4, TODO-6

**Objective**: Confirm Claude 4.5 proxy models work via Antigravity with thinking enabled.

**Implementation Steps**:
1. Test Claude Sonnet 4.5 with medium thinking:
   ```bash
   opencode run -m google/gemini-claude-sonnet-4-5-thinking-medium -p "explain recursion in programming" 2>&1 | head -40
   ```
2. Test Claude Opus 4.5 with high thinking:
   ```bash
   opencode run -m google/gemini-claude-opus-4-5-thinking-high -p "what are the tradeoffs between monoliths and microservices?" 2>&1 | head -60
   ```
3. Test Claude Sonnet without thinking (none variant):
   ```bash
   opencode run -m google/gemini-claude-sonnet-4-5-thinking-none -p "respond with just OK" 2>&1 | head -10
   ```
4. Verify each response:
   - Claude proxy working (not Gemini response style)
   - Thinking blocks present (except `-none` variant)
   - Interleaved thinking enabled automatically (thinking between tool calls)
   - No auth or proxy errors

**Expected Behavior**:
- Sonnet medium: 16k token thinking budget, concise reasoning
- Opus high: 32k token thinking budget, deep analysis
- Sonnet none: No thinking blocks, direct answer

**QA Scenarios**:
- ✅ All Claude variants respond successfully
- ✅ Thinking variants show extended reasoning
- ✅ `-none` variant returns direct answer (no thinking)
- ✅ Response style matches Claude (not Gemini patterns)
- ✅ No proxy errors or authentication failures

**Rollback**: If Claude models fail, verify `modalities` includes `["text", "image", "pdf"]`

---
### TODO-9: Verify Agent Model Resolution
**Priority**: High  
**Estimated Time**: 2 minutes  
**Dependencies**: TODO-6, TODO-8

**Objective**: Confirm OpenAgent and TaskManager resolve to correct thinking models.

**Implementation Steps**:
1. Create test prompt file `test-agent.txt`:
   ```
   Test prompt for OpenAgent verification.
   Respond with: "OpenAgent ready, using [model name]"
   ```
2. Test OpenAgent (should use Claude Opus 4.5 high thinking):
   ```bash
   opencode run --agent OpenAgent -f test-agent.txt 2>&1 | head -20
   ```
3. Verify OpenAgent response:
   - Mentions "Claude Opus 4.5" or shows Claude-style reasoning
   - No "model not found" errors
   - Thinking blocks present (high thinking = 32k budget)
4. Test TaskManager (should use Gemini 3 Pro medium):
   ```bash
   opencode run --agent TaskManager -p "list 3 tasks" 2>&1 | head -20
   ```
5. Verify TaskManager response:
   - Uses Gemini 3 Pro (not 2.5)
   - Medium thinking visible
   - Task list generated successfully
6. Cleanup: `rm test-agent.txt`

**QA Scenarios**:
- ✅ OpenAgent resolves to `google/gemini-claude-opus-4-5-thinking-high`
- ✅ TaskManager resolves to `google/gemini-3-pro-medium`
- ✅ Both agents respond without errors
- ✅ Thinking blocks visible in both responses
- ✅ Flash agents (ContextScout, etc.) still work unchanged

**Rollback**: Restore backup if agent resolution breaks

---

### TODO-10: Verify Flash Agents Unchanged
**Priority**: Medium  
**Estimated Time**: 1 minute  
**Dependencies**: TODO-6

**Objective**: Confirm ContextScout, ExternalScout, DocWriter, ContextOrganizer still work on Gemini 2.5 Flash.

**Implementation Steps**:
1. Test ContextScout:
   ```bash
   opencode run --agent ContextScout -p "summarize this: testing flash agent" 2>&1 | head -10
   ```
2. Verify response:
   - Fast response (<5s)
   - No thinking blocks (2.5 Flash doesn't support thinking)
   - Direct answer provided
   - No model resolution errors

**QA Scenarios**:
- ✅ ContextScout responds successfully
- ✅ Response is fast (Flash optimization intact)
- ✅ No thinking blocks (confirming 2.5 Flash, not 3 Flash)
- ✅ No errors about model not found

**Rollback**: If Flash agents break, verify `enabled_providers` still includes necessary providers

---

### TODO-11: Update Enabled Providers
**Priority**: Low  
**Estimated Time**: 1 minute  
**Dependencies**: TODO-6

**Objective**: Remove `opencode` from enabled_providers since no agents use it after migration.

**Implementation Steps**:
1. Read current `.opencode/opencode.json`
2. Locate `enabled_providers` array
3. Remove `"opencode"` from array (OpenAgent migrated to `google` provider)
4. Keep: `["openai", "anthropic", "google", "deepseek", "xai"]`
5. Validate JSON syntax
6. Save file

**Before**:
```json
"enabled_providers": ["openai", "anthropic", "google", "opencode", "deepseek", "xai"]
```

**After**:
```json
"enabled_providers": ["openai", "anthropic", "google", "deepseek", "xai"]
```

**Rationale**: OpenAgent was the only consumer of `opencode` provider. After migration to Antigravity's Claude proxy, `opencode` provider is unused.

**QA Scenarios**:
- ✅ JSON validates
- ✅ Exactly 5 providers in array (was 6)
- ✅ `google` provider present (required for Antigravity models)
- ✅ All agents still work after provider removal

**Rollback**: Add `"opencode"` back if unexpected breakage

---
### TODO-12: Test Cross-Model Conversations
**Priority**: Low  
**Estimated Time**: 2 minutes  
**Dependencies**: TODO-8

**Objective**: Verify thinking block preservation when switching between Gemini and Claude models in same session.

**Implementation Steps**:
1. Start interactive session with Claude:
   ```bash
   opencode -m google/gemini-claude-sonnet-4-5-thinking-high
   ```
2. First prompt (Claude thinking): "Explain what a binary tree is"
3. Verify Claude thinking blocks visible
4. Switch to Gemini in same session: `/model google/gemini-3-pro-high`
5. Second prompt (Gemini thinking): "Now explain what a hash table is"
6. Verify:
   - Claude thinking from Turn 1 removed (foreign signature)
   - Gemini thinking in Turn 2 visible
   - Conversation context preserved (text content flows through)
7. Switch back to Claude: `/model google/gemini-claude-opus-4-5-thinking-high`
8. Third prompt: "Compare both data structures"
9. Verify:
   - Gemini thinking from Turn 2 removed
   - Claude generates new thinking for Turn 3
   - Claude references previous conversation text correctly

**Expected Behavior**:
- Each model family caches its own thinking signatures separately
- Thinking blocks removed when switching families (Gemini ↔ Claude)
- Conversation text preserved across all switches
- No signature validation errors

**QA Scenarios**:
- ✅ Claude thinking visible in Turn 1
- ✅ Gemini thinking visible in Turn 2 (Claude thinking absent)
- ✅ Claude thinking visible in Turn 3 (Gemini thinking absent)
- ✅ Conversation context maintained (models reference previous text)
- ✅ No "invalid signature" or thinking block errors

**Rollback**: N/A (test only, no config changes)

---

### TODO-13: Document Model Variants and Usage
**Priority**: Low  
**Estimated Time**: 3 minutes  
**Dependencies**: All verification tasks (TODO-7 through TODO-12)

**Objective**: Create quick reference documentation for model selection.

**Implementation Steps**:
1. Create `.opencode/MODEL_VARIANTS.md` file
2. Document all thinking variants with use cases:
   - Gemini 3 Pro: low/medium/high
   - Gemini 3 Flash: minimal/low/medium/high
   - Claude Sonnet 4.5: none/low/medium/high
   - Claude Opus 4.5: low/medium/high
3. Add thinking level guidance:
   - Minimal/Low: Simple tasks, quick responses
   - Medium: Balanced quality/speed (default)
   - High: Complex reasoning, deep analysis
4. Add budget reference:
   - Gemini: `thinkingLevel` (qualitative)
   - Claude: `thinkingBudget` tokens (4k/16k/32k)
5. Add agent mapping:
   - OpenAgent → Claude Opus high (32k)
   - TaskManager → Gemini 3 Pro medium
   - Flash agents → No thinking (speed optimized)
6. Add cost/speed tradeoffs table
7. Save file

**Documentation Template**:
````markdown
# OpenCode Model Variants Guide

## Quick Reference

| Model | Variant | Use Case | Thinking Budget |
|-------|---------|----------|-----------------|
| Gemini 3 Pro | low | Simple reasoning | ~4k tokens (qualitative) |
| Gemini 3 Pro | medium | Balanced (default) | ~16k tokens (qualitative) |
| Gemini 3 Pro | high | Complex analysis | ~32k tokens (qualitative) |
| Gemini 3 Flash | minimal | Trivial tasks | <4k tokens |
| Gemini 3 Flash | medium | Fast reasoning | ~16k tokens |
| Claude Sonnet 4.5 | none | No thinking | 0 tokens |
| Claude Sonnet 4.5 | medium | Balanced | 16k tokens |
| Claude Opus 4.5 | high | Deep reasoning | 32k tokens |

## Agent Assignments

- **OpenAgent**: `google/gemini-claude-opus-4-5-thinking-high` (32k budget)
- **TaskManager**: `google/gemini-3-pro-medium` (~16k budget)
- **Flash Agents**: `gemini/gemini-2.5-flash` (no thinking, speed optimized)

## Cost Optimization

- Use Flash for simple context operations (search, summary)
- Use medium thinking for general tasks (default)
- Reserve high thinking for complex problems (architecture, debugging)
- Claude Opus most expensive; use only when necessary

## Command Examples

bash
# Gemini 3 Pro with high thinking
opencode run -m google/gemini-3-pro-high -p "your prompt"

# Claude Sonnet without thinking (fast)
opencode run -m google/gemini-claude-sonnet-4-5-thinking-none -p "your prompt"

# Claude Opus with high thinking (expensive)
opencode run -m google/gemini-claude-opus-4-5-thinking-high -p "your prompt"

````

**QA Scenarios**:
- ✅ Documentation file created at `.opencode/MODEL_VARIANTS.md`
- ✅ All model variants documented with accurate thinking budgets
- ✅ Agent assignments match config
- ✅ Command examples use correct model ID format
- ✅ Cost guidance provided

**Rollback**: Delete documentation file (no config impact)

---

## Final Verification Wave

### Post-Implementation Checklist

**Configuration Validation**:
- [ ] `.opencode/opencode.json` syntax valid (JSON parser succeeds)
- [ ] Backup exists at `.opencode/opencode.json.pre-antigravity.bak`
- [ ] Plugin array has 5 items (antigravity + 4 others)
- [ ] `provider.google.models` has 5 model definitions
- [ ] All models include `modalities` field
- [ ] `enabled_providers` has 5 items (removed `opencode`)

**Authentication Validation**:
- [ ] `~/.local/share/opencode/antigravity-accounts.json` exists
- [ ] Auth file contains at least 1 Google account
- [ ] Test model call succeeds: `opencode run -m google/gemini-2.5-flash-lite -p "OK"`

**Model Validation**:
- [ ] Gemini 3 Pro low/medium/high respond with thinking
- [ ] Gemini 3 Flash minimal/low/medium/high respond with thinking
- [ ] Claude Sonnet none/low/medium/high respond correctly
- [ ] Claude Opus low/medium/high respond with thinking
- [ ] Thinking blocks visible in high thinking responses

**Agent Validation**:
- [ ] OpenAgent resolves to Claude Opus 4.5 high
- [ ] TaskManager resolves to Gemini 3 Pro medium
- [ ] ContextScout still works on Gemini 2.5 Flash (fast)
- [ ] All 6 agents respond without errors

**Integration Validation**:
- [ ] Cross-model conversations work (Gemini ↔ Claude)
- [ ] Thinking blocks preserved within same family
- [ ] Thinking blocks removed when switching families
- [ ] No signature validation errors

**Documentation Validation**:
- [ ] `.opencode/MODEL_VARIANTS.md` created
- [ ] All variants documented with use cases
- [ ] Agent assignments documented
- [ ] Command examples provided

---

## Rollback Procedure

If any critical failures occur:

1. **Stop immediately** - Don't proceed to next task
2. **Restore backup**:
   ```bash
   cp .opencode/opencode.json.pre-antigravity.bak .opencode/opencode.json
   ```
3. **Verify restoration**:
   ```bash
   python3 -c "import json; json.load(open('.opencode/opencode.json'))"
   ```
4. **Test original config**:
   ```bash
   opencode run -m gemini/gemini-2.5-flash -p "test"
   ```
5. **Remove auth tokens** (optional, if auth issues):
   ```bash
   rm ~/.local/share/opencode/antigravity-accounts.json
   ```
6. **Report failure** with error logs

---

## Success Criteria

**All criteria must be met:**

1. ✅ Authentication completed via Google OAuth
2. ✅ All 5 model definitions added to config
3. ✅ All thinking variants respond successfully
4. ✅ OpenAgent migrated to Claude 4.5 high thinking
5. ✅ TaskManager upgraded to Gemini 3 Pro medium thinking
6. ✅ Flash agents still work on Gemini 2.5 (no changes)
7. ✅ Cross-model conversations work without errors
8. ✅ Documentation created for future reference
9. ✅ No JSON syntax errors in config
10. ✅ Backup created and preserved

**Definition of Done**: User can run `opencode run -m google/gemini-3-pro-high -p "solve X"` and see extended thinking blocks in response, and OpenAgent uses Claude Opus 4.5 with 32k thinking budget.

---

## Notes

**Antigravity ToS Warning**: Google's Antigravity Terms of Service (as of 2026-02-18) state the service cannot be used with third-party products. There are reports of account bans. User has accepted this risk.

**Model Version Downgrade**: OpenAgent migrates from Claude 4.6 to Claude 4.5. This is a model generation downgrade, but thinking variants (32k budget) may offset quality loss. User approved this change.

**Cost Implications**: Thinking adds latency and cost. High thinking variants should be used selectively for complex tasks. Flash agents kept on 2.5 to minimize cost for simple operations.

**Plugin Compatibility**: `@zenobius/opencode-skillful` is different from `opencode-skills` (warned incompatible in README). Monitor for compatibility issues after plugin swap.

**Multi-Account Load Balancing**: User can add multiple Google accounts during auth for automatic rotation when hitting rate limits. Optional but recommended for high-volume usage.

---

**End of Plan**