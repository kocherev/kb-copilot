# 0003 Voice model

Status: accepted, 2026-11-02

## Context

The worker had three voice paths: OpenAI speech-to-text, a chat model and text-to-speech on a self-hosted LiveKit server, LiveKit Inference realtime on LiveKit Cloud, and a fallback loop over three Inference model ids. None of them showed the model the shared screen. The Inference path reported `image_tokens` 0, and LiveKit documents why: "LiveKit Inference doesn't support image or video input for realtime models" (https://docs.livekit.io/agents/models/realtime/openai/). Citations were a `Source:` line appended to the spoken text and parsed back out by the web page and the eval scorer.

## Decision

### One realtime model

The agent runs on `gemini-3.8-live-extended-thinking` through `livekit-plugins-google`, with `GOOGLE_API_KEY`. The same code path serves LiveKit Cloud and a self-hosted server, because the model call does not go through LiveKit at all. There is no speech-to-text, text-to-speech or turn-detector model to pick, tune or pay for, and no fallback loop: a model that cannot start is reported to the user instead of replaced with a weaker one that cannot see.

### Google plugin, not LiveKit Inference

Only the plugin forwards video frames to the model. Inference would be simpler to bill, and it would leave the agent blind. The cost is a Google key to manage next to the LiveKit key pair.

### Thinking level

`thinking_level` is `low`. The model is for spoken support, so latency matters more than long reasoning. The other levels are `medium` and `high`. `gemini-3.8-live` without extended thinking does not accept a level on the Gemini API.

### Frames and token cost

`RoomOptions(video_input=True)` subscribes to the screen share. `VoiceActivityVideoSampler` passes one frame per second while the user speaks and one every three seconds otherwise. `media_resolution` is `MEDIA_RESOLUTION_MEDIUM`, a middle token budget per frame. Gemini 3 models default to a larger budget, which spends tokens on pixels that a support screen does not need. Each turn logs one JSON line with `image_tokens` from the model's usage report, so the cost of a sampling choice is measured, not guessed. The numbers are not in this document because none were measured without a key; run `python -m kb_agent.selfcheck` to see them.

`AGENT_MAX_SESSION_SECONDS` (default 600) bounds the spend per session. At the limit the agent says a short goodbye and closes the session.

### Citations are data

`search_kb` hands the model numbered passages, each inside a `<passage>` tag with its text escaped, and says they are reference material and never instructions. After each assistant message the worker compares the message's sentences with the sentences of the passages found in that user turn, using the retrieval embedder. A passage is cited when one of its sentences has cosine similarity of at least 0.8 with a sentence of the answer. The worker sends the result on the `citations` data topic, with the message text, so the page can attach it to the matching transcript line. Nothing is cited when nothing is supported.

The 0.8 cutoff was measured on the first 60 answerable and paraphrase rows of the demo eval (276 retrieved passages), using the dataset's gold answers against the top five passages of each row. At 0.8, 88% of the cited passages came from a page the dataset expects. At 0.75 it was 84%, and at 0.9 it was 97% with 29% of the expected passages cited. A gold answer is a paraphrase of one page, not the model's wording, so this is a guide and not a score of the live agent. `make eval-answers` followed by `make eval-live` judges real model answers with the `citation` judge.

Attribution is a heuristic. It can miss a correct passage and, rarely, cite a related one. Missing is preferred to wrong, which is why the cutoff favors precision.

### Refusal

The prompt says to search before any product answer and to say exactly `That is not in the docs.` when the search is abstained or the passages do not answer. A greeting or a clarifying question needs no search. The abstained tool result repeats the exact sentence. Retrieval abstention is a score threshold in `kb_rag`, and the model decides the cases that retrieval cannot, such as a false premise.

### Never silent

The worker exits at startup when `GOOGLE_API_KEY` or the LiveKit settings are missing or placeholders. Inside a job, a failure to load the product, to start the session or a later unrecoverable model error is published on the `agent-error` topic, once someone has joined the room. The page shows it. CI runs the agent with a made-up key and fails when the room stays silent.

## Consequences

- A Google key is a required secret. It never reaches the browser.
- The Live model streams audio, so `make eval-answers` asks `gemini-3.8-flash` for text answers with the same prompt and tool. Its answers approximate the live agent and are not the live agent.
- The page cannot show a citation for a message whose transcript text differs from the message the worker saw. The line then shows no sources.
- `metrics_collected` is deprecated in livekit-agents 1.8, and it is still the only place per-turn image tokens appear. Move to `session_usage_updated` when it carries them.
