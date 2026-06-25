from django.core.management.base import BaseCommand
from home.models import Profile, Confession, RoomListing, RoomRequest, Event
from home.campus_config import get_campus_by_alias

MODELS_FIELDS = [
    (Profile, "campus"),
    (Profile, "pref_campus"),
    (Confession, "campus"),
    (RoomListing, "campus"),
    (RoomRequest, "campus"),
    (Event, "campus"),
]


class Command(BaseCommand):
    help = "Migrates old campus DB values to canonical names from campus_config"

    def handle(self, *args, **options):
        total_updated = 0
        total_skipped = 0
        total_unresolved = 0
        unresolved_examples = []

        for model, field in MODELS_FIELDS:
            updated = 0
            skipped = 0
            unresolved = 0
            for obj in model.objects.all():
                val = getattr(obj, field)
                if not val:
                    continue
                if field == "pref_campus" and val.lower() == "any":
                    continue
                campus = get_campus_by_alias(val)
                if campus is None:
                    if len(unresolved_examples) < 5:
                        unresolved_examples.append(f"{model.__name__}.{field}: '{val}'")
                    unresolved += 1
                    continue
                canonical = campus["name"]
                if val == canonical:
                    skipped += 1
                    continue
                setattr(obj, field, canonical)
                obj.save(update_fields=[field])
                updated += 1

            if updated or unresolved:
                self.stdout.write(
                    f"  {model.__name__}.{field}: {updated} updated, {skipped} already canonical, {unresolved} unresolved"
                )
            total_updated += updated
            total_skipped += skipped
            total_unresolved += unresolved

        self.stdout.write(self.style.SUCCESS(f"Done! {total_updated} records updated."))
        if total_unresolved:
            self.stdout.write(
                self.style.WARNING(
                    f"{total_unresolved} records could not be resolved. "
                    f"First few: {', '.join(unresolved_examples)}"
                )
            )
