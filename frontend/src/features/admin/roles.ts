import type { Role } from "@/api/types";

export const roles: readonly Role[] = ["customer", "agent", "admin"];

export const roleNames: Record<Role, string> = {
  customer: "Customer",
  agent: "Agent",
  admin: "Admin",
};
