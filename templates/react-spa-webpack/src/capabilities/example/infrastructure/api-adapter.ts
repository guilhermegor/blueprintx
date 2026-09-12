import type { Note } from '../domain/entities';
import type { NoteRepository } from '../domain/ports';

// Local constant, not the `http-status-codes` package (blueprintx#453): this is the only
// bare status-code literal in the scaffold, and the template ships no runtime dependency
// on that package today — adding one for a single named value isn't worth it yet. Promote
// to `http-status-codes` (or a shared `shared/http-status.ts`) the day a second call site
// needs a status code.
const HTTP_STATUS_NOT_FOUND = 404;

export class ApiNoteRepository implements NoteRepository {
  constructor(private readonly baseUrl: string = '/api') {}

  async add(note: Note): Promise<Note> {
    const response = await fetch(`${this.baseUrl}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(note),
    });
    if (!response.ok) throw new Error(`Failed to create note: ${response.statusText}`);
    return response.json() as Promise<Note>;
  }

  async list(): Promise<Note[]> {
    const response = await fetch(`${this.baseUrl}/notes`);
    if (!response.ok) throw new Error(`Failed to list notes: ${response.statusText}`);
    return response.json() as Promise<Note[]>;
  }

  async get(id: string): Promise<Note | null> {
    const response = await fetch(`${this.baseUrl}/notes/${id}`);
    if (response.status === HTTP_STATUS_NOT_FOUND) return null;
    if (!response.ok) throw new Error(`Failed to get note: ${response.statusText}`);
    return response.json() as Promise<Note>;
  }
}
