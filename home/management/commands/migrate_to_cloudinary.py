import os
import requests
from io import BytesIO
from django.core.management.base import BaseCommand
from home.models import Profile, ProfileImage
from home.cloudinary_utils import upload_to_cloudinary

class Command(BaseCommand):
    help = 'Migrate existing Supabase/external images to Cloudinary'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting migration to Cloudinary...'))

        stats = {
            'total': 0,
            'migrated': 0,
            'skipped': 0,
            'failed': 0
        }

        # 1. Profile Pictures
        profiles = Profile.objects.exclude(profile_pic__isnull=True).exclude(profile_pic='')
        for profile in profiles:
            stats['total'] += 1
            if 'cloudinary.com' in profile.profile_pic:
                stats['skipped'] += 1
                continue

            self.stdout.write(f"Migrating PFP for user {profile.user.id} ({profile.name})...")
            new_url = self.migrate_image(profile.profile_pic, f"srm_match/profile_pics", f"pfp_{profile.user.id}")
            if new_url:
                profile.profile_pic = new_url
                profile.save()
                stats['migrated'] += 1
                self.stdout.write(self.style.SUCCESS(f"  -> SUCCESS: {new_url}"))
            else:
                stats['failed'] += 1

        # 2. Verification Images
        verif_profiles = Profile.objects.exclude(verification_image__isnull=True).exclude(verification_image='')
        for profile in verif_profiles:
            stats['total'] += 1
            if 'cloudinary.com' in profile.verification_image:
                stats['skipped'] += 1
                continue

            self.stdout.write(f"Migrating Verification for user {profile.user.id}...")
            new_url = self.migrate_image(profile.verification_image, f"srm_match/verification_images", f"verif_{profile.user.id}")
            if new_url:
                profile.verification_image = new_url
                profile.save()
                stats['migrated'] += 1
                self.stdout.write(self.style.SUCCESS(f"  -> SUCCESS: {new_url}"))
            else:
                stats['failed'] += 1

        # 3. Gallery Images
        gallery_images = ProfileImage.objects.all()
        for gimg in gallery_images:
            stats['total'] += 1
            if 'cloudinary.com' in gimg.image:
                stats['skipped'] += 1
                continue

            self.stdout.write(f"Migrating Gallery Image {gimg.id} for profile {gimg.profile.id}...")
            new_url = self.migrate_image(gimg.image, f"srm_match/gallery_images", f"gallery_{gimg.id}")
            if new_url:
                gimg.image = new_url
                gimg.save()
                stats['migrated'] += 1
                self.stdout.write(self.style.SUCCESS(f"  -> SUCCESS: {new_url}"))
            else:
                stats['failed'] += 1

        self.stdout.write(self.style.SUCCESS('\nMigration Summary:'))
        self.stdout.write(f"Total processed: {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"Successfully migrated: {stats['migrated']}"))
        self.stdout.write(f"Skipped (already on Cloudinary): {stats['skipped']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed uploads: {stats['failed']}"))
        else:
            self.stdout.write(self.style.SUCCESS("Failed uploads: 0"))

    def migrate_image(self, old_url, folder, public_id):
        try:
            response = requests.get(old_url, timeout=15)
            if response.status_code == 200:
                img_file = BytesIO(response.content)
                img_file.name = old_url.split('/')[-1] # give it a name
                return upload_to_cloudinary(img_file, folder=folder, public_id=public_id)
            else:
                self.stdout.write(self.style.ERROR(f"  -> FAILED: Status {response.status_code} for {old_url}"))
                return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  -> ERROR: {str(e)}"))
            return None
