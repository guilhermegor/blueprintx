import React, { useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useCreateNote, useListNotes } from './application/use-cases';
import { NoteContext, type NoteContextValue } from './use-context';
import type { NoteRepository } from './domain/ports';

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: NoteRepository;
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
