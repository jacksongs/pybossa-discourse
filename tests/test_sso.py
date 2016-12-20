# -*- coding: utf8 -*-

import base64
import urlparse
import urllib
from default import Test, flask_app, with_context
from nose.tools import assert_raises
from mock import patch, MagicMock
from pybossa_discourse import discourse_sso


class TestSSO(Test):

    def setUp(self):
        super(TestSSO, self).setUp()
        self.nonce = "cb68251eefb5211e58c00ff1395f0c0b"
        self.payload = 'bm9uY2U9Y2I2ODI1MWVlZmI1MjExZTU4YzAwZmYxMzk1ZjBjMGI' \
                       '%3D%0A'
        self.sig = '2828aa29899722b35a2f191d34ef9b3ce695e0e6eeec47deb46d588' \
                   'd70c7cb56'

    def test_validation_fails_when_nonce_missing_from_payload(self):
        pl = base64.encodestring('')
        assert_raises(ValueError, discourse_sso._validate_payload, pl,
                      self.sig)

    def test_validation_fails_when_payload_does_not_match_sig(self):
        pl = base64.encodestring('nonce=1234')
        assert_raises(ValueError, discourse_sso._validate_payload, pl,
                      self.sig)

    def test_nonce_returned_when_parameters_valid(self):
        nonce = discourse_sso._validate_payload(self.payload, self.sig)
        assert nonce == self.nonce

    @with_context
    @patch('pybossa_discourse.sso.current_user')
    def test_get_credentials_without_avatar(self, mock_user):
        mock_user.info = dict()
        secret = flask_app.config['DISCOURSE_SECRET']
        expected = {'nonce': self.nonce,
                    'email': mock_user.email_addr,
                    'name': mock_user.fullname,
                    'username': mock_user.name,
                    'external_id': mock_user.id,
                    'sso_secret': secret}
        actual = discourse_sso._get_credentials(self.nonce)
        assert cmp(actual, expected) == 0

    @with_context
    @patch('pybossa_discourse.sso.current_user')
    def test_get_credentials_with_avatar(self, mock_user):
        mock_user.info = dict(container='container', avatar='1.png')
        secret = flask_app.config['DISCOURSE_SECRET']
        expected = {'nonce': self.nonce,
                    'email': mock_user.email_addr,
                    'name': mock_user.fullname,
                    'username': mock_user.name,
                    'external_id': mock_user.id,
                    'sso_secret': secret,
                    'avatar_url': 'http://localhost/uploads/container/1.png',
                    'avatar_force_update': 'true'}
        with self.flask_app.test_request_context('/'):
            actual = discourse_sso._get_credentials(self.nonce)
        assert cmp(actual, expected) == 0

    def test_valid_return_query_string_built(self):
        credentials = {'nonce': self.nonce,
                       'email': 'joebloggs@example.com',
                       'name': 'JoeBloggs',
                       'username': 'joebloggs',
                       'external_id': '1',
                       'sso_secret': 'some_secret'}
        query_string = discourse_sso._build_return_query(credentials)
        params = urlparse.parse_qs(query_string)
        sso = params['sso'][0]
        sso = base64.decodestring(sso)
        sso = urllib.unquote(sso)
        sso = dict((p.split('=') for p in sso.split('&')))
        assert cmp(sso, credentials) == 0

    @with_context
    @patch('pybossa_discourse.sso.current_user')
    def test_valid_sso_login_url_built(self, mock_user):
        with self.flask_app.test_request_context('/'):
            url = discourse_sso.get_sso_login_url(self.payload, self.sig)
        parsed_url = urlparse.urlparse(url)
        params = urlparse.parse_qs(parsed_url.query)
        assert parsed_url.path == '/session/sso_login'
        assert 'sso' in params and 'sig' in params

    @patch('pybossa_discourse.sso.current_user')
    def test_base_url_returned_to_anonymous_users(self, mock_user):
        mock_user.is_anonymous.return_value = True
        expected = flask_app.config['DISCOURSE_URL']
        actual = discourse_sso.get_sso_url()
        assert expected == actual

    @patch('pybossa_discourse.sso.current_user')
    def test_sso_url_returned_to_authenticated_users(self, mock_user):
        mock_user.is_anonymous.return_value = False
        base_url = flask_app.config['DISCOURSE_URL']
        expected = '{0}/session/sso?return_path=%2F'.format(base_url)
        actual = discourse_sso.get_sso_url()
        assert expected == actual
