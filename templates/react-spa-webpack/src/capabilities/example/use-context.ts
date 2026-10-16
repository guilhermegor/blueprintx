import { createContext, useContext } from 'react';

import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';
import type { INotifier } from './domain/ports';

export interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  createLoading: boolean;
  createError: Error | null;
  listNotes: () => Promise<void>;
  listLoading: boolean;
  listError: Error | null;
  notifier: INotifier;
}

export const NoteContext = createContext<NoteContextValue | null>(null);

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
