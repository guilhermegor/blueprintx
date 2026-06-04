// Self-hosted default typeface (no Google CDN request). The weights below back
// the --font-* tokens in shared/styles/foundations/typography.css. Import fonts
// before the foundation styles so the @font-face rules register first. To change
// or drop the font, see the "Custom fonts" section in CLAUDE.md.
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';

import '@/shared/styles/foundations/index.css';
import '@/shared/styles/theme.css';
import '@/shared/styles/global.css';

import { createRoot } from 'react-dom/client';

import App from './App';

const container = document.getElementById('root');
if (!container) throw new Error('Root element not found');

createRoot(container).render(<App />);
