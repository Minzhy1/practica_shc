from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import *
from django.db.models import Avg, Max, Count, Sum


def login_user(request):
    if request.method == 'POST':
        login_input = request.POST.get('login')
        password_input = request.POST.get('password')

        try:
            user = User.objects.get(email=login_input)

            if user.password == password_input:
                request.session['user_id'] = user.id
                request.session['user_group_id'] = user.group_id
                request.session['user_group'] = user.group.name
                request.session['user_fio'] = user.full_name

                if user.group.name == 'учитель':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
            else:
                return render(request, 'login.html', {'error': 'Неверный пароль'})
        except User.DoesNotExist:
            return render(request, 'login.html', {'error': 'Пользователь не найден'})

    return render(request, 'login.html')


def register_user(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        group_name = request.POST.get('group', 'ученик')

        try:
            if User.objects.filter(email=email).exists():
                return render(request, 'register.html', {'error': 'Пользователь с таким email уже существует'})

            group, _ = Group.objects.get_or_create(name=group_name)
            user = User.objects.create(
                group=group,
                full_name=full_name,
                email=email,
                password=password
            )

            request.session['user_id'] = user.id
            request.session['user_group_id'] = user.group_id
            request.session['user_group'] = user.group.name
            request.session['user_fio'] = user.full_name

            if user.group.name == 'учитель':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        except Exception as e:
            return render(request, 'register.html', {'error': str(e)})

    return render(request, 'register.html')


def logout_user(request):
    request.session.flush()
    return redirect('login_user')


def dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    if user.group.name == 'учитель':
        return redirect('teacher_dashboard')
    else:
        return redirect('student_dashboard')


def teacher_dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    created_tests = Test.objects.filter(creator=user)
    created_questions = Question.objects.filter(creator=user).select_related('topic')

    return render(request, 'teacher_dashboard.html', {
        'user': user,
        'created_tests': created_tests,
        'created_questions': created_questions
    })


def student_dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    available_tests = Test.objects.all()
    attempts = TestAttempt.objects.filter(student=user).select_related('test')

    return render(request, 'student_dashboard.html', {
        'user': user,
        'available_tests': available_tests,
        'attempts': attempts
    })


def create_test(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        time_limit = request.POST.get('time_limit', 0)
        access_code = request.POST.get('access_code')

        if Test.objects.filter(access_code=access_code).exists():
            messages.error(request, 'Тест с таким кодом доступа уже существует')
            return render(request, 'create_test.html', {'user': user})

        test = Test.objects.create(
            creator=user,
            title=title,
            description=description,
            time_limit=int(time_limit),
            access_code=access_code
        )

        messages.success(request, 'Тест успешно создан')
        return redirect('edit_test', test_id=test.id)

    return render(request, 'create_test.html', {'user': user})


def edit_test(request, test_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    test = get_object_or_404(Test, id=test_id, creator_id=user_id)

    # Показываем только НЕ удаленные вопросы (deleted_at is NULL)
    test_questions = TestQuestion.objects.filter(test=test, deleted_at__isnull=True).select_related('question__topic')

    # Доступные вопросы - которые не добавлены в тест
    available_questions = Question.objects.filter(creator=user).exclude(
        id__in=test_questions.values_list('question_id', flat=True)
    ).select_related('topic')

    return render(request, 'edit_test.html', {
        'user': user,
        'test': test,
        'test_questions': test_questions,
        'available_questions': available_questions,
        'topics': Topic.objects.all()
    })


def add_question_to_test(request, test_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    test = get_object_or_404(Test, id=test_id, creator_id=user_id)

    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        points = request.POST.get('points', 1)

        if question_id:
            question = get_object_or_404(Question, id=question_id)

            if not TestQuestion.objects.filter(test=test, question=question).exists():
                TestQuestion.objects.create(
                    test=test,
                    question=question,
                    points=points
                )
                messages.success(request, 'Вопрос добавлен в тест')
            else:
                messages.error(request, 'Вопрос уже есть в тесте')

    return redirect('edit_test', test_id=test.id)


def remove_question_from_test(request, test_id, question_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    if request.method == 'POST':
        test_question = TestQuestion.objects.get(test_id=test_id, question_id=question_id)

        if test_question.test.creator_id == user_id:
            # Мягкое удаление - ставим текущую дату
            test_question.deleted_at = timezone.now()
            test_question.save()
            messages.success(request, 'Вопрос удален из теста')

    return redirect('edit_test', test_id=test_id)



def create_question(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    topics = Topic.objects.all()
    test_id = request.GET.get('test_id')

    if request.method == 'POST':
        # Определяем, выбрана существующая тема или создается новая
        topic_option = request.POST.get('topic_option', 'existing')
        topic_id = None

        if topic_option == 'new':
            new_topic_name = request.POST.get('new_topic_name')
            if not new_topic_name:
                messages.error(request, 'Введите название новой темы')
                return render(request, 'create_question.html', {
                    'user': user,
                    'topics': topics,
                    'test_id': test_id
                })

            topic, created = Topic.objects.get_or_create(name=new_topic_name)
            topic_id = topic.id
        else:
            topic_id = request.POST.get('topic_id')

        text = request.POST.get('text')
        question_type = request.POST.get('type')

        # Проверка обязательных полей
        if not topic_id:
            messages.error(request, 'Выберите или создайте тему вопроса')
            return render(request, 'create_question.html', {
                'user': user,
                'topics': topics,
                'test_id': test_id
            })

        if not text:
            messages.error(request, 'Введите текст вопроса')
            return render(request, 'create_question.html', {
                'user': user,
                'topics': topics,
                'test_id': test_id
            })

        try:
            with transaction.atomic():
                # Создаем вопрос
                question = Question.objects.create(
                    creator=user,
                    topic_id=topic_id,
                    text=text,
                    type=question_type
                )

                # Если вопрос с выбором (single/multiple)
                if question_type in ['single', 'multiple']:
                    answer_texts = request.POST.getlist('answer_text[]')
                    answer_correct = request.POST.getlist('answer_correct[]')

                    if not answer_texts or not any(answer_texts):
                        messages.error(request, 'Добавьте хотя бы один ответ')
                        question.delete()
                        return render(request, 'create_question.html', {
                            'user': user,
                            'topics': topics,
                            'test_id': test_id
                        })

                    if not any(str(i) in answer_correct for i in range(len(answer_texts))):
                        messages.error(request, 'Добавьте хотя бы один правильный ответ')
                        question.delete()
                        return render(request, 'create_question.html', {
                            'user': user,
                            'topics': topics,
                            'test_id': test_id
                        })

                    for i, answer_text in enumerate(answer_texts):
                        if answer_text.strip():
                            answer = Answer.objects.create(
                                text=answer_text,
                                creator=user
                            )
                            is_correct = str(i) in answer_correct
                            QuestionAnswer.objects.create(
                                question=question,
                                answer=answer,
                                is_correct=is_correct
                            )

                # Если текстовый вопрос
                elif question_type == 'text':
                    correct_text_answer = request.POST.get('correct_text_answer', '').strip()

                    if not correct_text_answer:
                        messages.error(request, 'Введите правильный ответ для текстового вопроса')
                        question.delete()
                        return render(request, 'create_question.html', {
                            'user': user,
                            'topics': topics,
                            'test_id': test_id
                        })

                    # Создаем один ответ с правильным текстом (регистр не важен, сохраняем в нижнем регистре)
                    answer = Answer.objects.create(
                        text=correct_text_answer.lower(),
                        creator=user
                    )
                    QuestionAnswer.objects.create(
                        question=question,
                        answer=answer,
                        is_correct=True
                    )

                messages.success(request, 'Вопрос успешно создан')

                if test_id:
                    return redirect('edit_test', test_id=test_id)
                return redirect('teacher_dashboard')

        except Exception as e:
            messages.error(request, f'Ошибка при создании вопроса: {str(e)}')

    return render(request, 'create_question.html', {
        'user': user,
        'topics': topics,
        'test_id': test_id
    })


def take_test(request, test_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)

    # Если test_id = 0, ищем по коду
    if test_id == 0:
        access_code = request.GET.get('code')
        if access_code:
            try:
                test = Test.objects.get(access_code=access_code)
                return redirect('take_test', test_id=test.id)
            except Test.DoesNotExist:
                messages.error(request, 'Тест с таким кодом доступа не найден')
                return redirect('student_dashboard')
        return redirect('student_dashboard')

    test = get_object_or_404(Test, id=test_id)

    # Проверяем, есть ли активная попытка
    attempt = TestAttempt.objects.filter(
        test=test,
        student=user,
        end_time__isnull=True
    ).first()

    if not attempt:
        attempt = TestAttempt.objects.create(
            test=test,
            student=user,
            start_time=timezone.now()
        )

    test_questions = TestQuestion.objects.filter(test=test).select_related('question__topic')

    for tq in test_questions:
        tq.question.answers_list = QuestionAnswer.objects.filter(
            question=tq.question
        ).select_related('answer')

    if request.method == 'POST':
        total_score = 0

        with transaction.atomic():
            for tq in test_questions:
                question = tq.question
                answer_key = f'question_{question.id}'

                student_answer = StudentAnswer.objects.create(
                    attempt=attempt,
                    question=question
                )

                if question.type == 'text':
                    text_answer = request.POST.get(answer_key, '').strip().lower()
                    student_answer.text_answer = text_answer
                    student_answer.save()

                    # Получаем правильный ответ
                    correct_answer = QuestionAnswer.objects.filter(
                        question=question,
                        is_correct=True
                    ).first()

                    # Проверяем, что правильный ответ существует
                    if correct_answer:
                        if text_answer == correct_answer.answer.text:
                            student_answer.is_correct = True
                            student_answer.points_earned = tq.points
                            total_score += tq.points
                            student_answer.save()

                elif question.type == 'single':
                    selected_answer_id = request.POST.get(answer_key)
                    if selected_answer_id:
                        qa = get_object_or_404(QuestionAnswer, id=selected_answer_id)
                        student_answer.selected_answers.add(qa)

                        if qa.is_correct:
                            student_answer.is_correct = True
                            student_answer.points_earned = tq.points
                            total_score += tq.points
                            student_answer.save()

                elif question.type == 'multiple':
                    selected_ids = request.POST.getlist(answer_key)
                    if selected_ids:
                        selected_qas = QuestionAnswer.objects.filter(id__in=selected_ids)
                        student_answer.selected_answers.set(selected_qas)

                        correct_qas = QuestionAnswer.objects.filter(question=question, is_correct=True)
                        if set(selected_qas) == set(correct_qas):
                            student_answer.is_correct = True
                            student_answer.points_earned = tq.points
                            total_score += tq.points
                            student_answer.save()

            attempt.end_time = timezone.now()
            attempt.score = total_score
            attempt.save()

        messages.success(request, f'Тест завершен! Ваш результат: {total_score} баллов')
        return redirect('test_result', attempt_id=attempt.id)

    return render(request, 'take_test.html', {
        'user': user,
        'test': test,
        'test_questions': test_questions,
        'attempt': attempt,
        'time_limit': test.time_limit * 60 if test.time_limit > 0 else 0
    })


def test_result(request, attempt_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    attempt = get_object_or_404(TestAttempt, id=attempt_id, student_id=user_id)
    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question__topic')

    for answer in student_answers:
        # Выбранные ответы ученика
        answer.selected_answers_list = answer.selected_answers.all().select_related('answer')
        # Правильные ответы на вопрос
        answer.correct_answers = QuestionAnswer.objects.filter(
            question=answer.question,
            is_correct=True
        ).select_related('answer')
        # ВСЕ варианты ответов на вопрос (добавляем)
        answer.all_answers = QuestionAnswer.objects.filter(
            question=answer.question
        ).select_related('answer')

    return render(request, 'test_result.html', {
        'user': User.objects.get(id=user_id),
        'attempt': attempt,
        'student_answers': student_answers
    })


def create_topic(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)

    # Получаем параметр next из GET или POST
    next_url = request.GET.get('next', 'create_question')
    if request.method == 'POST':
        next_url = request.POST.get('next', 'create_question')
        topic_name = request.POST.get('name')

        if topic_name:
            topic, created = Topic.objects.get_or_create(name=topic_name)
            messages.success(request, f'Тема "{topic_name}" успешно создана')

            # Получаем test_id если есть
            test_id = request.GET.get('test_id') or request.POST.get('test_id')

            # Формируем URL для возврата
            if next_url == 'create_question' and test_id:
                return redirect(f"{next_url}?test_id={test_id}")
            else:
                return redirect(next_url)

    # Для GET запроса передаем параметры в шаблон
    context = {
        'user': user,
        'next': next_url,
        'test_id': request.GET.get('test_id', '')
    }
    return render(request, 'create_topic.html', context)


def test_results_for_teacher(request, test_id):
    """Просмотр всех результатов по тесту для учителя"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    test = get_object_or_404(Test, id=test_id, creator_id=user_id)

    # Получаем все попытки по этому тесту
    attempts = TestAttempt.objects.filter(test=test, end_time__isnull=False).select_related('student').order_by(
        '-score', '-end_time')

    # Статистика по тесту
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(Avg('score'))['score__avg'] or 0
    max_score = attempts.aggregate(Max('score'))['score__max'] or 0
    total_possible = sum(tq.points for tq in test.testquestion_set.all())

    # Статистика по каждому вопросу
    questions_stats = []
    for tq in test.testquestion_set.all():
        correct_count = StudentAnswer.objects.filter(
            attempt__in=attempts,
            question=tq.question,
            is_correct=True
        ).count()

        questions_stats.append({
            'question': tq.question,
            'points': tq.points,
            'correct_count': correct_count,
            'total_count': total_attempts,
            'percent': (correct_count / total_attempts * 100) if total_attempts > 0 else 0
        })

    context = {
        'user': user,
        'test': test,
        'attempts': attempts,
        'total_attempts': total_attempts,
        'avg_score': round(avg_score, 2),
        'max_score': max_score,
        'total_possible': total_possible,
        'questions_stats': questions_stats,
    }

    return render(request, 'test_results_for_teacher.html', context)


def attempt_detail_for_teacher(request, test_id, attempt_id):
    """Детальный просмотр конкретной попытки ученика для учителя"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_user')

    user = User.objects.get(id=user_id)
    test = get_object_or_404(Test, id=test_id, creator_id=user_id)
    attempt = get_object_or_404(TestAttempt, id=attempt_id, test=test)

    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question__topic')

    for answer in student_answers:
        answer.selected_answers_list = answer.selected_answers.all().select_related('answer')
        answer.correct_answers = QuestionAnswer.objects.filter(
            question=answer.question,
            is_correct=True
        ).select_related('answer')
        answer.all_answers = QuestionAnswer.objects.filter(
            question=answer.question
        ).select_related('answer')

    context = {
        'user': user,
        'test': test,
        'attempt': attempt,
        'student_answers': student_answers,
    }

    return render(request, 'attempt_detail_for_teacher.html', context)