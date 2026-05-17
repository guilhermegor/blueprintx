import React, { useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useNoteStore } from './application/use-cases';
import { NoteContext, type NoteContextValue } from './use-context.zustand';
import type { NoteRepository } from './domain/ports';

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
      createLoading: loading,
      createError: error,
      listLoading: loading,
      listError: error,
      createNote: (dto) => storeCreate(repo, dto),
      listNotes: () => storeList(repo),
    }),
    [notes, loading, error, storeCreate, storeList, repo],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}
