import { useEffect, useEffectEvent } from "react";

type Bindings = Partial<Record<string, () => void>>;

// Single-key shortcuts like a ticket tool has (j/k, c). They stay out of the way while the
// user types in a field, and never shadow browser shortcuts that use a modifier key.
export function useHotkeys(bindings: Bindings): void {
  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (isTyping(event.target)) {
      return;
    }
    const action = bindings[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  });

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      onKeyDown(event);
    };
    document.addEventListener("keydown", listener);
    return () => {
      document.removeEventListener("keydown", listener);
    };
  }, []);
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}
