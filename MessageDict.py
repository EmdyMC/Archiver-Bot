from typing import TypedDict


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
    variant: str
    version: str
    drop: str
    condition: str
    rates: float
    interval: str
    note: str

class Rates(TypedDict):
    drops: list[Rate]
    consumption: list[Rate]
    
class LagEnvironment(TypedDict):
    cpu: str
    lithium: bool
    version: str

class LagEntry(TypedDict):
    variant: str
    lag: float

class LagInfo(TypedDict):
    environment: LagEnvironment
    idle: list[LagEntry]
    active: list[LagEntry]

class Files(TypedDict):
    schematics: list[str]
    world_downloads: list[str]
    images: list[str]

class Instructions(TypedDict):
    notes: list[str]
    build: list[str]
    usage: list[str]

class Figure(TypedDict):
    name: str
    link: str

class Message(TypedDict):
    variant_name: str
    designers: list[Contributor]
    credits: list[Contributor]
    versions: Versions
    rates: Rates
    lag_info: LagInfo | None
    video_links: list[str]
    files: Files
    description: list[str]
    positives: list[str]
    negatives: list[str]
    design_specifications: list[str]
    instructions: Instructions
    figures: list[Figure]
