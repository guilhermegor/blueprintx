import type { Note } from './entities';

export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
  get(id: string): Promise<Note | null>;
}
