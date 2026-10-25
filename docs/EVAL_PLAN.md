# Eval plan

Folio's promise is "ask anything, see the sources". Nothing measures that yet, so
the README makes no quality claims. These are the three numbers to measure next.

## 1. Citation coverage

- **Metric:** share of answers to research questions that attach at least one
  dossier source, and share of factual sentences that point at one.
- **How:** a fixed set of 20 questions (news, facts, "summarise this URL"), run
  through `run_chat`, scoring `sources` and the reply text. A research question
  costs two Gemini requests (one tool round, then a forced answer), so one run is
  about 40 requests. Check that against the key's daily limit before running.

## 2. Source validity

- **Metric:** share of cited URLs that resolve (HTTP 200) and actually contain the
  snippet shown in the dossier.
- **How:** re-fetch every `Source.url` from the run above and check the snippet
  text against the page. Free: no model calls.

## 3. Cost and latency per answer

- **Metric:** Gemini requests, tool calls and end-to-end seconds per question,
  p50 and p95.
- **How:** count `generate_content` calls and `tool_traces` per response, and time
  `POST /api/chat` around the same question set. This is what decides whether a
  hosted demo is affordable (see the README's note on the UI preview).
