"use client";

import { NarrativeTabs, type NarrativeTabsProps } from "@/components/narrative/NarrativeTabs";

/** /narrative page body: the tabbed view (My baskets, Discovery). */
export function NarrativeDashboard(props: NarrativeTabsProps) {
  return <NarrativeTabs {...props} />;
}
