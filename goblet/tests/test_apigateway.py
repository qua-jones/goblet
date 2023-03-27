import pytest
from goblet import Goblet
from goblet.config import GConfig
from goblet.resources.routes import Routes

from goblet.backends import CloudFunctionV1, CloudFunctionV2, CloudRun
from goblet_gcp_client import get_replay_count
from goblet_gcp_client.http_files import reset_replay_count


class TestApiGatewayConfig:
    def test_path_param_matching(self):
        gw = Routes("test", backend=CloudFunctionV1(Goblet()))
        assert gw._matched_path("/home/{home_id}", "/home/5")
        assert not gw._matched_path("/home/{home_id}", "/home/5/fail")

    def test_deadline(self):
        gw = Routes("test", backend=CloudRun(Goblet(backend="cloudrun")))
        assert gw.get_timeout(GConfig({"cloudrun_revision": {"timeout": 300}})) == 300
        assert gw.get_timeout(GConfig()) == 15

        gw = Routes("test", backend=CloudFunctionV1(Goblet()))
        assert gw.get_timeout(GConfig({"cloudfunction": {"timeout": 300}})) == 300
        assert gw.get_timeout(GConfig()) == 15

        gw = Routes("test", backend=CloudFunctionV2(Goblet()))
        assert (
            gw.get_timeout(
                GConfig({"cloudfunction": {"serviceConfig": {"timeoutSeconds": 300}}})
            )
            == 300
        )
        assert gw.get_timeout(GConfig()) == 15

        gw = Routes("test", backend=CloudFunctionV1(Goblet()))
        assert (
            gw.get_timeout(
                GConfig(
                    {
                        "cloudfunction": {"timeout": 300},
                        "api_gateway": {"deadline": 200},
                    }
                )
            )
            == 200
        )


class TestApiGatewayExisting:
    def test_invalid_inputs(self):
        with pytest.raises(ValueError):
            Goblet("test").apigateway("test", "URL")

        with pytest.raises(ValueError):
            Goblet("test").apigateway(
                "test", "URL", filename="xx", openapi_dict={"x": "x"}
            )

    def test_deploy_api_gateway(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "routes-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")
        reset_replay_count()

        openapi_dict = {
            "swagger": "2.0",
            "info": {
                "title": "media-serving-service",
                "description": "Goblet Autogenerated Spec",
                "version": "1.0.0",
            },
            "schemes": ["https"],
            "produces": ["application/json"],
            "paths": {
                "/": {
                    "get": {
                        "operationId": "get_main",
                        "responses": {"200": {"description": "A successful response"}},
                    }
                }
            },
            "definitions": {},
        }

        app = Goblet("goblet_routes")
        app.apigateway("goblet-routes", "URL", openapi_dict=openapi_dict)
        app.deploy(force=True, skip_resources=True, skip_backend=True)

        assert get_replay_count() == 7
