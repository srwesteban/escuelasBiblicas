from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Sede, User
from hechos.models import Curso, Escuela, Estudiante, Matricula, Profesor, RutaEstudio, SolicitudMatricula


class SolicitudMatriculaFlowTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre="Sede Norte", direccion="Calle 1")

        self.student_user = User(
            username="",
            email="estudiante@example.com",
            first_name="Ana",
            last_name="Perez",
        )
        self.student_user.set_password("local12345")
        self.student_user.save()
        self.estudiante = Estudiante.objects.create(user=self.student_user, sede=self.sede)

        profesor_user = User.objects.create_user(
            username="profesor1",
            email="profesor@example.com",
            password="local12345",
            first_name="Pedro",
            last_name="Lopez",
            sede=self.sede,
        )
        self.profesor = Profesor.objects.create(user=profesor_user, sede=self.sede)

        self.escuela = Escuela.objects.create(
            sede=self.sede,
            nombre="Escuela Inicial",
            descripcion="Escuela de prueba",
            maestro=self.profesor,
            fecha_inicio=timezone.now().date(),
            fecha_fin=(timezone.now() + timedelta(days=30)).date(),
            cupo_maximo=20,
        )
        self.ruta = RutaEstudio.objects.create(
            sede=self.sede,
            escuela=self.escuela,
            nombre="Fundamentos",
            descripcion="Ruta inicial",
            nivel="basico",
        )
        self.curso = Curso.objects.create(
            sede=self.sede,
            ruta_estudio=self.ruta,
            nombre="Primeros Pasos",
            descripcion="Introducción",
            orden=1,
            duracion_semanas=6,
        )

    def test_user_generates_username_from_email(self):
        self.assertTrue(self.student_user.username.startswith("estudiante"))

    def test_student_can_create_enrollment_request_via_escuela_id_legacy_url(self):
        self.client.force_login(self.student_user)

        response = self.client.post(reverse("hechos:solicitar_matricula", args=[self.escuela.id]))

        self.assertRedirects(response, reverse("hechos:mis_escuelas"))
        solicitud = SolicitudMatricula.objects.get(estudiante=self.estudiante, escuela=self.escuela)
        self.assertEqual(solicitud.estado, "pendiente")
        self.assertEqual(solicitud.sede, self.sede)

    def test_student_can_request_enrollment_via_escuela_url(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("hechos:solicitar_matricula_escuela", args=[self.escuela.id]),
        )
        self.assertRedirects(response, reverse("hechos:mis_escuelas"))
        solicitud = SolicitudMatricula.objects.get(estudiante=self.estudiante, escuela=self.escuela)
        self.assertEqual(solicitud.estado, "pendiente")

    def test_duplicate_request_is_not_created(self):
        SolicitudMatricula.objects.create(
            sede=self.sede,
            estudiante=self.estudiante,
            escuela=self.escuela,
        )
        self.client.force_login(self.student_user)

        self.client.post(reverse("hechos:solicitar_matricula", args=[self.escuela.id]))

        self.assertEqual(
            SolicitudMatricula.objects.filter(estudiante=self.estudiante, escuela=self.escuela).count(),
            1,
        )

    def test_student_with_active_matricula_cannot_create_request(self):
        Matricula.objects.create(
            sede=self.sede,
            estudiante=self.estudiante,
            escuela=self.escuela,
            periodo="2026-1",
        )
        self.client.force_login(self.student_user)

        self.client.post(reverse("hechos:solicitar_matricula_escuela", args=[self.escuela.id]))

        self.assertFalse(
            SolicitudMatricula.objects.filter(estudiante=self.estudiante, escuela=self.escuela).exists()
        )
