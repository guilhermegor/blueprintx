import { BrowserRouter, Route, Routes } from 'react-router';

import { ExamplePage } from '@/capabilities/example';

// Project sites are served from https://<owner>.github.io/<repo>/, so the
// browser pathname carries a `/<repo>/` prefix. react-router compares routes
// against the raw pathname — without a basename, `<Route path="/">` never
// matches `/<repo>/` and the SPA 404s. The deploy workflow exposes the subpath
// via `process.env.PUBLIC_PATH` (inlined by webpack's DefinePlugin); strip the
// trailing slash because react-router rejects it. Locally PUBLIC_PATH is unset
// → basename becomes '' (no prefix). The same code serves both environments.
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
