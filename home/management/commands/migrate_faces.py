from django.core.management.base import BaseCommand
from home.models import Profile

class Command(BaseCommand):
    help = 'Migrates existing users by setting their current PFP as verification face'

    def handle(self, *args, **options):
        profiles = Profile.objects.filter(is_face_verified=False).exclude(profile_pic='')
        count = 0
        for p in profiles:
            if p.profile_pic and ('http' in p.profile_pic or 'https' in p.profile_pic):
                p.verification_image = p.profile_pic
                p.is_face_verified = True
                p.save()
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully migrated {count} profiles.'))
