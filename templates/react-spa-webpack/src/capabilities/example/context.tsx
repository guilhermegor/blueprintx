import React, { useMemo } from 'react';

import { useCreateNote, useListNotes } from './application/use-cases';
import type { NoteRepository } from './domain/ports';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { consoleNotifier } from './infrastructure/console-notifier';
import { NoteContext, type NoteContextValue } from './use-context';

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: NoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const notifier = consoleNotifier;

  const { execute: createNote, loading: createLoading, error: createError } = useCreateNote(repo, notifier);
  const { notes, execute: listNotes, loading: listLoading, error: listError } = useListNotes(repo, notifier);

  const value = useMemo<NoteContextValue>(
    () => ({
      notes,
      createNote,
      createLoading,
      createError,
      listNotes,
      listLoading,
      listError,
      notifier,
    }),
    [notes, createNote, createLoading, createError, listNotes, listLoading, listError, notifier],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}
