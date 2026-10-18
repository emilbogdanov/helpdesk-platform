import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type User = Schemas["UserResponse"];
export type Role = Schemas["Role"];
