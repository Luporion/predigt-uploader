from __future__ import annotations

import base64
import binascii
import html
import re
from dataclasses import dataclass
from typing import Mapping, Protocol
from xml.etree import ElementTree

import requests

from ..credentials import StreamingVideoProviderCredentials


SVP_API_URL = "https://www.streamingvideoprovider.com/"


class StreamingVideoProviderError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.admin_hint = admin_hint


class StreamingVideoProviderAuthenticationError(StreamingVideoProviderError):
    pass


class StreamingVideoProviderNetworkError(StreamingVideoProviderError):
    pass


class StreamingVideoProviderResponseError(StreamingVideoProviderError):
    def __init__(self, user_message: str, admin_hint: str = "", *, code: str = "", api_message: str = "") -> None:
        super().__init__(user_message, admin_hint)
        self.code = code
        self.api_message = api_message


class StreamingVideoProviderPlayerError(StreamingVideoProviderError):
    pass


@dataclass(frozen=True)
class StreamingVideo:
    ref_no: str
    clip_key: str
    title: str
    video_source: str
    channel_ref: str
    duration: int
    date_created: int
    date_modified: int
    file_size: int

    @property
    def is_live(self) -> bool:
        return self.video_source.casefold() == "live"


@dataclass(frozen=True)
class StreamingVideoProperty:
    property_id: str
    name: str
    value: str


@dataclass(frozen=True)
class StreamingVideoList:
    videos: tuple[StreamingVideo, ...]
    count: int


class StreamingVideoProviderTransport(Protocol):
    def get(self, action: str, parameters: Mapping[str, str]) -> str: ...


class RequestsStreamingVideoProviderTransport:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def get(self, action: str, parameters: Mapping[str, str]) -> str:
        params = {"l": "api", "a": action, **parameters}
        try:
            response = requests.get(SVP_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            raise StreamingVideoProviderNetworkError(
                "StreamingVideoProvider ist derzeit nicht erreichbar.",
                f"{type(exc).__name__} beim Dienst {action}",
            ) from None


def _parse_xml(xml_text: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise StreamingVideoProviderResponseError(
            "StreamingVideoProvider hat eine ungültige Antwort geliefert.",
            f"XML konnte nicht gelesen werden: {exc}",
        ) from exc


def _text(element: ElementTree.Element, name: str, default: str = "") -> str:
    child = element.find(name)
    return (child.text or "").strip() if child is not None else default


def _integer(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _checked_root(xml_text: str) -> ElementTree.Element:
    root = _parse_xml(xml_text)
    if _text(root, "result").upper() != "OK":
        code = _text(root, "code")
        message = _text(root, "message", "Unbekannter API-Fehler")
        raise StreamingVideoProviderResponseError(
            "StreamingVideoProvider hat die Anfrage abgelehnt.",
            f"API-Fehler {code or '(ohne Code)'} beim angeforderten Dienst.",
            code=code,
            api_message=message,
        )
    return root


def parse_auth_token_xml(xml_text: str) -> str:
    root = _checked_root(xml_text)
    token = _text(root, "auth_token")
    if not token:
        raise StreamingVideoProviderAuthenticationError(
            "Die Anmeldung bei StreamingVideoProvider ist fehlgeschlagen.",
            "Die API-Antwort enthielt keinen Auth-Token.",
        )
    return token


def parse_video_list_xml(xml_text: str) -> StreamingVideoList:
    root = _checked_root(xml_text)
    videos = tuple(
        StreamingVideo(
            ref_no=_text(video, "ref_no"),
            clip_key=_text(video, "clip_key"),
            title=" ".join(_text(video, "title", "(ohne Titel)").split()),
            video_source=_text(video, "video_source"),
            channel_ref=_text(video, "channel_ref"),
            duration=_integer(_text(video, "duration")),
            date_created=_integer(_text(video, "date_created")),
            date_modified=_integer(_text(video, "date_modified")),
            file_size=_integer(_text(video, "file_size")),
        )
        for video in root.findall("./video_list/video")
    )
    return StreamingVideoList(videos=videos, count=_integer(_text(root, "count")) or len(videos))


def parse_video_properties_xml(xml_text: str) -> tuple[StreamingVideoProperty, ...]:
    root = _checked_root(xml_text)
    return tuple(
        StreamingVideoProperty(
            property_id=_text(item, "id"),
            name=_text(item, "name"),
            value=" ".join("".join(item.find("value").itertext()).split()) if item.find("value") is not None else "",
        )
        for item in root.findall("./video_properties/property")
    )


def parse_player_code_xml(xml_text: str) -> str:
    root = _checked_root(xml_text)
    encoded = _text(root, "embed_code_html")
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise StreamingVideoProviderPlayerError(
            "Der Zuschauer-Link konnte nicht gelesen werden.",
            "Der Player-Code war nicht gültig Base64-/UTF-8-kodiert.",
        ) from exc
    if not decoded:
        raise StreamingVideoProviderPlayerError("Der Zuschauer-Link konnte nicht erzeugt werden.")
    candidate = decoded
    if "<" in decoded:
        hrefs = re.findall(r"href=[\"']([^\"']+)[\"']", decoded, flags=re.IGNORECASE)
        candidate = next((value for value in hrefs if value and value != "#"), "")
        if not candidate:
            match = re.search(r"(?:https?:)?//play\.streamingvideoprovider\.com/[^\"'\s)]+", decoded)
            candidate = match.group(0) if match else ""
    candidate = html.unescape(candidate)
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    if not candidate.startswith(("https://", "http://")):
        raise StreamingVideoProviderPlayerError(
            "Der Zuschauer-Link konnte nicht erzeugt werden.",
            "Der offizielle Player-Code enthielt keine verwendbare HTTP-Adresse.",
        )
    return candidate


def _looks_like_auth_error(exc: StreamingVideoProviderResponseError) -> bool:
    text = f"{exc.code} {exc.api_message}".casefold()
    return any(word in text for word in ("token", "auth", "session", "expired"))


class StreamingVideoProviderService:
    """Read-only SVP API client. No mutating service is exposed by this class."""

    def __init__(
        self,
        credentials: StreamingVideoProviderCredentials,
        transport: StreamingVideoProviderTransport | None = None,
    ) -> None:
        self.credentials = credentials
        self.transport = transport or RequestsStreamingVideoProviderTransport()
        self._token: str | None = None

    def authenticate(self, *, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        xml = self.transport.get(
            "svp_auth_get_token",
            {"api_key": self.credentials.api_key, "api_code": self.credentials.api_code},
        )
        try:
            self._token = parse_auth_token_xml(xml)
        except StreamingVideoProviderResponseError as exc:
            raise StreamingVideoProviderAuthenticationError(
                "Die Anmeldung bei StreamingVideoProvider ist fehlgeschlagen.",
                exc.admin_hint,
            ) from exc
        return self._token

    def _read(self, action: str, parameters: Mapping[str, str] | None = None) -> str:
        for attempt in range(2):
            token = self.authenticate(force=attempt == 1)
            try:
                xml = self.transport.get(action, {"token": token, **(parameters or {})})
                _checked_root(xml)
                return xml
            except StreamingVideoProviderResponseError as exc:
                if attempt == 0 and _looks_like_auth_error(exc):
                    self._token = None
                    continue
                raise
        raise AssertionError("unreachable")

    def list_videos(self) -> StreamingVideoList:
        return parse_video_list_xml(self._read("svp_list_videos"))

    def list_recordings(self, live_video_ref: str) -> StreamingVideoList:
        return parse_video_list_xml(self._read("svp_list_recordings", {"video_ref": live_video_ref}))

    def list_stream_recordings(self) -> StreamingVideoList:
        """Combine on-demand entries with recordings linked to live broadcasts."""
        listing = self.list_videos()
        combined: dict[str, StreamingVideo] = {
            video.ref_no: video for video in listing.videos if not video.is_live
        }
        for live_video in listing.videos:
            if not live_video.is_live:
                continue
            recordings = self.list_recordings(live_video.ref_no)
            for recording in recordings.videos:
                combined.setdefault(recording.ref_no, recording)
        videos = tuple(combined.values())
        return StreamingVideoList(videos=videos, count=len(videos))

    def get_video_properties(self, video_ref: str) -> tuple[StreamingVideoProperty, ...]:
        return parse_video_properties_xml(self._read("svp_get_video_properties", {"video_ref": video_ref}))

    def get_player_link(self, video_ref: str) -> str:
        return parse_player_code_xml(
            self._read("svp_get_player_code", {"video_ref": video_ref, "embed_type": "player_link"})
        )
