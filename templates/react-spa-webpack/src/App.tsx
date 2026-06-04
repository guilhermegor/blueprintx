import { NoteProvider } from '@/capabilities/example';
import { MainRouter } from '@/routes/MainRouter';

const App = () => (
  <NoteProvider>
    <MainRouter />
  </NoteProvider>
);

export default App;
