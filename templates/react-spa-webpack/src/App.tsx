import React from 'react';
import { NoteProvider } from '@/capabilities/example';
import { ExamplePage } from '@/capabilities/example';

const App = () => (
  <NoteProvider>
    <ExamplePage />
  </NoteProvider>
);

export default App;
