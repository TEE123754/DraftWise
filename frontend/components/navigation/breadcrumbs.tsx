"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type BreadcrumbItem = { label: string; href?: string };

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  const path = usePathname();
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-[var(--ink-400)] mb-2">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path d="M4.5 2.5L7.5 6L4.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {isLast || !item.href ? (
              <span
                aria-current={isLast ? "page" : undefined}
                style={{ color: isLast ? "var(--ink-700)" : undefined, fontWeight: isLast ? 500 : undefined }}
              >
                {item.label}
              </span>
            ) : (
              <Link href={item.href} className="hover:text-[var(--ink-700)] transition-colors">
                {item.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
