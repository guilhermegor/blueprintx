import React, { createContext, useContext, useMemo } from 'react';
import { configureStore } from '@reduxjs/toolkit';
import { Provider, useDispatch, useSelector } from 'react-redux';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { noteSlice, createNoteThunk, listNotesThunk } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';
import type { NoteRepository } from './domain/ports';

const store = configureStore({ reducer: { notes: noteSlice.reducer } });
type RootState = ReturnType<typeof store.getState>;
type AppDispatch = typeof store.dispatch;

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

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
      loading,
      error,
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

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
