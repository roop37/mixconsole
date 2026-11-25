import { useEffect } from "react";
import { AuditionProvider } from "./audition";
import { AutomationEditor } from "./components/AutomationEditor";
import { Candidates } from "./components/Candidates";
import { Header, Help, JobBar, Notice } from "./components/Chrome";
import { Deck } from "./components/Deck";
import { ExportPanel, Inspector } from "./components/Inspector";
import { Library } from "./components/Library";
import { Listen } from "./components/Listen";
import { deckControls, isTypingTarget } from "./lib/registry";
import { currentDoc, type View } from "./state";
import { useStore } from "./store";

function useShortcuts(): void {
  const { state, dispatch, actions } = useStore();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      const mod = event.metaKey || event.ctrlKey;
      const interactive =
        event.target instanceof HTMLElement &&
        event.target.closest("button, a, summary, [role=slider], [role=tab]") !== null;
      let handled = true;
      if (mod && event.key.toLowerCase() === "z") {
        void (event.shiftKey ? actions.redo() : actions.undo());
      } else if (mod && event.key.toLowerCase() === "y") {
        void actions.redo();
      } else if (event.altKey && ["Digit1", "Digit2", "Digit3"].includes(event.code)) {
        const views: View[] = ["console", "library", "listen"];
        dispatch({ type: "view", view: views[Number(event.code.slice(-1)) - 1] as View });
      } else if (mod || event.altKey) {
        handled = false;
      } else if (event.key === "?") {
        document.getElementById("help")?.dispatchEvent(new Event("open"));
      } else if (state.view !== "console") {
        handled = false;
      } else if (event.key === " " && !interactive) {
        deckControls[state.activeDeck]?.toggle();
      } else if (event.key === "1" || event.key === "2") {
        dispatch({ type: "active-deck", deck: event.key === "1" ? "a" : "b" });
      } else if (event.key === "+" || event.key === "=") {
        deckControls[state.activeDeck]?.zoom(1.6);
      } else if (event.key === "-" || event.key === "_") {
        deckControls[state.activeDeck]?.zoom(1 / 1.6);
      } else if (event.key === "0") {
        deckControls[state.activeDeck]?.fit();
      } else if (event.key === "p" && !interactive) {
        void actions.plan();
      } else if (event.key === "r" && !interactive && currentDoc(state)) {
        void actions.render("wav");
      } else {
        handled = false;
      }
      if (handled) event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, dispatch, actions]);
}

function ConsoleView() {
  return (
    <AuditionProvider>
      <div className="console">
        <div className="decks">
          <Deck deck="a" />
          <Deck deck="b" />
        </div>
        <div className="workbench">
          <Candidates />
          <div className="side">
            <Inspector />
            <AutomationEditor />
            <ExportPanel />
          </div>
        </div>
      </div>
    </AuditionProvider>
  );
}

export function App() {
  const { state, actions } = useStore();
  useShortcuts();
  // biome-ignore lint/correctness/useExhaustiveDependencies: run once; actions are stable
  useEffect(() => {
    void actions.init();
  }, []);
  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Header />
      <Notice />
      <main id="main" className="main" tabIndex={-1}>
        {!state.ready ? (
          <p role="status" className="empty">
            Connecting to the local server…
          </p>
        ) : state.view === "console" ? (
          <ConsoleView />
        ) : state.view === "library" ? (
          <Library />
        ) : (
          <Listen />
        )}
      </main>
      <JobBar />
      <Help />
    </div>
  );
}
