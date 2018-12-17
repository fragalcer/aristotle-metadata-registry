const webpack = require('webpack')
const path = require('path')
const VueLoaderPlugin = require('vue-loader/lib/plugin')

var dev_wp_config = require('./webpack.dev.js')
delete dev_wp_config['entry']
delete dev_wp_config['output']
dev_wp_config['optimization'] = {minimize: false}

process.env.CHROME_BIN = require('puppeteer').executablePath()

module.exports = (config) => {
    config.set({
        frameworks: ['mocha'],
        browsers: ['ChromeHeadlessNoSandbox'],
        customLaunchers: {
            // Need this for travis container environment
            ChromeHeadlessNoSandbox: {
                base: 'ChromeHeadless',
                flags: ['--no-sandbox']
            }
        },
        reporters: ['mocha', 'coverage'],
        mochaReporter: {
            colors: {
                success: 'green',
                info: 'blue',
                warning: 'yellow',
                error: 'red'
            }
        },
        files: [
            // all files ending in "_test"
            { pattern: 'test/*_test.js', watched: false },
            { pattern: 'test/**/*_test.js', watched: false }
            // each file acts as entry point for the webpack configuration
        ],
        preprocessors: {
            // add webpack as preprocessor
            'test/*_test.js': [ 'webpack', 'sourcemap' ],
            'test/**/*_test.js': [ 'webpack', 'sourcemap' ]
        },
        webpack: {
            // karma watches the test entry points
            // (you don't need to specify the entry option)
            // webpack watches dependencies

            // webpack configuration
            devtool: 'inline-source-map',
            optimization: {
                minimize: false
            },
            module: {
                rules: [
                    {
                        // Load .vue files with vue-loader
                        test: /\.vue$/,
                        use: 'vue-loader'
                    },
                    {
                        test: /\.m?js$/,
                        exclude: /node_modules/,
                        use: [{
                            loader: 'babel-loader',
                            options: {
                                presets: ['@babel/preset-env'],
                                plugins: ['istanbul']
                            }
                        }]
                    },
                    {
                        test: /\.css$/,
                        use: [
                            'style-loader',
                            'css-loader'
                        ]
                    }
                ]
            },
            plugins: [
                new VueLoaderPlugin(),
                new webpack.ProvidePlugin({
                    // Provide $ and jQuery to scripts, no need to import
                    $: "jquery",
                    jQuery: "jquery"
                }),
            ],
            resolve: {
                alias: {
                    // Use compiler version of vue
                    'vue$': 'vue/dist/vue.esm.js',
                    'src': path.resolve(__dirname, 'src'),
                    '@': path.resolve(__dirname, 'src/components')
                }
            }
        },
        webpackMiddleware: {
            // webpack-dev-middleware configuration
            // i. e.
            stats: 'errors-only'
        }
    })
}
