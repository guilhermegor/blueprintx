import React, { createContext, useContext, useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useNoteStore } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';
import type { NoteRepository } from './domain/ports';

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: () => Promise<void>;
  loading: boolean;
  error: Error | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: NoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const { notes, loading, error, createNote: storeCreate, listNotes: storeList } = useNoteStore();

  const value = useMemo<NoteContextValue>(
    () => ({
      notes,
      loading,
      error,
      createNote: (dto) => storeCreate(repo, dto),
      listNotes: () => storeList(repo),
    }),
    [notes, loading, error, storeCreate, storeList, repo],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
