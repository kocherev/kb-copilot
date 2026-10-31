"use client";

import "@livekit/components-styles";

import { SessionStart } from "@/components/session-start";

export function SessionView({
  apiUrl,
  productId,
  productName,
}: {
  apiUrl: string;
  productId: string;
  productName: string;
}) {
  return (
    <SessionStart apiUrl={apiUrl} productId={productId} productName={productName} />
  );
}
