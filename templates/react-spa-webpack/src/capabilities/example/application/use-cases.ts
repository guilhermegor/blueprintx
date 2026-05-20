import { useState, useCallback } from 'react';

import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import type { INotifier, NoteRepository } from '../domain/ports';

import { noteFromCreateDTO, noteToResponseDTO } from './factories';

export function useCreateNote(repo: NoteRepository, notifier: INotifier) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (dto: NoteCreateDTO): Promise<NoteResponseDTO | null> => {
      setLoading(true);
      setError(null);
      try {
        const note = noteFromCreateDTO(dto);
        const saved = await repo.add(note);
        notifier.success('Note created');
        return noteToResponseDTO(saved);
      } catch (err) {
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        notifier.error(`Failed to create note: ${e.message}`);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [repo, notifier],
  );

  return { execute, loading, error };
}

export function useListNotes(repo: NoteRepository, notifier: INotifier) {
  const [notes, setNotes] = useState<NoteResponseDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const items = await repo.list();
      setNotes(items.map(noteToResponseDTO));
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      notifier.error(`Failed to load notes: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [repo, notifier]);

  return { notes, execute, loading, error };
}
