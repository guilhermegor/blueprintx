import type { Note } from '../domain/entities';
import type { NoteRepository } from '../domain/ports';

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
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Failed to get note: ${response.statusText}`);
    return response.json() as Promise<Note>;
  }
}
