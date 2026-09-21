"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

export type TipContent = { name: string; description: string };
type Side = "top" | "right" | "bottom" | "left";

const GAP = 8;
const TOUCH_MS = 3000;
const LEAVE_MS = 120;

/**
 * A hint with a name and a one-line function, e.g. "Trash · Moves the email to Trash for 30 days".
 * Shown on hover, on keyboard focus and on touch; Escape dismisses it, and the pointer may move
 * onto it without it closing (WCAG 1.4.13). It is drawn in a portal, so no scrolling or clipping
 * container (the sidebar, a table) can cut it off.
 */
export function Tooltip({
  name,
  description,
  side = "top",
  className,
  children,
}: TipContent & { side?: Side; className?: string; children: React.ReactElement<{ "aria-describedby"?: string }> }) {
  const id = React.useId();
  const anchor = React.useRef<HTMLSpanElement>(null);
  const leaving = React.useRef<number>(0);
  const [place, setPlace] = React.useState<{ top: number; left: number } | null>(null);

  const show = React.useCallback(() => {
    window.clearTimeout(leaving.current);
    // Measure the control itself: a fixed or absolutely placed child leaves the wrapper with no size.
    const box = (anchor.current?.firstElementChild ?? anchor.current)?.getBoundingClientRect();
    if (!box) return;
    const middle = Math.min(Math.max(box.left + box.width / 2, 140), window.innerWidth - 140);
    setPlace(
      side === "right"
        ? { top: box.top + box.height / 2, left: box.right + GAP }
        : side === "left"
          ? { top: box.top + box.height / 2, left: box.left - GAP }
          : side === "bottom"
          ? { top: box.bottom + GAP, left: middle }
          : { top: box.top - GAP, left: middle },
    );
  }, [side]);
  const hide = React.useCallback(() => {
    window.clearTimeout(leaving.current);
    setPlace(null);
  }, []);
  const hideSoon = () => {
    window.clearTimeout(leaving.current);
    leaving.current = window.setTimeout(hide, LEAVE_MS);
  };

  React.useEffect(() => {
    if (!place) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && hide();
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", hide, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", hide, true);
    };
  }, [place, hide]);
  React.useEffect(() => () => window.clearTimeout(leaving.current), []);

  const transform =
    side === "right"
      ? "translateY(-50%)"
      : side === "left"
        ? "translate(-100%, -50%)"
        : side === "bottom"
          ? "translateX(-50%)"
          : "translate(-50%, -100%)";
  return (
    <span
      ref={anchor}
      className={cn("inline-flex", className)}
      onMouseEnter={show}
      onMouseLeave={hideSoon}
      onFocus={(event) => event.target.matches(":focus-visible") && show()}
      onBlur={hide}
      onPointerDown={(event) => {
        if (event.pointerType !== "touch") return;
        show();
        leaving.current = window.setTimeout(hide, TOUCH_MS);
      }}
    >
      {place ? React.cloneElement(children, { "aria-describedby": id }) : children}
      {place &&
        createPortal(
          <span
            role="tooltip"
            id={id}
            onMouseEnter={() => window.clearTimeout(leaving.current)}
            onMouseLeave={hideSoon}
            style={{ position: "fixed", top: place.top, left: place.left, transform, zIndex: 80 }}
            className="block w-max max-w-64 rounded-md bg-slate-900 px-2.5 py-1.5 text-xs leading-4 text-white shadow-lg"
          >
            <strong className="block font-semibold">{name}</strong>
            <span className="block text-slate-200">{description}</span>
          </span>,
          document.body,
        )}
    </span>
  );
}
