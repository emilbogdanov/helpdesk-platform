import { useRouteError } from "react-router";

import { Button } from "@/ui/Button";
import { PageState } from "@/ui/PageState";

// A render error anywhere below the root lands here instead of a blank page.
export function RouteError() {
  const error = useRouteError();
  console.error(error);

  return (
    <PageState title="Something broke on this page">
      <p>Reloading usually fixes it. If it keeps happening, let the support team know.</p>
      <Button
        onClick={() => {
          window.location.reload();
        }}
      >
        Reload
      </Button>
    </PageState>
  );
}
