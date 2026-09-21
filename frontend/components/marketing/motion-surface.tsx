"use client";

import { useRef, type ReactNode, type PointerEvent } from "react";

/** Decorative motion only. No React re-render on pointer movement. */
export function MotionSurface({
  children,
  className = "",
  tilt = false,
}: {
  children: ReactNode;
  className?: string;
  tilt?: boolean;
}) {
  const surface = useRef<HTMLDivElement>(null);
  function move(event: PointerEvent<HTMLDivElement>) {
    if (
      event.pointerType !== "mouse" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = Math.max(
      -1,
      Math.min(1, ((event.clientX - box.left) / box.width - 0.5) * 2),
    );
    const y = Math.max(
      -1,
      Math.min(1, ((event.clientY - box.top) / box.height - 0.5) * 2),
    );
    const style = surface.current!.style;
    style.setProperty("--px", String(x));
    style.setProperty("--py", String(y));
    style.setProperty("--mouse-x", `${(x + 1) * 50}%`);
    style.setProperty("--mouse-y", `${(y + 1) * 50}%`);
  }
  function reset() {
    surface.current?.style.setProperty("--px", "0");
    surface.current?.style.setProperty("--py", "0");
  }
  return (
    <div
      ref={surface}
      onPointerMove={move}
      onPointerLeave={reset}
      onPointerCancel={reset}
      className={`${tilt ? "mw-tilt" : "mw-parallax"} ${className}`}
    >
      {children}
    </div>
  );
}
