import React, { useMemo } from 'react';

import { CONSOLE_EMITTER } from '@/shared/utils/log-emitter';

import { useCreateNote, useListNotes } from './application/use-cases';
import type { NoteRepository } from './domain/ports';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { createConsoleNotifier } from './infrastructure/console-notifier';
import { NoteContext, type NoteContextValue } from './use-context';

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: NoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  // CONSOLE_EMITTER is this skeleton's default LogEmitter (blueprintx#436) — the
  // composition root is the layer allowed to import `shared/`, so it injects the
  // emitter here rather than console-notifier.ts reaching into shared/ itself.
  const notifier = useMemo(() => createConsoleNotifier(CONSOLE_EMITTER), []);

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
