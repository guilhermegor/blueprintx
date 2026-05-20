import { useEffect } from 'react';

import { useNoteContext } from '../../use-context';
import { ExampleCard } from '../components/ExampleCard';
import styles from '../styles.module.css';

export function ExamplePage() {
  const { listNotes, notes, listLoading, listError } = useNoteContext();

  useEffect(() => {
    void listNotes();
  }, [listNotes]);

  if (listLoading) return <p>Loading...</p>;
  if (listError) return <p>Error: {listError.message}</p>;

  return (
    <main className={styles.page}>
      <h1>Notes</h1>
      {notes.map((note) => (
        <ExampleCard key={note.id} note={note} />
      ))}
    </main>
  );
}
