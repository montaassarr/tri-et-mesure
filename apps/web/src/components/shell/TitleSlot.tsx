/** Lets each page put its title in the shell's top bar (same row as the actions, as in the mock-up). */
import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

export const TitleSlotContext = createContext<HTMLElement | null>(null);

export function InTitleSlot({ children }: { children: ReactNode }) {
  const slot = useContext(TitleSlotContext);
  return slot ? createPortal(children, slot) : <>{children}</>;
}
