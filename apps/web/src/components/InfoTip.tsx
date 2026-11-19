import { Info } from "lucide-react";
import { useId, useState } from "react";
import { element, type SCREENS } from "@/help/content";

type Props = { screen: keyof typeof SCREENS; name: string; text?: never } | { text: string; screen?: never; name?: never };

/**
 * (i) next to a title: the explanation is there when asked for, out of sight otherwise.
 * Opens on hover, focus or click (keyboard and touch friendly).
 */
export function InfoTip(props: Props) {
  const help = props.text !== undefined ? { what: props.text, why: "" } : element(props.screen, props.name);
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!help) return null;
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-describedby={open ? id : undefined} aria-label="Plus d'informations"
              onClick={() => setOpen((v) => !v)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
              className="grid h-6 w-6 place-items-center rounded-full text-muted/70 hover:bg-accent-soft hover:text-accent">
        <Info size={15} aria-hidden />
      </button>
      {open && (
        <span id={id} role="tooltip"
              className="absolute left-1/2 top-7 z-30 w-72 -translate-x-1/2 rounded-2xl bg-ink p-3.5 text-left text-sm font-normal normal-case leading-relaxed tracking-normal text-white shadow-soft">
          {help.what}
          {help.why && <span className="mt-2 block text-white/75">{help.why}</span>}
        </span>
      )}
    </span>
  );
}
