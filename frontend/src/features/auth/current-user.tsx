import { createContext, use, type ReactNode } from "react";

import type { User } from "@/api/types";

const CurrentUserContext = createContext<User | null>(null);

export function CurrentUserProvider({ user, children }: { user: User; children: ReactNode }) {
  return <CurrentUserContext value={user}>{children}</CurrentUserContext>;
}

// For pages inside the signed-in shell, which only renders once the user has loaded.
export function useCurrentUserProfile(): User {
  const user = use(CurrentUserContext);
  if (!user) {
    throw new Error("useCurrentUserProfile is only available inside the signed-in app");
  }
  return user;
}
