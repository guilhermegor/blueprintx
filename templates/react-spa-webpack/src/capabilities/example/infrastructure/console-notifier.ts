import type { INotifier } from '../domain/ports';

/**
 * Default notifier used by the scaffold. Logs to the browser console
 * so the pattern works without pulling in a UI toast library.
 *
 * Replace with a toast-based adapter (e.g. wrapping react-toastify)
 * when your project wants visible notifications. The application
 * layer only depends on the `INotifier` port, so swapping the
 * implementation is a one-file change in the composition root.
 */
export const consoleNotifier: INotifier = {
  success: (msg) => {
    console.info('[notifier:success]', msg);
  },
  error: (msg) => {
    console.error('[notifier:error]', msg);
  },
  warning: (msg) => {
    console.warn('[notifier:warning]', msg);
  },
  info: (msg) => {
    console.info('[notifier:info]', msg);
  },
  dismiss: () => {
    // No-op for console; toast adapters would clear active toasts here.
  },
};
