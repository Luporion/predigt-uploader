from __future__ import annotations

import base64

import pytest
import requests

from predigt_uploader.credentials import StreamingVideoProviderCredentials
from predigt_uploader.publishing.streaming_video_provider import (
    StreamingVideoProviderResponseError,
    StreamingVideoProviderNetworkError,
    RequestsStreamingVideoProviderTransport,
    StreamingVideoProviderService,
    parse_auth_token_xml,
    parse_player_code_xml,
    parse_video_list_xml,
    parse_video_properties_xml,
)


VIDEO_XML = """<response><result>OK</result><count>2</count><video_list>
<video><ref_no>10</ref_no><clip_key>abc</clip_key><title>Gottesdienst Ä</title>
<video_source>ondemand</video_source><channel_ref>7</channel_ref><duration>125</duration>
<date_created>1700000000</date_created><date_modified>1700000100</date_modified><file_size>123456</file_size></video>
<video><ref_no>11</ref_no><clip_key>live</clip_key><title>Livestream</title>
<video_source>live</video_source><channel_ref>0</channel_ref><duration>0</duration>
<date_created>1700000200</date_created><date_modified>1700000200</date_modified><file_size>0</file_size></video>
</video_list></response>"""


class FakeTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, action: str, parameters):
        self.calls.append((action, dict(parameters)))
        return self.responses.pop(0)


def credentials() -> StreamingVideoProviderCredentials:
    return StreamingVideoProviderCredentials("secret-key", "secret-code", "test")


def test_parse_auth_and_video_list_xml():
    assert parse_auth_token_xml("<response><result>OK</result><auth_token>session</auth_token></response>") == "session"
    result = parse_video_list_xml(VIDEO_XML)
    assert result.count == 2
    assert result.videos[0].title == "Gottesdienst Ä"
    assert result.videos[0].duration == 125
    assert result.videos[0].file_size == 123456
    assert result.videos[1].is_live


def test_parse_recordings_uses_documented_video_list_shape():
    result = parse_video_list_xml(VIDEO_XML.replace("<count>2</count>", "<count>2</count>"))
    assert [video.ref_no for video in result.videos] == ["10", "11"]


def test_parse_properties_and_player_link():
    properties = parse_video_properties_xml(
        "<response><result>OK</result><video_properties>"
        "<property><id>1</id><name>Title</name><value>Test</value></property>"
        "</video_properties></response>"
    )
    assert properties[0].name == "Title"
    encoded = base64.b64encode(b"//play.streamingvideoprovider.com/example").decode()
    assert parse_player_code_xml(
        f"<response><result>OK</result><embed_code_html>{encoded}</embed_code_html></response>"
    ) == "https://play.streamingvideoprovider.com/example"


def test_api_error_is_structured_without_secret_values():
    with pytest.raises(StreamingVideoProviderResponseError) as caught:
        parse_video_list_xml(
            "<response><result>ERROR</result><code>42</code><message>invalid request</message></response>"
        )
    assert caught.value.code == "42"
    assert "secret" not in str(caught.value)


def test_service_reuses_token_and_calls_read_only_services():
    transport = FakeTransport([
        "<response><result>OK</result><auth_token>session</auth_token></response>",
        VIDEO_XML,
        VIDEO_XML,
    ])
    service = StreamingVideoProviderService(credentials(), transport)
    assert service.list_videos().count == 2
    assert service.list_recordings("11").count == 2
    assert [call[0] for call in transport.calls] == [
        "svp_auth_get_token", "svp_list_videos", "svp_list_recordings"
    ]


def test_stream_recordings_combine_normal_ondemand_and_live_recording_without_duplicates():
    recording_xml = VIDEO_XML.replace(
        "<video_source>live</video_source>", "<video_source>ondemand</video_source>"
    )
    transport = FakeTransport([
        "<response><result>OK</result><auth_token>session</auth_token></response>",
        VIDEO_XML,
        recording_xml,
    ])
    result = StreamingVideoProviderService(credentials(), transport).list_stream_recordings()
    assert {video.ref_no for video in result.videos} == {"10", "11"}
    assert result.count == 2


def test_expired_token_is_renewed_once():
    error = "<response><result>ERROR</result><code>401</code><message>Authentication token expired</message></response>"
    transport = FakeTransport([
        "<response><result>OK</result><auth_token>old</auth_token></response>",
        error,
        "<response><result>OK</result><auth_token>new</auth_token></response>",
        VIDEO_XML,
    ])
    result = StreamingVideoProviderService(credentials(), transport).list_videos()
    assert result.count == 2
    assert transport.calls[-1][1]["token"] == "new"


def test_credentials_never_appear_in_errors_or_calls_to_other_services():
    transport = FakeTransport([
        "<response><result>OK</result><auth_token>temporary</auth_token></response>",
        "<response><result>ERROR</result><code>500</code><message>failure</message></response>",
    ])
    with pytest.raises(StreamingVideoProviderResponseError) as caught:
        StreamingVideoProviderService(credentials(), transport).list_videos()
    assert "secret-key" not in str(caught.value)
    assert "secret-code" not in str(caught.value)
    assert "api_key" not in transport.calls[-1][1]


def test_network_error_is_friendly_and_does_not_expose_query(monkeypatch):
    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("request failed for ?api_key=must-not-leak")

    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(StreamingVideoProviderNetworkError) as caught:
        RequestsStreamingVideoProviderTransport().get(
            "svp_auth_get_token", {"api_key": "must-not-leak", "api_code": "also-secret"}
        )
    rendered = f"{caught.value} {caught.value.admin_hint}"
    assert "must-not-leak" not in rendered
    assert "also-secret" not in rendered


def test_player_code_can_contain_an_official_html_link():
    html_code = '<a href="//play.streamingvideoprovider.com/popplayer.php?it=abc&amp;w=100">Video</a>'
    encoded = base64.b64encode(html_code.encode()).decode()
    link = parse_player_code_xml(
        f"<response><result>OK</result><embed_code_html>{encoded}</embed_code_html></response>"
    )
    assert link == "https://play.streamingvideoprovider.com/popplayer.php?it=abc&w=100"
