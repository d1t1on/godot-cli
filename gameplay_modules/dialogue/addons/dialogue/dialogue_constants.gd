class_name DialogueConstants
extends RefCounted

const SAVE_GROUP: StringName = &"save_participants"
const SCHEMA_VERSION: int = 1
const MODULE_VERSION: String = "0.1.0"

const STATUS_INACTIVE: String = "inactive"
const STATUS_ACTIVE: String = "active"
const STATUS_COMPLETED: String = "completed"

const EVENT_DIALOGUE_STARTED: String = "dialogue_started"
const EVENT_DIALOGUE_ENDED: String = "dialogue_ended"
const EVENT_LINE_ENTERED: String = "line_entered"
const EVENT_LINE_EXITED: String = "line_exited"
const EVENT_CHOICE_SELECTED: String = "choice_selected"
const EVENT_DIALOGUES_CHANGED: String = "dialogues_changed"
