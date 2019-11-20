from django.core.management.base import BaseCommand
from django.apps import apps

from aristotle_mdr.utils.cache import recache_types


class Command(BaseCommand):
    args = ''
    help = ''

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--id",
            default=None,
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Do all',
        )

    def handle(self, *args, **options):
        from aristotle_glossary.models import reindex_metadata_item
        from aristotle_mdr.models import _concept

        if options['id']:
            print('Updating glossary index for object...')

            instance = _concept.objects.get(pk=options['id']).item
            glossary_set = reindex_metadata_item(instance)
            related_list = list(glossary_set.values_list("pk", flat=True))

            print(f"item {instance} is now linked to items {related_list}")
        elif options['all']:
            print("Processing all")
            # print(".", end="", flush=True)
            total = _concept.objects.count()
            for i, instance in enumerate(_concept.objects.all().select_subclasses()):
                if i % 1000 == 0:
                    percent = int(i / total * 100)
                    print('\r' + (' ' * 70), end="", flush=True)
                    print(f'\r{percent}% ', end="", flush=True)
                if i % 25 == 0:
                    print(".", end="", flush=True)
                reindex_metadata_item(instance)
            print('\r' + (' ' * 70), end="", flush=True)
            print(f'\r100% ... done!')
