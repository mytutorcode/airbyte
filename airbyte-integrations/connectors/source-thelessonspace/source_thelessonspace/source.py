from typing import Any, List, Mapping, Tuple

from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator
from airbyte_protocol.models import SyncMode

from .streams import OrganisationDetails, Sessions, SessionRecordings


class SourceTheLessonSpace(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        Test weather the inputs for the connection are correct and working as expected
        """
        try:
            org_detail = OrganisationDetails(
                authenticator=TokenAuthenticator(config['api_key'], auth_method='Organisation')
            )
            result = list(org_detail.read_records(sync_mode=SyncMode.full_refresh))[0]
            if result['id'] == config['organisation_id']:
                return True, result
            else:
                return False, "Organisation ID does not match"
        except Exception as e:
            return False, e

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        Streams included in this source -
        1. OrganisationDetails
        2. Sessions
        3. SessionRecordings
        """

        auth = TokenAuthenticator(token=config['api_key'],
                                  auth_method='Organisation')
        return [

            OrganisationDetails(authenticator=auth),

            Sessions(authenticator=auth,
                     organisation_id=config['organisation_id'],
                     start_at=config['start_at']),

            SessionRecordings(authenticator=auth,
                              organisation_id=config['organisation_id'],
                              start_at=config['start_at'])
        ]
