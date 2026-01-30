from typing import TypedDict
from typing import Literal

class TextNode(TypedDict):
    list_type: Literal["dashed", "numbered"]
    text: str
    children: list["TextNode"]

class Contributor(TypedDict):
    id: int
    name: str
    channel_link: str
    contribution: str
    contribution_link: str

class Versions(TypedDict):
    base: str
    modifications: str
    thread: str

class Rate(TypedDict):
    variants: list[str]
    version: str
    drop: str
    conditions: str
    rates: float
    interval: str
    note: str

class Rates(TypedDict):
    drops: list[Rate]
    consumption: list[Rate]
    notes: list[str] | None
    
class LagEnvironment(TypedDict):
    cpu: str
    has_lithium: bool
    version: str

class LagEntry(TypedDict):
    conditions: list[str]
    lag: float

class LagInfo(TypedDict):
    environment: LagEnvironment
    idle: list[LagEntry]
    active: list[LagEntry]
    notes: list[TextNode]

class VideoLink(TypedDict):
    name: str
    url: str

class FileNode(TypedDict):
    type: Literal["file"]
    name: str
    url: str
    note: str | None

class FolderNode(TypedDict):
    type: Literal["folder"]
    name: str
    children: list["FileTreeNode"]

FileTreeNode = FileNode | FolderNode

class Files(TypedDict):
    schematics: list[FileTreeNode]
    world_downloads: list[FileTreeNode]
    images: list[FileTreeNode]

class Instructions(TypedDict):
    notes: list[TextNode]
    build: list[TextNode]
    usage: list[TextNode]

class Figure(TypedDict):
    url: str

class Message(TypedDict):
    designers: list[Contributor]
    credits: list[Contributor]
    versions: Versions
    rates: Rates
    lag_info: LagInfo | None
    video_links: list[VideoLink]
    files: Files
    description: list[TextNode]
    positives: list[TextNode]
    negatives: list[TextNode]
    design_specifications: list[TextNode]
    instructions: Instructions
    figures: list[Figure]
