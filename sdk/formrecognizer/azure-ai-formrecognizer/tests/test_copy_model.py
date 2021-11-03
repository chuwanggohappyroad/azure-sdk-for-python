# coding=utf-8
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

import pytest
import uuid
import functools
from azure.core.exceptions import HttpResponseError
from azure.ai.formrecognizer._generated.v2021_09_30_preview.models import GetOperationResponse, ModelInfo
from azure.ai.formrecognizer import CustomFormModel, DocumentModel
from azure.ai.formrecognizer import FormTrainingClient, DocumentModelAdministrationClient
from testcase import FormRecognizerTest
from preparers import GlobalClientPreparer as _GlobalClientPreparer
from preparers import FormRecognizerPreparer
import os


FormTrainingClientPreparer = functools.partial(_GlobalClientPreparer, FormTrainingClient)
DocumentModelAdministrationClientPreparer = functools.partial(_GlobalClientPreparer, DocumentModelAdministrationClient)


class TestCopyModel(FormRecognizerTest):

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_none_model_id(self, client):
        with pytest.raises(ValueError):
            client.begin_copy_model(model_id=None, target={})

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_empty_model_id(self, client):
        with pytest.raises(ValueError):
            client.begin_copy_model(model_id="", target={})

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_successful(self, client, formrecognizer_storage_container_sas_url):

        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        target = client.get_copy_authorization()

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()

        assert copy.model_id == target["targetModelId"]
        assert copy.description is None
        assert copy.created_on
        for name, doc_type in copy.doc_types.items():
            assert name == target["targetModelId"]
            for key, field in doc_type.field_schema.items():
                assert key
                assert field["type"]
                assert doc_type.field_confidence[key] is not None

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_with_model_id_and_desc(self, client, formrecognizer_storage_container_sas_url):

        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        model_id = str(uuid.uuid4())
        description = "this is my copied model"
        target = client.get_copy_authorization(model_id=model_id, description=description)

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()
        if self.is_live:
            assert copy.model_id == model_id
        assert copy.model_id
        # assert copy.description == "this is my copied model" TODO not showing up?
        assert copy.created_on
        for name, doc_type in copy.doc_types.items():
            if self.is_live:
                assert name == target["targetModelId"]
            for key, field in doc_type.field_schema.items():
                assert key
                assert field["type"]
                assert doc_type.field_confidence[key] is not None

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_fail_bad_model_id(self, client, formrecognizer_storage_container_sas_url):

        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        target = client.get_copy_authorization()

        with pytest.raises(HttpResponseError):
            # give bad model_id
            poller = client.begin_copy_model("00000000-0000-0000-0000-000000000000", target=target)
            copy = poller.result()

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_transform(self, client, formrecognizer_storage_container_sas_url):

        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        target = client.get_copy_authorization()

        raw_response = []

        def callback(response, _, headers):
            op_response = client._deserialize(GetOperationResponse, response)
            model_info = client._deserialize(ModelInfo, op_response.result)
            document_model = DocumentModel._from_generated(model_info)
            raw_response.append(model_info)
            raw_response.append(document_model)

        poller = client.begin_copy_model(model.model_id, target=target, cls=callback)
        copy = poller.result()

        generated = raw_response[0]
        copy = raw_response[1]
        self.assertModelTransformCorrect(copy, generated)

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_authorization(self, client, formrecognizer_region, formrecognizer_resource_id):

        target = client.get_copy_authorization()

        assert target["targetResourceId"] == formrecognizer_resource_id
        assert target["targetResourceRegion"] == formrecognizer_region
        assert target["targetModelId"]
        assert target["accessToken"]
        assert target["expirationDateTime"]
        assert target["targetModelLocation"]

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_copy_model_with_composed_model(self, client, formrecognizer_storage_container_sas_url):

        poller_1 = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model_1 = poller_1.result()

        poller_2 = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model_2 = poller_2.result()

        composed_poller = client.begin_create_composed_model([model_1.model_id, model_2.model_id])
        composed_model = composed_poller.result()

        target = client.get_copy_authorization()

        poller = client.begin_copy_model(composed_model.model_id, target=target)
        copy = poller.result()

        assert target["targetModelId"] == copy.model_id
        assert target["targetModelId"] != composed_model.model_id
        assert copy.model_id
        assert copy.description is None
        assert copy.created_on
        for name, doc_type in copy.doc_types.items():
            assert name in [model_1.model_id, model_2.model_id]
            for key, field in doc_type.field_schema.items():
                assert key
                assert field["type"]
                assert doc_type.field_confidence[key] is not None

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    @pytest.mark.live_test_only
    def test_copy_continuation_token(self, client, formrecognizer_storage_container_sas_url):

        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        target = client.get_copy_authorization()
        initial_poller = client.begin_copy_model(model.model_id, target=target)
        cont_token = initial_poller.continuation_token()

        poller = client.begin_copy_model(model.model_id, None, continuation_token=cont_token)
        result = poller.result()
        assert result

        initial_poller.wait()  # necessary so azure-devtools doesn't throw assertion error

    @FormRecognizerPreparer()
    @DocumentModelAdministrationClientPreparer()
    def test_poller_metadata(self, client, formrecognizer_storage_container_sas_url):
        poller = client.begin_build_model(formrecognizer_storage_container_sas_url)
        model = poller.result()

        target = client.get_copy_authorization()

        poller = client.begin_copy_model(model.model_id, target=target)
        assert poller.operation_id
        assert poller.percent_completed is not None
        poller.result()
        assert poller.operation_kind == "documentModelCopyTo"
        assert poller.percent_completed == 100
        assert poller.resource_location_url
        assert poller.created_on
        assert poller.last_updated_on

    # --------------------------------------- BACK COMPATABILITY TESTS ---------------------------------------

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.0"})
    def test_copy_model_successful_v2(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        poller = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=False)
        model = poller.result()

        target = client.get_copy_authorization(resource_region=formrecognizer_region, resource_id=formrecognizer_resource_id)

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()

        copied_model = client.get_custom_model(copy.model_id)

        assert copy.status == "ready"
        assert copy.training_started_on
        assert copy.training_completed_on
        assert target["modelId"] == copy.model_id
        assert target["modelId"] != model.model_id
        assert copied_model

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_model_with_labeled_model_name_v21(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        poller = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=True, model_name="mymodel")
        model = poller.result()

        target = client.get_copy_authorization(resource_region=formrecognizer_region, resource_id=formrecognizer_resource_id)

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()

        copied_model = client.get_custom_model(copy.model_id)

        assert copy.status =="ready"
        assert copy.training_started_on
        assert copy.training_completed_on
        assert target["modelId"] == copy.model_id
        assert target["modelId"] != model.model_id
        assert copied_model
        assert copied_model.model_name == "mymodel"

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_model_with_unlabeled_model_name_v21(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        poller = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=False, model_name="mymodel")
        model = poller.result()

        target = client.get_copy_authorization(resource_region=formrecognizer_region, resource_id=formrecognizer_resource_id)

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()

        copied_model = client.get_custom_model(copy.model_id)

        assert copy.status == "ready"
        assert copy.training_started_on
        assert copy.training_completed_on
        assert target["modelId"] == copy.model_id
        assert target["modelId"] != model.model_id
        assert copied_model
        assert copied_model.model_name == "mymodel"

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_model_fail_v21(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        FORMRECOGNIZER_TEST_ENDPOINT = os.environ["FORMRECOGNIZER_TEST_ENDPOINT"]
        if ".cognitiveservices.azure.us" in  FORMRECOGNIZER_TEST_ENDPOINT or ".cognitiveservices.azure.cn" in FORMRECOGNIZER_TEST_ENDPOINT:
            pytest.skip("This test times out in usgov/china region. Follow up with service team")

        poller = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=False)
        model = poller.result()

        # give an incorrect region
        target = client.get_copy_authorization(resource_region="eastus", resource_id=formrecognizer_resource_id)

        with pytest.raises(HttpResponseError) as e:
            poller = client.begin_copy_model(model.model_id, target=target)
            copy = poller.result()
        assert e.value.error.code == "2024"
        assert e.value.error.message

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_model_case_insensitive_region_v21(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        poller = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=False)
        model = poller.result()

        # give region all uppercase
        target = client.get_copy_authorization(resource_region=formrecognizer_region.upper(), resource_id=formrecognizer_resource_id)

        poller = client.begin_copy_model(model.model_id, target=target)
        copy = poller.result()

        assert copy.status == "ready"
        assert copy.training_started_on
        assert copy.training_completed_on
        assert target["modelId"] == copy.model_id
        assert target["modelId"] != model.model_id

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.0"})
    def test_copy_authorization_v2(self, client, formrecognizer_region, formrecognizer_resource_id):

        target = client.get_copy_authorization(resource_region="eastus", resource_id=formrecognizer_resource_id)

        assert target["modelId"]
        assert target["accessToken"]
        assert target["expirationDateTimeTicks"]
        assert target["resourceRegion"] == "eastus"
        assert target["resourceId"] == formrecognizer_resource_id

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_authorization_v21(self, client, formrecognizer_region, formrecognizer_resource_id):

        target = client.get_copy_authorization(resource_region="eastus", resource_id=formrecognizer_resource_id)

        assert target["modelId"]
        assert target["accessToken"]
        assert target["expirationDateTimeTicks"]
        assert target["resourceRegion"] == "eastus"
        assert target["resourceId"] == formrecognizer_resource_id

    @FormRecognizerPreparer()
    @FormTrainingClientPreparer(client_kwargs={"api_version": "2.1"})
    def test_copy_model_with_composed_model_v21(self, client, formrecognizer_storage_container_sas_url_v2, formrecognizer_region, formrecognizer_resource_id):

        poller_1 = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=True, model_name="model1")
        model_1 = poller_1.result()

        poller_2 = client.begin_training(formrecognizer_storage_container_sas_url_v2, use_training_labels=True, model_name="model2")
        model_2 = poller_2.result()

        composed_poller = client.begin_create_composed_model([model_1.model_id, model_2.model_id], model_name="composedmodel")
        composed_model = composed_poller.result()

        target = client.get_copy_authorization(resource_region=formrecognizer_region, resource_id=formrecognizer_resource_id)

        poller = client.begin_copy_model(composed_model.model_id, target=target)
        copy = poller.result()

        copied_model = client.get_custom_model(copy.model_id)

        assert copy.status == "ready"
        assert copy.training_started_on
        assert copy.training_completed_on
        assert target["modelId"] == copy.model_id
        assert target["modelId"] != composed_model.model_id
        assert copied_model
        assert copied_model.model_name == "composedmodel"
        for submodel in copied_model.submodels:
            assert submodel.model_id in [model_1.model_id, model_2.model_id]
