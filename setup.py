import os
from setuptools import setup, PackageFinder


# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


version_info = {
    'major': 3,
    'minor': 0,
    'micro': 8,
    'releaselevel': 'final',
    'serial': 0
}


def get_version(release_level=True):
    """
    Return the formatted version information
    """
    vers = ["%(major)i.%(minor)i.%(micro)i" % version_info]
    if release_level and version_info['releaselevel'] != 'final':
        vers.append('%(releaselevel)s%(serial)i' % version_info)
    return ''.join(vers)


def get_readme():
    with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
        return readme.read()


__version__ = get_version()


class MonoRepoPackageFinder(PackageFinder):
    """Find python packages within repo"""

    @staticmethod
    def _looks_like_package(path):
        """Does a directory look like a package?"""
        return os.path.isfile(os.path.join(path, '__init__.py'))

    @staticmethod
    def _looks_like_sub_repo(path):
        """Does a directory look like a package?"""
        return os.path.isfile(os.path.join(path, 'setup.py'))

    @classmethod
    def _find_packages_iter(cls, where, exclude, include):
        """
        All the packages found in 'where' that pass the 'include' filter, but
        not the 'exclude' filter.
        """
        for root, dirs, files in os.walk(where, followlinks=True):
            # Copy dirs to iterate over it, then empty dirs.
            all_dirs = dirs[:]
            dirs[:] = []

            for dir in all_dirs:
                full_path = os.path.join(root, dir)
                rel_path = os.path.relpath(full_path, where)
                # base_path =

                if cls._looks_like_sub_repo(full_path):
                    dirs.append(dir)
                    continue
                else:
                    package = rel_path.replace(os.path.sep, '.')
                    package = ".".join(rel_path.split(os.path.sep)[1:])

                # Skip directory trees that are not valid packages
                if ('.' in dir or not cls._looks_like_package(full_path)):
                    continue
                # Should this package be included?
                if include(package) and not exclude(package):
                    yield package

                # Keep searching subdirectories, as there may be more packages
                # down there, even if the parent was excluded.
                dirs.append(dir)

    @classmethod
    def find_dirs(cls, where='.', exclude=(), include=('*',)):
        from distutils.util import convert_path
        x= dict(cls._find_packages_dirs_iter(
            convert_path(where),
            cls._build_filter('ez_setup', '*__pycache__', *exclude),
            cls._build_filter(*include)))
        return(x)

    @classmethod
    def _find_packages_dirs_iter(cls, where, exclude, include):
        """
        All the packages found in 'where' that pass the 'include' filter, but
        not the 'exclude' filter.
        """
        for root, dirs, files in os.walk(where, followlinks=True):
            # Copy dirs to iterate over it, then empty dirs.
            all_dirs = dirs[:]
            dirs[:] = []

            for dir in all_dirs:
                full_path = os.path.join(root, dir)
                rel_path = os.path.relpath(full_path, where)

                if cls._looks_like_sub_repo(full_path):
                    dirs.append(dir)
                    continue
                else:
                    package = ".".join(rel_path.split(os.path.sep)[1:])

                # Skip directory trees that are not valid packages
                if ('.' in dir or not cls._looks_like_package(full_path)):
                    continue
                # Should this package be included?
                if include(package) and not exclude(package):
                    yield (package, full_path)

                # Keep searching subdirectories, as there may be more packages
                # down there, even if the parent was excluded.
                # dirs.append(dir)

    @classmethod
    def fetch_requirements(cls, where=""):
        return list(cls._fetch_requirements_iter(where))

    @classmethod
    def _fetch_requirements_iter(cls, where=""):
        this_dir = os.path.dirname(os.path.abspath(__file__))
        py_path = os.path.join(this_dir, where)
        reqs = []
        for d in os.listdir(py_path):
            if os.path.isdir(os.path.join(py_path, d)):
                setup_py_path = os.path.join(py_path, d, "setup.py")
                if os.path.isfile(os.path.join(setup_py_path)):
                    with open(setup_py_path, "r") as f:
                        import ast
                        t = compile(f.read(), setup_py_path, 'exec', ast.PyCF_ONLY_AST)
                        for node in t.body:
                            if isinstance(node, ast.Expr):
                                c = node.value
                                for k in getattr(c, "keywords", []):
                                    if k.arg == "install_requires" and isinstance(k.value, ast.List):
                                        v = ast.literal_eval(k.value)
                                        for v in ast.literal_eval(k.value):
                                            yield(v)
                                        continue
                            else:
                                pass


setup(
    name="aristotle-metadata-registry",
    version=__version__,
    packages=MonoRepoPackageFinder.find("python"),
    package_dir=MonoRepoPackageFinder.find_dirs("python"),
    include_package_data=True,
    license='Aristotle-MDR Modified BSD Licence',
    description='Aristotle-MDR is an open-source metadata registry as laid out by the requirements of the IEC/ISO 11179:2013 specification.',
    long_description=get_readme(),
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
        'Intended Audience :: Developers',

        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=MonoRepoPackageFinder.fetch_requirements("python"),
    tests_require=['tox'],
    entry_points={
        'console_scripts': ['aristotle-installer=easy_installer.install:main']
    },
)
