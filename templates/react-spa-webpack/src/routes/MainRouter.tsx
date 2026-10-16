import { BrowserRouter, Route, Routes } from 'react-router';

import { ExamplePage } from '@/capabilities/example';

const basename = (process.env.PUBLIC_PATH || '/').replace(/\/$/, '');

export function MainRouter() {
  return (
    <BrowserRouter basename={basename}>
      <Routes>
        <Route path="/" element={<ExamplePage />} />
      </Routes>
    </BrowserRouter>
  );
}
