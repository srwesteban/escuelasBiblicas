from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import AppModule, Sede, User, UserAppPermission
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
                "departamento": "5",
                "ciudad": "Medellín",
                "telefono": "555-1000",
                "email": "norte@example.com",
                "descripcion": "Sede principal",
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
                "nombres": "Ana",
                "apellidos": "Lopez",
                "tipo_documento": "CC",
                "documento_identidad": "1234567890",
                "celular": "3001234567",
                "email": "ana@example.com",
                "tipo_coordinador": AdminEscuela.TipoCoordinador.SEDE,
                "avatar": self.make_test_image(),
                "password1": "coord12345",
                "password2": "coord12345",
            },
        )

        coordinador = AdminEscuela.objects.get(sede=sede)
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(coordinador.user.username, "ana")
        self.assertEqual(coordinador.tipo_coordinador, AdminEscuela.TipoCoordinador.SEDE)
        self.assertEqual(
            coordinador.cargo,
            AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.SEDE, sede.nombre),
        )
        self.assertEqual(coordinador.user.role, "app_admin")
        self.assertTrue(bool(coordinador.user.avatar))
        self.assertTrue(
            UserAppPermission.objects.filter(
                user=coordinador.user,
                app_module=self.hechos_module,
                can_manage=True,
            ).exists()
        )
        self.assertEqual(coordinador.user.documento_identidad, "1234567890")
        self.assertEqual(coordinador.user.tipo_documento, "CC")
        self.assertEqual(coordinador.user.phone, "3001234567")

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
            documento_identidad="9876543210",
            tipo_documento=User.TipoDocumento.CC,
            phone="3109876543",
        )
        coordinador = AdminEscuela.objects.create(
            user=user,
            sede=sede,
            tipo_coordinador=AdminEscuela.TipoCoordinador.SEDE,
            cargo=AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.SEDE, sede.nombre),
            is_active=True,
        )
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:coordinador_edit", args=[sede.id, coordinador.id]),
            {
                "nombres": "Ana María",
                "apellidos": "Lopez",
                "tipo_documento": "CC",
                "documento_identidad": "9876543210",
                "celular": "3109876543",
                "email": "ana.maria@example.com",
                "tipo_coordinador": AdminEscuela.TipoCoordinador.SEDE,
                "avatar": self.make_test_image("avatar-edit.gif"),
                "password1": "",
                "password2": "",
            },
        )

        coordinador.refresh_from_db()
        coordinador.user.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(coordinador.user.first_name, "Ana María")
        self.assertEqual(coordinador.user.username, "anamaria")
        self.assertEqual(coordinador.user.email, "ana.maria@example.com")
        self.assertEqual(coordinador.tipo_coordinador, AdminEscuela.TipoCoordinador.SEDE)
        self.assertEqual(
            coordinador.cargo,
            AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.SEDE, sede.nombre),
        )
        self.assertTrue(bool(coordinador.user.avatar))

    def test_director_cannot_delete_team_coordinator(self):
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
            tipo_coordinador=AdminEscuela.TipoCoordinador.ACADEMICO,
            cargo=AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.ACADEMICO, sede.nombre),
            is_active=True,
        )
        self.client.force_login(self.director)

        delete_response = self.client.post(reverse("core:coordinador_delete", args=[sede.id, coordinador.id]))

        coordinador.refresh_from_db()
        coordinador.user.refresh_from_db()
        self.assertRedirects(delete_response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertTrue(coordinador.is_active)
        self.assertTrue(coordinador.user.is_active)

        detail_response = self.client.get(reverse("core:director_sede_detail", args=[sede.id]))
        self.assertContains(detail_response, "ana@example.com")
        self.assertContains(detail_response, "Equipo de la sede")
        self.assertContains(detail_response, "Ver ficha")

        ficha = self.client.get(
            reverse("core:director_coordinador_ficha_fragment", args=[sede.id, coordinador.id])
        )
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, "ana@example.com")
        self.assertContains(ficha, "Académico")
    def test_director_cannot_delete_last_sede_coordinator(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        user = User.objects.create_user(
            username="coord.sede",
            email="coordsede@example.com",
            password="coord12345",
            first_name="Coord",
            last_name="Sede",
            role="app_admin",
            sede=sede,
            is_active=True,
            is_staff=True,
        )
        coordinador = AdminEscuela.objects.create(
            user=user,
            sede=sede,
            tipo_coordinador=AdminEscuela.TipoCoordinador.SEDE,
            cargo=AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.SEDE, sede.nombre),
            is_active=True,
        )
        self.client.force_login(self.director)

        delete_response = self.client.post(reverse("core:coordinador_delete", args=[sede.id, coordinador.id]))

        coordinador.refresh_from_db()
        self.assertRedirects(delete_response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertTrue(coordinador.is_active)
    def test_director_can_edit_sede(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123")
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_edit", args=[sede.id]),
            {
                "nombre": "Hechos Norte Actualizada",
                "direccion": "Nueva dirección 456",
                "departamento": "5",
                "ciudad": "Guadalupe",
                "telefono": "555-9999",
                "email": "actualizada@example.com",
                "descripcion": "Sede actualizada",
            },
        )

        sede.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        self.assertEqual(sede.nombre, "Hechos Norte Actualizada")
        self.assertEqual(sede.ciudad, "Guadalupe")
        self.assertEqual(sede.departamento, "5")

    def test_director_can_delete_sede(self):
        sede = Sede.objects.create(nombre="Hechos Norte", direccion="Calle Principal 123", is_active=True)
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_delete", args=[sede.id]),
            {"confirm_password": "local12345"},
        )

        sede.refresh_from_db()
        self.assertRedirects(response, reverse("core:director_dashboard"))
        self.assertFalse(sede.is_active)

    def test_director_cannot_delete_sede_with_wrong_password(self):
        sede = Sede.objects.create(nombre="Hechos Sur", direccion="Calle Sur 1", is_active=True)
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_delete", args=[sede.id]),
            {"confirm_password": "clave-incorrecta"},
        )

        sede.refresh_from_db()
        self.assertTrue(sede.is_active)
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))

    def test_director_can_create_sede_with_new_coordinador(self):
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("core:sede_create"),
            {
                "nombre": "Hechos Centro",
                "direccion": "Calle Centro 321",
                "departamento": "5",
                "ciudad": "Medellín",
                "telefono": "",
                "email": "",
                "descripcion": "",
                "coordinador_modo": "nuevo",
                "coord-nombres": "Carlos",
                "coord-apellidos": "Ramirez",
                "coord-tipo_documento": "CC",
                "coord-documento_identidad": "1122334455",
                "coord-celular": "3001112233",
                "coord-email": "carlos@example.com",
                "coord-password1": "coord12345",
                "coord-password2": "coord12345",
                "coord-tipo_coordinador": AdminEscuela.TipoCoordinador.SEDE,
            },
        )

        sede = Sede.objects.get(nombre="Hechos Centro")
        self.assertRedirects(response, reverse("core:director_sede_detail", args=[sede.id]))
        coordinador = AdminEscuela.objects.get(sede=sede)
        self.assertEqual(coordinador.user.documento_identidad, "1122334455")
        self.assertEqual(coordinador.tipo_coordinador, AdminEscuela.TipoCoordinador.SEDE)

    def test_director_profesores_list(self):
        from hechos.models import Profesor

        sede = Sede.objects.create(
            nombre="Hechos ProfTest",
            direccion="Dir",
            departamento="5",
            ciudad="Pasto",
            is_active=True,
        )
        u = User.objects.create_user(
            username="prof_e2e",
            email="prof_e2e@example.com",
            password="pwd12345!!",
            first_name="Luis",
            last_name="Maestro",
            role="user",
        )
        Profesor.objects.create(user=u, sede=sede, is_active=True)
        self.client.force_login(self.director)
        response = self.client.get(reverse("core:director_profesores"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis")

    def test_director_profesor_ficha_fragment(self):
        from hechos.models import Profesor

        sede = Sede.objects.create(
            nombre="Hechos EditPy",
            direccion="Dir",
            departamento="5",
            ciudad="Cali",
            is_active=True,
        )
        u = User.objects.create_user(
            username="prof_edit_1",
            email="prof_edit_1@example.com",
            password="pwd12345!!",
            first_name="Ana",
            last_name="Pérez",
            role="user",
            documento_identidad="1234567890",
            tipo_documento=User.TipoDocumento.CC,
            phone="3001112233",
        )
        p = Profesor.objects.create(
            user=u, sede=sede, is_active=True
        )
        self.client.force_login(self.director)
        url = reverse("core:director_profesor_ficha_fragment", args=[p.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")
        self.assertContains(response, "Pérez")
        self.assertContains(response, "prof_edit_1@example.com")

    def test_non_director_cannot_open_director_profesores(self):
        other = User.objects.create_user(
            username="norm_user",
            email="norm@example.com",
            password="pwd12345!!",
            first_name="N",
            last_name="U",
            role="user",
        )
        self.client.force_login(other)
        response = self.client.get(reverse("core:director_profesores"))
        self.assertEqual(response.status_code, 302)
