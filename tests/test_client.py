from unittest import TestCase
from unittest.mock import patch
import itertools
import json

from jsonschema import ValidationError
from testfixtures import LogCapture

from jsonrpcclient import Request, config, exceptions
from jsonrpcclient.client import Client


class DummyClient(Client):
    """A dummy class for testing the abstract Client class"""

    def send_message(self, request):
        return 15


class TestClient(TestCase):
    def setUp(self):
        Request.id_iterator = itertools.count(1)
        self.client = DummyClient("http://non-existant:80/")

    def tearDown(self):
        config.validate = True


class TestLogging(TestClient):
    def test_request(self, *_):
        with LogCapture() as capture:
            self.client.log_request('{"jsonrpc": "2.0", "method": "go"}')
        capture.check(
            (
                "jsonrpcclient.client.request",
                "INFO",
                '{"jsonrpc": "2.0", "method": "go"}',
            )
        )

    def test_response(self):
        with LogCapture() as capture:
            self.client.log_response('{"jsonrpc": "2.0", "result": 5, "id": 1}')
        capture.check(
            (
                "jsonrpcclient.client.response",
                "INFO",
                '{"jsonrpc": "2.0", "result": 5, "id": 1}',
            )
        )


class TestSend(TestClient):
    @patch("jsonrpcclient.client.Client.request_log")
    def test(self, *_):
        self.assertEqual(
            15, self.client.send({"jsonrpc": "2.0", "method": "out", "id": 1})
        )


class TestRequest(TestClient):
    @patch("jsonrpcclient.client.Client.request_log")
    def test(self, *_):
        self.assertEqual(15, self.client.request("multiply", 3, 5))


class TestNotify(TestClient):
    @patch("jsonrpcclient.client.Client.request_log")
    def test(self, *_):
        self.assertEqual(15, self.client.notify("multiply", 3, 5))


class TestDirect(TestClient):
    @patch("jsonrpcclient.client.Client.request_log")
    def test_alternate_usage(self, *_):
        self.assertEqual(15, self.client.multiply(3, 5))


class TestProcessResponse(TestClient):
    @patch("jsonrpcclient.client.Client.request_log")
    def test_none(self, *_):
        response = None
        self.assertEqual(None, self.client.process_response(response))

    def test_empty_string(self):
        response = ""
        self.assertEqual(None, self.client.process_response(response))

    @patch("jsonrpcclient.client.Client.response_log")
    def test_valid_json(self, *_):
        response = {"jsonrpc": "2.0", "result": 5, "id": 1}
        self.assertEqual(5, self.client.process_response(response))

    @patch("jsonrpcclient.client.Client.response_log")
    def test_valid_json_null_id(self, *_):
        response = {"jsonrpc": "2.0", "result": 5, "id": None}
        self.assertEqual(5, self.client.process_response(response))

    @patch("jsonrpcclient.client.Client.response_log")
    def test_valid_string(self, *_):
        response = '{"jsonrpc": "2.0", "result": 5, "id": 1}'
        self.assertEqual(5, self.client.process_response(response))

    @patch("jsonrpcclient.client.Client.response_log")
    def test_invalid_json(self, *_):
        response = "{dodgy}"
        with self.assertRaises(exceptions.ParseResponseError):
            self.client.process_response(response)

    @patch("jsonrpcclient.client.Client.response_log")
    def test_invalid_jsonrpc(self, *_):
        response = {"json": "2.0"}
        with self.assertRaises(ValidationError):
            self.client.process_response(response)

    @patch("jsonrpcclient.client.Client.response_log")
    def test_without_validation(self, *_):
        config.validate = False
        response = {"json": "2.0"}
        self.client.process_response(response)

    @patch("jsonrpcclient.client.Client.response_log")
    def test_error_response(self, *_):
        response = {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Not Found"},
            "id": None,
        }
        with self.assertRaises(exceptions.ReceivedErrorResponse) as ex:
            self.client.process_response(response)
        self.assertEqual(ex.exception.code, -32000)
        self.assertEqual(ex.exception.message, "Not Found")
        self.assertEqual(ex.exception.data, None)

    @patch("jsonrpcclient.client.Client.response_log")
    def test_error_response_with_data(self, *_):
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": "Not Found",
                "data": "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
            },
            "id": None,
        }
        with self.assertRaises(exceptions.ReceivedErrorResponse) as ex:
            self.client.process_response(response)
        self.assertEqual(ex.exception.code, -32000)
        self.assertEqual(ex.exception.message, "Not Found")
        self.assertEqual(
            ex.exception.data, "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        )

    @patch("jsonrpcclient.client.Client.response_log")
    def test_error_response_with_nonstring_data(self, *_):
        """Reported in issue #56"""
        response = {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Not Found", "data": {}},
            "id": None,
        }
        with self.assertRaises(exceptions.ReceivedErrorResponse) as ex:
            self.client.process_response(response)
        self.assertEqual(ex.exception.code, -32000)
        self.assertEqual(ex.exception.message, "Not Found")
        self.assertEqual(ex.exception.data, {})

    @patch("jsonrpcclient.client.Client.response_log")
    def test_batch(self, *_):
        response = [
            {"jsonrpc": "2.0", "result": 5, "id": 1},
            {"jsonrpc": "2.0", "result": None, "id": 2},
            {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Not Found"},
                "id": 3,
            },
        ]
        self.assertEqual(response, self.client.process_response(response))

    @patch("jsonrpcclient.client.Client.response_log")
    def test_batch_string(self, *_):
        response = (
            "["
            '{"jsonrpc": "2.0", "result": 5, "id": 1},'
            '{"jsonrpc": "2.0", "result": null, "id": 2},'
            '{"jsonrpc": "2.0", "error": {"code": -32000, "message": "Not Found"}, "id": 3}]'
        )
        self.assertEqual(json.loads(response), self.client.process_response(response))