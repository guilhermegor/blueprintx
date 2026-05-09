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
    new HtmlWebpackPlugin({
      template: './public/index.html',
      filename: 'index.html',
    }),
    new ModuleFederationPlugin({
      name: '__APP_NAME__',
      filename: 'remoteEntry.js',
      exposes: {
        './example': './src/capabilities/example/index.ts',
      },
      remotes: {},
      shared: {
        react:       { singleton: true, requiredVersion: `^${reactVersion}` },
        'react-dom': { singleton: true, requiredVersion: `^${reactVersion}` },
      },
    }),
    !isDevelopment && new MiniCssExtractPlugin({ filename: '[name].[contenthash].css' }),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
};
