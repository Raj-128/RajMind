from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from accounts.models import User
from documents.models import Document
from .models import Workspace, WorkspaceMember


class RolePermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='owner@x.com', username='owner', password='pw')
        self.viewer = User.objects.create_user(email='viewer@x.com', username='viewer', password='pw')
        self.outsider = User.objects.create_user(email='out@x.com', username='out', password='pw')
        self.ws = Workspace.objects.create(name='WS', slug='ws', owner=self.owner)
        WorkspaceMember.objects.create(workspace=self.ws, user=self.owner, role='owner')
        WorkspaceMember.objects.create(workspace=self.ws, user=self.viewer, role='viewer')

    def upload(self):
        return self.client.post(f'/api/workspaces/{self.ws.id}/documents/', {
            'title': 'Doc', 'file': SimpleUploadedFile('a.txt', b'hello world'),
        })

    @mock.patch('documents.views.start_document_processing')
    def test_viewer_cannot_upload_but_owner_can(self, _):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.upload().status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.upload().status_code, 201)

    def test_viewer_cannot_delete_document(self):
        doc = Document.objects.create(workspace=self.ws, title='D', file='x.txt', file_type='txt')
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.delete(f'/api/workspaces/{self.ws.id}/documents/{doc.id}/').status_code, 403)

    def test_only_owner_deletes_workspace(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.delete(f'/api/workspaces/{self.ws.id}/').status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(f'/api/workspaces/{self.ws.id}/').status_code, 204)

    def test_outsider_cannot_open_conversations(self):
        self.client.force_authenticate(self.outsider)
        res = self.client.post(f'/api/workspaces/{self.ws.id}/chat/conversations/', {'title': 'x'})
        self.assertEqual(res.status_code, 404)

    def test_workspace_list_reports_my_role(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get('/api/workspaces/').data[0]['my_role'], 'viewer')
