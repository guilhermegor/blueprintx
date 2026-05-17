import React, { useMemo } from 'react';
import { configureStore } from '@reduxjs/toolkit';
import { Provider, useDispatch, useSelector } from 'react-redux';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { noteSlice, createNoteThunk, listNotesThunk } from './application/use-cases';
import { NoteContext, type NoteContextValue } from './use-context.rtk';
import type { NoteRepository } from './domain/ports';

const store = configureStore({ reducer: { notes: noteSlice.reducer } });
type RootState = ReturnType<typeof store.getState>;
type AppDispatch = typeof store.dispatch;

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: NoteRepository;
}

function NoteContextBridge({ children, repository }: NoteProviderProps) {
  const dispatch = useDispatch<AppDispatch>();
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const { notes, loading, error } = useSelector((state: RootState) => state.notes);

  const value = useMemo<NoteContextValue>(
    () => ({
      notes,
      createLoading: loading,
      createError: error ? new Error(error) : null,
      listLoading: loading,
      listError: error ? new Error(error) : null,
      createNote: async (dto) => {
        const result = await dispatch(createNoteThunk({ repo, dto }));
        return createNoteThunk.fulfilled.match(result) ? result.payload : null;
      },
      listNotes: async () => { await dispatch(listNotesThunk({ repo })); },
    }),
    [notes, loading, error, dispatch, repo],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  return (
    <Provider store={store}>
      <NoteContextBridge repository={repository}>{children}</NoteContextBridge>
    </Provider>
  );
}
