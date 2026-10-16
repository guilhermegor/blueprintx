declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}

declare module '*.css' {
  const content: Record<string, string>;
  export default content;
}

declare namespace NodeJS {
  interface ProcessEnv {
    PUBLIC_PATH?: string;
  }
}
