from django.urls import path
from . import views
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("api/verify-token/", views.api_verify_token, name="api_verify_token"),
    path("", views.home, name="home"),
    path("setup/", views.setup, name="setup"),
    path("complete_profile/", views.complete_profile, name="complete_profile"),
    path("check_match/", views.check_match, name="check_match"),
    path("answer_question/<int:question_id>/", views.answer_question, name="answer_question"),
    path("match/send/<int:receiver_id>/", views.send_match_request, name="send_match_request"),
    path("match/skip/<int:receiver_id>/", views.skip_match, name="skip_match"),
    path("match/accept/<int:req_id>/", views.accept_match, name="accept_match"),
    path("match/reject/<int:req_id>/", views.reject_match, name="reject_match"),
    path("connections/", views.connections_view, name="connections"),
    path("chat/<int:partner_id>/", views.chat_view, name="chat_view"),
    path("chats/", views.chat_list_view, name="chat_list"),
    path("api/chat/<int:partner_id>/", views.chat_api_messages, name="chat_api_messages"),
]