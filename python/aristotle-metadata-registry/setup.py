import os
from setuptools import setup, find_packages
from aristotle_mdr import get_version

VERSION = get_version()

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='aristotle-metadata-registry',
    version=VERSION,
    packages=find_packages(),
    include_package_data=True,
    license='Aristotle-MDR Modified BSD Licence',
    description='Aristotle-MDR is an open-source metadata registry as laid out by the requirements of the IEC/ISO 11179:2013 specification.',
    long_description=README,
    url='https://github.com/aristotle-mdr/aristotle-metadata-registry',
    author='Samuel Spencer',
    author_email='sam@aristotlemetadata.com',
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',

        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        "Django~=2.2.0",
        'six',  # Setuptools > 36 doesn't install this by default
        'pytz',
        'pyyaml',
        'dj-database-url',

        'django-model-utils>=2.3.1',
        'django-notifications-hq==1.4',
        'django-braces',
        'docutils',

        # Search requirements
        'django-haystack~=2.8.0',

        # Rich text editors
        'django-ckeditor>=5.3.0',

        # Image manipulation
        'pillow',

        # Revision control
        "django-reversion>=2.0,<2.1",
        'django-reversion-compare~=0.8.0',
        'diff-match-patch',

        # Fancy UI stuff
        'django-autocomplete-light>=3.0.0,<3.3.0',
        'django-bootstrap3>8.0,<9.0',
        'django-bootstrap3-datetimepicker-2>=2.5.0',

        'django-formtools>=2.0',

        # required for help, but thats required
        'django-autoslug',

        # This is only needed for Migration 0024 once this is squashed, remove this dependency
        'sqlparse',

        'django-organizations',

        # Improved User Model
        'django-improved-user>=1.0.0',

        # File upload
        'django-constrainedfilefield',

        # File type checking
        'python-magic>=0.4.2'

        # Generic json field
        'jsonfield',

        # User sessions
        'django-user-sessions',
        'geoip2',

        # Vendored package
        # 'django-missing', 

        # Webpack loading
        'django-webpack-loader',

        'attrs',
        'jsonschema',

        # Webpack loading
        'django-webpack-loader',

        # Storages
        'django-storages',

        # Sanitization
        'bleach',

        # File conversion
        'pypandoc',

        # Html to pdf
        'weasyprint',
        'pdfkit',

        # Pdf toolkit
        'PyPDF2',

        # Bulk updates
        'django-bulk-update',
        'django-mptt'
    ],

)
