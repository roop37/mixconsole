/**
 * Undo/redo over MixScript versions. Versions are append-only on the server, so an edit never
 * loses anything: undo only moves the pointer; the next edit becomes a child of where we are.
 */
export interface History {
  current: string | null;
  past: string[];
  future: string[];
}

export const emptyHistory: History = { current: null, past: [], future: [] };

export function commit(history: History, versionId: string): History {
  if (history.current === versionId) return history;
  return {
    current: versionId,
    past: history.current ? [...history.past, history.current] : history.past,
    future: [],
  };
}

export function undo(history: History): History {
  const previous = history.past[history.past.length - 1];
  if (previous === undefined || history.current === null) return history;
  return {
    current: previous,
    past: history.past.slice(0, -1),
    future: [history.current, ...history.future],
  };
}

export function redo(history: History): History {
  const next = history.future[0];
  if (next === undefined || history.current === null) return history;
  return {
    current: next,
    past: [...history.past, history.current],
    future: history.future.slice(1),
  };
}

export const canUndo = (history: History) => history.past.length > 0;
export const canRedo = (history: History) => history.future.length > 0;
