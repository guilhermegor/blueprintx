# React SPA DDD Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `templates/react-spa-webpack` from a flat folder structure to a full DDD scaffold with `capabilities/` per feature, FSD import discipline via ESLint, two-tier CSS token system, and a blueprintx menu offering state management (Context/Zustand/RTK) and Module Federation variants.

**Architecture:** Each capability owns `domain/` → `application/` → `infrastructure/` → `ui/` layers, mirroring the Python `ddd-service-*` templates. `context.tsx` per capability is the composition root (≡ `container.py`). ESLint enforces the import direction rule: domain imports nothing, context imports everything, cross-capability only via barrel `index.ts`.

**Tech Stack:** React 19, TypeScript 6, Webpack 5, Babel, ESLint v9 flat config, `eslint-plugin-boundaries`, `css-loader`, `style-loader`, `mini-css-extract-plugin`, CSS Modules, CSS custom properties.

**Reference paths:**
- Template root: `templates/react-spa-webpack/`
- Common assets: `templates/ts-common/`
- Scaffold script: `bin/scaffold/ts_react_app.sh`
- Design spec: `docs/superpowers/specs/2026-05-06-react-spa-ddd-scaffold-design.md`

---

### Task 1: Add CSS and path-alias support to webpack + tsconfig

**Files:**
- Modify: `templates/react-spa-webpack/webpack.config.js`
- Modify: `templates/react-spa-webpack/tsconfig.json`
- Modify: `templates/ts-common/package.json`
- Create: `templates/react-spa-webpack/src/declarations.d.ts`

- [ ] **Step 1: Add CSS loaders and @/ alias to webpack.config.js**

Replace the full contents of `templates/react-spa-webpack/webpack.config.js`:

```js
import ReactRefreshWebpackPlugin from '@pmmmwh/react-refresh-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isDevelopment = process.env.NODE_ENV !== 'production';

export default {
  entry: './src/index.tsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.[contenthash].js',
    clean: true,
  },
  devServer: {
    static: './dist',
    port: 3000,
    hot: true,
    open: true,
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            plugins: isDevelopment ? ['react-refresh/babel'] : [],
          },
        },
      },
      {
        test: /\.module\.css$/,
        use: [
          isDevelopment ? 'style-loader' : MiniCssExtractPlugin.loader,
          {
            loader: 'css-loader',
            options: {
              modules: {
                localIdentName: isDevelopment
                  ? '[name]__[local]--[hash:base64:5]'
                  : '[hash:base64]',
              },
            },
          },
        ],
      },
      {
        test: /\.css$/,
        exclude: /\.module\.css$/,
        use: [
          isDevelopment ? 'style-loader' : MiniCssExtractPlugin.loader,
          'css-loader',
        ],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html',
      filename: 'index.html',
    }),
    !isDevelopment && new MiniCssExtractPlugin({ filename: '[name].[contenthash].css' }),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
};
```

- [ ] **Step 2: Add paths alias to tsconfig.json**

In `templates/react-spa-webpack/tsconfig.json`, add `baseUrl` and `paths` inside `compilerOptions`, after `"moduleResolution": "bundler"`:

```json
"baseUrl": ".",
"paths": {
  "@/*": ["src/*"]
},
```

- [ ] **Step 3: Add CSS module type declaration**

Create `templates/react-spa-webpack/src/declarations.d.ts`:

```ts
declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}
```

- [ ] **Step 4: Add new devDependencies to ts-common/package.json**

In `templates/ts-common/package.json`, add inside `devDependencies`:

```json
"css-loader": "^7.1.2",
"eslint-plugin-boundaries": "^5.0.1",
"mini-css-extract-plugin": "^2.9.2",
"style-loader": "^4.0.0",
```

- [ ] **Step 5: Verify type-check passes**

From `templates/react-spa-webpack/`, run (after `npm install`):

```bash
npm run type-check
```

Expected: no errors. If tsconfig paths cause issues ensure `moduleResolution` is `bundler`.

---

### Task 2: Restructure src/ — remove flat directories, add new scaffolding

**Files:**
- Delete: `templates/react-spa-webpack/src/adapters/.gitkeep`
- Delete: `templates/react-spa-webpack/src/contexts/.gitkeep`
- Delete: `templates/react-spa-webpack/src/models/.gitkeep`
- Delete: `templates/react-spa-webpack/src/pages/.gitkeep`
- Delete: `templates/react-spa-webpack/src/routers/.gitkeep`
- Delete: `templates/react-spa-webpack/src/styles/.gitkeep`
- Delete: `templates/react-spa-webpack/src/templates/.gitkeep`
- Delete: `templates/react-spa-webpack/src/utils/.gitkeep`
- Delete: `templates/react-spa-webpack/src/workers/.gitkeep`
- Delete: `templates/react-spa-webpack/src/assets/.gitkeep`
- Create: `templates/react-spa-webpack/src/shared/components/.gitkeep`
- Create: `templates/react-spa-webpack/src/shared/assets/.gitkeep`
- Create: `templates/react-spa-webpack/src/shared/templates/.gitkeep`
- Create: `templates/react-spa-webpack/src/shared/utils/.gitkeep`
- Create: `templates/react-spa-webpack/src/shared/workers/.gitkeep`
- Create: `templates/react-spa-webpack/src/routes/.gitkeep`

- [ ] **Step 1: Remove old flat directories**

```bash
rtk find templates/react-spa-webpack/src -name '.gitkeep' -not -path '*/capabilities/*' -not -path '*/shared/*' -delete
rmdir templates/react-spa-webpack/src/adapters \
      templates/react-spa-webpack/src/contexts \
      templates/react-spa-webpack/src/models \
      templates/react-spa-webpack/src/pages \
      templates/react-spa-webpack/src/routers \
      templates/react-spa-webpack/src/styles \
      templates/react-spa-webpack/src/templates \
      templates/react-spa-webpack/src/utils \
      templates/react-spa-webpack/src/workers \
      templates/react-spa-webpack/src/assets 2>/dev/null || true
```

- [ ] **Step 2: Create new directory structure with gitkeep files**

```bash
mkdir -p templates/react-spa-webpack/src/shared/components \
         templates/react-spa-webpack/src/shared/assets \
         templates/react-spa-webpack/src/shared/templates \
         templates/react-spa-webpack/src/shared/utils \
         templates/react-spa-webpack/src/shared/workers \
         templates/react-spa-webpack/src/routes

touch templates/react-spa-webpack/src/shared/components/.gitkeep \
      templates/react-spa-webpack/src/shared/assets/.gitkeep \
      templates/react-spa-webpack/src/shared/templates/.gitkeep \
      templates/react-spa-webpack/src/shared/utils/.gitkeep \
      templates/react-spa-webpack/src/shared/workers/.gitkeep \
      templates/react-spa-webpack/src/routes/.gitkeep
```

- [ ] **Step 3: Verify structure**

```bash
rtk find templates/react-spa-webpack/src -type d | sort
```

Expected output includes: `src/shared/components`, `src/shared/assets`, `src/shared/templates`, `src/shared/utils`, `src/shared/workers`, `src/routes`. Old directories (`adapters`, `contexts`, `models`, `pages`, `routers`, `styles`, `templates`, `utils`, `workers`) must be absent.

- [ ] **Step 4: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "refactor(react-spa-webpack): replace flat src/ structure with DDD capabilities layout"
```

---

### Task 3: Create CSS foundations

**Files:**
- Create: `templates/react-spa-webpack/src/shared/styles/global.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/scale.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/primary.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/status.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/text.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/spacing.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/typography.css`
- Create: `templates/react-spa-webpack/src/shared/styles/foundations/index.css`
- Create: `templates/react-spa-webpack/src/shared/styles/theme.css`

- [ ] **Step 1: Create foundations/scale.css**

```css
:root {
  --neutral-100: #f8f9fa;
  --neutral-200: #e9ecef;
  --neutral-300: #dee2e6;
  --neutral-400: #ced4da;
  --neutral-500: #adb5bd;
  --neutral-600: #6c757d;
  --neutral-700: #495057;
  --neutral-800: #343a40;
  --neutral-900: #212529;
}
```

- [ ] **Step 2: Create foundations/primary.css**

```css
:root {
  --green-400: #4de7b7;
  --green-600: #0da170;
  --green-800: #065f46;

  --color-primary-light: var(--green-400);
  --color-primary:       var(--green-600);
  --color-primary-dark:  var(--green-800);
}
```

- [ ] **Step 3: Create foundations/status.css**

```css
:root {
  --color-success: #22c55e;
  --color-warning: #eab308;
  --color-error:   #991b1b;
  --color-info:    #0ea5e9;
}
```

- [ ] **Step 4: Create foundations/text.css**

```css
:root {
  --color-text-default:  #e6e9f0;
  --color-text-muted:    #aab3cc;
  --color-text-disabled: #555f7d;
}
```

- [ ] **Step 5: Create foundations/spacing.css**

```css
:root {
  --space-1: 0.4rem;
  --space-2: 0.8rem;
  --space-3: 1.2rem;
  --space-4: 1.6rem;
  --space-5: 2.4rem;
  --space-6: 3.2rem;
  --space-7: 4.8rem;
  --space-8: 6.4rem;
}
```

- [ ] **Step 6: Create foundations/typography.css**

```css
:root {
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'Courier New', Courier, monospace;

  --text-xs:   1.2rem;
  --text-sm:   1.4rem;
  --text-base: 1.6rem;
  --text-lg:   1.8rem;
  --text-xl:   2.0rem;
  --text-2xl:  2.4rem;
  --text-3xl:  3.2rem;
  --text-4xl:  4.2rem;

  --font-normal:   400;
  --font-medium:   500;
  --font-semibold: 600;
  --font-bold:     700;

  --leading-tight:   1.2;
  --leading-normal:  1.6;
  --leading-relaxed: 1.8;
}
```

- [ ] **Step 7: Create foundations/index.css**

```css
@import './scale.css';
@import './primary.css';
@import './status.css';
@import './text.css';
@import './spacing.css';
@import './typography.css';
```

- [ ] **Step 8: Create theme.css (dark-first, light override)**

```css
:root {
  --color-background: var(--neutral-900);
  --color-surface:    var(--neutral-800);
  --color-border:     var(--neutral-700);
}

[data-theme='light'] {
  --color-background:    var(--neutral-100);
  --color-surface:       var(--neutral-200);
  --color-border:        var(--neutral-300);
  --color-text-default:  #1a1d27;
  --color-text-muted:    #555f7d;
  --color-text-disabled: #aab3cc;
}
```

- [ ] **Step 9: Create global.css**

```css
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 62.5%;
}

body {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  background-color: var(--color-background);
  color: var(--color-text-default);
}
```

- [ ] **Step 10: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/src/shared/styles/
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(react-spa-webpack): add two-tier CSS token system and global styles"
```

---

### Task 4: Create example capability — domain layer

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/domain/enums.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/domain/entities.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/domain/dto.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/domain/ports.ts`

- [ ] **Step 1: Create domain/enums.ts**

```ts
export enum NoteStatus {
  Draft = 'draft',
  Published = 'published',
  Archived = 'archived',
}
```

- [ ] **Step 2: Create domain/entities.ts**

```ts
import type { NoteStatus } from './enums';

export interface Note {
  id: string;
  title: string;
  createdAt: Date;
  status: NoteStatus;
}
```

- [ ] **Step 3: Create domain/dto.ts**

```ts
import type { NoteStatus } from './enums';

export interface NoteCreateDTO {
  title: string;
}

export interface NoteResponseDTO {
  id: string;
  title: string;
  createdAt: Date;
  status: NoteStatus;
}
```

- [ ] **Step 4: Create domain/ports.ts**

```ts
import type { Note } from './entities';

export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
  get(id: string): Promise<Note | null>;
}
```

- [ ] **Step 5: Run type-check**

```bash
npm run type-check
```

Expected: no errors. Domain files have no external dependencies — if type-check fails here, there is a syntax error in one of the domain files above.

---

### Task 5: Create example capability — application layer (Context variant)

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/application/factories.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/application/use-cases.context.ts`

- [ ] **Step 1: Create application/factories.ts**

```ts
import { NoteStatus } from '../domain/enums';
import type { Note } from '../domain/entities';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';

export function noteFromCreateDTO(dto: NoteCreateDTO): Note {
  return {
    id: crypto.randomUUID(),
    title: dto.title,
    createdAt: new Date(),
    status: NoteStatus.Draft,
  };
}

export function noteToResponseDTO(note: Note): NoteResponseDTO {
  return {
    id: note.id,
    title: note.title,
    createdAt: note.createdAt,
    status: note.status,
  };
}
```

- [ ] **Step 2: Create application/use-cases.context.ts**

This is the React Context variant. The scaffold script renames it to `use-cases.ts`.

```ts
import { useState, useCallback } from 'react';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

export function useCreateNote(repo: NoteRepository) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (dto: NoteCreateDTO): Promise<NoteResponseDTO | null> => {
      setLoading(true);
      setError(null);
      try {
        const note = noteFromCreateDTO(dto);
        const saved = await repo.add(note);
        return noteToResponseDTO(saved);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [repo],
  );

  return { execute, loading, error };
}

export function useListNotes(repo: NoteRepository) {
  const [notes, setNotes] = useState<NoteResponseDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const items = await repo.list();
      setNotes(items.map(noteToResponseDTO));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [repo]);

  return { notes, execute, loading, error };
}
```

- [ ] **Step 3: Run type-check**

```bash
npm run type-check
```

Expected: no errors.

---

### Task 6: Create example capability — infrastructure layer

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/infrastructure/api-adapter.ts`

- [ ] **Step 1: Create infrastructure/api-adapter.ts**

```ts
import type { Note } from '../domain/entities';
import type { NoteRepository } from '../domain/ports';

export class ApiNoteRepository implements NoteRepository {
  constructor(private readonly baseUrl: string = '/api') {}

  async add(note: Note): Promise<Note> {
    const response = await fetch(`${this.baseUrl}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(note),
    });
    if (!response.ok) throw new Error(`Failed to create note: ${response.statusText}`);
    return response.json() as Promise<Note>;
  }

  async list(): Promise<Note[]> {
    const response = await fetch(`${this.baseUrl}/notes`);
    if (!response.ok) throw new Error(`Failed to list notes: ${response.statusText}`);
    return response.json() as Promise<Note[]>;
  }

  async get(id: string): Promise<Note | null> {
    const response = await fetch(`${this.baseUrl}/notes/${id}`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Failed to get note: ${response.statusText}`);
    return response.json() as Promise<Note>;
  }
}
```

- [ ] **Step 2: Run type-check**

```bash
npm run type-check
```

Expected: no errors. `ApiNoteRepository` must satisfy `NoteRepository` — TypeScript will error if the interface is not implemented correctly.

---

### Task 7: Create example capability — UI layer, composition root, barrel

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/ui/styles.module.css`
- Create: `templates/react-spa-webpack/src/capabilities/example/ui/components/ExampleCard.tsx`
- Create: `templates/react-spa-webpack/src/capabilities/example/ui/pages/ExamplePage.tsx`
- Create: `templates/react-spa-webpack/src/capabilities/example/context.context.tsx`
- Create: `templates/react-spa-webpack/src/capabilities/example/index.ts`

- [ ] **Step 1: Create ui/styles.module.css**

```css
.page {
  padding: var(--space-5);
}

.card {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.8rem;
  padding: var(--space-4);
  margin-bottom: var(--space-3);
}

.card h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text-default);
  margin-bottom: var(--space-2);
}

.card span {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
```

- [ ] **Step 2: Create ui/components/ExampleCard.tsx**

```tsx
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
```

- [ ] **Step 3: Create ui/pages/ExamplePage.tsx**

```tsx
import React, { useEffect } from 'react';
import { useNoteContext } from '../../context';
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
```

- [ ] **Step 4: Create context.context.tsx (composition root — Context variant)**

The scaffold script renames this to `context.tsx`.

```tsx
import React, { createContext, useContext, useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useCreateNote, useListNotes } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  createLoading: boolean;
  createError: Error | null;
  listNotes: () => Promise<void>;
  listLoading: boolean;
  listError: Error | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: ApiNoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);

  const { execute: createNote, loading: createLoading, error: createError } = useCreateNote(repo);
  const { notes, execute: listNotes, loading: listLoading, error: listError } = useListNotes(repo);

  const value = useMemo<NoteContextValue>(
    () => ({ notes, createNote, createLoading, createError, listNotes, listLoading, listError }),
    [notes, createNote, createLoading, createError, listNotes, listLoading, listError],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
```

- [ ] **Step 5: Create index.ts (public barrel)**

```ts
export { NoteProvider, useNoteContext } from './context';
export type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';
export { NoteStatus } from './domain/enums';
```

- [ ] **Step 6: Run type-check**

```bash
npm run type-check
```

Expected: no errors.

---

### Task 8: Update App.tsx and index.tsx

**Files:**
- Modify: `templates/react-spa-webpack/src/App.tsx`
- Modify: `templates/react-spa-webpack/src/index.tsx`

- [ ] **Step 1: Update index.tsx to import global styles**

```tsx
import '@/shared/styles/foundations/index.css';
import '@/shared/styles/theme.css';
import '@/shared/styles/global.css';
import { createRoot } from 'react-dom/client';
import App from './App';

const container = document.getElementById('root');
if (!container) throw new Error('Root element not found');

createRoot(container).render(<App />);
```

- [ ] **Step 2: Update App.tsx to render the example capability**

```tsx
import React from 'react';
import { NoteProvider } from '@/capabilities/example';
import { ExamplePage } from '@/capabilities/example/ui/pages/ExamplePage';

const App = () => (
  <NoteProvider>
    <ExamplePage />
  </NoteProvider>
);

export default App;
```

- [ ] **Step 3: Run type-check**

```bash
npm run type-check
```

Expected: no errors. The `@/` alias must resolve correctly via tsconfig paths.

- [ ] **Step 4: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(react-spa-webpack): add DDD example capability with Context composition root"
```

---

### Task 9: Add ESLint import boundary rules

**Files:**
- Modify: `templates/react-spa-webpack/eslint.config.js`

- [ ] **Step 1: Add boundaries plugin to eslint.config.js**

Add the import at the top, after existing imports:

```js
import boundaries from 'eslint-plugin-boundaries';
```

Add a new config block before the `prettierConfig` entry (which must remain last):

```js
  // 6. DDD import boundary rules
  {
    plugins: { boundaries },
    settings: {
      'boundaries/elements': [
        { type: 'domain',         pattern: 'capabilities/*/domain/**' },
        { type: 'application',    pattern: 'capabilities/*/application/**' },
        { type: 'infrastructure', pattern: 'capabilities/*/infrastructure/**' },
        { type: 'ui',             pattern: 'capabilities/*/ui/**' },
        { type: 'context',        pattern: 'capabilities/*/context.tsx' },
        { type: 'barrel',         pattern: 'capabilities/*/index.ts' },
        { type: 'shared',         pattern: 'shared/**' },
        { type: 'routes',         pattern: 'routes/**' },
      ],
      'boundaries/ignore': ['**/*.test.*', '**/*.spec.*'],
    },
    rules: {
      'boundaries/element-types': ['error', {
        default: 'disallow',
        rules: [
          { from: ['domain'],         allow: [] },
          { from: ['application'],    allow: ['domain'] },
          { from: ['infrastructure'], allow: ['domain'] },
          { from: ['ui'],             allow: ['application', 'domain'] },
          { from: ['context'],        allow: ['domain', 'application', 'infrastructure'] },
          { from: ['barrel'],         allow: ['domain', 'application', 'ui', 'context'] },
          { from: ['shared'],         allow: ['shared'] },
          { from: ['routes'],         allow: ['barrel', 'shared'] },
        ],
      }],
    },
  },
```

Update the ignores block at the top to also ignore config files but NOT eslint.config.js (which should not be self-referencing). The existing ignore pattern `"**/*.config.js"` already excludes `webpack.config.js`. Keep it as-is.

- [ ] **Step 2: Run lint to verify boundaries are enforced**

```bash
npm run lint
```

Expected: passes without boundary errors (all current imports respect the rules).

- [ ] **Step 3: Verify the rule catches a violation**

Temporarily add a forbidden import to `ui/pages/ExamplePage.tsx` — add this line at the top:

```ts
import { ApiNoteRepository } from '../../infrastructure/api-adapter';
```

Run lint:

```bash
npm run lint
```

Expected: ESLint error from `boundaries/element-types` — `ui` importing `infrastructure` is not allowed. Remove the line after confirming the error appears.

- [ ] **Step 4: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/eslint.config.js
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(react-spa-webpack): enforce DDD import boundaries via eslint-plugin-boundaries"
```

---

### Task 10: Create Zustand variant

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/application/use-cases.zustand.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/context.zustand.tsx`

- [ ] **Step 1: Create application/use-cases.zustand.ts**

```ts
import { create } from 'zustand';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

interface NoteState {
  notes: NoteResponseDTO[];
  loading: boolean;
  error: Error | null;
  createNote: (repo: NoteRepository, dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: (repo: NoteRepository) => Promise<void>;
}

export const useNoteStore = create<NoteState>()((set) => ({
  notes: [],
  loading: false,
  error: null,

  createNote: async (repo, dto) => {
    set({ loading: true, error: null });
    try {
      const note = noteFromCreateDTO(dto);
      const saved = await repo.add(note);
      const response = noteToResponseDTO(saved);
      set((state) => ({ notes: [...state.notes, response], loading: false }));
      return response;
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err : new Error(String(err)) });
      return null;
    }
  },

  listNotes: async (repo) => {
    set({ loading: true, error: null });
    try {
      const items = await repo.list();
      set({ notes: items.map(noteToResponseDTO), loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err : new Error(String(err)) });
    }
  },
}));
```

- [ ] **Step 2: Create context.zustand.tsx**

```tsx
import React, { createContext, useContext, useMemo } from 'react';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { useNoteStore } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: () => Promise<void>;
  loading: boolean;
  error: Error | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: ApiNoteRepository;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const { notes, loading, error, createNote: storeCreate, listNotes: storeList } = useNoteStore();

  const value = useMemo<NoteContextValue>(
    () => ({
      notes,
      loading,
      error,
      createNote: (dto) => storeCreate(repo, dto),
      listNotes: () => storeList(repo),
    }),
    [notes, loading, error, storeCreate, storeList, repo],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
```

---

### Task 11: Create Redux Toolkit variant

**Files:**
- Create: `templates/react-spa-webpack/src/capabilities/example/application/use-cases.rtk.ts`
- Create: `templates/react-spa-webpack/src/capabilities/example/context.rtk.tsx`

- [ ] **Step 1: Create application/use-cases.rtk.ts**

```ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { NoteRepository } from '../domain/ports';
import type { NoteCreateDTO, NoteResponseDTO } from '../domain/dto';
import { noteFromCreateDTO, noteToResponseDTO } from './factories';

interface NoteState {
  notes: NoteResponseDTO[];
  loading: boolean;
  error: string | null;
}

const initialState: NoteState = { notes: [], loading: false, error: null };

export const createNoteThunk = createAsyncThunk(
  'notes/create',
  async ({ repo, dto }: { repo: NoteRepository; dto: NoteCreateDTO }) => {
    const note = noteFromCreateDTO(dto);
    const saved = await repo.add(note);
    return noteToResponseDTO(saved);
  },
);

export const listNotesThunk = createAsyncThunk(
  'notes/list',
  async ({ repo }: { repo: NoteRepository }) => {
    const items = await repo.list();
    return items.map(noteToResponseDTO);
  },
);

export const noteSlice = createSlice({
  name: 'notes',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(createNoteThunk.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(createNoteThunk.fulfilled, (state, action) => {
        state.loading = false;
        state.notes.push(action.payload);
      })
      .addCase(createNoteThunk.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Unknown error';
      })
      .addCase(listNotesThunk.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(listNotesThunk.fulfilled, (state, action) => {
        state.loading = false;
        state.notes = action.payload;
      })
      .addCase(listNotesThunk.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Unknown error';
      });
  },
});
```

- [ ] **Step 2: Create context.rtk.tsx**

```tsx
import React, { createContext, useContext, useMemo } from 'react';
import { configureStore } from '@reduxjs/toolkit';
import { Provider, useDispatch, useSelector } from 'react-redux';
import { ApiNoteRepository } from './infrastructure/api-adapter';
import { noteSlice, createNoteThunk, listNotesThunk } from './application/use-cases';
import type { NoteCreateDTO, NoteResponseDTO } from './domain/dto';

const store = configureStore({ reducer: { notes: noteSlice.reducer } });
type RootState = ReturnType<typeof store.getState>;
type AppDispatch = typeof store.dispatch;

interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  listNotes: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

interface NoteProviderProps {
  children: React.ReactNode;
  repository?: ApiNoteRepository;
}

function NoteContextBridge({ children, repository }: NoteProviderProps) {
  const dispatch = useDispatch<AppDispatch>();
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const { notes, loading, error } = useSelector((state: RootState) => state.notes);

  const value = useMemo<NoteContextValue>(
    () => ({
      notes,
      loading,
      error,
      createNote: async (dto) => {
        const result = await dispatch(createNoteThunk({ repo, dto }));
        return createNoteThunk.fulfilled.match(result) ? result.payload : null;
      },
      listNotes: async () => { await dispatch(listNotesThunk({ repo })); },
    }),
    [notes, loading, error, dispatch, repo],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  return (
    <Provider store={store}>
      <NoteContextBridge repository={repository}>{children}</NoteContextBridge>
    </Provider>
  );
}

export function useNoteContext(): NoteContextValue {
  const ctx = useContext(NoteContext);
  if (!ctx) throw new Error('useNoteContext must be used within NoteProvider');
  return ctx;
}
```

- [ ] **Step 3: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(react-spa-webpack): add Zustand and Redux Toolkit capability variants"
```

---

### Task 12: Create webpack Module Federation variant

**Files:**
- Create: `templates/react-spa-webpack/webpack.mf.config.js`

- [ ] **Step 1: Create webpack.mf.config.js**

This is the MF variant of `webpack.config.js`. The scaffold script copies this as `webpack.config.js` when the user selects Module Federation. The placeholder `__APP_NAME__` is replaced by the scaffold script with the project name.

```js
import { ModuleFederationPlugin } from 'webpack/lib/container/ModuleFederationPlugin.js';
import ReactRefreshWebpackPlugin from '@pmmmwh/react-refresh-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isDevelopment = process.env.NODE_ENV !== 'production';
const { version: reactVersion } = require('react/package.json');

export default {
  entry: './src/index.tsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.[contenthash].js',
    publicPath: 'auto',
    clean: true,
  },
  devServer: {
    static: './dist',
    port: 3000,
    hot: true,
    open: true,
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            plugins: isDevelopment ? ['react-refresh/babel'] : [],
          },
        },
      },
      {
        test: /\.module\.css$/,
        use: [
          isDevelopment ? 'style-loader' : MiniCssExtractPlugin.loader,
          {
            loader: 'css-loader',
            options: {
              modules: {
                localIdentName: isDevelopment
                  ? '[name]__[local]--[hash:base64:5]'
                  : '[hash:base64]',
              },
            },
          },
        ],
      },
      {
        test: /\.css$/,
        exclude: /\.module\.css$/,
        use: [
          isDevelopment ? 'style-loader' : MiniCssExtractPlugin.loader,
          'css-loader',
        ],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({ template: './public/index.html', filename: 'index.html' }),
    new ModuleFederationPlugin({
      name: '__APP_NAME__',
      filename: 'remoteEntry.js',
      exposes: {
        './example': './src/capabilities/example/index.ts',
      },
      remotes: {},
      shared: {
        react:     { singleton: true, requiredVersion: `^${reactVersion}` },
        'react-dom': { singleton: true, requiredVersion: `^${reactVersion}` },
      },
    }),
    !isDevelopment && new MiniCssExtractPlugin({ filename: '[name].[contenthash].css' }),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
};
```

- [ ] **Step 2: Commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/react-spa-webpack/webpack.mf.config.js
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(react-spa-webpack): add webpack Module Federation variant"
```

---

### Task 13: Update scaffold script with state management and MF menus

**Files:**
- Modify: `bin/scaffold/ts_react_app.sh`

- [ ] **Step 1: Add prompt_state_management function**

Add the following function after the `resolve_github_username` function (before `create_directory_structure`):

```bash
prompt_state_management() {
    echo ""
    print_status "info" "State management strategy:"
    echo "  1) React Context  (zero deps, default)"
    echo "  2) Zustand        (lightweight store)"
    echo "  3) Redux Toolkit  (enterprise, RTK Query)"
    read -r -p "Choice [1]: " sm_choice || true
    STATE_MGMT_CHOICE="${sm_choice:-1}"
    case "$STATE_MGMT_CHOICE" in
        1) print_status "config" "State management: React Context" ;;
        2) print_status "config" "State management: Zustand" ;;
        3) print_status "config" "State management: Redux Toolkit" ;;
        *) print_status "warning" "Invalid choice; defaulting to React Context"
           STATE_MGMT_CHOICE=1 ;;
    esac
}

prompt_module_federation() {
    echo ""
    read -r -p "Enable Webpack Module Federation? [y/N]: " mf_answer || true
    case "$mf_answer" in
        y|Y) USE_MODULE_FEDERATION=1
             print_status "config" "Module Federation: enabled" ;;
        *)   USE_MODULE_FEDERATION=0
             print_status "config" "Module Federation: disabled" ;;
    esac
}
```

- [ ] **Step 2: Add apply_variants function**

Add after `copy_skeleton_files`:

```bash
apply_variants() {
    local project_path="$1"
    local capabilities_path="$project_path/src/capabilities/example"
    local application_path="$capabilities_path/application"

    print_status "info" "Applying state management variant..."

    case "$STATE_MGMT_CHOICE" in
        2)
            mv "$application_path/use-cases.zustand.ts" "$application_path/use-cases.ts"
            mv "$capabilities_path/context.zustand.tsx" "$capabilities_path/context.tsx"
            rm -f "$application_path/use-cases.context.ts" \
                  "$application_path/use-cases.rtk.ts" \
                  "$capabilities_path/context.context.tsx" \
                  "$capabilities_path/context.rtk.tsx"
            python3 -c "
import json
pkg = json.load(open('$project_path/package.json'))
pkg['dependencies']['zustand'] = '^5.0.0'
json.dump(pkg, open('$project_path/package.json', 'w'), indent=2)
print('')
"
            ;;
        3)
            mv "$application_path/use-cases.rtk.ts" "$application_path/use-cases.ts"
            mv "$capabilities_path/context.rtk.tsx" "$capabilities_path/context.tsx"
            rm -f "$application_path/use-cases.context.ts" \
                  "$application_path/use-cases.zustand.ts" \
                  "$capabilities_path/context.context.tsx" \
                  "$capabilities_path/context.zustand.tsx"
            python3 -c "
import json
pkg = json.load(open('$project_path/package.json'))
pkg['dependencies']['@reduxjs/toolkit'] = '^2.0.0'
pkg['dependencies']['react-redux'] = '^9.0.0'
json.dump(pkg, open('$project_path/package.json', 'w'), indent=2)
print('')
"
            ;;
        *)
            mv "$application_path/use-cases.context.ts" "$application_path/use-cases.ts"
            mv "$capabilities_path/context.context.tsx" "$capabilities_path/context.tsx"
            rm -f "$application_path/use-cases.zustand.ts" \
                  "$application_path/use-cases.rtk.ts" \
                  "$capabilities_path/context.zustand.tsx" \
                  "$capabilities_path/context.rtk.tsx"
            ;;
    esac

    if [ "$USE_MODULE_FEDERATION" -eq 1 ]; then
        print_status "info" "Applying Module Federation webpack config..."
        cp "$SKELETON_TEMPLATE_ROOT/webpack.mf.config.js" "$project_path/webpack.config.js"
        sed -i "s/__APP_NAME__/$PROJECT_NAME/g" "$project_path/webpack.config.js"
    fi

    print_status "success" "Variants applied"
}
```

- [ ] **Step 3: Update main() to call new functions**

Replace the `main()` function body:

```bash
main() {
    PROJECT_PATH="$PROJECT_ROOT/$PROJECT_NAME"

    print_section "React SPA (Webpack) scaffold"
    print_status "config" "Target: $PROJECT_PATH"

    validate_inputs
    resolve_github_username
    prompt_state_management
    prompt_module_federation
    create_directory_structure "$PROJECT_PATH"
    copy_skeleton_files "$PROJECT_PATH"
    copy_common_templates "$PROJECT_PATH"
    apply_variants "$PROJECT_PATH"
    prompt_git_remote_setup "$PROJECT_PATH"

    print_status "success" "React SPA scaffold complete!"
    print_status "info" "Project path: $PROJECT_PATH"
    print_status "info" "Run 'npm install && npm start' to begin development"
}
```

- [ ] **Step 4: Verify scaffold runs without errors**

Run a dry scaffold to a temp directory:

```bash
bash bin/scaffold/ts_react_app.sh /tmp my-test-spa "Test SPA"
```

When prompted: select option `1` (Context), select `N` for Module Federation and git. Expected: scaffold completes without errors, `/tmp/my-test-spa/src/capabilities/example/context.tsx` exists, `use-cases.ts` exists, no `.context.ts` or `.zustand.ts` files remain.

- [ ] **Step 5: Clean up and commit**

```bash
rm -rf /tmp/my-test-spa
git -C "$(rtk git rev-parse --show-toplevel)" add bin/scaffold/ts_react_app.sh
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "feat(scaffold): add state management and Module Federation menu prompts"
```

---

### Task 14: Create CLAUDE.md files

**Files:**
- Create: `templates/react-spa-webpack/CLAUDE.md`
- Modify/Create: `templates/ts-common/CLAUDE.md`

- [ ] **Step 1: Check existing ts-common/CLAUDE.md**

```bash
cat templates/ts-common/CLAUDE.md 2>/dev/null || echo "File does not exist"
```

Read the output to determine whether to create or update.

- [ ] **Step 2: Create templates/react-spa-webpack/CLAUDE.md**

```markdown
# React SPA (Webpack) — Architecture Guide

## Folder Structure

```
src/
├── capabilities/   # one folder per business capability (≡ Python capabilities/)
├── shared/         # cross-cutting: components, templates, utils, workers, styles
├── routes/         # app-level routing config
├── App.tsx         # root component — wires capability providers
└── index.tsx       # entry point — imports global styles, renders App
```

## DDD Layers (per capability)

| Folder | Imports from | Responsibility |
|--------|-------------|----------------|
| `domain/` | nothing | DTOs, entities, enums, port interfaces |
| `application/` | `domain/` only | hooks (use-cases), DTO↔entity assemblers |
| `infrastructure/` | `domain/` only | API adapters implementing domain ports |
| `ui/` | `application/` + `domain/` | components, pages, scoped CSS Modules |
| `context.tsx` | all layers | composition root — wires infrastructure into application |
| `index.ts` | all layers | public barrel — only intended public exports |

`context.tsx` is the only file that imports infrastructure. It is the React equivalent of Python's `container.py`.

## Import Rules (enforced by ESLint)

Cross-layer imports that violate the table above are caught at lint time via `eslint-plugin-boundaries`. Run `npm run lint` to verify.

Cross-capability imports must go through the barrel `index.ts` — never import from internal paths of another capability.

## Adding a New Capability

1. Create `src/capabilities/<name>/domain/{dto,entities,enums,ports}.ts`
2. Create `src/capabilities/<name>/application/{use-cases,factories}.ts`
3. Create `src/capabilities/<name>/infrastructure/api-adapter.ts`
4. Create `src/capabilities/<name>/ui/{components/,pages/,styles.module.css}`
5. Create `src/capabilities/<name>/context.tsx` (composition root)
6. Create `src/capabilities/<name>/index.ts` (public barrel)
7. Add the new provider to `App.tsx`
8. Add the `infrastructure` pattern to the `boundaries/elements` setting in `eslint.config.js` if needed

## CSS Conventions

- Global design tokens live in `shared/styles/foundations/` — import via `shared/styles/foundations/index.css`
- `shared/styles/theme.css` controls dark/light switching via `[data-theme='light']` on `<html>`
- Component styles use CSS Modules (`*.module.css`). Reference tokens via `var(--space-4)` etc.
- Never use magic numbers — always reference a token variable

## Custom Fonts

The scaffold uses a system font stack. To add a custom font without a Google CDN request:

```bash
npm install @fontsource/inter
```

```ts
// index.tsx
import '@fontsource/inter/400.css';
import '@fontsource/inter/700.css';
```

Then update `--font-sans` in `shared/styles/foundations/typography.css`.

## State Management

The active variant (`context`, `zustand`, or `rtk`) was selected at scaffold time. Only `application/use-cases.ts` and `context.tsx` differ between variants — all other layers are identical.

## Module Federation

If enabled at scaffold time, `webpack.config.js` uses `ModuleFederationPlugin`. Each capability's `index.ts` is the natural `exposes` entry point. To add a new exposed capability, add it to the `exposes` map in `webpack.config.js`.
```

- [ ] **Step 3: Create or update templates/ts-common/CLAUDE.md**

If the file does not exist, create it. If it exists, add the following section without removing existing content:

```markdown
# TypeScript Common Templates

## Purpose

Provides shared assets copied into every TypeScript scaffold at generation time. The
scaffold script runs `envsubst` on `package.json` to substitute `${PROJECT_NAME}` and
`${PROJECT_DESCRIPTION}`.

## Files

| File | Purpose |
|------|---------|
| `package.json` | Base dependencies for all TS scaffolds. Use `envsubst` substitution. |
| `.gitignore` | Node/TypeScript standard ignores |
| `CONTRIBUTING.md` | Generic contribution guide |
| `.vscode/settings.json` | Shared editor settings |

## What Belongs Here

Only assets shared by ALL TypeScript templates (currently only `react-spa-webpack`). If
an asset is specific to one scaffold, it belongs in that scaffold's template directory.

## What Does NOT Belong Here

- React-specific or SPA-specific configuration
- State management dependencies (handled by scaffold script variants)
- Framework-specific ESLint plugins
```

- [ ] **Step 4: Final lint and type-check**

```bash
npm run lint && npm run type-check
```

Expected: both pass with no errors.

- [ ] **Step 5: Final commit**

```bash
git -C "$(rtk git rev-parse --show-toplevel)" add templates/
git -C "$(rtk git rev-parse --show-toplevel)" commit -m "docs(blueprintx): add CLAUDE.md for react-spa-webpack and ts-common templates"
```
