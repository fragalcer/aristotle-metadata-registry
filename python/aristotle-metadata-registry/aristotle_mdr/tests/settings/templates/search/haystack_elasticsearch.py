HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack_elasticsearch.elasticsearch5.Elasticsearch5SearchEngine',
        'URL': 'http://elasticsearch:9200',
        'INDEX_NAME': 'test_index',
        'INCLUDE_SPELLING': True,
        'KWARGS': {
            'http_auth': 'elastic:changeme'
                }
            }
        }

