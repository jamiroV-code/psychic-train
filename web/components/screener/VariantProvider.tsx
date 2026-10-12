"use client";

import { createContext, useContext, type ReactNode } from "react";
import { CRYPTO_VARIANT, type ScreenerVariant } from "@/lib/screener-variant";

// T47 / S9C: the board's variant. No provider means crypto, today's page.
const VariantContext = createContext<ScreenerVariant>(CRYPTO_VARIANT);

export function VariantProvider({ variant, children }: { variant: ScreenerVariant; children?: ReactNode }) {
  return <VariantContext.Provider value={variant}>{children}</VariantContext.Provider>;
}

export function useVariant(): ScreenerVariant {
  return useContext(VariantContext);
}
