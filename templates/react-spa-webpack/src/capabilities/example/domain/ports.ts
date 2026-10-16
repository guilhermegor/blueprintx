import type { Note } from './entities';

export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
  get(id: string): Promise<Note | null>;
}

export interface INotifier {
  success(message: string): void;
  error(message: string): void;
  warning(message: string): void;
  info(message: string): void;
  dismiss(): void;
}
