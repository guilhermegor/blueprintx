import type { INotifier } from '../domain/ports';

interface LogSink {
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
}

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
  }
}
