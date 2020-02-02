from model_utils import Choices

DOWNLOAD_KEY_PREFIX = 'download_res_key'

TIME_TO_DOWNLOAD = 60 * 60

FILE_FORMAT = {
    'csv-vd': 'csv',
    'pdf': 'pdf',
    'txt': 'txt'
}

REVERSION_FORMATS = {
    'json': 'v1',
    'aristotle_mdr_json': 'v2',
    'aristotle_mdr_json_uuid_compatible': 'v3',
}

visibility_permission_choices = Choices(
    (0, 'public', 'Public'),
    (1, 'auth', 'Authenticated'),
    (2, 'workgroup', 'Workgroup'),
    (10, 'administrators', 'Registry Administrators'),
)
