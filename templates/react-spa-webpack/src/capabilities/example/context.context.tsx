import React, { createContext, useContext, useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useCreateNote, useListNotes } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  createLoading: boolean;
  createError: Error | null;
  listNotes: () => Promise<void>;
  listLoading: boolean;
  listError: Error | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: ApiNoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);

  const { execute: createNote, loading: createLoading, error: createError } = useCreateNote(repo);
  const { notes, execute: listNotes, loading: listLoading, error: listError } = useListNotes(repo);

  const value = useMemo<NoteContextValue>(
    () => ({ notes, createNote, createLoading, createError, listNotes, listLoading, listError }),
    [notes, createNote, createLoading, createError, listNotes, listLoading, listError],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
