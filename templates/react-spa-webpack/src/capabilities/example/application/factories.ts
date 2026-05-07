import { NoteStatus } from '../domain/enums';
import type { Note } from '../domain/entities';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';

export function noteFromCreateDTO(dto: NoteCreateDTO): Note {
  return {
    id: crypto.randomUUID(),
    title: dto.title,
    createdAt: new Date(),
    status: NoteStatus.Draft,
  };
}

export function noteToResponseDTO(note: Note): NoteResponseDTO {
  return {
    id: note.id,
    title: note.title,
    createdAt: note.createdAt,
    status: note.status,
  };
}
