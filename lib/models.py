from dataclasses import dataclass, fields
from typing import List, Optional
import datetime

@dataclass
class User:
    id: str
    email: str
    name: str
    profileImagePath: str
    avatarColor: str
    profileChangedAt:  str | datetime.datetime
    
    def __post_init__(self):
        if isinstance(self.profileChangedAt, str):
            self.profileChangedAt = datetime.datetime.fromisoformat(self.profileChangedAt)

@dataclass
class AlbumUser:
    user: User
    role: str
    def __post_init__(self):
        if isinstance(self.user, dict):
            self.user = User(**self.user) 

@dataclass
class Album:
    albumName: str
    description: str
    albumThumbnailAssetId: str
    createdAt: str
    updatedAt: str
    id: str
    albumUsers: List[AlbumUser]
    shared: bool
    hasSharedLink: bool
    isActivityEnabled: bool
    order: str
    assetCount: int = 0
    # Additional optional fields for API resilience
    startDate: datetime.datetime = None
    endDate: datetime.datetime = None
    lastModifiedAssetTimestamp: datetime.datetime = None
    albumOrder: Optional[str] = None
    isPinned: bool = False
    timelineEnabled: bool = True
    unknown_fields: Optional[dict] = None

    def __post_init__(self):
        if isinstance(self.albumUsers, list):
            self.albumUsers = [AlbumUser(**user) for user in self.albumUsers]

    @classmethod
    def from_api_response(cls, data: dict) -> "Album":
        try:
            """Create Album from API response, ignoring unknown fields."""
            known_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in known_fields}
            unknown = {k: v for k, v in data.items() if k not in known_fields}
            
            for x in ['startDate', 'endDate', 'lastModifiedAssetTimestamp', 'createdAt', 'updatedAt']:
                    if x in filtered_data:
                        filtered_data[x] = datetime.datetime.fromisoformat(filtered_data[x])
            
            if unknown:
                filtered_data["unknown_fields"] = unknown
            return cls(**filtered_data)
        except Exception as e:
            print(f"Error reading {data}: {e}")
            return False


@dataclass
class ExifInfo:
    make: Optional[str] = None
    model: Optional[str] = None
    exifImageWidth: Optional[int] = None
    exifImageHeight: Optional[int] = None
    fileSizeInByte: Optional[int] = None
    orientation: Optional[str] = None
    dateTimeOriginal: Optional[str] = None
    modifyDate: Optional[str] = None
    timeZone: Optional[str] = None
    lensModel: Optional[str] = None
    fNumber: Optional[float] = None
    focalLength: Optional[float] = None
    iso: Optional[int] = None
    exposureTime: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    projectionType: Optional[str] = None
    rating: Optional[int] = None
    # Additional optional fields for API resilience
    artist: Optional[str] = None
    software: Optional[str] = None
    copyright: Optional[str] = None
    unknown_fields: Optional[dict] = None

    @classmethod
    def from_api_response(cls, data: dict) -> "ExifInfo":
        """Create ExifInfo from API response, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        unknown = {k: v for k, v in data.items() if k not in known_fields}
        if unknown:
            filtered_data["unknown_fields"] = unknown
        return cls(**filtered_data)

    def to_kodi_info(self) -> dict[str, str]:
        fnames = [x.name for x in fields(self)]
        info = {f"exif:{key}": getattr(self, key) for key in fnames if getattr(self, key)}
        return info


@dataclass
class ItemAsset:
    id: str
    ownerId: str
    type: str
    originalPath: str
    originalFileName: str
    originalMimeType: str
    thumbhash: str
    fileCreatedAt: datetime.datetime
    createdAt: datetime.datetime
    fileModifiedAt: datetime.datetime
    localDateTime: datetime.datetime
    updatedAt: str
    isFavorite: bool
    isArchived: bool
    isTrashed: bool
    visibility: str
    duration: str
    exifInfo: ExifInfo
    libraryId: Optional[str] = None
    livePhotoVideoId: Optional[str] = None
    people: Optional[List[str]] = None
    checksum: Optional[str] = None
    isOffline: bool = False
    hasMetadata: bool = True
    duplicateId: Optional[str] = None
    resized: bool = False
    owner: Optional[User] = None
    tags: Optional[List[str]] = None
    unassignedFaces: Optional[List[str]] = None
    stack: Optional[str] = None
    # Additional fields from newer Immich API versions
    width: Optional[int] = None
    height: Optional[int] = None
    thumbhashV2: Optional[str] = None
    encodedVideoPath: Optional[str] = None
    isExternal: bool = False
    isReadOnly: bool = False
    sidecarPath: Optional[str] = None
    isVisible: bool = True
    isEdited: bool = None
    # Accept and ignore any additional fields from API
    unknown_fields: Optional[dict] = None

    def __post_init__(self):
        if isinstance(self.exifInfo, dict):
            self.exifInfo = ExifInfo.from_api_response(self.exifInfo)

    @classmethod
    def from_api_response(cls, data: dict) -> "ItemAsset":
        """Create ItemAsset from API response, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        unknown = {k: v for k, v in data.items() if k not in known_fields}
        
        for x in ['fileModifiedAt', 'localDateTime','updatedAt', 'fileCreatedAt', 'createdAt']:
                if x in filtered_data:
                    filtered_data[x] = datetime.datetime.fromisoformat(filtered_data[x])
                    
        if unknown:
            filtered_data["unknown_fields"] = unknown
        return cls(**filtered_data)


@dataclass
class TimelineBucket:
    timeBucket: str
    count: int
    # Additional optional fields for API resilience
    unknown_fields: Optional[dict] = None

    @classmethod
    def from_api_response(cls, data: dict) -> "TimelineBucket":
        """Create TimelineBucket from API response, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        unknown = {k: v for k, v in data.items() if k not in known_fields}
        if unknown:
            filtered_data["unknown_fields"] = unknown
        return cls(**filtered_data)


@dataclass
class TimeBucket:
    city: Optional[List[str]]
    country: Optional[List[str]]
    duration: Optional[List[float]]
    id: List[str]
    visibility: List[str]
    isFavorite: List[str]
    isImage: List[str]
    isTrashed: List[str]
    livePhotoVideoId: List[str]
    localOffsetHours: List[int]
    fileCreatedAt: List[str]
    ownerId: List[str]
    projectionType: Optional[str]
    ratio: Optional[float]
    status: List[str]
    thumbhash: List[str]
    visibility: List[str]
