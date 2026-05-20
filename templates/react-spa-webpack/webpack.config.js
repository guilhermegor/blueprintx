import ReactRefreshWebpackPlugin from '@pmmmwh/react-refresh-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import MiniCssExtractPlugin from 'mini-css-extract-plugin';
import path from 'path';
import { fileURLToPath } from 'url';
import webpack from 'webpack';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isDevelopment = process.env.NODE_ENV !== 'production';

// GitHub Pages serves project sites under `/<repo-name>/`. Set
// PUBLIC_PATH (e.g. via the deploy workflow) to point webpack at the
// right subpath. Default `/` works for local dev and root-served hosts.
const publicPath = process.env.PUBLIC_PATH || '/';

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
      'process.env.PUBLIC_PATH': JSON.stringify(publicPath),
    }),
    !isDevelopment && new MiniCssExtractPlugin({ filename: '[name].[contenthash].css' }),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
};
