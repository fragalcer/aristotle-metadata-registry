const path = require('path')
const webpack = require('webpack')
const glob = require('glob')
const entry = require('webpack-glob-entry')
const CleanWebpackPlugin = require('clean-webpack-plugin');
const VueLoaderPlugin = require('vue-loader/lib/plugin')

module.exports = {
  entry: entry('./src/pages/*.js'),
  output: {
    filename: '[name].js',
    path: path.resolve(__dirname, 'dist/bundles'),
  },
  module: {
    rules: [
      {
        // Expose jquery outside bundle
        // Wont need this when using only bundle code
        test: require.resolve('jquery'),
        use: [{
          loader: 'expose-loader',
          options: '$'
        },{
          loader: 'expose-loader',
          options: 'jQuery'
        }]
      },
      {
        // Load .vue files with vue-loader
        test: /\.vue$/,
        use: 'vue-loader'
      }
    ]
  },
  plugins: [
    // Clean dist folder before builds
    new CleanWebpackPlugin(['dist']),
    new VueLoaderPlugin(),
    new webpack.ProvidePlugin({
      // Provide $ and jQuery to scripts, no need to import
      $: "jquery",
      jQuery: "jquery"
    })
  ],
  optimization: {
    splitChunks: {
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/](jquery|bootstrap)[\\/]/,
          name: 'vendor',
          chunks: 'all',
        }
      }
    }
  },
  resolve: {
    alias: {
      // Use compiler version of vue
      'vue$': 'vue/dist/vue.esm.js'
    }
  }
};
