from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import AppModule, PastorSede, Sede, User, UserAppPermission
from hechos.models import AdminEscuela


class DirectorInterfaceTests(TestCase):
    @staticmethod
    def make_test_image(name="avatar.gif"):
        return SimpleUploadedFile(
            name,
            (
                b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
                b"\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00"
                b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01"
                b"\x00\x3b"
            ),
            content_type="image/gif",
        )

    def setUp(self):
        self.director = User.objects.create_user(
            username="director1",
            email="director@example.com",
            password="local12345",
            first_name="Director",
            last_name="General",
            role="super_admin",
            is_staff=True,
            is_superuser=True,
        )
        self.hechos_module = AppModule.objects.create(
            name="hechos",
            display_name="Hechos",
            description="Escuelas Bíblicas",
            url_name="hechos:dashboard",
        )

    def test_director_can_create_sede(self):
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_create"),
            {
                "nombre": "Hechos Norte",
                "direccion": "Calle Principal 123",
                "ciudad": "Monterrey",
                "telefono": "555-1000",
                "email": "norte@example.com",
                "pastor_responsable": "Pastor Norte",
                "descripcion": "Sede principal",
                "pastores-TOTAL_FORMS": "3",
                "pastores-INITIAL_FORMS": "0",
                "pastores-MIN_NUM_FORMS": "0",
                "pastores-MAX_NUM_FORMS": "1000",
                "pastores-0-nombre": "",
                "pastores-1-nombre": "",
                "pastores-2-nombre": "",
            },
        )

        sede = Sede.objects.get(nombre="Hechos Norte")
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))

    def test_director_can_create_coordinator_for_sede(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:coordinador_create", args=[sede.id]),
            {
                "first_name": "Ana",
                "last_name": "Lopez",
                "username": "ana.lopez",
                "email": "ana@example.com",
                "cargo": "Coordinadora de sede",
                "avatar": self.make_test_image(),
                "password1": "coord12345",
                "password2": "coord12345",
                "is_active": "on",
            },
        )

        coordinador = AdminEscuela.objects.get(sede=sede)
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(coordinador.user.role, "app_admin")
        self.assertTrue(bool(coordinador.user.avatar))
        self.assertTrue(
            UserAppPermission.objects.filter(
                user=coordinador.user,
                app_module=self.hechos_module,
                can_manage=True,
            ).exists()
        )

    def test_director_can_edit_coordinator(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        user = User.objects.create_user(
            username="ana.lopez",
            email="ana@example.com",
            password="coord12345",
            first_name="Ana",
            last_name="Lopez",
            role="app_admin",
            sede=sede,
            is_active=True,
            is_staff=True,
        )
        coordinador = AdminEscuela.objects.create(
            user=user,
            sede=sede,
            cargo="Coordinadora de sede",
            is_active=True,
        )
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:coordinador_edit", args=[sede.id, coordinador.id]),
            {
                "first_name": "Ana Maria",
                "last_name": "Lopez",
                "username": "ana.maria",
                "email": "ana.maria@example.com",
                "cargo": "Coordinadora general",
                "avatar": self.make_test_image("avatar-edit.gif"),
                "password1": "",
                "password2": "",
                "is_active": "on",
            },
        )

        coordinador.refresh_from_db()
        coordinador.user.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(coordinador.user.first_name, "Ana Maria")
        self.assertEqual(coordinador.user.username, "ana.maria")
        self.assertEqual(coordinador.user.email, "ana.maria@example.com")
        self.assertEqual(coordinador.cargo, "Coordinadora general")
        self.assertTrue(bool(coordinador.user.avatar))

    def test_deleted_coordinator_is_hidden_from_sede_detail(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        user = User.objects.create_user(
            username="ana.lopez",
            email="ana@example.com",
            password="coord12345",
            first_name="Ana",
            last_name="Lopez",
            role="app_admin",
            sede=sede,
            is_active=True,
            is_staff=True,
        )
        coordinador = AdminEscuela.objects.create(
            user=user,
            sede=sede,
            cargo="Coordinadora de sede",
            is_active=True,
        )
        self.client.force_login(self.director)

        delete_response = self.client.post(reverse("core:coordinador_delete", args=[sede.id, coordinador.id]))

        coordinador.refresh_from_db()
        coordinador.user.refresh_from_db()
        self.assertRedirects(delete_response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertFalse(coordinador.is_active)
        self.assertFalse(coordinador.user.is_active)

        detail_response = self.client.get(reverse("core:director_sede_detail", args=[sede.id]))
        self.assertNotContains(detail_response, "ana.lopez")
        self.assertContains(detail_response, "No hay coordinadores en esta sede")

    def test_director_can_edit_sede(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_edit", args=[sede.id]),
            {
                "nombre": "Hechos Norte Actualizada",
                "direccion": "Nueva dirección 456",
                "ciudad": "Guadalupe",
                "telefono": "555-9999",
                "email": "actualizada@example.com",
                "pastor_responsable": "Pastor Actualizado",
                "descripcion": "Sede actualizada",
                "pastores-TOTAL_FORMS": "3",
                "pastores-INITIAL_FORMS": "0",
                "pastores-MIN_NUM_FORMS": "0",
                "pastores-MAX_NUM_FORMS": "1000",
                "pastores-0-nombre": "",
                "pastores-1-nombre": "",
                "pastores-2-nombre": "",
            },
        )

        sede.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(sede.nombre, "Hechos Norte Actualizada")
        self.assertEqual(sede.ciudad, "Guadalupe")

    def test_director_can_delete_sede(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123", is_active=True)
        self.client.force_login(self.director)

        response = self.client.post(reverse("core:sede_delete", args=[sede.id]))

        sede.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_dashboard"))
        self.assertFalse(sede.is_active)

    def test_director_can_add_optional_additional_pastors(self):
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_create"),
            {
                "nombre": "Hechos Centro",
                "direccion": "Calle Centro 321",
                "ciudad": "Monterrey",
                "telefono": "",
                "email": "",
                "pastor_responsable": "Pastor Principal",
                "descripcion": "",
                "pastores-TOTAL_FORMS": "3",
                "pastores-INITIAL_FORMS": "0",
                "pastores-MIN_NUM_FORMS": "0",
                "pastores-MAX_NUM_FORMS": "1000",
                "pastores-0-nombre": "Pastor Dos",
                "pastores-1-nombre": "Pastor Tres",
                "pastores-2-nombre": "",
            },
        )

        sede = Sede.objects.get(nombre="Hechos Centro")
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(PastorSede.objects.filter(sede=sede).count(), 2)
