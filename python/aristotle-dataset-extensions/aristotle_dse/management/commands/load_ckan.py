import requests
import json
import re
from django.db.models import Q
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from django.utils.text import slugify
from aristotle_dse import models as DSE
from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.identifiers import models as MDR_ID


def super_intelligent_hueristics(resource,data):
    data_list = zip(*(data[:10])) # pivot it

    from aristotle_mdr.models import DataElement, ValueDomain

    data_elements = []
    for data in data_list:
        name = data[0].strip()
        data = [d.strip() for d in data[1:]]
        max_length = len(max(data, key=len))

        queries = Q()
        splitter = max([(len(name.split(i)),i) for i in ' -_'])[1]
        tokens = name.split(splitter)
        if len(tokens) == 1:
            queries &= Q(name__iexact=tokens[0])
        else:
            for token in tokens:
                token = token.strip()
                queries &= Q(name__icontains=token)
        de = DataElement.objects.filter(queries) #.filter(Q(valueDomain__maximum_length__gte=max_length) | Q(valueDomain=None))
        if not de.exists():
            print(name)
            count = -1
            vd = ValueDomain.objects.create(name="Value Domain for %s"%name, description="Auto-generated", maximum_length=max_length)
            de = DataElement.objects.create(name=name,definition="Auto-generated data element for resource '%s'"%resource['name'],valueDomain=vd)

            if 'date' in name.lower() or re.search(r'(_?|\b)dt(\b|_)?', name):
                # If it has a dt on its own or surrounded by a word boundary or underscore
                # Probably a date/time, lets hope so
                vd.data_type=MDR.DataType.objects.filter(name__icontains='date').first()
                vd.save()
            else:
                try:
                    for i in data[1:]:
                        int(i)
                    # Yay! It succeeded.
                    vd.data_type=MDR.DataType.objects.filter(name__icontains='number').first()
                    vd.save()
                except:
                    vd.data_type=MDR.DataType.objects.filter(name__icontains='string').first()
                    vd.save()

            #elif set(data[1:]) < 15:


        else:
            count = de.all().count()
            de = de.first()
            print(" %s is like %s and %s others" %(name, de.name, count-1))
        data_elements.append([name, de, count])

    return data_elements


class Command(BaseCommand):
    args = 'ckan_api_link catalog_url'
    help = 'Mines the given CKAN instance for data catalog records.'

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('ckan_api_link', type=str)
        parser.add_argument('catalog_url', type=str)
        parser.add_argument('--catalog_name', type=str)
        parser.add_argument('--catalog_definition', type=str)
        parser.add_argument(
            '-D',
            '--days_to_fetch',
            dest='days_to_fetch',
            default=False,
            help='Specify the number of days to get.',
        )
        parser.add_argument(
            '-A',
            '--all',
            action='store_true',
            dest='get_all',
            default=False,
            help='Fetch everything',
        )
        parser.add_argument(
            '-f',
            '--force_reload',
            action='store_true',
            dest='force_reload',
            default=False,
            help='Force reload of previously downloaded files',
        )
        parser.add_argument(
            '-V',
            '--verify_ssl',
            action='store_false',
            dest='verify_ssl',
            default=True,
            help='Disables SSL verification',
        )
        parser.add_argument(
            '-q',
            '--query',
            dest='query',
            default=None,
            help='Query string.',
        )

    def vprint(self, *args, **kwargs):
        verbosity = kwargs.pop('verbosity', 0) or kwargs.pop('v', 0)
        std = kwargs.pop('std', 'out')

        if self.verbosity >= verbosity:
            out = self.stdout
            if std == 'err':
                self.stderr
            args = " ".join(map(str, args))

            out.write(args, **kwargs)

    def handle(self, *args, **options):
        self.api_base = options['ckan_api_link']
        self.catalog_url = options['catalog_url']
        self.get_all = options['get_all']
        self.days_to_fetch = options['days_to_fetch']
        self.verbosity = options['verbosity']
        self.verify_ssl = options['verify_ssl']
        self.force_reload = options['force_reload']
        self.query = options['query']

        if not (self.get_all or self.days_to_fetch or self.query):
            raise CommandError("Specify the number of days to fetch, enter a query or request to get all")

        self.org, c = MDR.Organization.objects.get_or_create(
            uri = self.catalog_url,
            defaults = {
                'name':self.catalog_url,
                'definition':'Auto-created Organization for %s' % self.catalog_url
            }
        )
        catalog_details = {
            'name':self.catalog_url,
            'definition':'Auto-created Catalog for %s' % self.catalog_url,
            'origin_URI': self.catalog_url,
            'publisher': self.org
        }
        if options.get('catalog_name', None):
            catalog_details['name'] = options['catalog_name']
        if options.get('catalog_definition', None):
            catalog_details['definition'] = options['catalog_definition']

        self.catalog, c = DSE.DataCatalog.objects.update_or_create(
            homepage = self.catalog_url,
            defaults = catalog_details
            )
        self.catalog_namespace, c = MDR_ID.Namespace.objects.get_or_create(
            naming_authority = self.org,
            shorthand_prefix = slugify(self.catalog_url)
        )

        gotten = self.load_ckan(force_reload=self.force_reload)
        self.vprint("Successfully loaded %s records" % gotten)

    def load_ckan_all(self, force_reload=True):
        ckan = requests.get(self.api_base+'action/package_list', data={})
        if ckan.status_code != 200:
            self.vprint("Mining failed --- ", ckan.text)
            return -1
        ckan = json.loads(ckan.text)

        for result in ckan['result']:
            dataset = self.get_dataset(name)
            if dataset:
                dataset_exists = DSE.Dataset.objects.filter(
                    identifiers__namespace__naming_authority=self.catalog.publisher,
                    identifiers__identifier=dataset['name'],
                    catalog=self.catalog
                ).exists()
                if not dataset_exists or force_reload:
                    self.load_dataset(dataset)
                else:
                    self.vprint("   skipping load of ", dataset['name'], v=1)

    def load_ckan_some(self, force_reload=True):
        if not self.query:
            now = datetime.datetime.now()
            then = now - datetime.timedelta(days=int(self.days_to_fetch))
            query = "metadata_modified:[%sZ TO %sZ]" % (
                then.isoformat(),
                now.isoformat(),
            )
            self.vprint("SOLR Time query -- %s" %(query), v=3)
        else:
            query = self.query
        ckan = requests.get(
            self.api_base+'action/package_search',
            params={
                'q': query
            },
            verify=self.verify_ssl
        )

        if ckan.status_code != 200:
            self.vprint("Mining failed %s --- \n %s" %(self.api_base, ckan.text))
            return -1
        ckan = json.loads(ckan.text)
        num_results = int(ckan['result']['count'])

        self.vprint("Found this many results -- %s" %(num_results),v = 1)
        num_per_query = 25
        for offset in range(0,num_results, num_per_query):
            ckan = requests.get(
                self.api_base+'action/package_search',
                params={
                    'q': query,
                    'start': offset,
                    'rows': num_per_query
                },
                verify=self.verify_ssl
            )
            if ckan.status_code != 200:
                self.vprint("    Chunk failed failed %s --- offset: %s" %(self.api_base, offset))
                continue
            ckan = json.loads(ckan.text)

            for dataset in ckan['result']['results']:
                dataset_name=dataset['name']
                dataset_exists = DSE.Dataset.objects.filter(
                    identifiers__namespace__naming_authority=self.catalog.publisher,
                    identifiers__identifier=dataset_name,
                    catalog=self.catalog
                ).exists()
                if not dataset_exists or force_reload:
                    self.load_dataset(dataset)
                else:
                    self.vprint("   skipping load of ", dataset_name, v=1)

    def load_ckan(self, force_reload=True):
        if self.get_all:
            return self.load_ckan_all(force_reload)
        else:
            return self.load_ckan_some(force_reload)

        self.vprint("got ckan", v=1)
        self.vprint(ckan.keys(), v=1)

    def get_dataset(self, uuid):
        dataset = requests.get(
            self.api_base+'action/package_show',
            params={'id':uuid},
            verify=self.verify_ssl,
            timeout=5
        )
        if dataset.status_code != 200:
            print("Dataset failed --- ", dataset.text)
            return False
        dataset = json.loads(dataset.text)
        dataset = dataset['result']
        return dataset

    def get_resource(self, uuid):
        dataset = requests.get(
            self.api_base+'action/resource_show',
            params={'id':uuid},
            verify=self.verify_ssl,
            timeout=5
        )
        if dataset.status_code != 200:
            print("Dataset failed --- ", dataset.text)
            return False
        dataset = json.loads(dataset.text)
        dataset = dataset['result']
        return dataset

    def load_dataset(self, dataset):
        print("loading - ", dataset['name'])
        try:
            with transaction.atomic():
                org = dataset.get('organization',None) or dataset.get('organisation',None)
                if org:
                    publishing_org,c = MDR.Organization.objects.update_or_create(
                        name=org['title'],
                        defaults = {'definition': org['description']},
                    )
                    if c:
                        self.vprint('made Organization : ', publishing_org.name, v=1)
                else:
                    publishing_org = None
                    print("no organi[sz]ation for dataset - ", dataset['name'])
                ds_checks = DSE.Dataset.objects.filter(
                    identifiers__namespace__naming_authority=self.catalog.publisher,
                    identifiers__identifier=dataset['name'],
                    catalog = self.catalog
                )
                if ds_checks.count() == 1:
                    ds = ds_checks.first()
                    self.vprint('Updating Dataset with ID %s in Catalog %s' % (dataset['name'], self.catalog), v=1)
                elif ds_checks.count() > 1:
                    self.vprint('Search for matching datasets return more than 1! It returned %s' % checks.count(), v=1)
                    return
                else:
                    ds = DSE.Dataset(
                        catalog = self.catalog
                    )
                ds.name = dataset['title']
                ds.version = dataset.get('version','') or ds.version
                ds.definition = dataset.get('notes','') or ds.definition
                ds.spatial = dataset.get('spatial_coverage','') or ds.spatial
                ds.temporal = dataset.get('temporal_coverage_from','') or ds.temporal
                ds.comments = dataset.get('notes','') or ds.comments

                ds.publisher = publishing_org or ds.publisher
                ds.contact_point = dataset.get('contact_point','') or ds.contact_point
                ds.frequency = dataset.get('update_freq','') or ds.frequency
                ds.origin_URI = "%s/dataset/%s" % (self.catalog_url, dataset['name'])

                ds.save()
                if ds_checks.count() == 0:
                    # Make identifier
                    MDR_ID.ScopedIdentifier.objects.get_or_create(
                        namespace = self.catalog_namespace,
                        concept = ds,
                        identifier = dataset['name']
                    )

                for resource in dataset['resources']:
                    dd_checks = DSE.Distribution.objects.filter(
                        identifiers__namespace__naming_authority=self.catalog.publisher,
                        identifiers__identifier=resource['id'],
                    )
                    if dd_checks.count() == 1:
                        dd = dd_checks.first()
                    elif dd_checks.count() > 1:
                        self.vprint('Search for matching resources return more than 1! It returned %s' % dd_checks.count(), v=1)
                        continue
                    else:
                        dd = DSE.Distribution()

                    dd.dataset = ds
                    dd.name = resource.get('name', False) or dd.name or resource.get('description', False) or "No name"
                    dd.license = dataset.get('license_title','') or dd.license
                    dd.definition = resource.get('Description','') or resource.get('description','') or dd.definition or 'No description'
                    dd.access_URL = resource['url'] or dd.access_URL
                    dd.download_URL = resource['url'] or dd.download_URL
                    ds.origin_URI = "%s/dataset/%s/resource/%s" % (self.catalog_url, dataset['name'], dd.name)
                    #dd.order = resource['position'] or dd.order
                    dd.format_type = resource['format'] or dd.format_type

                    dd.save()
                    if dd_checks.count() == 0:
                        # Make identifier
                        MDR_ID.ScopedIdentifier.objects.get_or_create(
                            namespace = self.catalog_namespace,
                            concept = dd,
                            identifier = resource['id']
                        )

                    # Get the file then process the columns!
                # if org:
                #     # We have an organisation, we can probably register it
                #     reg_date = map(int,dataset['metadata_modified'].split('T')[0].split('-')[0:3])
                #     ra.cascaded_register(
                #         item=ds,
                #         state=MDR.STATES.recorded,
                #         effective_date=datetime.date(*reg_date),
                #     )
        except KeyboardInterrupt:
            raise
        except:
            print("Everything just went bad - ", dataset['name'])
            raise
