import * as React from "react";

const MOBILE_BREAKPOINT = 768;

/**
 * Phase 16 (RWD): true when the viewport is below the `md` breakpoint (768px).
 * JS-driven (matchMedia) rather than CSS-only so navigation can conditionally
 * render the mobile drawer vs the desktop inline bar — and so the behaviour is
 * unit-testable (jsdom has no layout engine for CSS media queries).
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}
