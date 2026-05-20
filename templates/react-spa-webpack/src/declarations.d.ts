declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}

declare module '*.css' {
  const content: Record<string, string>;
  export default content;
}

// Injected by webpack's DefinePlugin. The deploy workflow sets PUBLIC_PATH
// to `/<repo-name>/`; local dev leaves it undefined and defaults to '/'.
declare namespace NodeJS {
  interface ProcessEnv {
    PUBLIC_PATH?: string;
  }
}
