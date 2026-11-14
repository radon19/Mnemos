"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useSession } from "./session";

export function QueryProvider({ children }: { children: React.ReactNode }): React.ReactNode {
  const { status, account, unlocked } = useSession();
  const boundary = `${status}:${account ?? "none"}:${unlocked ? "open" : "locked"}`;
  // Remount private screens as well as replacing their query cache. Clearing
  // only the cache would leave revealed notes/answers in component state.
  const client = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
    [boundary],
  );
  useEffect(() => () => {
    void client.cancelQueries();
    client.clear();
  }, [client]);
  return <QueryClientProvider key={boundary} client={client}>{children}</QueryClientProvider>;
}
