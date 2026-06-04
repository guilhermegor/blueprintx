import ReactRefreshWebpackPlugin from '@pmmmwh/react-refresh-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import fs from 'fs';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import { fileURLToPath } from 'url';
import webpack from 'webpack';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isDevelopment = process.env.NODE_ENV !== 'production';

// Zero-dependency .env parser. Reads KEY=VALUE lines (ignoring blanks and
// `#` comments) so build-time vars can be inlined without a dotenv package.
// Real process env (CI, Docker BuildKit secret mount) takes precedence over
// the committed file at the call sites below.
function readEnvFile(name) {
  const file = path.resolve(__dirname, name);
  if (!fs.existsSync(file)) return {};
  return Object.fromEntries(
    fs
      .readFileSync(file, 'utf8')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('#'))
      .map((line) => {
        const eq = line.indexOf('=');
        return [line.slice(0, eq).trim(), line.slice(eq + 1).trim()];
      }),
  );
}

const fileEnv = readEnvFile('.env');

// NODE_ENV is owned by the build mode (cross-env + webpack `mode`); PUBLIC_PATH
// is special-cased below. Inlining either from the file would fight those, so
// they're reserved out of the generic inlining.
const RESERVED_ENV_KEYS = new Set(['NODE_ENV', 'PUBLIC_PATH']);

// GitHub Pages serves project sites under `/<repo-name>/`. Set
// PUBLIC_PATH (e.g. via the deploy workflow) to point webpack at the
// right subpath. Default `/` works for local dev and root-served hosts.
const publicPath = process.env.PUBLIC_PATH || fileEnv.PUBLIC_PATH || '/';

// Inline every other .env key as `process.env.<KEY>` so app code can read
// custom build-time vars (e.g. an API key) without editing this config.
const inlinedEnv = Object.fromEntries(
  Object.entries(fileEnv)
    .filter(([key]) => !RESERVED_ENV_KEYS.has(key))
    .map(([key, value]) => [`process.env.${key}`, JSON.stringify(process.env[key] ?? value)]),
);

export default {
  entry: './src/index.tsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.[contenthash].js',
    publicPath,
    clean: true,
  },
  devServer: {
    static: './dist',
    port: 3000,
    hot: true,
    open: true,
    // Serve index.html for any unmatched path so client-side routes
    // (e.g. /about) survive a direct load or refresh in dev. Production
    // mirrors this via the deploy workflow's 404.html fallback.
    historyApiFallback: true,
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
                // css-loader v7 changed namedExport default to true. The app uses
                // `import styles from '...'` everywhere, so we opt back into the
                // default-export shape. Without this, `styles.container` becomes
                // `undefined.container` at runtime.
                namedExport: false,
                exportLocalsConvention: 'as-is',
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
    // Inline PUBLIC_PATH into the bundle so React code can read it at
    // runtime — react-router needs the subpath as `basename` to route
    // correctly under GitHub Pages's /<repo>/ project-site URL.
    new webpack.DefinePlugin({
      ...inlinedEnv,
      'process.env.PUBLIC_PATH': JSON.stringify(publicPath),
    }),
    !isDevelopment && new MiniCssExtractPlugin({ filename: '[name].[contenthash].css' }),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
};
