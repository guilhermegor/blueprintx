import React from 'react';
import type { NoteResponseDTO } from '../../domain/dto';
import styles from '../styles.module.css';

interface ExampleCardProps {
  note: NoteResponseDTO;
}

export function ExampleCard({ note }: ExampleCardProps) {
  return (
    <article className={styles.card}>
      <h2>{note.title}</h2>
      <span>{note.status}</span>
    </article>
  );
}
