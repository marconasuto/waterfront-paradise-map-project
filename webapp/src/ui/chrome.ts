/**
 * Foldable side-panels, intro curtain, and hamburger menu drawer.
 *
 * All four are tiny pieces of DOM glue that used to live as inline
 * closures in `main.ts`. Splitting them out lets us cover them with
 * jsdom tests without booting Mapbox, and gives each chrome bit a
 * single clear contract.
 */

/** Configurable timer surface so tests can advance time synchronously. */
export interface TimerLike {
  setTimeout: (cb: () => void, delayMs: number) => unknown;
}

const REAL_TIMERS: TimerLike = {
  setTimeout: (cb, delayMs) => window.setTimeout(cb, delayMs),
};

export interface PanelToggleOptions {
  /** The grid root that owns the `*-collapsed` class. */
  root: HTMLElement;
  /** The button that flips the collapsed state. */
  button: HTMLElement;
  /** The class added to `root` when the panel is collapsed. */
  collapsedClass: string;
  /** ARIA label when the panel is currently visible. */
  expandedLabel: string;
  /** ARIA label when the panel is currently collapsed. */
  collapsedLabel: string;
  /** Fired after the CSS transition completes (the grid has resettled). */
  onResize?: () => void;
  /** Resize delay (matches the CSS grid transition). Defaults to 300 ms. */
  resizeDelayMs?: number;
  timers?: TimerLike;
}

/**
 * Wire a story / layer panel toggle button. Returns the click handler
 * (handy for tests, never used by callers).
 */
export function attachPanelToggle(opts: PanelToggleOptions): () => void {
  const timers = opts.timers ?? REAL_TIMERS;
  const delay = opts.resizeDelayMs ?? 300;
  const handler = (): void => {
    const collapsed = opts.root.classList.toggle(opts.collapsedClass);
    opts.button.setAttribute(
      "aria-label",
      collapsed ? opts.collapsedLabel : opts.expandedLabel,
    );
    opts.button.setAttribute("aria-expanded", String(!collapsed));
    if (opts.onResize) {
      timers.setTimeout(opts.onResize, delay);
    }
  };
  opts.button.addEventListener("click", handler);
  return handler;
}

export interface IntroCurtainOptions {
  curtain: HTMLElement;
  closeBtn: HTMLElement;
  /** Fired after the fade-out completes; the host can `map.resize()`. */
  onDismissed?: () => void;
  /** Fade duration (matches CSS). Defaults to 360 ms. */
  fadeMs?: number;
  /** Optional Escape-key handler attachment target. Defaults to `document`. */
  keyTarget?: Document | HTMLElement;
  timers?: TimerLike;
}

/**
 * Wire the first-load intro curtain. Returns the dismiss function so
 * the host (or a test) can trigger it programmatically.
 */
export function attachIntroCurtain(opts: IntroCurtainOptions): () => void {
  const timers = opts.timers ?? REAL_TIMERS;
  const fadeMs = opts.fadeMs ?? 360;
  const keyTarget = opts.keyTarget ?? document;

  const dismiss = (): void => {
    if (opts.curtain.classList.contains("is-closing")) return;
    if (opts.curtain.classList.contains("is-hidden")) return;
    opts.curtain.classList.add("is-closing");
    timers.setTimeout(() => {
      opts.curtain.classList.add("is-hidden");
      opts.onDismissed?.();
    }, fadeMs);
  };

  opts.closeBtn.addEventListener("click", dismiss);
  keyTarget.addEventListener("keydown", (ev) => {
    const e = ev as KeyboardEvent;
    if (
      e.key === "Escape" &&
      !opts.curtain.classList.contains("is-hidden") &&
      !opts.curtain.classList.contains("is-closing")
    ) {
      dismiss();
    }
  });
  return dismiss;
}

export interface MenuDrawerOptions {
  toggleBtn: HTMLElement;
  closeBtn: HTMLElement;
  drawer: HTMLElement;
  /** Optional Escape-key target. Defaults to `document`. */
  keyTarget?: Document | HTMLElement;
}

/**
 * Wire the slide-in hamburger menu drawer. Returns a `setOpen` so
 * tests (and any consumers) can drive the state directly.
 */
export function attachMenuDrawer(opts: MenuDrawerOptions): (open: boolean) => void {
  const keyTarget = opts.keyTarget ?? document;

  const setOpen = (open: boolean): void => {
    opts.drawer.classList.toggle("is-open", open);
    opts.drawer.setAttribute("aria-hidden", String(!open));
    opts.toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      opts.closeBtn.focus();
    } else {
      opts.toggleBtn.focus();
    }
  };

  opts.toggleBtn.addEventListener("click", () => setOpen(true));
  opts.closeBtn.addEventListener("click", () => setOpen(false));
  opts.drawer.addEventListener("click", (ev) => {
    const target = ev.target as HTMLElement | null;
    if (target?.classList.contains("menu-drawer__link")) {
      setOpen(false);
    }
  });
  keyTarget.addEventListener("keydown", (ev) => {
    const e = ev as KeyboardEvent;
    if (e.key === "Escape" && opts.drawer.classList.contains("is-open")) {
      setOpen(false);
    }
  });

  return setOpen;
}
