import { Link } from "react-router";

import { PageState } from "@/ui/PageState";

export function NotFoundPage() {
  return (
    <PageState title="There's nothing at this address">
      <p>The link may be mistyped, or the page was moved.</p>
      <Link to="/">Go to the helpdesk</Link>
    </PageState>
  );
}
