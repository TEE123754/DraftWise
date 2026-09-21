import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Tooltip, type TipContent } from "@/components/ui/tooltip";

/**
 * The only button style in the app. Every clickable control is a `Button`, or a link styled with
 * `buttonVariants`, so it is a box with the same focus ring and disabled look everywhere.
 * `default` and `outline` are older names for `primary` and `secondary`.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-brand-800 text-white hover:bg-brand-900",
        default: "bg-brand-800 text-white hover:bg-brand-900",
        secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50",
        outline: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50",
        ghost: "text-slate-700 hover:bg-slate-100",
        danger: "bg-red-700 text-white hover:bg-red-800 focus-visible:outline-red-700",
        link: "rounded-sm font-normal text-slate-700 underline underline-offset-2 hover:text-slate-900",
      },
      size: {
        md: "min-h-10 px-4 py-2",
        sm: "min-h-8 px-3 py-1 text-xs",
        icon: "size-8 p-0",
        bare: "",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
    /** Name and one-line function, shown on hover, keyboard focus and touch. */
    tip?: TipContent & { side?: "top" | "right" | "bottom" | "left"; className?: string };
  };

function Button({ className, variant, size, asChild = false, tip, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  const node = (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size: variant === "link" && !size ? "bare" : size, className }))}
      {...props}
    />
  );
  return tip ? <Tooltip {...tip}>{node}</Tooltip> : node;
}
export { Button, buttonVariants };
