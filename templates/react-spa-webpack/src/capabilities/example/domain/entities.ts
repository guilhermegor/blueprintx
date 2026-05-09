import type { NoteStatus } from './enums';

export interface Note {
  id: string;
  title: string;
  createdAt: Date;
  status: NoteStatus;
}
