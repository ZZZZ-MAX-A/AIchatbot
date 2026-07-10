import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

type AutoRefreshContextValue = {
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
};

const AutoRefreshContext = createContext<AutoRefreshContextValue | null>(null);

export function AutoRefreshProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabledState] = useState(false);
  const setEnabled = useCallback((nextEnabled: boolean) => {
    setEnabledState(nextEnabled);
  }, []);
  const value = useMemo(
    () => ({ enabled, setEnabled }),
    [enabled, setEnabled],
  );

  return (
    <AutoRefreshContext.Provider value={value}>
      {children}
    </AutoRefreshContext.Provider>
  );
}

export function useAutoRefreshPreference(): AutoRefreshContextValue {
  const value = useContext(AutoRefreshContext);
  if (!value) {
    throw new Error("useAutoRefreshPreference requires AutoRefreshProvider");
  }
  return value;
}
