import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type User = Schemas["UserResponse"];
export type Role = Schemas["Role"];
export type Person = Schemas["PersonResponse"];

export type Ticket = Schemas["TicketResponse"];
export type TicketStatus = Schemas["TicketStatus"];
export type TicketSort = Schemas["TicketSort"];
export type Priority = Schemas["Priority"];
export type Comment = Schemas["CommentResponse"];
export type Visibility = Schemas["Visibility"];
