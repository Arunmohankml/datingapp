from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Profile, Question, Option, UserAnswer, RoomRequest, Conversation, DailyQuestion, QuestionOption, QuestionVote, QuestionSuggestion, KnotPost, KnotComment, KnotReport, CommunityMember, CommunityMute


# ✅ Inline options inside Question admin
class OptionInline(admin.TabularInline):  # or admin.StackedInline
    model = Option
    extra = 2  # show 2 blank options by default


class ProfileAdminForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        verify = {'verification_image', 'verification_status', 'is_face_verified'}
        for field_name in self.fields:
            if field_name not in verify:
                self.fields[field_name].required = False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ('name', 'user', 'age', 'gender', 'campus', 'clg_year', 'verification_status', 'is_face_verified')
    search_fields = ('name', 'user__username', 'campus')
    list_filter = ('campus', 'gender', 'clg_year', 'looking_for', 'verification_status')
    fieldsets = (
        ('Verification', {
            'fields': ('verification_image', 'verification_status', 'is_face_verified'),
            'classes': ('wide',),
        }),
        ('Profile Info', {
            'fields': ('name', 'gender', 'profile_pic', 'age', 'clg_year', 'campus', 'course',
                       'living_place', 'native_place', 'languages', 'mother_tongues',
                       'bio', 'liked_songs', 'liked_movies', 'fav_shows', 'interest_tags',
                       'looking_for', 'pref_age_min', 'pref_age_max', 'pref_gender',
                       'pref_languages', 'pref_campus', 'is_banned', 'is_discoverable'),
        }),
    )


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


@admin.register(RoomRequest)
class RoomRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'campus', 'min_rent', 'max_rent', 'preferred_room_type', 'is_active', 'created_at')
    list_filter = ('campus', 'preferred_room_type', 'is_active')
    search_fields = ('title', 'user__username', 'looking_near')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('user1', 'user2', 'source', 'listing_id', 'request_id', 'created_at')
    list_filter = ('source',)
    search_fields = ('user1__username', 'user2__username')


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2


@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'date', 'is_admin_question', 'created_by', 'vote_count')
    list_filter = ('is_admin_question', 'date')
    search_fields = ('question_text',)
    inlines = [QuestionOptionInline]

    def vote_count(self, obj):
        return QuestionVote.objects.filter(option__question=obj).count()
    vote_count.short_description = 'Votes'


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'order', 'vote_count')
    list_filter = ('question__date',)

    def vote_count(self, obj):
        return obj.votes.count()
    vote_count.short_description = 'Votes'


@admin.register(QuestionSuggestion)
class QuestionSuggestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'suggested_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('question_text', 'suggested_by__username')
    actions = ['approve_suggestion', 'reject_suggestion']

    def approve_suggestion(self, request, queryset):
        queryset.update(status='approved')
    approve_suggestion.short_description = 'Mark selected as Approved'

    def reject_suggestion(self, request, queryset):
        queryset.update(status='rejected')
    reject_suggestion.short_description = 'Mark selected as Rejected'


@admin.register(KnotPost)
class KnotPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'college', 'campus', 'category', 'created_at')
    list_filter = ('college', 'campus', 'category', 'created_at')
    search_fields = ('title', 'content', 'user__username', 'user__email')


@admin.register(KnotComment)
class KnotCommentAdmin(admin.ModelAdmin):
    list_display = ('short_content', 'user', 'post', 'parent', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('content', 'user__username', 'post__title')

    @admin.display(description='Comment')
    def short_content(self, obj):
        return str(obj)[:80]


@admin.register(KnotReport)
class KnotReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'reason', 'post', 'comment', 'created_at')
    list_filter = ('reason', 'created_at')
    search_fields = ('reporter__username', 'details', 'post__title', 'comment__content')


@admin.register(QuestionVote)
class QuestionVoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'option', 'voted_at')
    list_filter = ('option__question', 'voted_at')


@admin.register(CommunityMember)
class CommunityMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'joined_at')
    list_filter = ('community', 'joined_at')
    search_fields = ('user__username', 'community__name')


@admin.register(CommunityMute)
class CommunityMuteAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'is_muted')
    list_filter = ('community', 'is_muted')

