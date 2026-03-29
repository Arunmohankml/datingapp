from django.contrib import admin
from .models import Profile, Question, Option, UserAnswer


# ✅ Inline options inside Question admin
class OptionInline(admin.TabularInline):  # or admin.StackedInline
    model = Option
    extra = 2  # show 2 blank options by default


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'age', 'gender', 'campus', 'clg_year')
    search_fields = ('name', 'user__username', 'campus', 'branch')
    list_filter = ('campus', 'gender', 'clg_year', 'looking_for')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text",)
    inlines = [OptionInline]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("text", "question")


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "option")
    list_filter = ("question", "option", "user")
