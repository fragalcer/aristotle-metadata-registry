HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack_elasticsearch.elasticsearch5.Elasticsearch5SearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'haystack',
        'KWARGS': {
            'http_auth': 'elastic:changeme'
        }
    },
}
