# SRM Match - High-End Dating App

## Recent Improvements
- **Skip/Pass Functionality**: You can now skip matches that don't vibe with you. This will prevent them from appearing in your feed again.
- **Improved Feed Filtering**: Candidates you've liked or skipped are automatically filtered out of your feed and discovery cards.
- **Discovery Mode**: Answer more questions to refine your match percentage and find better vibes.

## Google Login Troubleshooting (401 Unauthorized)

If you see a `401 Unauthorized` error when logging in via Google on your Vercel deployment, please follow these steps:

### 1. Firebase Console Settings
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Select your project: **datingapp-636fa**.
3. Go to **Authentication** -> **Settings** -> **Authorized Domains**.
4. Click **Add Domain** and enter: `datingapp-vert.vercel.app`.

### 2. Google Cloud Console Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Find the OAuth 2.0 Client ID used by Firebase (check `login.html` for the `client_id`).
3. Under **Authorized JavaScript Origins**, add: `https://datingapp-vert.vercel.app`.
4. Under **Authorized Redirect URIs**, ensure your Firebase Auth handler is present: `https://datingapp-636fa.firebaseapp.com/__/auth/handler`.

## Database Migrations
Since the `MatchRequest` model was updated to include a `skipped` status, you must apply the migrations in your production database:
```bash
python manage.py makemigrations home
python manage.py migrate
```
If using Vercel, ensuring your `vercel.json` or build settings includes a migration command is recommended.
