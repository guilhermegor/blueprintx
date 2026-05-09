import { ExamplePage, NoteProvider } from '@/capabilities/example';

const App = () => (
  <NoteProvider>
    <ExamplePage />
  </NoteProvider>
);

export default App;
