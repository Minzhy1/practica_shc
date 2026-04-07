from django.urls import path
from tesonl import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_user, name='login_user'),
    path('register/', views.register_user, name='register_user'),
    path('logout/', views.logout_user, name='logout_user'),

    # Учитель
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('test/create/', views.create_test, name='create_test'),
    path('test/<int:test_id>/edit/', views.edit_test, name='edit_test'),
    path('test/<int:test_id>/add-question/', views.add_question_to_test, name='add_question_to_test'),
    path('test/<int:test_id>/remove-question/<int:question_id>/', views.remove_question_from_test,
         name='remove_question_from_test'),
    path('question/create/', views.create_question, name='create_question'),
    path('test/<int:test_id>/results/', views.test_results_for_teacher, name='test_results_for_teacher'),
    path('test/<int:test_id>/attempt/<int:attempt_id>/detail/', views.attempt_detail_for_teacher, name='attempt_detail_for_teacher'),

    # Ученик
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('test/<int:test_id>/take/', views.take_test, name='take_test'),
    path('attempt/<int:attempt_id>/result/', views.test_result, name='test_result'),

]