import { NextResponse, type NextRequest } from "next/server";

import { serverApi } from "@/lib/api/server";
import type { LinearNotice } from "@/lib/linear";

// Linear sends the browser here after the user answers. The API checks the
// state against this signed-in user and org, then swaps the code for tokens.
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const code = params.get("code");
  const state = params.get("state");
  let notice: LinearNotice = "failed";
  if (params.get("error")) {
    notice = "denied";
  } else if (code && state) {
    try {
      const api = await serverApi();
      const { response } = await api.POST("/integrations/linear/callback", {
        body: { code, state },
      });
      notice = response.ok ? "connected" : "failed";
    } catch {
      notice = "failed";
    }
  }
  return NextResponse.redirect(new URL(`/settings?linear=${notice}`, request.url));
}
