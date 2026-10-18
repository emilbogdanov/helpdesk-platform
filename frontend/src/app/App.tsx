import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { createQueryClient } from "@/app/query-client";

export function App() {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <main>
        <h1>Helpdesk</h1>
      </main>
    </QueryClientProvider>
  );
}
