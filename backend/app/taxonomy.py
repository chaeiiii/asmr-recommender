"""Canonical taxonomy v2.0 data, transcribed from TRIGGER_TAXONOMY.md."""

from dataclasses import dataclass

TAXONOMY_VERSION = "2.0"


@dataclass(frozen=True)
class TriggerDefinition:
    key: str
    display_name: str
    family: str
    description: str | None = None
    is_core: bool = False
    active: bool = True


TRIGGERS = (
    TriggerDefinition(
        "tapping", "Tapping", "sound", "wood/glass/plastic/nail tapping", True
    ),
    TriggerDefinition(
        "scratching",
        "Scratching",
        "sound",
        "surface scratching; mic scratching is a subtype",
        True,
    ),
    TriggerDefinition(
        "mic_brushing", "Mic Brushing", "sound", "fluffy/brush-on-mic sounds", True
    ),
    TriggerDefinition(
        "ear_cleaning",
        "Ear Cleaning",
        "sound",
        "ear picking, cotton swab, ear-focused cleaning",
        True,
    ),
    TriggerDefinition(
        "mouth_sounds", "Mouth Sounds", "sound", "lip/tongue/wet/dry mouth sounds", True
    ),
    TriggerDefinition(
        "paper_crinkling",
        "Paper / Crinkling",
        "sound",
        "page turning, paper, wrapper crinkles",
        True,
    ),
    TriggerDefinition(
        "typing_writing",
        "Typing / Writing",
        "sound",
        "keyboard, pen, pencil writing",
        True,
    ),
    TriggerDefinition(
        "fabric_soft_object",
        "Fabric / Soft Object",
        "sound",
        "cloth/towel/soft-object rubbing",
        True,
    ),
    TriggerDefinition(
        "water_liquid",
        "Water / Liquid",
        "sound",
        "pouring, drops, spray, liquid shaking",
        True,
    ),
    TriggerDefinition(
        "eating_chewing",
        "Eating / Chewing",
        "sound",
        "chewing, crunching, food sounds",
        True,
    ),
    TriggerDefinition("whisper", "Whisper", "voice"),
    TriggerDefinition("soft_spoken", "Soft Spoken", "voice"),
    TriggerDefinition("no_talking", "No Talking", "voice"),
    TriggerDefinition("hand_movements", "Hand Movements", "visual"),
    TriggerDefinition("camera_brushing", "Camera Brushing", "visual"),
    TriggerDefinition("light_triggers", "Light Triggers", "visual"),
    TriggerDefinition("slow_movements", "Slow Movements", "visual"),
    TriggerDefinition("roleplay", "Roleplay", "format"),
    TriggerDefinition("personal_attention", "Personal Attention", "format"),
    TriggerDefinition("trigger_assortment", "Trigger Assortment", "format"),
    TriggerDefinition("single_trigger", "Single Trigger", "format"),
    TriggerDefinition("slow", "Slow", "speed"),
    TriggerDefinition("normal", "Normal", "speed"),
    TriggerDefinition("fast", "Fast", "speed"),
    TriggerDefinition("gentle", "Gentle", "intensity"),
    TriggerDefinition("normal_intensity", "Normal Intensity", "intensity"),
    TriggerDefinition("aggressive", "Aggressive", "intensity"),
)
