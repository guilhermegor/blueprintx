import type { Note } from './entities';

export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
  get(id: string): Promise<Note | null>;
}

/**
 * Port for emitting transient UI messages from use-cases.
 *
 * Define the contract here in `domain/`; concrete adapters live in
 * `infrastructure/` (e.g. `console-notifier.ts`, `toast-notifier.ts`).
 * Use-cases accept this port as a parameter — they never import
 * concrete adapters. The composition root wires the chosen
 * implementation when constructing the context value.
 */
export interface INotifier {
  success(message: string): void;
  error(message: string): void;
  warning(message: string): void;
  info(message: string): void;
  dismiss(): void;
}
