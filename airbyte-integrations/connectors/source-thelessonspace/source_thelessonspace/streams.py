import requests
import pendulum
from abc import ABC
from urllib.parse import urlparse
from typing import Any, Iterable, Mapping, MutableMapping, Optional

from airbyte_protocol.models import SyncMode
from airbyte_cdk.sources.streams.http import HttpStream


class TheLessonSpaceStream(HttpStream, ABC):
    url_base = "https://api.thelessonspace.com/v2/"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {}


class OrganisationDetails(TheLessonSpaceStream):
    primary_key = "id"

    def path(
            self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "my-organisation"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        return [response.json()]


class Sessions(TheLessonSpaceStream):
    primary_key = "uuid"

    # we are using end_time as state so setting this to None
    state_checkpoint_interval = None

    def __init__(self, organisation_id: int, start_at: str, **kwargs):
        super().__init__(**kwargs)
        self.organisation_id = organisation_id
        self.start_at = start_at
        self.logger.info(f"Syncing windows starts from: {self.start_at}")

    @property
    def cursor_field(self) -> str:
        """
        Field to use for incremental sync
        """
        return "end_time"

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]):
        """
        Update the state for incremental sync
        """
        latest_state = pendulum.DateTime.min
        latest_cursor = latest_record.get(self.cursor_field)
        if latest_cursor is not None:
            latest_state = pendulum.parse(latest_cursor)
        current_state_iso_format = current_stream_state.get(self.cursor_field)
        current_state_dt = pendulum.parse(current_state_iso_format) if current_state_iso_format is not None else pendulum.DateTime.min
        updated_state = max(latest_state, current_state_dt)
        return {self.cursor_field: updated_state.isoformat()}

    def request_params(self, stream_state: Mapping[str, Any], **kwargs) -> MutableMapping[str, Any]:
        stream_state = stream_state or {}
        params = super().request_params(stream_state=stream_state, **kwargs)

        state_based_start_timestamp = stream_state.get(self.cursor_field)

        if self.start_at is not None:
            params["start_time_after"] = pendulum.parse(self.start_at).isoformat()

        if state_based_start_timestamp:
            self.logger.info(f"Starting sync for last saved state: {self.cursor_field} - {state_based_start_timestamp}")
            params["end_time_after"] = pendulum.parse(state_based_start_timestamp).isoformat()

        return params

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        next_page_url = response.json()['next']
        if next_page_url:
            url = urlparse(next_page_url)
            return {'query': url.query}

    def path(
            self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        if next_page_token is not None:
            return f"organisations/{self.organisation_id}/sessions/?{next_page_token['query']}"

        return f"organisations/{self.organisation_id}/sessions/"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        result = response.json()['results']
        return result


class Recording(HttpStream):
    url_base = "https://ue2.room.sh/stateless/"
    primary_key = "uuid"

    @property
    def max_retries(self) -> int:
        # the lesson space api can be unpredictable so increasing number of retries
        return 10

    def __init__(self, playback_link: str, uuid: str, start_time: str, end_time: str, **kwargs):
        super().__init__(**kwargs)
        self.playback_link = playback_link
        self.uuid = uuid
        self.start_time = start_time
        self.end_time = end_time

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {"playbackUrl": self.playback_link}

    def path(
            self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "export-recording/export"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        result = response.json()
        result['uuid'] = self.uuid
        result['playback_url'] = self.playback_link
        result['start_time'] = self.start_time
        result['end_time'] = self.end_time
        return [result]


class SessionRecordings(Sessions):
    primary_key = "uuid"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.record_read = 0

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        result = []
        for session in response.json()['results']:
            if session['end_time'] is not None:
                recording = list(Recording(playback_link=session['playback_url'],
                                           uuid=session['uuid'],
                                           start_time=session['start_time'],
                                           end_time=session['end_time']).read_records(sync_mode=SyncMode.full_refresh))[0]
                result.append(recording)

        self.record_read += len(result)
        self.logger.info(f"Successfully read recordings for {self.record_read} sessions")
        return result
