import type { INotifier } from '../domain/ports';

/**
 * Structural shape of the injected log sink — matches `LogEmitter` from
 * `@/shared/utils/log-emitter` without importing it. `infrastructure/` may
 * only import `../domain/ports` and external libs (see
 * `_layers/infrastructure.md`); reaching into `shared/` from here would
 * violate that boundary, so the composition root (`context.tsx`) injects
 * the concrete emitter (`CONSOLE_EMITTER`) instead.
 */
interface LogSink {
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
}

/**
 * Default notifier used by the scaffold. One class per infrastructure module,
 * filename matching the class in kebab-case — the same shape as
 * `ApiNoteRepository` in `api-adapter.ts`. Delegates to an injected
 * `LogSink` (typically `CONSOLE_EMITTER`) instead of calling `console`
 * directly, so the destination stays swappable from the composition root
 * without touching this file (blueprintx#436).
 *
 * Replace with a toast-based adapter (e.g. wrapping react-toastify)
 * when your project wants visible notifications. The application
 * layer only depends on the `INotifier` port, so swapping the
 * implementation is a one-file change in the composition root.
 */
export class ConsoleNotifier implements INotifier {
  constructor(private readonly logEmitter: LogSink) {}

  success(msg: string): void {
    this.logEmitter.info(`[notifier:success] ${msg}`);
  }

  error(msg: string): void {
    this.logEmitter.error(`[notifier:error] ${msg}`);
  }

  warning(msg: string): void {
    this.logEmitter.warn(`[notifier:warning] ${msg}`);
  }

  info(msg: string): void {
    this.logEmitter.info(`[notifier:info] ${msg}`);
  }

  dismiss(): void {
    // No-op for console; toast adapters would clear active toasts here.
  }
}
