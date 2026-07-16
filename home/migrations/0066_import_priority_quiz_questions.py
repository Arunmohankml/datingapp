from django.db import migrations, models

from home.migrations.data.quiz_questions_20260716 import QUESTIONS


def _normalise_question_text(text):
    return ' '.join(text.split()).casefold()


def import_priority_questions(apps, schema_editor):
    Question = apps.get_model('home', 'Question')
    Option = apps.get_model('home', 'Option')

    existing_by_text = {
        _normalise_question_text(question.text): question
        for question in Question.objects.all().only('id', 'text', 'is_priority')
    }
    existing_to_promote = []
    questions_to_create = []
    options_by_text = {}

    for question_text, option_texts in QUESTIONS:
        key = _normalise_question_text(question_text)
        existing = existing_by_text.get(key)
        if existing is not None:
            if not existing.is_priority:
                existing_to_promote.append(existing.id)
            continue

        question = Question(text=question_text, is_priority=True)
        questions_to_create.append(question)
        options_by_text[key] = option_texts
        existing_by_text[key] = question

    if existing_to_promote:
        Question.objects.filter(id__in=existing_to_promote).update(is_priority=True)

    if not questions_to_create:
        return

    Question.objects.bulk_create(questions_to_create, batch_size=250)
    option_objects = []
    for question in questions_to_create:
        option_texts = options_by_text[_normalise_question_text(question.text)]
        option_objects.extend(
            Option(question=question, text=option_text, weight=float(index))
            for index, option_text in enumerate(option_texts, start=1)
        )
    Option.objects.bulk_create(option_objects, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0065_drop_stale_fcmtoken_device_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='is_priority',
            field=models.BooleanField(db_index=True, default=False),
        ),
        # Intentionally keep imported questions when reversing so answers are
        # never cascaded away for users who have already received this set.
        migrations.RunPython(import_priority_questions, migrations.RunPython.noop),
    ]
