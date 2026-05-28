import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  attachIntroCurtain,
  attachMenuDrawer,
  attachPanelToggle,
} from "../src/ui/chrome";

/** Synchronous timer surface — fires the callback inline. */
function syncTimers(): {
  setTimeout: (cb: () => void) => unknown;
  calls: Array<{ delay: number }>;
} {
  const calls: Array<{ delay: number }> = [];
  return {
    setTimeout: (cb: () => void) => {
      calls.push({ delay: 0 });
      cb();
      return 0;
    },
    calls,
  };
}

function makeButton(): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  return b;
}

beforeEach(() => {
  document.body.innerHTML = "";
});

describe("attachPanelToggle", () => {
  function setup(): {
    root: HTMLElement;
    button: HTMLButtonElement;
    onResize: ReturnType<typeof vi.fn>;
    timers: ReturnType<typeof syncTimers>;
  } {
    const root = document.createElement("main");
    const button = makeButton();
    button.setAttribute("aria-label", "Chiudi pannello dei livelli");
    button.setAttribute("aria-expanded", "true");
    document.body.append(root, button);
    const onResize = vi.fn();
    const timers = syncTimers();
    attachPanelToggle({
      root,
      button,
      collapsedClass: "layer-panel-collapsed",
      expandedLabel: "Chiudi pannello dei livelli",
      collapsedLabel: "Apri pannello dei livelli",
      onResize,
      timers,
    });
    return { root, button, onResize, timers };
  }

  it("adds the collapsed class on first click and removes it on the second", () => {
    const { root, button } = setup();
    button.click();
    expect(root.classList.contains("layer-panel-collapsed")).toBe(true);
    button.click();
    expect(root.classList.contains("layer-panel-collapsed")).toBe(false);
  });

  it("flips aria-label and aria-expanded in lock-step with the class", () => {
    const { button } = setup();
    button.click();
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-label")).toBe("Apri pannello dei livelli");
    button.click();
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(button.getAttribute("aria-label")).toBe("Chiudi pannello dei livelli");
  });

  it("schedules onResize once per click, after the grid transition", () => {
    const { button, onResize, timers } = setup();
    button.click();
    button.click();
    expect(onResize).toHaveBeenCalledTimes(2);
    expect(timers.calls).toHaveLength(2);
  });

  it("does not schedule onResize when none is supplied", () => {
    const root = document.createElement("main");
    const button = makeButton();
    document.body.append(root, button);
    const timers = syncTimers();
    attachPanelToggle({
      root,
      button,
      collapsedClass: "story-panel-collapsed",
      expandedLabel: "open",
      collapsedLabel: "closed",
      timers,
    });
    button.click();
    expect(timers.calls).toHaveLength(0);
  });
});

describe("attachIntroCurtain", () => {
  function setup(): {
    curtain: HTMLElement;
    closeBtn: HTMLButtonElement;
    onDismissed: ReturnType<typeof vi.fn>;
    dismiss: () => void;
  } {
    const curtain = document.createElement("section");
    curtain.id = "intro-curtain";
    const closeBtn = makeButton();
    document.body.append(curtain, closeBtn);
    const onDismissed = vi.fn();
    const dismiss = attachIntroCurtain({
      curtain,
      closeBtn,
      onDismissed,
      fadeMs: 1,
      timers: syncTimers(),
    });
    return { curtain, closeBtn, onDismissed, dismiss };
  }

  it("adds is-closing immediately, then is-hidden after the timer", () => {
    const { curtain, closeBtn, onDismissed } = setup();
    closeBtn.click();
    expect(curtain.classList.contains("is-closing")).toBe(true);
    expect(curtain.classList.contains("is-hidden")).toBe(true);
    expect(onDismissed).toHaveBeenCalledTimes(1);
  });

  it("is idempotent — a second click while closing is a no-op", () => {
    const { closeBtn, onDismissed } = setup();
    closeBtn.click();
    closeBtn.click();
    expect(onDismissed).toHaveBeenCalledTimes(1);
  });

  it("dismisses on Escape when visible", () => {
    const { curtain, onDismissed } = setup();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(curtain.classList.contains("is-hidden")).toBe(true);
    expect(onDismissed).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape once it has already been dismissed", () => {
    const { closeBtn, onDismissed } = setup();
    closeBtn.click();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(onDismissed).toHaveBeenCalledTimes(1);
  });

  it("ignores keys other than Escape", () => {
    const { onDismissed } = setup();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: " " }));
    expect(onDismissed).not.toHaveBeenCalled();
  });

  it("exposes the dismiss function for programmatic close", () => {
    const { curtain, dismiss, onDismissed } = setup();
    dismiss();
    expect(curtain.classList.contains("is-hidden")).toBe(true);
    expect(onDismissed).toHaveBeenCalledTimes(1);
  });
});

describe("attachMenuDrawer", () => {
  function setup(): {
    drawer: HTMLElement;
    toggleBtn: HTMLButtonElement;
    closeBtn: HTMLButtonElement;
    link: HTMLAnchorElement;
    setOpen: (open: boolean) => void;
  } {
    const drawer = document.createElement("nav");
    drawer.id = "menu-drawer";
    drawer.setAttribute("aria-hidden", "true");
    const toggleBtn = makeButton();
    toggleBtn.setAttribute("aria-expanded", "false");
    const closeBtn = makeButton();
    const link = document.createElement("a");
    link.href = "#about";
    link.className = "menu-drawer__link";
    link.textContent = "About";
    drawer.appendChild(closeBtn);
    drawer.appendChild(link);
    document.body.append(toggleBtn, drawer);
    const setOpen = attachMenuDrawer({ toggleBtn, closeBtn, drawer });
    return { drawer, toggleBtn, closeBtn, link, setOpen };
  }

  it("opens on the toggle button and reflects state via ARIA", () => {
    const { drawer, toggleBtn } = setup();
    toggleBtn.click();
    expect(drawer.classList.contains("is-open")).toBe(true);
    expect(drawer.getAttribute("aria-hidden")).toBe("false");
    expect(toggleBtn.getAttribute("aria-expanded")).toBe("true");
  });

  it("closes on the close button", () => {
    const { drawer, toggleBtn, closeBtn } = setup();
    toggleBtn.click();
    closeBtn.click();
    expect(drawer.classList.contains("is-open")).toBe(false);
    expect(drawer.getAttribute("aria-hidden")).toBe("true");
    expect(toggleBtn.getAttribute("aria-expanded")).toBe("false");
  });

  it("closes when a menu link is clicked", () => {
    const { drawer, link, setOpen } = setup();
    setOpen(true);
    link.click();
    expect(drawer.classList.contains("is-open")).toBe(false);
  });

  it("closes on Escape when open, ignores it when closed", () => {
    const { drawer, toggleBtn } = setup();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(drawer.classList.contains("is-open")).toBe(false);

    toggleBtn.click();
    expect(drawer.classList.contains("is-open")).toBe(true);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(drawer.classList.contains("is-open")).toBe(false);
  });

  it("moves focus to the close button on open, back to the toggle on close", () => {
    const { toggleBtn, closeBtn } = setup();
    toggleBtn.click();
    expect(document.activeElement).toBe(closeBtn);
    closeBtn.click();
    expect(document.activeElement).toBe(toggleBtn);
  });
});
