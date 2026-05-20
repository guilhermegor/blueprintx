import { render, screen } from '@testing-library/react';

import type { NoteResponseDTO } from '../../domain/dto';
import { NoteStatus } from '../../domain/enums';

import { ExampleCard } from './ExampleCard';

function buildNote(overrides: Partial<NoteResponseDTO> = {}): NoteResponseDTO {
  return {
    id: 'n-1',
    title: 'Sample note',
    createdAt: new Date('2026-01-01T00:00:00Z'),
    status: NoteStatus.Draft,
    ...overrides,
  };
}

describe('ExampleCard', () => {
  it('renders the note title as a heading', () => {
    render(<ExampleCard note={buildNote({ title: 'Buy milk' })} />);
    expect(screen.getByRole('heading', { name: 'Buy milk' })).toBeInTheDocument();
  });

  it('renders the note status next to the title', () => {
    render(<ExampleCard note={buildNote({ status: NoteStatus.Archived })} />);
    expect(screen.getByText(NoteStatus.Archived)).toBeInTheDocument();
  });
});
