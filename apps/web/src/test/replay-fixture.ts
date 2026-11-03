import type { Replay, Turn } from "@/lib/api/client";

const PRODUCT = "11111111-1111-4111-8111-111111111111";

const passage = {
  id: "p1",
  title: "Reset a password",
  source: "upload://reset.md",
  score: 0.91,
};

const question: Turn = {
  id: "t1",
  role: "user",
  text: "How do I reset my password?",
  started_at: "2026-11-03T10:00:05Z",
  ended_at: "2026-11-03T10:00:07Z",
  searches: [],
  citations: [],
  latency: { end_of_turn_delay_ms: 300, transcription_delay_ms: 120 },
  image_tokens: null,
};

export const answer: Turn = {
  id: "t2",
  role: "assistant",
  text: "Open Settings, then Security.",
  started_at: "2026-11-03T10:00:09Z",
  ended_at: "2026-11-03T10:00:12Z",
  searches: [
    {
      query: "reset password",
      passages: [passage, { ...passage, id: "p2", title: "Roles", score: 0.42 }],
      abstained: false,
      duration_ms: 180,
    },
  ],
  citations: [{ id: "p1", title: "Reset a password", source: "upload://reset.md" }],
  latency: { llm_ttft_ms: 420, tts_ttfb_ms: 90, e2e_latency_ms: 1100 },
  image_tokens: 258,
};

export const replay: Replay = {
  id: "s1",
  product_id: PRODUCT,
  room: "kb-room",
  user_id: "user-a",
  created_at: "2026-11-03T10:00:00Z",
  ended_at: "2026-11-03T10:02:05Z",
  turn_count: 2,
  action_count: 1,
  handoff_count: 1,
  turns: [question, answer],
  actions: [
    { event: "proposed", at: "2026-11-03T10:01:00Z", task: "t", detail: "Click Save" },
    { event: "performed", at: "2026-11-03T10:01:05Z", task: "t", detail: "Click Save" },
  ],
  handoffs: [
    {
      title: "Cannot reset password",
      status: "created",
      issue_identifier: "ENG-7",
      issue_url: null,
      created_at: "2026-11-03T10:01:30Z",
    },
  ],
};
