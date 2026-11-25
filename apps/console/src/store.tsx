import {
  createContext,
  type Dispatch,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import { type Actions, createActions } from "./actions";
import { type Action, type AppState, initialState, reducer } from "./state";

interface Store {
  state: AppState;
  dispatch: Dispatch<Action>;
  actions: Actions;
}

const Context = createContext<Store | null>(null);

/**
 * The reducer runs synchronously against a ref, so async actions that dispatch and then read
 * `get()` always see their own writes; React state only mirrors it for rendering.
 */
export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initialState);
  const latest = useRef(state);
  const dispatch = useCallback((action: Action) => {
    latest.current = reducer(latest.current, action);
    setState(latest.current);
  }, []);
  const actions = useMemo(() => createActions(() => latest.current, dispatch), [dispatch]);
  const value = useMemo(() => ({ state, dispatch, actions }), [state, dispatch, actions]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useStore(): Store {
  const store = useContext(Context);
  if (!store) throw new Error("StoreProvider missing");
  return store;
}
