import { useState, useCallback } from 'react';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

export function useCreateNote(repo: NoteRepository) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (dto: NoteCreateDTO): Promise<NoteResponseDTO | null> => {
      setLoading(true);
      setError(null);
      try {
        const note = noteFromCreateDTO(dto);
        const saved = await repo.add(note);
        return noteToResponseDTO(saved);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [repo],
  );

  return { execute, loading, error };
}

export function useListNotes(repo: NoteRepository) {
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
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [repo]);

  return { notes, execute, loading, error };
}
