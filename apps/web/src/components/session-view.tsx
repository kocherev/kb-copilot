"use client";

import "@livekit/components-styles";

import { SessionStart } from "@/components/session-start";

export function SessionView({
  apiUrl,
  productId,
  productName,
  agentName,
}: {
  apiUrl: string;
  productId: string;
  productName: string;
  agentName: string;
}) {
  return (
    <SessionStart
      apiUrl={apiUrl}
      productId={productId}
      productName={productName}
      agentName={agentName}
    />
  );
}
