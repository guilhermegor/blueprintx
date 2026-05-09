import type { NoteStatus } from './enums';

export interface NoteCreateDTO {
  title: string;
}

export interface NoteResponseDTO {
  id: string;
  title: string;
  createdAt: Date;
  status: NoteStatus;
}
