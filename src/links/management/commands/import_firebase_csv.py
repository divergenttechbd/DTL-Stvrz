import csv
from django.core.management.base import BaseCommand
from links.models import Link

class Command(BaseCommand):
    help = "Import Firebase Dynamic Links CSV export"

    def add_arguments(self, parser):
        parser.add_argument('csvfile')

    def handle(self, *args, **options):
        path = options['csvfile']
        count = 0
        with open(path, newline='') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                short = row.get('shortLink') or row.get('Short Link') or row.get('short')
                long = row.get('longLink') or row.get('Long Link') or row.get('long')
                if not short or not long:
                    self.stdout.write(self.style.WARNING(f"Skipping row missing links: {row}"))
                    continue
                code = short.rstrip('/').split('/')[-1]
                obj, created = Link.objects.update_or_create(code=code, defaults={'target_url': long})
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {count} links"))
