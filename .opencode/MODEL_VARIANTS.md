# OpenCode Model Variants Guide

## Quick Reference

| Model | Variant | Use Case | Thinking Budget |
|-------|---------|----------|-----------------|
| Gemini 3 Pro | low | Simple reasoning | ~4k tokens (qualitative) |
| Gemini 3 Pro | medium | Balanced (default) | ~16k tokens (qualitative) |
| Gemini 3 Pro | high | Complex analysis | ~32k tokens (qualitative) |
| Gemini 3 Flash | minimal | Trivial tasks | <4k tokens |
| Gemini 3 Flash | low | Quick reasoning | ~4k tokens |
| Gemini 3 Flash | medium | Fast reasoning (default) | ~16k tokens |
| Gemini 3 Flash | high | Detailed analysis | ~32k tokens |
| Gemini 2.5 Flash Lite | none | No thinking | 0 tokens |
| Claude Sonnet 4.5 | none | No thinking | 0 tokens |
| Claude Sonnet 4.5 | low | Light reasoning | 4k tokens |
| Claude Sonnet 4.5 | medium | Balanced | 16k tokens |
| Claude Sonnet 4.5 | high | Deep reasoning | 32k tokens |
| Claude Opus 4.5 | low | Light reasoning | 4k tokens |
| Claude Opus 4.5 | medium | Balanced | 16k tokens |
| Claude Opus 4.5 | high | Deep reasoning (agent default) | 32k tokens |

## Agent Assignments

- **OpenAgent**: `google/gemini-claude-opus-4-5-thinking-high` (32k budget)
  - For complex code generation, architecture decisions, and deep reasoning tasks
- **TaskManager**: `google/gemini-3-pro-medium` (~16k budget)
  - For task orchestration and planning
- **ContextScout**: `gemini/gemini-2.5-flash` (no thinking)
  - Speed-optimized for context gathering
- **ExternalScout**: `gemini/gemini-2.5-flash` (no thinking)
  - Speed-optimized for external resource discovery
- **DocWriter**: `gemini/gemini-2.5-flash` (no thinking)
  - Speed-optimized for documentation generation
- **ContextOrganizer**: `gemini/gemini-2.5-flash` (no thinking)
  - Speed-optimized for context organization

## Default Models

- **Primary**: `google/gemini-3-pro-medium` (medium thinking, balanced quality/cost)
- **Small**: `google/gemini-3-flash-medium` (medium thinking, fast inference)

## Cost Optimization

### When to Use Flash Agents (No Thinking)
- Simple context operations (search, summary, listing)
- Quick documentation updates
- File organization and metadata tasks
- Any task where speed > reasoning quality

### When to Use Medium Thinking (Default)
- General coding tasks
- Code reviews
- Moderate complexity problem-solving
- Balanced quality and cost for most use cases

### When to Use High Thinking
- Architecture design and tradeoff analysis
- Complex debugging with multiple failure points
- Security-sensitive implementations
- Performance optimization requiring deep analysis
- **Reserve for genuinely hard problems**

### Cost Tiers (Approximate)
1. **Flash agents (2.5)**: Cheapest, fastest, no thinking
2. **Gemini 3 Flash low/minimal**: Very cheap, minimal thinking
3. **Gemini 3 Flash medium**: Cheap, fast with reasoning
4. **Gemini 3 Pro low/medium**: Moderate cost, better reasoning
5. **Claude Sonnet medium**: Moderate-high cost
6. **Gemini 3 Pro high**: High cost, deep reasoning
7. **Claude Opus high**: Highest cost, deepest reasoning

## Command Examples

### Using Gemini 3 Pro with Thinking
```bash
# Low thinking (quick tasks)
opencode run -m google/gemini-3-pro-low -p "what is 2+2, explain briefly"

# Medium thinking (default, balanced)
opencode run -m google/gemini-3-pro-medium -p "explain recursion with examples"

# High thinking (complex analysis)
opencode run -m google/gemini-3-pro-high -p "compare microservices vs monoliths with production tradeoffs"
```

### Using Gemini 3 Flash (Fast)
```bash
# Minimal thinking (trivial tasks)
opencode run -m google/gemini-3-flash-minimal -p "list 3 prime numbers"

# Medium thinking (fast reasoning, default for small_model)
opencode run -m google/gemini-3-flash-medium -p "summarize this code snippet"

# High thinking (detailed but fast)
opencode run -m google/gemini-3-flash-high -p "find bugs in this function"
```

### Using Claude Proxy Models
```bash
# No thinking (fastest Claude)
opencode run -m google/gemini-claude-sonnet-4-5-thinking-none -p "respond with OK"

# Medium thinking (balanced)
opencode run -m google/gemini-claude-sonnet-4-5-thinking-medium -p "explain async/await"

# High thinking (deep analysis, most expensive)
opencode run -m google/gemini-claude-opus-4-5-thinking-high -p "design a distributed caching layer"
```

### Using Flash Lite (No Thinking, Cheapest)
```bash
# Basic text-only tasks
opencode run -m google/gemini-2.5-flash-lite -p "format this JSON"
```

## Thinking Configuration Details

### Gemini Models (thinkingLevel)
- **Type**: Qualitative levels (`minimal`, `low`, `medium`, `high`)
- **Control**: Google's internal heuristic determines token budget
- **Visibility**: `includeThoughts: true` shows reasoning in output
- **Use Case**: When you want model to determine reasoning depth

### Claude Models (thinkingBudget)
- **Type**: Explicit token counts (4000, 16000, 32000)
- **Control**: Hard limit on thinking token usage
- **Visibility**: `includeThoughts: true` shows reasoning in output
- **Use Case**: When you need precise cost control

### Interleaved Thinking
Claude models with thinking enabled automatically support **interleaved thinking** - the model can reason between tool calls for multi-step tasks.

## Model Capabilities

### Gemini 3 Pro
- **Context**: 1M tokens
- **Output**: 64k tokens
- **Modalities**: Text, image, video, audio, PDF input
- **Best For**: Complex reasoning, multimodal tasks, long documents

### Gemini 3 Flash
- **Context**: 1M tokens (1,048,576)
- **Output**: 65k tokens
- **Modalities**: Text, image, video, audio, PDF input
- **Best For**: Fast reasoning with multimodal support

### Gemini 2.5 Flash Lite
- **Context**: Standard (not specified)
- **Output**: Standard
- **Modalities**: Text, image input only
- **Best For**: Cheapest option, text-heavy tasks

### Claude Sonnet 4.5 (via Antigravity Proxy)
- **Context**: 200k tokens
- **Output**: 64k tokens
- **Modalities**: Text, image, PDF input
- **Best For**: Balanced reasoning, tool use, code generation

### Claude Opus 4.5 (via Antigravity Proxy)
- **Context**: 200k tokens
- **Output**: 64k tokens
- **Modalities**: Text, image, PDF input
- **Best For**: Highest quality reasoning, complex problem-solving

## Authentication

All models require **Antigravity OAuth authentication**:

```bash
opencode auth login
# Select: Google → OAuth with Google (Antigravity)
# Authenticate in browser
```

Tokens stored at: `~/.local/share/opencode/antigravity-accounts.json`

### Multi-Account Load Balancing
Add multiple Google accounts during auth to automatically rotate when hitting rate limits:
```bash
opencode auth login
# Add first account
# When prompted "Add another account? (y/n)", press y
# Add second account
# Repeat as needed
```

## Cross-Model Conversations

When switching between Gemini and Claude models in the same session:
- **Thinking blocks are removed** when switching model families (Gemini ↔ Claude)
- **Conversation text is preserved** across all switches
- **Each family caches its own thinking signatures** separately
- Use `/model <model-id>` to switch models mid-conversation

Example:
```bash
opencode -m google/gemini-3-pro-high
> "Explain binary trees"
[Gemini thinking blocks visible]

> /model google/gemini-claude-sonnet-4-5-thinking-medium
> "Now explain hash tables"
[Claude thinking blocks visible, Gemini thinking removed]

> /model google/gemini-3-pro-high
> "Compare both"
[Gemini thinking visible, Claude thinking removed, conversation context intact]
```

## Troubleshooting

### "Model not found" Error
- Verify authentication: `ls -lh ~/.local/share/opencode/antigravity-accounts.json`
- If file missing, run `opencode auth login`
- Check model ID format: `google/gemini-3-pro-medium` (not `gemini/`)

### Slow Response Times
- High thinking adds latency (30s+ for complex prompts)
- Try lower thinking level (high → medium → low)
- Use Flash models for speed-critical tasks

### Rate Limits
- Add multiple Google accounts for load balancing
- Use lower-cost models (Flash instead of Pro/Opus)
- Reduce thinking levels

### Image Input Rejected
- Verify model supports images (check "Modalities" above)
- Flash Lite only supports text and image (no video/audio/PDF)
- Claude models support text, image, PDF (no video/audio)

## Important Notes

### Google Account Risk
**WARNING**: Google's Antigravity Terms of Service (as of 2026-02-18) state the service cannot be used with third-party products. There are reports of account bans. Use at your own risk.

### Model Version Downgrade
OpenAgent migrated from Claude Opus 4.6 → Claude Opus 4.5 (downgrade). High thinking budget (32k tokens) may offset quality loss.

### Plugin Compatibility
Using `@zenobius/opencode-skillful` plugin (different from `opencode-skills` mentioned in plugin README warnings). Monitor for compatibility issues.

## References

- **Plugin**: `opencode-google-antigravity-auth`
- **Config**: `.opencode/opencode.json`
- **Backup**: `.opencode/opencode.json.pre-antigravity.bak`
- **Plan**: `.sisyphus/plans/thinking-config.md`
