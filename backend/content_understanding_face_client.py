import base64
import requests
from requests.models import Response
import logging


class AzureContentUnderstandingFaceClient:
    def __init__(
        self,
        endpoint: str,
        api_version: str,
        subscription_key: str = None,
        token_provider: callable = None,
        x_ms_useragent: str = "cu-face-sample-code",
    ):
        if not subscription_key and not token_provider:
            raise ValueError(
                "Either subscription key or token provider must be provided."
            )
        if not api_version:
            raise ValueError("API version must be provided.")
        if not endpoint:
            raise ValueError("Endpoint must be provided.")

        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version
        self._logger = logging.getLogger(__name__)

        token = token_provider() if token_provider else None

        self._headers = self._get_headers(subscription_key, token, x_ms_useragent)

    def _get_face_url(self, endpoint, api_version, action):
        return (
            f"{endpoint}/contentunderstanding/faces:{action}?api-version={api_version}"
        )

    def _get_person_directory_url(self, endpoint, api_version, path=None):
        url = f"{endpoint}/contentunderstanding/personDirectories"
        if path:
            url += f"/{path}"
        return f"{url}?api-version={api_version}"

    def _get_headers(self, subscription_key, api_token, x_ms_useragent):
        """Returns the headers for the HTTP requests.
        Args:
            subscription_key (str): The subscription key for the service.
            api_token (str): The API token for the service.
        Returns:
            dict: A dictionary containing the headers for the HTTP requests.
        """
        headers = (
            {"Ocp-Apim-Subscription-Key": subscription_key}
            if subscription_key
            else {"Authorization": f"Bearer {api_token}"}
        )
        headers["x-ms-useragent"] = x_ms_useragent
        return headers

    def _handle_response(self, response: Response, action: str):
        if response.status_code == 204:
            self._logger.info(f"{action} completed successfully with status 204.")
            return None
        if response.status_code != 200 and response.status_code != 201:
            self._logger.error(
                f"Error in {action}: {response.status_code} - {response.text}"
            )
            raise Exception(
                f"Error in {action}: {response.status_code} - {response.text}"
            )
        return response.json()

    def detect_faces(self, url: str = None, data: str = None):
        request_body = {"url": url, "data": data}
        response = requests.post(
            self._get_face_url(self._endpoint, self._api_version, "detect"),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "detect_faces")

    def compare_faces(self, data1: str, data2: str):
        request_body = {
            "faceSource1": {"data": data1},
            "faceSource2": {"data": data2},
        }
        response = requests.post(
            self._get_face_url(self._endpoint, self._api_version, "compare"),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "compare_faces")

    def get_person_directories(self):
        response = requests.get(
            self._get_person_directory_url(self._endpoint, self._api_version),
            headers=self._headers,
        )
        return self._handle_response(response, "get_person_directories")

    def get_person_directory(self, person_directory_id: str):
        response = requests.get(
            self._get_person_directory_url(
                self._endpoint, self._api_version, person_directory_id
            ),
            headers=self._headers,
        )
        return self._handle_response(response, "get_person_directory")

    def create_person_directory(
        self, person_directory_id: str, description: str = None, tags: dict = None
    ):
        request_body = {"description": description, "tags": tags}
        response = requests.put(
            self._get_person_directory_url(
                self._endpoint, self._api_version, person_directory_id
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "create_person_directory")

    def update_person_directory(
        self, person_directory_id: str, description: str = None, tags: dict = None
    ):
        request_body = {"description": description, "tags": tags}
        response = requests.patch(
            self._get_person_directory_url(
                self._endpoint, self._api_version, person_directory_id
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "update_person_directory")

    def delete_person_directory(self, person_directory_id: str):
        response = requests.delete(
            self._get_person_directory_url(
                self._endpoint, self._api_version, person_directory_id
            ),
            headers=self._headers,
        )
        return self._handle_response(response, "delete_person_directory")

    def list_persons(self, person_directory_id: str):
        response = requests.get(
            self._get_person_directory_url(
                self._endpoint, self._api_version, f"{person_directory_id}/persons"
            ),
            headers=self._headers,
        )
        
        ret = self._handle_response(response, "list_persons")
        print(f"list_persons response: {ret}")
        return ret
        # return self._handle_response(response, "list_persons")

    def get_person(self, person_directory_id: str, person_id: str):
        response = requests.get(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons/{person_id}",
            ),
            headers=self._headers,
        )
        return self._handle_response(response, "get_person")

    def add_person(
        self, person_directory_id: str, tags: dict = None, face_ids: list = None
    ):
        if face_ids:
            request_body = {"tags": tags, "faceIds": face_ids}
        else:
            request_body = {"tags": tags}
        response = requests.post(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "add_person")

    def update_person(
        self,
        person_directory_id: str,
        person_id: str,
        tags: dict = None,
        face_ids: list = None,
    ):
        request_body = {"tags": tags, "faceIds": face_ids}
        response = requests.patch(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons/{person_id}",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "update_person")

    def delete_person(self, person_directory_id: str, person_id: str):
        response = requests.delete(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons/{person_id}",
            ),
            headers=self._headers,
        )
        return self._handle_response(response, "delete_person")

    def list_faces(self, person_directory_id: str):
        response = requests.get(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces",
            ),
            headers=self._headers,
        )
        ret = self._handle_response(response, "list_faces")
        print(f"list_faces response: {ret}")
        return ret
        # return self._handle_response(response, "list_faces")

    def get_face(self, person_directory_id: str, face_id: str):
        print(f"Getting face {face_id} from directory {person_directory_id}")
        response = requests.get(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces/{face_id}",
            ),
            headers=self._headers,
        )
        ret = self._handle_response(response, "get_face")
        print(f"get_face response: {ret}")
        return ret
        # return self._handle_response(response, "get_face")

    def add_face(self, person_directory_id: str, data: str, person_id: str = None):
        if person_id:
            request_body = {"faceSource": {"data": data}, "personId": person_id}
        else:
            request_body = {"faceSource": {"data": data}}
        response = requests.post(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "add_face")

    def update_face(self, person_directory_id: str, face_id: str, person_id: str):
        request_body = {"personId": person_id}
        response = requests.patch(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces/{face_id}",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "update_face")

    def delete_face(self, person_directory_id: str, face_id: str):
        response = requests.delete(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces/{face_id}",
            ),
            headers=self._headers,
        )
        return self._handle_response(response, "delete_face")

    def identify_person(
        self, person_directory_id: str, data: str, targetBoundingBox: dict = None
    ):
        request_body = {
            "faceSource": {"data": data, "targetBoundingBox": targetBoundingBox}
        }
        response = requests.post(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons:identify",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "identify")

    def verify_person(
        self,
        person_directory_id: str,
        person_id: str,
        data: str,
        targetBoundingBox: dict = None,
    ):
        request_body = {
            "faceSource": {"data": data, "targetBoundingBox": targetBoundingBox}
        }
        response = requests.post(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/persons/{person_id}:verify",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "verify")

    def find_similar_faces(
        self, person_directory_id: str, data: str, targetBoundingBox: dict = None
    ):
        request_body = {
            "faceSource": {"data": data, "targetBoundingBox": targetBoundingBox}
        }
        response = requests.post(
            self._get_person_directory_url(
                self._endpoint,
                self._api_version,
                f"{person_directory_id}/faces:find",
            ),
            headers=self._headers,
            json=request_body,
        )
        return self._handle_response(response, "find_similar_faces")

    @staticmethod
    def read_file_to_base64(file_path: str) -> str:
        with open(file_path, "rb") as f:
            file_data = f.read()
        return base64.b64encode(file_data).decode("utf-8")
