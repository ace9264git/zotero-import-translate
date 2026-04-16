#!/usr/bin/env python3

import hashlib
import json
import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, parse, request


class ZoteroError(RuntimeError):
    pass


@dataclass
class LibraryRef:
    library_type: str
    library_id: str

    @property
    def prefix(self) -> str:
        if self.library_type == "user":
            return f"/users/{self.library_id}"
        if self.library_type == "group":
            return f"/groups/{self.library_id}"
        raise ZoteroError(f"Unsupported library type: {self.library_type}")


class ZoteroClient:
    def __init__(
        self,
        api_key: str,
        library_type: str = "user",
        library_id: Optional[str] = None,
        base_url: str = "https://api.zotero.org",
    ) -> None:
        self.api_key = api_key
        self.library_type = library_type
        self.library_id = library_id
        self.base_url = base_url.rstrip("/")
        self._library_ref: Optional[LibraryRef] = None

    @classmethod
    def from_env(cls) -> "ZoteroClient":
        api_key = os.environ.get("ZOTERO_API_KEY")
        if not api_key:
            raise ZoteroError("Missing ZOTERO_API_KEY")
        library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user").strip().lower() or "user"
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        return cls(api_key=api_key, library_type=library_type, library_id=library_id)

    @property
    def library_ref(self) -> LibraryRef:
        if self._library_ref is None:
            self._library_ref = self._discover_library_ref()
        return self._library_ref

    def _default_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "codex-zotero-import-translate/1.0",
            "Zotero-API-Key": self.api_key,
            "Zotero-API-Version": "3",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        form_data: Optional[Dict[str, Any]] = None,
        raw_data: Optional[bytes] = None,
        absolute_url: bool = False,
        include_auth: bool = True,
    ) -> Tuple[int, Dict[str, str], bytes]:
        url = path if absolute_url else f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query, doseq=True)}"
        body = raw_data
        request_headers = self._default_headers(headers) if include_auth else {
            "Accept": "application/json",
            "User-Agent": "codex-zotero-import-translate/1.0",
            "Zotero-API-Version": "3",
            **(headers or {}),
        }
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif form_data is not None:
            body = parse.urlencode(form_data).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

        req = request.Request(url, data=body, method=method.upper(), headers=request_headers)
        try:
            with request.urlopen(req, timeout=120) as response:
                return response.status, dict(response.headers.items()), response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ZoteroError(f"Zotero API {exc.code} for {method.upper()} {url}: {detail}") from exc
        except error.URLError as exc:
            raise ZoteroError(f"Zotero API request failed for {method.upper()} {url}: {exc}") from exc

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        status, _, body = self._request(method, path, **kwargs)
        if status == 204 or not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _discover_library_ref(self) -> LibraryRef:
        if self.library_type == "group":
            if not self.library_id:
                raise ZoteroError("ZOTERO_LIBRARY_ID is required when ZOTERO_LIBRARY_TYPE=group")
            return LibraryRef(library_type="group", library_id=self.library_id)

        info = self._request_json(
            "GET",
            f"/keys/{parse.quote(self.api_key, safe='')}",
            include_auth=False,
        )
        user_id = info.get("userID")
        if not user_id:
            raise ZoteroError("Unable to discover Zotero user ID from API key metadata")
        return LibraryRef(library_type="user", library_id=str(user_id))

    def get_item_template(self, item_type: str, **params: str) -> Dict[str, Any]:
        query = {"itemType": item_type}
        query.update(params)
        return self._request_json("GET", "/items/new", query=query)

    def create_item(self, item_data: Dict[str, Any]) -> str:
        response = self._request_json(
            "POST",
            f"{self.library_ref.prefix}/items",
            json_data=[item_data],
            headers={"Zotero-Write-Token": uuid.uuid4().hex},
        )
        success = (response or {}).get("success", {})
        item_key = success.get("0")
        if not item_key:
            raise ZoteroError(f"Zotero item creation failed: {json.dumps(response, ensure_ascii=False)}")
        return item_key

    def create_note(self, parent_item_key: str, note_html: str) -> str:
        return self.create_item(
            {
                "itemType": "note",
                "parentItem": parent_item_key,
                "note": note_html,
                "tags": [],
                "relations": {},
            }
        )

    def list_collections(self, parent_key: Optional[str] = None) -> List[Dict[str, Any]]:
        if parent_key:
            path = f"{self.library_ref.prefix}/collections/{parent_key}/collections"
        else:
            path = f"{self.library_ref.prefix}/collections/top"

        collections: List[Dict[str, Any]] = []
        start = 0
        while True:
            payload = self._request_json("GET", path, query={"format": "json", "limit": 100, "start": start})
            payload = payload or []
            collections.extend(payload)
            if len(payload) < 100:
                break
            start += len(payload)
        return collections

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> str:
        body: Dict[str, Any] = {"name": name}
        if parent_key:
            body["parentCollection"] = parent_key
        response = self._request_json(
            "POST",
            f"{self.library_ref.prefix}/collections",
            json_data=[body],
            headers={"Zotero-Write-Token": uuid.uuid4().hex},
        )
        success = (response or {}).get("success", {})
        collection_key = success.get("0")
        if not collection_key:
            raise ZoteroError(f"Zotero collection creation failed: {json.dumps(response, ensure_ascii=False)}")
        return collection_key

    def ensure_collection_path(self, collection_path: str) -> str:
        current_parent: Optional[str] = None
        for segment in [part.strip() for part in collection_path.split("/") if part.strip()]:
            existing = None
            for collection in self.list_collections(parent_key=current_parent):
                data = collection.get("data", {})
                if data.get("name") == segment:
                    existing = data.get("key")
                    break
            if existing:
                current_parent = existing
                continue
            current_parent = self.create_collection(segment, parent_key=current_parent)

        if not current_parent:
            raise ZoteroError(f"Invalid collection path: {collection_path}")
        return current_parent

    def upload_attachment_file(
        self,
        parent_item_key: str,
        file_path: Path,
        *,
        title: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        file_path = Path(file_path).expanduser().resolve()
        if not file_path.is_file():
            raise ZoteroError(f"Attachment file not found: {file_path}")

        template = self.get_item_template("attachment", linkMode="imported_file")
        guessed_content_type = content_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        attachment = dict(template)
        attachment.update(
            {
                "parentItem": parent_item_key,
                "linkMode": "imported_file",
                "title": title or file_path.name,
                "contentType": guessed_content_type,
                "charset": "utf-8" if guessed_content_type.startswith("text/") else "",
                "filename": file_path.name,
                "tags": [],
                "relations": {},
            }
        )
        attachment_key = self.create_item(attachment)
        self._upload_file_contents(attachment_key, file_path)
        return attachment_key

    def _upload_file_contents(self, attachment_key: str, file_path: Path) -> None:
        content = file_path.read_bytes()
        stat = file_path.stat()
        md5_hash = hashlib.md5(content).hexdigest()
        mtime = int(stat.st_mtime * 1000)
        filename = file_path.name

        authorization = self._request_json(
            "POST",
            f"{self.library_ref.prefix}/items/{attachment_key}/file",
            form_data={
                "md5": md5_hash,
                "filename": filename,
                "filesize": len(content),
                "mtime": mtime,
            },
            headers={"If-None-Match": "*"},
        )

        if authorization and authorization.get("exists") == 1:
            return

        if not authorization:
            raise ZoteroError(f"Missing upload authorization for attachment {attachment_key}")

        upload_body = authorization["prefix"].encode("utf-8") + content + authorization["suffix"].encode("utf-8")
        self._request(
            "POST",
            authorization["url"],
            headers={"Content-Type": authorization["contentType"]},
            raw_data=upload_body,
            absolute_url=True,
            include_auth=False,
        )
        self._request(
            "POST",
            f"{self.library_ref.prefix}/items/{attachment_key}/file",
            form_data={"upload": authorization["uploadKey"]},
            headers={"If-None-Match": "*"},
        )
