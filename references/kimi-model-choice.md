# Why Kimi K2.5

The skill uses `moonshotai/kimi-k2.5` for both parse (text-only) and
critique (multimodal) stages. The choice was load-bearing — not a
token integration for prize eligibility.

## What K2.5 brings

K2.5 is Moonshot AI's native multimodal model: continued pretraining on
~15T mixed visual+text tokens on top of Kimi K2 base, with strong
benchmarks on VideoMMMU, HLE, and SWE-bench Multilingual. It supports
both instant and thinking modes, with a 256k context window — generous
for the kind of multi-scene storyboard sessions this skill is built
around.

For storyboarding specifically, two K2.5 capabilities matter:

1. **Visual coding lineage.** K2.5 was trained to look at UI mockups
   and produce code. Storyboard critique is the same shape of problem:
   look at a rendered SVG, reason about what it shows, propose
   structured edits. The model's existing prior on "I see a thing → I
   recommend a change" transfers directly.

2. **Strict-JSON output reliability.** Both parse and critique need
   structured JSON. K2.5 in instant mode (temperature 0.3-0.5) produces
   valid JSON with a strict system prompt at a rate that makes our
   one-retry policy sufficient. We measured this during prototyping;
   no other open-weight multimodal model in the same price tier hits
   the same JSON-validity rate without an explicit JSON-mode flag.

## What K2.5 does NOT do here

The critique is bounded by `references/critique-criteria.md`. K2.5 is
not asked for "creative direction" or to invent shots. The model is
constrained to the five film-grammar rules and a fixed whitelist of
revisable fields. This is intentional — a model proposing entirely new
scenes would be unverifiable; a model checking explicit rules is
auditable by design.

## Routing

We call K2.5 through OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)
with model identifier `moonshotai/kimi-k2.5`. OpenRouter is preferred
over direct Moonshot endpoints because:

- single API surface for the user (they already have an OpenRouter key
  for other Hermes skills)
- automatic provider failover if Fireworks or Moonshot is degraded
- consistent rate-limit semantics

The plumbing is in `scripts/kimi_client.py`. The cache is keyed on the
full request payload sha256, so identical prompts during dev/demo
recording don't hit the API repeatedly.

## Cost ballpark

Per board (parse + critique, single round):
- parse: ~600 input tokens + ~1500 output tokens
- critique: ~2000 input tokens (incl. base64 PNG) + ~800 output tokens

At OpenRouter pricing (~$0.50/M input, ~$2.80/M output as of April 2026),
that's well under one cent per board. The cache makes repeated demos
free.

## Forward compatibility

K2.6 shipped April 20, 2026 with stronger long-horizon coding. We
continue to use K2.5 because:

- the Kimi Hackathon track explicitly rewards Kimi K2.5 demonstrations
- K2.5 is sufficient for the critique workload — K2.6's improvements
  target multi-step coding, not visual critique
- the v0.2 plan is to evaluate K2.6 for parsing larger multi-scene
  scripts after the hackathon

The model identifier is centralized in `kimi_client.KIMI_MODEL`; one
constant change swaps the model.
