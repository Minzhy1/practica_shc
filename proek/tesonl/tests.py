from django.test import TestCase, Client
from django.utils import timezone
from .models import *


class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_teacher = Group.objects.create(name='учитель')
        self.group_student = Group.objects.create(name='ученик')

        self.user = User.objects.create(
            group=self.group_teacher,
            full_name='Test Teacher',
            email='test@mail.ru',
            password='12345'
        )

    def test_successful_login(self):
        response = self.client.post('/login/', {
            'login': 'test@mail.ru',
            'password': '12345'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('user_id', self.client.session)


class QuestionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_teacher = Group.objects.create(name='учитель')

        self.user = User.objects.create(
            group=self.group_teacher,
            full_name='Teacher',
            email='teacher@mail.ru',
            password='12345'
        )

        self.topic = Topic.objects.create(name='Тестовая тема')

        self.client.post('/login/', {
            'login': 'teacher@mail.ru',
            'password': '12345'
        })

    def test_create_single_choice_question(self):
        response = self.client.post('/question/create/', {
            'topic_id': self.topic.id,
            'text': 'Какой язык программирования?',
            'type': 'single',
            'answer_text[]': ['Python', 'Java', 'C++'],
            'answer_correct[]': ['0']
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Question.objects.filter(text='Какой язык программирования?').exists())


class TestTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_teacher = Group.objects.create(name='учитель')

        self.user = User.objects.create(
            group=self.group_teacher,
            full_name='Teacher',
            email='teacher@mail.ru',
            password='12345'
        )

        self.client.post('/login/', {
            'login': 'teacher@mail.ru',
            'password': '12345'
        })

    def test_create_test(self):
        response = self.client.post('/test/create/', {
            'title': 'Новый тест',
            'description': 'Описание теста',
            'time_limit': '30',
            'access_code': 'TEST123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Test.objects.filter(access_code='TEST123').exists())


class AnswerScoringTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_teacher = Group.objects.create(name='учитель')
        self.group_student = Group.objects.create(name='ученик')

        self.teacher = User.objects.create(
            group=self.group_teacher,
            full_name='Teacher',
            email='teacher@mail.ru',
            password='12345'
        )

        self.student = User.objects.create(
            group=self.group_student,
            full_name='Student',
            email='student@mail.ru',
            password='12345'
        )

        self.topic = Topic.objects.create(name='Тестовая тема')

        self.test = Test.objects.create(
            creator=self.teacher,
            title='Тест',
            description='Описание',
            time_limit=30,
            access_code='ABC123'
        )

        self.question = Question.objects.create(
            creator=self.teacher,
            topic=self.topic,
            text='Сколько будет 2+2?',
            type='single'
        )

        self.answer1 = Answer.objects.create(text='3', creator=self.teacher)
        self.answer2 = Answer.objects.create(text='4', creator=self.teacher)
        self.answer3 = Answer.objects.create(text='5', creator=self.teacher)

        self.correct_qa = QuestionAnswer.objects.create(
            question=self.question,
            answer=self.answer2,
            is_correct=True
        )

        self.wrong_qa = QuestionAnswer.objects.create(
            question=self.question,
            answer=self.answer1,
            is_correct=False
        )

        self.tq = TestQuestion.objects.create(
            test=self.test,
            question=self.question,
            points=5
        )

        self.client.post('/login/', {
            'login': 'student@mail.ru',
            'password': '12345'
        })

        self.attempt = TestAttempt.objects.create(
            test=self.test,
            student=self.student,
            start_time=timezone.now()
        )

    def test_correct_single_answer(self):
        self.client.post(f'/test/{self.test.id}/take/', {
            f'question_{self.question.id}': self.correct_qa.id
        })

        student_answer = StudentAnswer.objects.filter(attempt=self.attempt).first()
        self.assertIsNotNone(student_answer)
        self.assertTrue(student_answer.is_correct)
        self.assertEqual(student_answer.points_earned, 5)


class ResultTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_teacher = Group.objects.create(name='учитель')
        self.group_student = Group.objects.create(name='ученик')

        self.teacher = User.objects.create(
            group=self.group_teacher,
            full_name='Teacher',
            email='teacher@mail.ru',
            password='12345'
        )

        self.student = User.objects.create(
            group=self.group_student,
            full_name='Student',
            email='student@mail.ru',
            password='12345'
        )

        self.test = Test.objects.create(
            creator=self.teacher,
            title='Тест',
            description='Описание',
            time_limit=30,
            access_code='ABC123'
        )

        self.attempt = TestAttempt.objects.create(
            test=self.test,
            student=self.student,
            start_time=timezone.now(),
            end_time=timezone.now(),
            score=10
        )

        self.client.post('/login/', {
            'login': 'student@mail.ru',
            'password': '12345'
        })

    def test_view_own_results(self):
        response = self.client.get(f'/attempt/{self.attempt.id}/result/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt', response.context)
        self.assertIn('student_answers', response.context)