import type { User } from "@/api/types";

export interface Account {
  user: User;
  password: string;
}

export const petar: Account = {
  user: {
    id: "3c275c1d-477f-4325-9ded-1e0b3e77c457",
    email: "petar.georgiev@acme.test",
    display_name: "Petar Georgiev",
    role: "customer",
    is_active: true,
    created_at: "2026-09-02T09:14:00Z",
  },
  password: "winter-orchard-42",
};

export const elena: Account = {
  user: {
    id: "eaaeee17-af3c-4a5b-aa7c-fb571b282210",
    email: "elena.dimitrova@northwind.test",
    display_name: "Elena Dimitrova",
    role: "agent",
    is_active: true,
    created_at: "2026-06-11T07:30:00Z",
  },
  password: "quiet-harbour-17",
};

export const maria: Account = {
  user: {
    id: "717567b3-3dcf-4471-9850-080409238a0d",
    email: "maria.ivanova@northwind.test",
    display_name: "Maria Ivanova",
    role: "admin",
    is_active: true,
    created_at: "2026-05-28T12:00:00Z",
  },
  password: "correct-horse-battery",
};
