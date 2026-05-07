import React, { useEffect } from 'react';
import { useNoteContext } from '../../context';
import { ExampleCard } from '../components/ExampleCard';
import styles from '../styles.module.css';

export function ExamplePage() {
  const { listNotes, notes, loading, error } = useNoteContext();

  useEffect(() => {
    void listNotes();
  }, [listNotes]);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error.message}</p>;

  return (
    <main className={styles.page}>
      <h1>Notes</h1>
      {notes.map((note) => (
        <ExampleCard key={note.id} note={note} />
      ))}
    </main>
  );
}
