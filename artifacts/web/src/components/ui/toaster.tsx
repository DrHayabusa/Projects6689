import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useToast, type ToastVariant } from "./use-toast";

function variantStyles(variant: ToastVariant | undefined): {
  ring: string;
  icon: ReturnType<typeof Info>;
} {
  switch (variant) {
    case "destructive":
      return {
        ring: "border-destructive/40",
        icon: <AlertCircle className="h-5 w-5 text-[hsl(var(--destructive))]" />,
      };
    case "success":
      return {
        ring: "border-secondary/40",
        icon: <CheckCircle2 className="h-5 w-5 text-secondary" />,
      };
    default:
      return {
        ring: "border-primary/30",
        icon: <Info className="h-5 w-5 text-primary" />,
      };
  }
}

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex flex-col items-center gap-2 p-4">
      <AnimatePresence>
        {toasts.map((t) => {
          const styles = variantStyles(t.variant);
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: -24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -16, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className={`glass-card pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border px-4 py-3 ${styles.ring}`}
            >
              <div className="mt-0.5 shrink-0">{styles.icon}</div>
              <div className="min-w-0 flex-1">
                {t.title && (
                  <p className="text-sm font-semibold text-foreground">{t.title}</p>
                )}
                {t.description && (
                  <p className="mt-0.5 text-sm text-muted-foreground">{t.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
