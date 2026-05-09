import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

interface NoteState {
  notes: NoteResponseDTO[];
  loading: boolean;
  error: string | null;
}

const initialState: NoteState = { notes: [], loading: false, error: null };

export const createNoteThunk = createAsyncThunk(
  'notes/create',
  async ({ repo, dto }: { repo: NoteRepository; dto: NoteCreateDTO }) => {
    const note = noteFromCreateDTO(dto);
    const saved = await repo.add(note);
    return noteToResponseDTO(saved);
  },
);

export const listNotesThunk = createAsyncThunk(
  'notes/list',
  async ({ repo }: { repo: NoteRepository }) => {
    const items = await repo.list();
    return items.map(noteToResponseDTO);
  },
);

export const noteSlice = createSlice({
  name: 'notes',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(createNoteThunk.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(createNoteThunk.fulfilled, (state, action) => {
        state.loading = false;
        state.notes.push(action.payload);
      })
      .addCase(createNoteThunk.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Unknown error';
      })
      .addCase(listNotesThunk.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(listNotesThunk.fulfilled, (state, action) => {
        state.loading = false;
        state.notes = action.payload;
      })
      .addCase(listNotesThunk.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Unknown error';
      });
  },
});
