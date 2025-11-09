from django.test import TestCase, Client
from django.db import connection
import json


class SedeDeleteTests(TestCase):
	"""Pruebas básicas para eliminación de sedes."""

	def setUp(self):
		self.client = Client()
		# Verificar disponibilidad mínima de la BD Oracle
		try:
			with connection.cursor() as cur:
				cur.execute("SELECT 1 FROM dual")
				cur.fetchone()
			self.db_ready = True
		except Exception:
			self.db_ready = False

	def skip_if_no_db(self):
		if not self.db_ready:
			self.skipTest("Base de datos Oracle no disponible para pruebas.")

	def crear_sede(self, nombre='Tmp', ciudad='Test', slot=120, maxg=5):
		payload = {
			'nombre': nombre,
			'ciudad': ciudad,
			'slot_minutos': slot,
			'max_guardias': maxg
		}
		resp = self.client.post('/api/sedes/crear/', data=json.dumps(payload), content_type='application/json')
		self.assertEqual(resp.status_code, 200, resp.content)
		return resp.json()['sede_id']

	def crear_guardia(self, sede_id, apellidos='Perez', nombres='Juan', sueldo=1000.0, orden=1):
		payload = {
			'sede_id': sede_id,
			'apellidos': apellidos,
			'nombres': nombres,
			'sueldo': sueldo,
			'orden_rotativo': orden
		}
		resp = self.client.post('/api/guardias/alta/', data=json.dumps(payload), content_type='application/json')
		self.assertEqual(resp.status_code, 200, resp.content)
		return resp.json()['guardia_id']

	def test_eliminar_sede_sin_dependencias(self):
		self.skip_if_no_db()
		sede_id = self.crear_sede()
		resp_del = self.client.post(f'/api/sedes/{sede_id}/eliminar/')
		self.assertEqual(resp_del.status_code, 200, resp_del.content)
		# La consulta por detalle debe dar 404
		resp_det = self.client.get(f'/api/sedes/{sede_id}/')
		self.assertEqual(resp_det.status_code, 404)

	def test_eliminar_sede_con_guardias_conflicto(self):
		self.skip_if_no_db()
		sede_id = self.crear_sede(nombre='ConG', ciudad='Conf')
		self.crear_guardia(sede_id)
		resp_del = self.client.post(f'/api/sedes/{sede_id}/eliminar/')
		# Debe retornar 409 por integridad (FK guardias -> sedes)
		self.assertEqual(resp_del.status_code, 409, resp_del.content)
		data = resp_del.json()
		self.assertIn('error', data)

