import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastVariant = "default" | "destructive" | "success";

export interface Toast {
  id: number;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

export type ToastInput = Omit<Toast, "id">;

interface ToastContextValue {
  toasts: Toast[];
  toast: (input: ToastInput) => number;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (input: ToastInput) => {
      const id = ++idRef.current;
      const duration = input.duration ?? 4000;
      setToasts((prev) => [...prev, { ...input, id }]);
      const timer = setTimeout(() => dismiss(id), duration);
      timers.current.set(id, timer);
      return id;
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toasts, toast, dismiss }), [toasts, toast, dismiss]);

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
