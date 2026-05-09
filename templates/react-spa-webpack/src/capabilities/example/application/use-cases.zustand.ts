import { create } from 'zustand';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

interface NoteState {
  notes: NoteResponseDTO[];
  loading: boolean;
  error: Error | null;
  createNote: (repo: NoteRepository, dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: (repo: NoteRepository) => Promise<void>;
}

export const useNoteStore = create<NoteState>()((set) => ({
  notes: [],
  loading: false,
  error: null,

  createNote: async (repo, dto) => {
    set({ loading: true, error: null });
    try {
      const note = noteFromCreateDTO(dto);
      const saved = await repo.add(note);
      const response = noteToResponseDTO(saved);
      set((state) => ({ notes: [...state.notes, response], loading: false }));
      return response;
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err : new Error(String(err)) });
      return null;
    }
  },

  listNotes: async (repo) => {
    set({ loading: true, error: null });
    try {
      const items = await repo.list();
      set({ notes: items.map(noteToResponseDTO), loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err : new Error(String(err)) });
    }
  },
}));
