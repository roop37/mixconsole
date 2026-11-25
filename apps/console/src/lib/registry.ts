import type { DeckId } from "../state";

export interface DeckControls {
  toggle(): void;
  zoom(factor: number): void;
  fit(): void;
  seek(seconds: number): void;
}

/** Imperative handles for keyboard shortcuts (wavesurfer owns the media element). */
export const deckControls: Partial<Record<DeckId, DeckControls>> = {};

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    (target instanceof HTMLInputElement &&
      !["button", "checkbox", "radio", "range"].includes(target.type))
  );
}
